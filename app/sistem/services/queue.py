"""RQ клиент — очередь задач."""
from __future__ import annotations

import logging

from redis import Redis
from rq import Queue

from sistem.config import get_settings

log = logging.getLogger("sistem.queue")

_redis: Redis | None = None
_queue: Queue | None = None


def _init() -> None:
    global _redis, _queue
    if _queue is not None:
        return
    s = get_settings()
    _redis = Redis.from_url(s.redis_url, decode_responses=False)
    _queue = Queue("sistem", connection=_redis)


def get_queue() -> Queue:
    _init()
    assert _queue is not None
    return _queue


def get_redis() -> Redis:
    _init()
    assert _redis is not None
    return _redis
