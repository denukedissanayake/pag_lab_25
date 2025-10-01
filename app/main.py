from fastapi import FastAPI
from app.api.v1 import endpoints
from app.core.config import setup_logging

# Apply the logging configuration
setup_logging()

app = FastAPI(
    title="Anomaly Detection Service",
    description="A service to detect anomalies in API traffic.",
    version="1.0.0"
)

app.include_router(endpoints.router, prefix="/api/v1")
