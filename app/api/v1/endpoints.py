from fastapi import APIRouter, Body
from typing import List
from app.models.anomaly import ApiCall, AnomalyReport, DetectedAnomaly
from app.services import anomaly_detector

router = APIRouter()

@router.post("/predict", response_model=AnomalyReport)
async def predict_anomaly(api_call: ApiCall = Body(...)):
    """
    Analyzes an API call to detect anomalies using a hybrid approach.
    """
    detected_anomalies: List[DetectedAnomaly] = []
    
    reconstruction_error = anomaly_detector.get_autoencoder_reconstruction_error(api_call)
    anomaly_score = reconstruction_error
    
    if reconstruction_error > 0.8:
        detected_anomalies.append(DetectedAnomaly(
            type="LATENCY_SPIKE_OR_NEW_SCHEMA",
            reason=f"High reconstruction error ({reconstruction_error:.2f}) from model. Response time: {api_call.response_time_ms}ms."
        ))

    rate_anomaly = anomaly_detector.check_increased_request_rate(api_call)
    if rate_anomaly:
        detected_anomalies.append(rate_anomaly)
        anomaly_score = max(anomaly_score, 0.9)

    repetitive_anomaly = anomaly_detector.check_repetitive_requests(api_call)
    if repetitive_anomaly:
        detected_anomalies.append(repetitive_anomaly)
        anomaly_score = max(anomaly_score, 0.95)

    is_anomaly = len(detected_anomalies) > 0
    
    return AnomalyReport(
        request_id=api_call.request_id,
        is_anomaly=is_anomaly,
        anomaly_score=min(1.0, anomaly_score),
        detected_anomalies=detected_anomalies
    )
