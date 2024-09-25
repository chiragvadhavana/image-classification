from dotenv import load_dotenv
load_dotenv()
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


Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
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


#------------------------------------
@app.post("/gitlab-webhook")
async def gitlab_webhook(request: Request):
    payload = await request.json()

    # Save the received payload to a JSON file for inspection (optional)
    with open("received_data.json", "w") as f:
        json.dump(payload, f, indent=4)

    # Check if this event is a note (comment) on an issue
    if payload.get("object_kind") == "note":
        comment = payload.get("object_attributes", {}).get("note", "")
        
        # Check for the 'classify-image' command in the comment
        if "classify-image" in comment:
            # Extract image URL after the 'classify-image' command
            command_parts = comment.split("classify-image")
            if len(command_parts) > 1:
                image_url = command_parts[1].strip()

                # Download the image using the URL
                image_response = requests.get(image_url)
                if image_response.status_code == 200:
                    # Send the image to your /upload endpoint
                    files = {"file": ("received_image.jpg", image_response.content)}
                    upload_response = requests.post("http://localhost:8000/upload", files=files)
                    
                    if upload_response.status_code == 200:
                        return {"status": "success", "message": "Image received and passed to upload"}
                    else:
                        return {"status": "error", "message": "Failed to process image through upload endpoint"}
                else:
                    return {"status": "error", "message": "Failed to download image"}
    
    return {"status": "error", "message": "No classify-image command found or event not a comment"}
