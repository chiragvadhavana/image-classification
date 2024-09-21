from dotenv import load_dotenv
load_dotenv()

import uuid
import os
from celery import Celery
from sqlalchemy.orm import Session
from .models import UploadTask, BatchUpload
from .database import SessionLocal
from .utils import classify_image, upload_to_storage
import io
import zipfile

app = Celery('tasks', broker=os.getenv('REDIS_URL'))
print(f"celery env - REDIS_URL: {os.getenv('REDIS_URL')}") 

@app.task
def process_task(file_data, filename, batch_id, is_zip=False):
    db = SessionLocal()
    try:
        batch = db.query(BatchUpload).filter(BatchUpload.batch_id == batch_id).first()
        if not batch:
            batch = BatchUpload(batch_id=batch_id, status="In-progress")
            db.add(batch)
            db.commit()

        if is_zip:
            process_zip(file_data, filename, batch, db)
        else:
            process_single_file(file_data, filename, batch, db)

        batch.status = "Completed"
        db.commit()
    except Exception as e:
        batch.status = "Failed"
        db.commit()
    finally:
        db.close()

def process_single_file(file_data, filename, batch: BatchUpload, db: Session):
    task_id = str(uuid.uuid4())
    task = UploadTask(task_id=task_id, batch_id=batch.batch_id, filename=filename, status="In-progress")
    db.add(task)
    db.commit()

    try:
        result = classify_image(file_data)
        upload_to_storage(batch.batch_id, filename, file_data)

        task.status = "Done"
        task.result = result
        db.commit()
    except Exception as e:
        task.status = "Failed"
        task.result = str(e)
        db.commit()

def process_zip(zip_data, zip_filename, batch: BatchUpload, db: Session):
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
        for filename in zip_file.namelist():
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                file_data = zip_file.read(filename)
                process_single_file(file_data, filename, batch, db)