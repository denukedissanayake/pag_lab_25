from fastapi import FastAPI, Body
from pydantic import BaseModel, Field
import datetime
import redis
from typing import List, Optional

# --- 1. API Contract: Pydantic Models ---

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

# --- 2. Service Architecture: FastAPI App & Redis Connection ---

app = FastAPI(
    title="Anomaly Detection Service",
    description="A hybrid model service to detect anomalies in API traffic.",
    version="1.0.0"
)

# Connect to Redis. Ensure Redis is running on localhost:6379
# For production, use a more robust configuration management.
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# --- 3. Hybrid Anomaly Detection Logic ---

# Placeholder for a pre-trained Autoencoder model
# In a real scenario, you would load a trained model (e.g., from TensorFlow/PyTorch)
# and use it to calculate reconstruction error.
def get_autoencoder_reconstruction_error(api_call: ApiCall) -> float:
    """
    Simulates an Autoencoder model by checking for high response times.
    A real implementation would feed a feature vector into a neural network.
    """
    # Simple rule-based simulation:
    # Anomaly if response time is above a threshold (e.g., 50ms)
    if api_call.response_time_ms > 50.0:
        # Return a high error to signify an anomaly
        return 0.9 + (api_call.response_time_ms - 50.0) / 100.0
    
    # A new or rare schema_hash would also increase reconstruction error.
    # This logic would be part of the trained model's behavior.
    # For simulation, we can check if we've seen this hash before.
    schema_key = f"schema_hashes:{api_call.endpoint}"
    if not redis_client.sismember(schema_key, api_call.schema_hash):
        # Add the new hash to the set for future checks
        redis_client.sadd(schema_key, api_call.schema_hash)
        return 0.85 # High error for a new schema
        
    return 0.1 # Low error for normal requests

def check_increased_request_rate(api_call: ApiCall) -> Optional[DetectedAnomaly]:
    """
    Checks for spikes in request rates per endpoint using Redis counters with TTL.
    """
    # Time window for the counter (e.g., 60 seconds)
    time_window = 60
    current_minute = api_call.timestamp_utc.strftime("%Y-%m-%dT%H:%M")
    
    # Key for tracking request rate for a specific endpoint
    rate_key = f"rate:{api_call.endpoint}:{current_minute}"
    
    # Increment the counter for the current time window
    current_rate = redis_client.incr(rate_key)
    
    # Set a TTL on the key when it's first created
    if current_rate == 1:
        redis_client.expire(rate_key, time_window)
        
    # Define a threshold (e.g., 100 requests per minute for this endpoint)
    # This threshold could be dynamic and learned from historical data.
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
    # Time window and request count for detection
    time_window_seconds = 30
    request_count_threshold = 20
    
    key = f"repetitive:{api_call.client_ip}:{api_call.endpoint}"
    now_timestamp = api_call.timestamp_utc.timestamp()
    
    # Use a sorted set to store timestamps. The score is the timestamp itself.
    # This allows easy removal of old entries.
    redis_client.zadd(key, {str(now_timestamp): now_timestamp})
    
    # Remove timestamps older than our time window
    redis_client.zremrangebyscore(key, '-inf', now_timestamp - time_window_seconds)
    
    # Get the count of recent requests
    recent_requests_count = redis_client.zcard(key)
    
    # Set an expiry on the key itself to clean up memory
    redis_client.expire(key, time_window_seconds + 5)
    
    if recent_requests_count > request_count_threshold:
        return DetectedAnomaly(
            type="REPETITIVE_REQUEST",
            reason=f"Client IP {api_call.client_ip} made {recent_requests_count} requests to {api_call.endpoint} in the last {time_window_seconds} seconds."
        )
    return None

# --- 4. API Endpoint ---

@app.post("/predict", response_model=AnomalyReport)
async def predict_anomaly(api_call: ApiCall = Body(...)):
    """
    Analyzes an API call to detect anomalies using a hybrid approach.
    """
    detected_anomalies: List[DetectedAnomaly] = []
    
    # 1. Autoencoder for Point Anomalies (Response Time & Schema)
    reconstruction_error = get_autoencoder_reconstruction_error(api_call)
    anomaly_score = reconstruction_error # Base score from the primary model
    
    if reconstruction_error > 0.8: # Threshold for the autoencoder
        detected_anomalies.append(DetectedAnomaly(
            type="LATENCY_SPIKE_OR_NEW_SCHEMA",
            reason=f"High reconstruction error ({reconstruction_error:.2f}) from model. Response time: {api_call.response_time_ms}ms."
        ))

    # 2. Redis for Collective Anomalies (Request Rate)
    rate_anomaly = check_increased_request_rate(api_call)
    if rate_anomaly:
        detected_anomalies.append(rate_anomaly)
        anomaly_score = max(anomaly_score, 0.9) # Boost score if rate is high

    # 3. Redis for Behavioral Anomalies (Repetitive Requests)
    repetitive_anomaly = check_repetitive_requests(api_call)
    if repetitive_anomaly:
        detected_anomalies.append(repetitive_anomaly)
        anomaly_score = max(anomaly_score, 0.95) # Boost score for repetitive behavior

    is_anomaly = len(detected_anomalies) > 0
    
    return AnomalyReport(
        request_id=api_call.request_id,
        is_anomaly=is_anomaly,
        anomaly_score=min(1.0, anomaly_score), # Cap score at 1.0
        detected_anomalies=detected_anomalies
    )

# --- To run this application ---
# 1. Make sure you have Redis running.
# 2. In your terminal, run: uvicorn main:app --reload
# 3. The API will be available at http://127.0.0.1:8000
# 4. You can access the interactive API documentation at http://127.0.0.1:8000/docs
