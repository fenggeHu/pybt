import logging
import os


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger = logging.getLogger()
    formatter = "%(asctime)-15s %(levelname)-8s [PID:%(process)d] [%(filename)s:%(lineno)d - %(funcName)s] %(message)s"

    if not root_logger.handlers:
        logging.basicConfig(level=level, format=formatter)
        return

    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        if handler.formatter is None:
            handler.setFormatter(logging.Formatter(formatter))
