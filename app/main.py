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
import csv
from io import StringIO
import time
import asyncio


Base.metadata.create_all(bind=engine)

app = FastAPI()

GITLAB_API_TOKEN = os.getenv("GITLAB_API_TOKEN")
GITLAB_API_URL = os.getenv("GITLAB_API_URL")
MAX_WAIT_TIME = 300 

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


@app.post("/gitlab-webhook")
async def gitlab_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
        logger.info(f"Received GitLab webhook payload: {payload}")

        if payload.get("object_kind") == "note" and payload.get("object_attributes", {}).get("note"):
            comment = payload["object_attributes"]["note"]
            
            if "classify-image" in comment:
                image_url = comment.split("classify-image", 1)[1].strip()
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(image_url)
                    response.raise_for_status()
                
                file_content = response.content
                filename = image_url.split("/")[-1]
                
                batch_id = str(uuid.uuid4())
                batch = models.BatchUpload(batch_id=batch_id, status="In-queue")
                db.add(batch)
                db.commit()
                
                is_zip = filename.lower().endswith('.zip')
                process_task.delay(file_content, filename, batch_id, is_zip=is_zip)
                
                asyncio.create_task(handle_task_completion(batch_id, payload, db))
                
                return {"message": "Processing started", "batch_id": batch_id}
        
        return {"message": "No action taken"}
    
    except httpx.HTTPError as e:
        logger.error(f"HTTP error occurred while fetching the image: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch image: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing GitLab webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def handle_task_completion(batch_id: str, payload: dict, db: Session):
    # MAX_WAIT_TIME   = 300
    # start_time = asyncio.get_event_loop().time()
    
    # while asyncio.get_event_loop().time() - start_time < MAX_WAIT_TIME:
    while True:
        db.refresh(db.query(models.BatchUpload).filter(models.BatchUpload.batch_id == batch_id).first())
        batch = db.query(models.BatchUpload).filter(models.BatchUpload.batch_id == batch_id).first()
        if batch.status in ["Completed", "Failed"]:
            break
        await asyncio.sleep(5)  
        
    if batch.status == "Completed":
        try:
            csv_content = generate_csv(batch_id, db)
            project_id = payload["project"]["id"]
            issue_iid = payload["issue"]["iid"]
            discussion_id = payload["object_attributes"]["discussion_id"]
            
            async with httpx.AsyncClient() as client:
                upload_url = f"{GITLAB_API_URL}/projects/{project_id}/uploads"
                files = {'file': (f'batch_{batch_id}_results.csv', csv_content)}
                headers = {"PRIVATE-TOKEN": GITLAB_API_TOKEN}
                upload_response = await client.post(upload_url, files=files, headers=headers)
                upload_response.raise_for_status()
                upload_data = upload_response.json()
                download_url = f"https://gitlab.com{upload_data['full_path']}"

                reply_url = f"{GITLAB_API_URL}/projects/{project_id}/issues/{issue_iid}/discussions/{discussion_id}/notes"
                data = {
                    "body": f"Classification completed. Results attached: [Download CSV]({download_url})"
                }
                await client.post(reply_url, json=data, headers=headers)
        except Exception as e:
            logger.error(f"Error handling task completion: {str(e)}", exc_info=True)
    else:
        logger.error(f"Task processing failed or timed out for batch {batch_id}")


def generate_csv(batch_id, db):
    tasks = db.query(models.UploadTask).filter(models.UploadTask.batch_id == batch_id).all()
    
    csv_io = StringIO()
    csv_writer = csv.writer(csv_io)
    csv_writer.writerow(["Filename", "Status", "Result"])
    
    for task in tasks:
        csv_writer.writerow([task.filename, task.status, task.result])
    
    return csv_io.getvalue()