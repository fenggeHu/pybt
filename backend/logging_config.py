import logging
import sys

from pythonjsonlogger import jsonlogger


def setup_logging():
    logger = logging.getLogger()
    
    # Defaults to INFO
    logger.setLevel(logging.INFO)

    logHandler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    
    # Squelch some noisy libraries
    logging.getLogger("uvicorn.access").disabled = True
