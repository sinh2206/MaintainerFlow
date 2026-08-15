import dramatiq
from dramatiq.brokers.redis import RedisBroker

from maintainerflow.config import get_settings

broker = RedisBroker(  # type: ignore[no-untyped-call]
    url=get_settings().redis_url,
    namespace="maintainerflow",
)
dramatiq.set_broker(broker)
