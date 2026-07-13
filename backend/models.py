from sqlalchemy import Column, Integer, String, Text, DateTime, func
from database import Base

class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    filepath = Column(String)
    uploaded_at = Column(DateTime, default=func.now())

class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    prompt = Column(Text)
    generated_code = Column(Text, nullable=True)
    execution_output = Column(Text, nullable=True)
    images_csv = Column(Text, nullable=True)
    model_provider = Column(String)
    status = Column(String, default="pending") 
    timestamp = Column(DateTime, default=func.now())
