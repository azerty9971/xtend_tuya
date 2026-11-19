"""Self-check for DP-based lock/unlock command support (LEZN-D12, videolock).

The LEZN-D12 video door lock (Tuya category "videolock") does not expose the
cloud door-lock API ("Smart Lock Open Service"). Like other videolock devices,
it unlocks on a raw write of dp47 (lock_motor_state) — the thing model marks it
as required for speaker/remote door opening.

This test pins the dynamic lock description for such a device: dp47 must be in
the manual unlock command list so the DPCODE_COMMAND mechanism (tried by the
AUTO mode after the door-operate/door-open APIs) can drive the lock.

Needs Home Assistant (with the tuya requirements) installed.

Run: `python tests/test_lock_motor_state_command.py`
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from custom_components.xtend_tuya.const import XTDPCode  # noqa: E402
from custom_components.xtend_tuya.lock import (  # noqa: E402
    LOCK_MANUAL_COMMAND_DPCODES,
    XTLockEntity,
)


class _StubDevice:
    """Just enough of XTDevice for the lock description lookup."""

    def __init__(self, category: str, status: dict):
        self.category = category
        self.status = status


def test_lock_motor_state_is_a_manual_command_dp():
    assert XTDPCode.LOCK_MOTOR_STATE in LOCK_MANUAL_COMMAND_DPCODES


def test_videolock_description_uses_dp47_command():
    device = _StubDevice(
        category="videolock",
        status={
            "unlock_method_create": "",
            "lock_motor_state": False,
            "closed_opened": "closed",
        },
    )
    description = XTLockEntity.get_entity_description(None, device, None, {})
    assert description is not None
    assert XTDPCode.LOCK_MOTOR_STATE in description.manual_unlock_command
    assert XTDPCode.LOCK_MOTOR_STATE in description.unlock_status_list
    assert XTDPCode.CLOSED_OPENED in description.unlock_status_list
    assert description.temporary_unlock is False


def test_device_without_dp47_gets_no_motor_command():
    device = _StubDevice(
        category="videolock",
        status={
            "unlock_method_create": "",
            "closed_opened": "closed",
        },
    )
    description = XTLockEntity.get_entity_description(None, device, None, {})
    assert description is not None
    assert XTDPCode.LOCK_MOTOR_STATE not in description.manual_unlock_command


def test_non_lock_device_is_not_a_lock():
    device = _StubDevice(category="videolock", status={"switch_1": True})
    assert XTLockEntity.get_entity_description(None, device, None, {}) is None


if __name__ == "__main__":
    test_lock_motor_state_is_a_manual_command_dp()
    test_videolock_description_uses_dp47_command()
    test_device_without_dp47_gets_no_motor_command()
    test_non_lock_device_is_not_a_lock()
    print("ok")
