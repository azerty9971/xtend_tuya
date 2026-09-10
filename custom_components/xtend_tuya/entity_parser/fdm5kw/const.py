"""Constants for fdm5kw irrigation valve entity parser."""

from __future__ import annotations

# Tuya device category for this valve controller
DEVICE_CATEGORY = "sfkzq"

# Product ID for the fdm5kw irrigation valve
PRODUCT_ID = "o6dagifntoafakst"

# Days of week bitmask mapping (for time_task decoding)
DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Tuya OpenAPI error: controllable-device pool quota exceeded. Empirically
# validated 2026-05-13 against a live fdm5kw fleet; not in Tuya's public
# docs. Returned on cloud-timer POST when the account's device count is
# above the plan limit. Treat as a soft failure with a persistent
# notification, not an exception.
TUYA_ERR_DEVICE_POOL_QUOTA = 60001001
TUYA_ERR_DEVICE_POOL_QUOTA_MSG = (
    "Tuya controllable-device quota exceeded. Cloud-side timer write was "
    "rejected; the on-device timer DP was still saved and will fire "
    "locally. To re-enable cloud sync (and SmartLife schedule edits), "
    "upgrade the IoT-Core plan or remove unused devices from the project."
)
