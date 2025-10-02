from typing import Optional, List
from app.schemas.anomaly import AnomalyRequest, DetectedAnomaly
from app.config.redis import redisClient
import logging

logger = logging.getLogger(__name__)

# Placeholder for a pre-trained Autoencoder model
def getAutoEncoderReconstructionError(anomalyRequest: AnomalyRequest) -> float:
    """Simulates an Autoencoder model by checking for high response times"""

    if anomalyRequest.responseTime > 50.0:
        return 0.9 + (anomalyRequest.responseTime - 50.0) / 100.0
    
    schemaKey = f"schema_hashes:{anomalyRequest.endpoint}"
    if not redisClient.sismember(schemaKey, anomalyRequest.schemaHash):
        redisClient.sadd(schemaKey, anomalyRequest.schemaHash)
        return 0.85
        
    return 0.1

def checkSuddenSpikesInRequests(anomalyRequest: AnomalyRequest) -> Optional[DetectedAnomaly]:
    """A sudden spike in the total volume of requests to an endpoint from all users combined"""

    timeWindowSeconds = 60
    requestRateThreshold = 10
    currentMinute = anomalyRequest.timestamp.strftime("%Y-%m-%dT%H:%M")
    
    rateKey = f"rate:{anomalyRequest.endpoint}:{currentMinute}"
    currentRate = redisClient.incr(rateKey)
    
    if currentRate == 1:
        redisClient.expire(rateKey, timeWindowSeconds)

    logger.info(f"Request rate check: {currentRate} requests from {anomalyRequest.authCompanyId} "
                f"to {anomalyRequest.endpoint} in the last {timeWindowSeconds} seconds.")

    if currentRate > requestRateThreshold:
        return DetectedAnomaly(
            type="INCREASED_REQUEST_RATE",
            reason=f"Request rate of {currentRate} in the last minute exceeds threshold of "
            f"{requestRateThreshold} for endpoint {anomalyRequest.endpoint}."
        )
    return None

def checkRepetitiveRequestsByUsers(anomalyRequest: AnomalyRequest) -> Optional[DetectedAnomaly]:
    """A single user (or client) hitting an endpoint repeatedly and rapidly"""

    timeWindowSeconds = 60
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
            reason=f"Client IP {anomalyRequest.authCompanyId} made {recentRequestsCount} "
            f"requests to {anomalyRequest.endpoint} in the last {timeWindowSeconds} seconds."
        )
    return None

def checkDelayResponseSpikes(anomalyRequest: AnomalyRequest) -> Optional[DetectedAnomaly]:
    """Detects if the average response time for an endpoint is increasing"""

    requestWindowSize = 100
    latencyThreshold = 150.0  # milliseconds

    key = f"latency_window:{anomalyRequest.endpoint}"
    
    redisClient.lpush(key, anomalyRequest.responseTime)
    redisClient.ltrim(key, 0, requestWindowSize - 1)

    if redisClient.llen(key) < requestWindowSize:
        return None

    latencies = redisClient.lrange(key, 0, -1)
    totalLatency = sum(float(ms) for ms in latencies)
    averageLatency = totalLatency / len(latencies)

    logger.info(f"Collective latency check for {anomalyRequest.endpoint}: "
                f"Average is {averageLatency:.2f}ms over last {requestWindowSize} requests.")

    if averageLatency > latencyThreshold:
        return DetectedAnomaly(
            type="COLLECTIVE_LATENCY_SPIKE",
            reason=f"Average response time for {anomalyRequest.endpoint} is {averageLatency:.2f}ms, "
                   f"exceeding the threshold of {latencyThreshold}ms."
        )
    return None

def checkErrorRateSpike(anomalyRequest: AnomalyRequest) -> List[DetectedAnomaly]:
    """Detects spikes in the rate of client-side (4xx) and server-side (5xx) errors for an endpoint."""
    detectedAnomalies: List[DetectedAnomaly] = []
    
    if anomalyRequest.statusCode < 400:
        return detectedAnomalies

    timeWindowSeconds = 60
    currentMinute = anomalyRequest.timestamp.strftime("%Y-%m-%dT%H:%M")
    
    if 400 <= anomalyRequest.statusCode < 500:
        clientErrorThreshold = 10
        clientRateKey = f"client_error_rate:{anomalyRequest.endpoint}:{currentMinute}"
        currentClientErrorRate = redisClient.incr(clientRateKey)
        
        if currentClientErrorRate == 1:
            redisClient.expire(clientRateKey, timeWindowSeconds)

        logger.info(f"Client error rate check for {anomalyRequest.endpoint}: {currentClientErrorRate} errors in the current minute.")

        if currentClientErrorRate > clientErrorThreshold:
            detectedAnomalies.append(DetectedAnomaly(
                type="INCREASED_CLIENT_ERROR_RATE",
                reason=f"Client error rate (4xx) of {currentClientErrorRate} in the "
                f"last minute exceeds threshold of {clientErrorThreshold} for endpoint {anomalyRequest.endpoint}."
            ))
    
    if 500 <= anomalyRequest.statusCode < 600:
        serverErrorThreshold = 5
        serverRateKey = f"server_error_rate:{anomalyRequest.endpoint}:{currentMinute}"
        currentServerErrorRate = redisClient.incr(serverRateKey)
        
        if currentServerErrorRate == 1:
            redisClient.expire(serverRateKey, timeWindowSeconds)

        logger.info(f"Server error rate check for {anomalyRequest.endpoint}: {currentServerErrorRate} errors in the current minute.")

        if currentServerErrorRate > serverErrorThreshold:
            detectedAnomalies.append(DetectedAnomaly(
                type="INCREASED_SERVER_ERROR_RATE",
                reason=f"Server error rate (5xx) of {currentServerErrorRate} in the last minute exceeds threshold of "
                f"{serverErrorThreshold} for endpoint {anomalyRequest.endpoint}."
            ))
    
    return detectedAnomalies
