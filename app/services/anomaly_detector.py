from typing import Optional, List
from app.models.anomaly import AnomalyRequest, DetectedAnomaly
from app.core.redis_client import redisClient
import logging

logger = logging.getLogger(__name__)

# Placeholder for a pre-trained Autoencoder model
def getAutoEncoderReconstructionError(api_call: AnomalyRequest) -> float:
    """
    Simulates an Autoencoder model by checking for high response times.
    """
    if api_call.responseTimeMs > 50.0:
        return 0.9 + (api_call.responseTimeMs - 50.0) / 100.0
    
    schema_key = f"schema_hashes:{api_call.endpoint}"
    if not redisClient.sismember(schema_key, api_call.schemaHash):
        redisClient.sadd(schema_key, api_call.schemaHash)
        return 0.85
        
    return 0.1

def check_increased_request_rate(api_call: AnomalyRequest) -> Optional[DetectedAnomaly]:
    """
    Checks for spikes in request rates per endpoint using Redis counters with TTL.
    """
    time_window = 60
    current_minute = api_call.timestamp.strftime("%Y-%m-%dT%H:%M")
    
    rate_key = f"rate:{api_call.endpoint}:{current_minute}"
    
    current_rate = redisClient.incr(rate_key)
    
    if current_rate == 1:
        redisClient.expire(rate_key, time_window)
        
    rate_threshold = 100
    
    if current_rate > rate_threshold:
        return DetectedAnomaly(
            type="INCREASED_REQUEST_RATE",
            reason=f"Request rate of {current_rate} in the last minute exceeds threshold of {rate_threshold} for endpoint {api_call.endpoint}."
        )
    return None

def check_repetitive_requests(api_call: AnomalyRequest) -> Optional[DetectedAnomaly]:
    """
    Detects rapid, repetitive requests from a single client to a single endpoint.
    """
    time_window_seconds = 30
    request_count_threshold = 2
    
    key = f"repetitive:{api_call.authCompanyId}:{api_call.endpoint}"
    now_timestamp = api_call.timestamp.timestamp()
    
    redisClient.zadd(key, {f"{now_timestamp}:{api_call.requestId}": now_timestamp})
    
    redisClient.zremrangebyscore(key, '-inf', now_timestamp - time_window_seconds)
    
    recent_requests_count = redisClient.zcard(key)
    
    redisClient.expire(key, time_window_seconds + 5)

    logger.info(f"Repetitive check: {recent_requests_count} requests from {api_call.authCompanyId} to {api_call.endpoint} in the last {time_window_seconds} seconds.")
    
    if recent_requests_count > request_count_threshold:
        return DetectedAnomaly(
            type="REPETITIVE_REQUEST",
            reason=f"Client IP {api_call.authCompanyId} made {recent_requests_count} requests to {api_call.endpoint} in the last {time_window_seconds} seconds."
        )
    return None
