"""Tuya iot logging."""

from __future__ import annotations

import logging  # noqa: F401
from typing import Any
from ...const import LOGGER as logger

#logger = logging.getLogger(__package__)

#default_handler = logging.StreamHandler()
#default_handler.setFormatter(
#    logging.Formatter("[%(asctime)s] [tuya-%(module)s] %(message)s")
#)

#logger.addHandler(default_handler)
TUYA_LOGGER = logger

FILTER_LIST = [
    "access_token",
    "client_id",
    "ip",
    "lat",
    "link_id",
    "local_key",
    "lon",
    "password",
    "refresh_token",
    "uid",
]

STAR = "***"


def _mask(value: Any) -> Any:
    """Return a copy of value with every FILTER_LIST key masked, at any depth."""
    if isinstance(value, dict):
        return {
            key: STAR if key in FILTER_LIST else _mask(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_mask(item) for item in value]
    return value


def filter_logger(result_info: dict[str, Any] | None):
    """Filter log, hide sensitive info.

    Works on a copy, masks sensitive keys at any depth (including inside
    lists and next to "result"), and never raises on unexpected shapes,
    since it runs on every logged request/response.
    """
    if result_info is None:
        return result_info
    return _mask(result_info)
