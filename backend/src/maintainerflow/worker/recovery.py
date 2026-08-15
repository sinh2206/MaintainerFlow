import logging
import time

from maintainerflow.config import get_settings
from maintainerflow.worker.tasks import recover_deliveries

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    while True:
        try:
            recover_deliveries.send()
        except Exception:
            logger.exception("unable to enqueue recovery scan")
        time.sleep(settings.recovery_interval_seconds)


if __name__ == "__main__":
    main()
