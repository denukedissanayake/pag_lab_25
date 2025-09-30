from pydantic import BaseModel
import datetime
from typing import List

class ApiCall(BaseModel):
    request_id: str
    timestamp_utc: datetime.datetime
    endpoint: str
    http_method: str
    status_code: int
    response_time_ms: float
    client_ip: str
    schema_hash: str

class DetectedAnomaly(BaseModel):
    type: str
    reason: str

class AnomalyReport(BaseModel):
    request_id: str
    is_anomaly: bool
    anomaly_score: float
    detected_anomalies: List[DetectedAnomaly] = []
