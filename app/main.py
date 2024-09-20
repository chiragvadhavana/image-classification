from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
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