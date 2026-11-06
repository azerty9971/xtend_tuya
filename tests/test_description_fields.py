"""Self-check that XT descriptions accept every core Tuya description.

XT copies core Tuya descriptions with XT...EntityDescription(**description.__dict__).
Home Assistant 2026.11 added channel_index and channel_condition to the core
TuyaEntityDescription, plus TuyaDeprecatedSwitchEntityDescription with
deprecated and breaks_in_ha_version. With frozen_or_thawed=True the XT switch,
siren and vacuum descriptions did not inherit the new fields, so the copy raised
"unexpected keyword argument 'channel_index'" and the platforms failed to set up.

Needs Home Assistant 2026.11 or later (with the tuya requirements) installed.

Run: `python tests/test_description_fields.py`
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from homeassistant.components.tuya.siren import SIRENS  # noqa: E402
from homeassistant.components.tuya.switch import SWITCHES  # noqa: E402
from homeassistant.components.tuya.vacuum import VACUUMS  # noqa: E402

from custom_components.xtend_tuya.siren import XTSirenEntityDescription  # noqa: E402
from custom_components.xtend_tuya.switch import (  # noqa: E402
    XTSwitchEntity,
    XTSwitchEntityDescription,
)
from custom_components.xtend_tuya.vacuum import XTVacuumEntityDescription  # noqa: E402


def _all(descriptions):
    for value in descriptions.values():
        yield from value if isinstance(value, tuple) else (value,)


def test_xt_descriptions_have_core_fields():
    for xt_type in (
        XTSwitchEntityDescription,
        XTSirenEntityDescription,
        XTVacuumEntityDescription,
    ):
        description = xt_type(key="switch_1", channel_index=1)
        assert description.channel_index == 1, xt_type.__name__


def test_xt_switch_keeps_own_fields():
    description = XTSwitchEntityDescription(
        key="switch_1", channel_index=2, override_tuya=True, dont_send_to_cloud=True
    )
    assert description.channel_index == 2
    assert description.override_tuya is True
    assert description.dont_send_to_cloud is True
    assert description.ignore_other_dp_code_handler is False


def test_copy_core_sirens_and_vacuums():
    for xt_type, core in (
        (XTSirenEntityDescription, SIRENS),
        (XTVacuumEntityDescription, VACUUMS),
    ):
        for description in _all(core):
            copied = xt_type(**description.__dict__)
            assert copied.key == description.key


class _Recorder:
    """Stands in for XTSwitchEntity and records the description it receives."""

    def __init__(self, **kwargs):
        self.description = kwargs["description"]


def test_convert_all_core_switches():
    convert = XTSwitchEntity.get_entity_instance
    module = sys.modules[XTSwitchEntity.__module__]
    original = module.XTSwitchEntity
    module.XTSwitchEntity = _Recorder # type: ignore
    try:
        for description in _all(SWITCHES):
            entity = convert(
                device=None, # type: ignore
                device_manager=None, # type: ignore
                description=description, # type: ignore
                definition=None, # type: ignore
            )
            assert isinstance(entity.description, XTSwitchEntityDescription)
            assert entity.description.key == description.key
            assert entity.description.channel_index == description.channel_index
    finally:
        module.XTSwitchEntity = original # type: ignore


if __name__ == "__main__":
    test_xt_descriptions_have_core_fields()
    test_xt_switch_keeps_own_fields()
    test_copy_core_sirens_and_vacuums()
    test_convert_all_core_switches()
    print("ok")
