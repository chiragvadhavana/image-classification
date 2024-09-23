from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class BatchUpload(Base):
    __tablename__ = 'batch_uploads'
    
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, unique=True, index=True)
    upload_time = Column(DateTime, default=datetime.utcnow)
    status = Column(String)
    tasks = relationship("UploadTask", back_populates="batch")

class UploadTask(Base):
    __tablename__ = 'upload_tasks'
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    batch_id = Column(String, ForeignKey('batch_uploads.batch_id'))
    filename = Column(String)
    status = Column(String)
    result = Column(String)
    batch = relationship("BatchUpload", back_populates="tasks")
