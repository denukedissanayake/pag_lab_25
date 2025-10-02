from fastapi import APIRouter, Body
from typing import List
import logging
from app.models.anomaly import AnomalyRequest, AnomalyReport, DetectedAnomaly
from app.services import anomalyDetector

# Get a logger for this module
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/hello")
async def get_hello():
    return {"message": "hello"}

@router.post("/predict", response_model=AnomalyReport)
async def predict_anomaly(anomalyRequest: AnomalyRequest = Body(...)):
    logger.info(f"Received prediction request: {anomalyRequest.requestId} for endpoint {anomalyRequest.endpoint}")
    
    detectedAnomalies: List[DetectedAnomaly] = []

    # Check here REQUEST or REQUESTANDRESPONSE and do check accordingly
    
    reconstructionError = anomalyDetector.getAutoEncoderReconstructionError(anomalyRequest)
    anomalyScore = reconstructionError
    
    if reconstructionError > 0.8:
        anomaly = DetectedAnomaly(
            type="LATENCY_SPIKE_OR_NEW_SCHEMA",
            reason=f"High reconstruction error ({reconstructionError:.2f}) from model. Response time: {anomalyRequest.responseTime}ms."
        )
        detectedAnomalies.append(anomaly)
        logger.warning(f"Anomaly detected: {anomaly.type} for request {anomalyRequest.requestId}")

    rateAnomaly = anomalyDetector.checkSuddenSpikesInRequests(anomalyRequest)
    if rateAnomaly:
        detectedAnomalies.append(rateAnomaly)
        anomalyScore = max(anomalyScore, 0.9)
        logger.warning(f"Anomaly detected: {rateAnomaly.type} for request {anomalyRequest.requestId}")

    repetitiveAnomaly = anomalyDetector.checkRepetitiveRequestsByUsers(anomalyRequest)
    if repetitiveAnomaly:
        detectedAnomalies.append(repetitiveAnomaly)
        anomalyScore = max(anomalyScore, 0.95)
        logger.warning(f"Anomaly detected: {repetitiveAnomaly.type} for request {anomalyRequest.requestId}")

    collectiveLatencyAnomaly = anomalyDetector.checkDelayResponseSpikes(anomalyRequest)
    if collectiveLatencyAnomaly:
        detectedAnomalies.append(collectiveLatencyAnomaly)
        anomalyScore = max(anomalyScore, 0.85)
        logger.warning(f"Anomaly detected: {collectiveLatencyAnomaly.type} for request {anomalyRequest.requestId}")

    errorAnomalies = anomalyDetector.checkErrorRateSpike(anomalyRequest)
    for errorAnomaly in errorAnomalies:
        detectedAnomalies.append(errorAnomaly)
        anomalyScore = max(anomalyScore, 0.98 if "SERVER" in errorAnomaly.type else 0.9)
        logger.warning(f"Anomaly detected: {errorAnomaly.type} for request {anomalyRequest.requestId}")

    isAnomaly = len(detectedAnomalies) > 0

    finalReport = AnomalyReport(
        requestId=anomalyRequest.requestId,
        isAnomaly=isAnomaly,
        anomalyScore=min(1.0, anomalyScore),
        detectedAnomalies=detectedAnomalies
    )

    if finalReport.isAnomaly:
        logger.info(f"Final report for {anomalyRequest.requestId}: ANOMALY DETECTED with score {finalReport.anomalyScore:.2f}")
    else:
        logger.info(f"Final report for {anomalyRequest.requestId}: No anomaly detected.")
        
    return finalReport
