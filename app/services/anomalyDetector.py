from typing import Optional, List
from app.models.anomaly import AnomalyRequest, DetectedAnomaly
from app.core.redis_client import redisClient
import logging

logger = logging.getLogger(__name__)

# Placeholder for a pre-trained Autoencoder model
def getAutoEncoderReconstructionError(anomalyRequest: AnomalyRequest) -> float:
    """Simulates an Autoencoder model by checking for high response times"""

    if anomalyRequest.responseTimeMs > 50.0:
        return 0.9 + (anomalyRequest.responseTimeMs - 50.0) / 100.0
    
    schema_key = f"schema_hashes:{anomalyRequest.endpoint}"
    if not redisClient.sismember(schema_key, anomalyRequest.schemaHash):
        redisClient.sadd(schema_key, anomalyRequest.schemaHash)
        return 0.85
        
    return 0.1

def checkSuddenSpikesInRequests(anomalyRequest: AnomalyRequest) -> Optional[DetectedAnomaly]:
    """A sudden spike in the total volume of requests to an endpoint from all users combined"""

    timeWindow = 60
    currentMinute = anomalyRequest.timestamp.strftime("%Y-%m-%dT%H:%M")
    
    rateKey = f"rate:{anomalyRequest.endpoint}:{currentMinute}"
    
    currentRate = redisClient.incr(rateKey)
    
    if currentRate == 1:
        redisClient.expire(rateKey, timeWindow)
        
    rateThreshold = 100

    logger.info(f"Request rate check: {currentRate} requests from {anomalyRequest.authCompanyId} "
                f"to {anomalyRequest.endpoint} in the last {timeWindow} seconds.")

    if currentRate > rateThreshold:
        return DetectedAnomaly(
            type="INCREASED_REQUEST_RATE",
            reason=f"Request rate of {currentRate} in the last minute exceeds threshold of "
            f"{rateThreshold} for endpoint {anomalyRequest.endpoint}."
        )
    return None

def checkRepetitiveRequestsByUsers(anomalyRequest: AnomalyRequest) -> Optional[DetectedAnomaly]:
    """A single user (or client) hitting an endpoint repeatedly and rapidly"""

    timeWindowSeconds = 30
    requestCountThreshold = 2
    
    key = f"repetitive:{anomalyRequest.authCompanyId}:{anomalyRequest.endpoint}"
    anomalyTimestamp = anomalyRequest.timestamp.timestamp()
    
    redisClient.zadd(key, {f"{anomalyTimestamp}:{anomalyRequest.requestId}": anomalyTimestamp})
    redisClient.zremrangebyscore(key, '-inf', anomalyTimestamp - timeWindowSeconds)
    recentRequestsCount = redisClient.zcard(key)
    redisClient.expire(key, timeWindowSeconds + 5)

    logger.info(f"Repetitive check: {recentRequestsCount} requests from {anomalyRequest.authCompanyId} "
                f"to {anomalyRequest.endpoint} in the last {timeWindowSeconds} seconds.")

    if recentRequestsCount > requestCountThreshold:
        return DetectedAnomaly(
            type="REPETITIVE_REQUEST",
            reason=f"Client IP {anomalyRequest.authCompanyId} made {recentRequestsCount} requests to {anomalyRequest.endpoint} in the last {timeWindowSeconds} seconds."
        )
    return None
