from __future__ import annotations
from typing import Optional, Literal, Any
import json
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from tuya_sharing.home import (
    HomeRepository,
)
from tuya_sharing.scenes import (
    SceneRepository,
)
from tuya_sharing.user import (
    UserRepository,
)
from tuya_sharing.customerapi import (
    CustomerTokenInfo,
)
from .xt_tuya_sharing_manager import (
    XTSharingDeviceManager,
)
from ..shared.interface.device_manager import (
    XTDeviceManagerInterface,
)
from ..shared.shared_classes import (
    XTConfigEntry,
    XTDeviceMap,
    XTDevice,
)
from .xt_tuya_sharing_data import (
    TuyaSharingData,
)
from .xt_tuya_sharing_token_listener import (
    XTSharingTokenListener,
)
from .xt_tuya_sharing_device_repository import (
    XTSharingDeviceRepository,
)
from .xt_tuya_sharing_api import (
    XTSharingAPI,
)
from .ha_tuya_integration.config_entry_handler import (
    XTHATuyaIntegrationConfigEntryManager,
)
from .ha_tuya_integration.tuya_decorators import (
    XTDecorator,
    decorate_tuya_manager,
    decorate_tuya_integration,
)
from .const import (
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    CONF_ENDPOINT,
    TUYA_CLIENT_ID,
    DOMAIN_ORIG,
)
from .util import (
    get_overriden_tuya_integration_runtime_data,
)
from .ha_tuya_integration.platform_descriptors import get_tuya_platform_descriptors
from ..multi_manager import (
    MultiManager,
)
from ...const import (
    DOMAIN,
    MESSAGE_SOURCE_TUYA_SHARING,
    MESSAGE_SOURCE_TUYA_IOT,
    TUYA_DISCOVERY_NEW,
    TUYA_DISCOVERY_NEW_ORIG,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    XTDeviceSourcePriority,
    LOGGER,
)


def get_plugin_instance() -> XTTuyaSharingDeviceManagerInterface | None:
    return XTTuyaSharingDeviceManagerInterface()


class XTTuyaSharingDeviceManagerInterface(XTDeviceManagerInterface):
    def __init__(self) -> None:
        super().__init__()
        self.sharing_account: TuyaSharingData | None = None
        self.hass: HomeAssistant | None = None
        self.tuya_manager_decorator: list[XTDecorator] = []
        self.tuya_integration_decorator: list[XTDecorator] = []

    def get_type_name(self) -> str:
        return MESSAGE_SOURCE_TUYA_SHARING

    def is_type_initialized(self) -> bool:
        return self.sharing_account is not None

    async def setup_from_entry(
        self,
        hass: HomeAssistant,
        config_entry: XTConfigEntry,
        multi_manager: MultiManager,
    ) -> bool:
        self.multi_manager: MultiManager = multi_manager
        self.hass = hass
        self.sharing_account: TuyaSharingData | None = await self._init_from_entry(
            hass, config_entry
        )
        if self.sharing_account:
            return True
        return False

    async def _init_from_entry(
        self, hass: HomeAssistant, config_entry: XTConfigEntry
    ) -> TuyaSharingData | None:
        ha_tuya_integration_config_manager: (
            XTHATuyaIntegrationConfigEntryManager | None
        ) = None
        # See if our current entry is an override of a Tuya integration entry
        tuya_integration_runtime_data = get_overriden_tuya_integration_runtime_data(
            hass, config_entry
        )
        if tuya_integration_runtime_data:
            # We are using an override of the Tuya integration
            sharing_device_manager = XTSharingDeviceManager(
                multi_manager=self.multi_manager,
                other_device_manager=tuya_integration_runtime_data.device_manager,
            )
            ha_tuya_integration_config_manager = XTHATuyaIntegrationConfigEntryManager(
                sharing_device_manager, config_entry
            )
            self.tuya_manager_decorator = decorate_tuya_manager(
                tuya_integration_runtime_data.device_manager,
                ha_tuya_integration_config_manager,
            )
            sharing_device_manager.terminal_id = (
                tuya_integration_runtime_data.device_manager.terminal_id
            )
            sharing_device_manager.mq = tuya_integration_runtime_data.device_manager.mq
            sharing_device_manager.customer_api = (
                tuya_integration_runtime_data.device_manager.customer_api
            )
            # tuya_integration_runtime_data.device_manager.device_listeners.clear()
            # self.convert_tuya_devices_to_xt(tuya_integration_runtime_data.device_manager)
        else:
            # We are using XT as a standalone integration
            sharing_device_manager = XTSharingDeviceManager(
                multi_manager=self.multi_manager, other_device_manager=None
            )
            token_listener = XTSharingTokenListener(hass, config_entry)
            sharing_device_manager.terminal_id = config_entry.data[CONF_TERMINAL_ID]
            sharing_device_manager.customer_api = XTSharingAPI(
                CustomerTokenInfo(config_entry.data[CONF_TOKEN_INFO]),
                TUYA_CLIENT_ID,
                config_entry.data[CONF_USER_CODE],
                config_entry.data[CONF_ENDPOINT],
                token_listener,
            )
            sharing_device_manager.mq = None
        sharing_device_manager.home_repository = HomeRepository(
            sharing_device_manager.customer_api
        )
        sharing_device_manager.device_repository = XTSharingDeviceRepository(
            sharing_device_manager.customer_api,
            sharing_device_manager,
            self.multi_manager,
        )
        sharing_device_manager.scene_repository = SceneRepository(
            sharing_device_manager.customer_api
        )
        sharing_device_manager.user_repository = UserRepository(
            sharing_device_manager.customer_api
        )
        sharing_device_manager.add_device_listener(self.multi_manager.multi_device_listener)  # type: ignore
        return TuyaSharingData(
            device_manager=sharing_device_manager,
            device_ids=[],
            ha_tuya_integration_config_manager=ha_tuya_integration_config_manager,
        )

    def update_device_cache(self):
        if self.sharing_account is None:
            return None
        try:
            self.sharing_account.device_manager.update_device_cache()
            new_device_ids: list[str] = [
                device_id
                for device_id in self.sharing_account.device_manager.device_map
            ]
            self.sharing_account.device_ids.clear()
            self.sharing_account.device_ids.extend(new_device_ids)

            # if other_manager := self.sharing_account.device_manager.get_overriden_device_manager():
            #    for device in other_manager.device_map.values():
            #        self.multi_manager.device_watcher.report_message(device.id, f"Update device cache TUYA: {device}", device)
        except Exception as exc:
            # While in general, we should avoid catching broad exceptions,
            # we have no other way of detecting this case.
            if "sign invalid" in str(exc):
                if self.sharing_account.device_manager.reuse_config:
                    raise ConfigEntryNotReady(
                        "Authentication failed. Please re-authenticate the Tuya integration"
                    ) from exc
                else:
                    raise ConfigEntryAuthFailed(
                        "Authentication failed. Please re-authenticate."
                    )
            raise

    def get_available_device_maps(self) -> list[XTDeviceMap]:
        return_list: list[XTDeviceMap] = []
        if self.sharing_account is None or self.sharing_account.device_manager is None:
            return return_list
        if (
            other_device_map := self.sharing_account.device_manager.get_overriden_device_map()
        ):
            return_list.append(other_device_map)
        return_list.append(self.sharing_account.device_manager.device_map)
        return return_list

    def refresh_mq(self):
        if self.sharing_account is None:
            return None
        self.sharing_account.device_manager.refresh_mq()

    def remove_device_listeners(self) -> None:
        if self.sharing_account is None:
            return None
        self.sharing_account.device_manager.remove_device_listener(self.multi_manager.multi_device_listener)  # type: ignore

    def unload(self):
        for decorator in self.tuya_integration_decorator:
            decorator.unwrap()
        for decorator in self.tuya_manager_decorator:
            decorator.unwrap()
        if (
            self.sharing_account is None
            or self.sharing_account.device_manager.user_repository is None
            or self.sharing_account.device_manager.terminal_id is None
        ):
            return None
        if not self.multi_manager.get_account_by_name(MESSAGE_SOURCE_TUYA_IOT):
            self.sharing_account.device_manager.user_repository.unload(
                self.sharing_account.device_manager.terminal_id
            )

    def on_message(self, msg: dict):
        if self.sharing_account is None:
            return None
        self.sharing_account.device_manager.on_message(msg)

    def query_scenes(self) -> list:
        if self.sharing_account is None:
            return []
        # Regular Tuya scenes will be deleted by the cleanup_device_registry, readd them regardless of if we override or not
        return self.sharing_account.device_manager.query_scenes()

    def get_device_stream_allocate(
        self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        if self.sharing_account is None:
            return None
        if device_id in self.sharing_account.device_ids:
            return self.sharing_account.device_manager.get_device_stream_allocate(
                device_id, stream_type
            )

    def get_device_registry_identifiers(self) -> list:
        if self.sharing_account is None:
            return []
        if self.sharing_account.device_manager.reuse_config:
            return [DOMAIN_ORIG, DOMAIN]
        return [DOMAIN]

    def get_domain_identifiers_of_device(self, device_id: str) -> list:
        return [DOMAIN]

    def on_update_device(self, device: XTDevice) -> list[str] | None:
        return_list: list[str] = []
        if self.sharing_account is None:
            return None
        if device.id in self.sharing_account.device_ids:
            return_list.append(TUYA_HA_SIGNAL_UPDATE_ENTITY)
        if self.sharing_account.device_manager.reuse_config:
            self.sharing_account.device_manager.copy_statuses_to_tuya(device)
        if return_list:
            return return_list
        return None

    def on_add_device(self, device: XTDevice) -> list[str] | None:
        return_list: list[str] = []
        if self.sharing_account is None:
            return None
        if device.id in self.sharing_account.device_ids:
            return_list.append(TUYA_DISCOVERY_NEW)
        if self.sharing_account.device_manager.reuse_config:
            return_list.append(TUYA_DISCOVERY_NEW_ORIG)
        if return_list:
            return return_list
        return None

    def on_mqtt_stop(self):
        if (
            self.sharing_account is not None
            and self.sharing_account.device_manager.mq
            and not self.sharing_account.device_manager.reuse_config
        ):
            self.sharing_account.device_manager.mq.stop()

    def on_post_setup(self):
        if self.sharing_account is None:
            return None

        if self.sharing_account.ha_tuya_integration_config_manager is not None:
            self.tuya_integration_decorator = decorate_tuya_integration(
                self.sharing_account.ha_tuya_integration_config_manager
            )

        for device in self.sharing_account.device_manager.device_map.values():
            # This should in theory already be done, I kept it here just to be safe...
            self.sharing_account.device_manager.copy_statuses_to_tuya(device)

            # Trigger Tuya's rediscovery
            self.multi_manager.multi_device_listener.trigger_device_discovery(
                device, [TUYA_DISCOVERY_NEW_ORIG]
            )

    def get_platform_descriptors_to_merge(self, platform: Platform) -> Any:
        if self.sharing_account is None:
            return None
        if self.sharing_account.device_manager.reuse_config:
            return None
        return get_tuya_platform_descriptors(platform)
    
    def get_platform_descriptors_to_exclude(self, platform: Platform) -> Any:
        if self.sharing_account is not None and self.sharing_account.device_manager.reuse_config:
            return get_tuya_platform_descriptors(platform)

    def send_commands(self, device_id: str, commands: list[dict[str, Any]]) -> bool:
        if self.sharing_account is None:
            return False
        regular_commands: list[dict[str, Any]] = []
        device = self.multi_manager.device_map.get(device_id)
        return_result = True
        if device is None:
            return False
        for command in commands:
            command_code: str = command["code"]
            """command_value: str = command["value"]"""

            # Filter commands that require the use of OpenAPI
            if dpId := self.multi_manager._read_dpId_from_code(command_code, device):
                if device.local_strategy[dpId].get("use_open_api", False):
                    return_result = False  # Part of the commands have not been issues, forward to other managers
                    continue
            regular_commands.append(command)

        try:
            if regular_commands:
                self.sharing_account.device_manager.send_commands(
                    device_id, regular_commands
                )
            return return_result
        except Exception as e:
            LOGGER.warning(
                f"[Sharing]Send command failed, device id: {device_id}, commands: {commands}, exception: {e}"
            )
            return False

    def convert_to_xt_device(
        self, device: Any, device_source_priority: XTDeviceSourcePriority | None = None
    ) -> XTDevice:
        device_new: XTDevice = XTDevice.from_compatible_device(
            device, device_source_priority=device_source_priority
        )
        if device_source_priority == XTDeviceSourcePriority.REGULAR_TUYA:
            device_new.force_compatibility = True
            device_new.regular_tuya_device = device
        return device_new

    def send_lock_unlock_command(self, device: XTDevice, lock: bool) -> bool:
        if self.sharing_account is None:
            return False
        return self.sharing_account.device_manager.send_lock_unlock_command(
            device, lock
        )

    def call_api(
        self, method: str, url: str, payload: str | None
    ) -> dict[str, Any] | None:
        params: dict[str, Any] | None = None
        if (
            self.sharing_account is None
            or self.sharing_account.device_manager.customer_api is None
        ):
            return None
        if payload:
            params = json.loads(payload)
        match method:
            case "GET":
                return self.sharing_account.device_manager.customer_api.get(url, params)
            case "POST":
                return self.sharing_account.device_manager.customer_api.post(
                    url, params
                )
        return None

    def trigger_scene(self, home_id: str, scene_id: str) -> bool:
        if self.sharing_account is None:
            return False
        self.sharing_account.device_manager.trigger_scene(home_id, scene_id)
        return True
