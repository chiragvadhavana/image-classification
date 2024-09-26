from dotenv import load_dotenv
load_dotenv()
import logging
from io import BytesIO
import requests
import json
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from . import models, utils
from .celery_tasks import process_task
import uuid
from .models import Base
import os  
import httpx

Base.metadata.create_all(bind=engine)

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    logger.info("into upload endpoint")
    batch_id = str(uuid.uuid4())
    
    try:
        file_content = await file.read()
        batch = models.BatchUpload(batch_id=batch_id, status="In-queue")
        db.add(batch)
        db.commit()

        if file.filename.lower().endswith('.zip'):
            process_task.delay(file_content, file.filename, batch_id, is_zip=True)
        else:
            process_task.delay(file_content, file.filename, batch_id, is_zip=False)
        
        return {"message": "Task added to queue", "batch_id": batch_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{batch_id}")
async def get_tasks(batch_id: str, db: Session = Depends(get_db)):
    batch = db.query(models.BatchUpload).filter(models.BatchUpload.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    tasks = db.query(models.UploadTask).filter(models.UploadTask.batch_id == batch_id).all()
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "upload_time": batch.upload_time,
        "tasks": [{"task_id": task.task_id, "filename": task.filename, "status": task.status, "result": task.result} for task in tasks]
    }

@app.get("/batches")
async def get_batches(db: Session = Depends(get_db)):
    batches = db.query(models.BatchUpload).order_by(models.BatchUpload.upload_time.desc()).all()
    return [{"batch_id": batch.batch_id, "status": batch.status, "upload_time": batch.upload_time} for batch in batches]


# Assuming logger is already defined
# @app.post("/gitlab-webhook")
# async def gitlab_webhook(request: Request):
    
#     try:
#         payload = await request.json()

#         # Check if this is a comment event
#         if payload.get("object_kind") == "note":
#             comment = payload.get("object_attributes", {}).get("note", "")

#             # Check for the 'classify-image' command
#             if "classify-image" in comment:
#                 # Extract image URL
#                 image_url = comment.split("classify-image", 1)[1].strip()

#                 # Download the image
#                 image_response = requests.get(image_url, timeout=30)
#                 image_response.raise_for_status()
#                 logger.info("Image downloaded successfully")

#                 # Wrap the byte content in BytesIO for file upload
#                 file_content = BytesIO(image_response.content)
                
#                 # Prepare the file to be sent to the upload endpoint
#                 files = {"file": ("image.jpg", file_content, "image/jpeg")}

#                 # Send the file to the upload endpoint
#                 upload_url = "http://localhost:8000/upload"
#                 logger.info(f"Sending file to upload endpoint: {upload_url}")
#                 upload_response = requests.post(upload_url, files=files, timeout=30)
#                 # upload_response.raise_for_status()

#                 logger.info(f"Upload response status: {upload_response.status_code}")
#                 logger.info(f"Upload response content: {upload_response.text}")

#                 return {"status": "success", "message": "Image processed successfully"}

#         return {"status": "info", "message": "No action taken"}

#     except Exception as e:
#         logger.error(f"Error in webhook processing: {str(e)}", exc_info=True)
#         return {"status": "error", "message": str(e)}


@app.post("/gitlab-webhook")
async def gitlab_webhook(request: Request):
    BACKEND_URL = "http://localhost:8000"  
    try:
        payload = await request.json()

        if payload.get("object_kind") == "note":
            comment = payload.get("object_attributes", {}).get("note", "")
            if "classify-image" in comment:
                image_url = comment.split("classify-image", 1)[1].strip()

                async with httpx.AsyncClient() as client:
                    image_response = await client.get(image_url)
                    image_response.raise_for_status()

                file_content = BytesIO(image_response.content)
                files = {"file": ("image.jpg", file_content, "image/jpeg")}
                logger.info("start of request ")

                async with httpx.AsyncClient() as client:
                    upload_response = await client.post(f"{BACKEND_URL}/upload", files=files)
                    
                logger.info("end of request ")
                return {"status": "success", "message": "Image processed successfully"}

        return {"status": "info", "message": "No action taken"}

    except Exception as e:
        logger.error(f"Error in webhook processing: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}
