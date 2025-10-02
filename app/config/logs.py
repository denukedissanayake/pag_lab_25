import logging
from logging.config import dictConfig

def setup_logging():
    """
    Configures logging for the application.
    """
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(asctime)s - %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            # Configure the logger for the 'app' package
            "app": {"handlers": ["default"], "level": "INFO", "propagate": False},
        },
    }
    dictConfig(log_config)
