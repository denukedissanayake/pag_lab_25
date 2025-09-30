from fastapi import FastAPI
from app.api.v1 import endpoints

app = FastAPI(
    title="Anomaly Detection Service",
    description="A service to detect anomalies in API traffic.",
    version="1.0.0"
)

app.include_router(endpoints.router, prefix="/api/v1")
