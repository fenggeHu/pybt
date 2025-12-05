import logging

from pybt.logging import configure_logging


def test_configure_logging_plain_and_json() -> None:
    # plain
    configure_logging(level="DEBUG")
    logger = logging.getLogger("pybt.test")
    logger.debug("hello")

    # json
    configure_logging(level="INFO", json_format=True)
    logger.info("world")
