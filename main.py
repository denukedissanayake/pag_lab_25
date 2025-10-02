from fastapi import FastAPI
from app.api.v1 import endpoints
from app.config.logs import setup_logging
import uvicorn

setup_logging()

app = FastAPI(
    title="Anomaly Detection Service",
    description="A service to detect anomalies in API traffic.",
    version="1.0.0"
)

app.include_router(endpoints.router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
