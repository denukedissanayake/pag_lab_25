from typing import Optional, List
from app.models.anomaly import ApiCall, DetectedAnomaly
from app.core.redis_client import redis_client

# Placeholder for a pre-trained Autoencoder model
def get_autoencoder_reconstruction_error(api_call: ApiCall) -> float:
    """
    Simulates an Autoencoder model by checking for high response times.
    """
    if api_call.response_time_ms > 50.0:
        return 0.9 + (api_call.response_time_ms - 50.0) / 100.0
    
    schema_key = f"schema_hashes:{api_call.endpoint}"
    if not redis_client.sismember(schema_key, api_call.schema_hash):
        redis_client.sadd(schema_key, api_call.schema_hash)
        return 0.85
        
    return 0.1

def check_increased_request_rate(api_call: ApiCall) -> Optional[DetectedAnomaly]:
    """
    Checks for spikes in request rates per endpoint using Redis counters with TTL.
    """
    time_window = 60
    current_minute = api_call.timestamp_utc.strftime("%Y-%m-%dT%H:%M")
    
    rate_key = f"rate:{api_call.endpoint}:{current_minute}"
    
    current_rate = redis_client.incr(rate_key)
    
    if current_rate == 1:
        redis_client.expire(rate_key, time_window)
        
    rate_threshold = 100
    
    if current_rate > rate_threshold:
        return DetectedAnomaly(
            type="INCREASED_REQUEST_RATE",
            reason=f"Request rate of {current_rate} in the last minute exceeds threshold of {rate_threshold} for endpoint {api_call.endpoint}."
        )
    return None

def check_repetitive_requests(api_call: ApiCall) -> Optional[DetectedAnomaly]:
    """
    Detects rapid, repetitive requests from a single client to a single endpoint.
    """
    time_window_seconds = 30
    request_count_threshold = 20
    
    key = f"repetitive:{api_call.client_ip}:{api_call.endpoint}"
    now_timestamp = api_call.timestamp_utc.timestamp()
    
    redis_client.zadd(key, {str(now_timestamp): now_timestamp})
    
    redis_client.zremrangebyscore(key, '-inf', now_timestamp - time_window_seconds)
    
    recent_requests_count = redis_client.zcard(key)
    
    redis_client.expire(key, time_window_seconds + 5)
    
    if recent_requests_count > request_count_threshold:
        return DetectedAnomaly(
            type="REPETITIVE_REQUEST",
            reason=f"Client IP {api_call.client_ip} made {recent_requests_count} requests to {api_call.endpoint} in the last {time_window_seconds} seconds."
        )
    return None
