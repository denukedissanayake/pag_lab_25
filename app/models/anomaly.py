from pydantic import BaseModel, Field
import datetime
from typing import List
import uuid

class AnomalyRequest(BaseModel):
    requestId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime
    endpoint: str
    httpMethod: str
    statusCode: int
    responseTimeMs: float
    authCompanyId: str
    schemaHash: str

class DetectedAnomaly(BaseModel):
    type: str
    reason: str

class AnomalyReport(BaseModel):
    requestId: str
    isAnomaly: bool
    anomalyScore: float
    detectedAnomalies: List[DetectedAnomaly] = []
