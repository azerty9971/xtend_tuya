# Xtend Tuya - AI Coding Agent Instructions

## Project Overview
**Xtend Tuya** is a Home Assistant custom integration that extends the official Tuya integration by adding missing entities and supporting multiple cloud sources (Tuya IoT, Tuya Sharing). It bridges the gap between raw Tuya device capabilities and Home Assistant's platform architecture through a sophisticated multi-source device management system.

**Key Constraints**: Uses "hacks" (undocumented Home Assistant patterns) to override official integration functionality. Must maintain compatibility with both standalone and alongside-official-integration modes.

## Architecture Overview

### Core Data Flow
```
MultiManager (hub orchestrator)
  ├─ MultiMQTTQueue → Message routing from sources
  ├─ MultiDeviceListener → Entity updates via dispatcher_send
  ├─ XTVirtualStateHandler → Synthesize virtual data points
  ├─ XTVirtualFunctionHandler → Process virtual commands
  └─ Accounts (dict[str, XTDeviceManagerInterface])
      ├─ TuyaIOTManager (tuya_iot) → Cloud API via OpenAPI SDK
      └─ TuyaSharingManager (tuya_sharing) → P2P via tuya_sharing library
```

**Device Merging Strategy**: Multiple sources provide the same device with different capabilities. `XTMergingManager` reconciles conflicts using `XTDeviceSourcePriority` (REGULAR_TUYA=10, TUYA_SHARED=20, TUYA_IOT=30). Lower priority wins on conflict.

### Critical Components

#### 1. **XTDevice** (pseudo-Tuya device wrapper)
- Located: `multi_manager/shared/shared_classes.py`
- Attributes: `id`, `name`, `category`, `status` (dict[code → value]), `local_strategy` (data point definitions), `function` (device capabilities)
- **Virtual States**: Synthesized data points created by `XTVirtualStateHandler` for energy/status rollup
- **Virtual Functions**: Commands that manipulate virtual states (e.g., reset energy counters)

#### 2. **MultiManager**
- Located: `multi_manager/multi_manager.py`
- Orchestrates all device managers and synchronizes their views
- **Key methods**:
  - `setup_entry()` → Dynamically loads manager plugins (tuya_iot, tuya_sharing)
  - `setup_entity_parsers()` → Initializes custom entity descriptors
  - `_merge_devices_from_multiple_sources()` → Resolves device conflicts
  - `_read_dpId_from_code()` / `_read_code_from_dpId()` → Bridge between Tuya's data point codes and numeric IDs

#### 3. **XTDeviceManagerInterface** (plugin contract)
- Located: `multi_manager/shared/interface/device_manager.py`
- Abstract base for manager implementations (TuyaIOT, TuyaSharing)
- Implementations must provide:
  - Device conversion to XTDevice
  - Platform descriptor merging/exclusion
  - Device lifecycle (add, update, remove)
  - Signal routing back to MultiManager

#### 4. **Multi-Source Message Handling**
- `MultiMQTTQueue`: Routes MQTT messages from both managers
- `MultiSourceHandler`: Filters status lists via `filter_status_list()` to prevent duplicate virtual state processing
- **Key Insight**: Virtual states can cascade—must detect and deduplicate to avoid infinite loops

### Entity Platform Patterns

**Fully Overridden Platforms** (`const.py:FULLY_OVERRIDEN_PLATFORMS`):
- Camera, Climate, Cover, Fan, Humidifier, Lock, Remote
- Xtend Tuya provides ALL entities for these platforms; official integration's are ignored

**Augmented Platforms**:
- All other platforms coexist with official Tuya entities; Xtend Tuya adds extras

**Entity Descriptors**:
- Located in platform files (e.g., `sensor.py`, `switch.py`)
- Keyed by Tuya device category; fall back to `CROSS_CATEGORY_DEVICE_DESCRIPTOR` if needed
- Descriptors inherit from Home Assistant base (e.g., `SensorEntityDescription`) with extra `virtual_state` / `virtual_function` fields

### Configuration & Discovery

**Config Flow** (`config_flow.py`):
- Supports multiple auth modes: Tuya Smart app, SmartLife app, OpenTuya custom
- Multiple account support via "Add hub" button
- Optional Tuya Cloud credentials for full entity discovery
- Cloud endpoint selection (China, Europe, America, etc.)

**Data Entry Manager Pattern** (`multi_manager/shared/data_entry/shared_data_entry.py`):
- Async wrapper for user interactions during setup
- Generates flow data and fires bus events for UI callbacks
- Used for multi-step flows (auth → device selection → options)

## Key Developer Workflows

### Adding a New Entity Type

1. **Create platform file** (e.g., `humidity.py`):
   ```python
   from homeassistant.components.humidifier import ...
   from .entity import XTEntity
   
   HUMIDIFIERS = {
       "category_id": (
           HumidifierEntityDescription(key="humidity_set", ...),
       ),
       CROSS_CATEGORY_DEVICE_DESCRIPTOR: (...),
   }
   
   async def async_setup_entry(hass, config_entry, async_add_entities):
       # Fetch devices and create entities
   ```

2. **Register descriptors** in `MultiManager`:
   - `register_device_descriptors("platform_name", DESCRIPTORS)`
   - Triggered during `setup_entry()` phase

3. **Virtual State Consideration**:
   - If descriptor has `virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME`, handler auto-creates copies
   - Add to `const.py:XTDPCode` if new Tuya data point code needed

### Debugging Device Issues

**Key Tools**:
- `DeviceWatcher` (`multi_manager/shared/`) → Tracks device messages and state transitions
- `DebugHelper` → Formats device info for logs
- Loggers configured in `manifest.json`: `tuya_iot`, `tuya_sharing` set to CRITICAL by default

**Common Patterns**:
```python
# Check device exists and has capability
device = multi_manager.device_map.get(device_id)
if not device or device.category not in allowed_categories:
    return

# Read data point value
dpid = multi_manager._read_dpId_from_code("code_name", device)
value = device.status.get("code_name")
```

### Threading & Async Patterns

**Critical Constraint**: Tuya SDKs (tuya_iot, tuya_sharing) run on separate threads.

**Use `XTEventLoopProtector`** (mandatory):
```python
# Call blocking SDK methods OFF event loop
await XTEventLoopProtector.execute_out_of_event_loop_and_return(
    sdk_function, arg1, arg2
)

# Fire-and-forget
XTEventLoopProtector.execute_out_of_event_loop(blocking_func, arg1)
```

**Concurrency Management**:
- `XTConcurrencyManager` limits parallel tasks (default 9)
- Use for batch operations: `await manager.gather()`

## Project-Specific Conventions

### Naming
- **Files**: snake_case (e.g., `multi_manager.py`)
- **Classes**: PascalCase with "XT" prefix (e.g., `XTDevice`, `XTVirtualStateHandler`)
- **Data Points**: Tuya conventions—lowercase with underscores (e.g., `add_ele`, `temp_current_f`)
- **Constants**: UPPER_CASE in `const.py` (never inline magic strings)

### Code Structure
- **Imports**: Always group by Home Assistant, external libraries, then local
- **Type Hints**: Mandatory for public methods; use `|` for unions (Python 3.10+)
- **Docstrings**: Minimal—focus on WHY, not WHAT (code is clear)

### Device State Updates
- **Never directly mutate device.status** in handlers
- Use `multi_manager.multi_device_listener.update_device(device)` to emit dispatcher signal
- Virtual states apply transformations **before** entity refresh

### Configuration Entry
- Stored in `entry.runtime_data` as `HomeAssistantXTData` (multi_manager + service_manager)
- Access via `config_entry.runtime_data.multi_manager` in platform code
- Services registered via `ServiceManager` during setup_entry

## Integration Points & Dependencies

### External SDKs
- **tuya_iot** (Home Assistant's Tuya IoT SDK): For cloud API operations
- **tuya_sharing** (custom P2P library): For local device communication
- **ffmpeg**: Required by camera platform (video streaming)
- **http**: Required for web-based operations

### Monkey Patches (Hacks)
- **Location**: `multi_manager/shared/tuya_patches/tuya_patches.py`
- Patches official Tuya SDK to prevent conflicts with official integration
- Applied once in `async_setup_entry()` via `XTTuyaPatcher.patch_tuya_code()`
- **Never remove without understanding patch_tuya_code() logic**

### Device Registry Cleanup
- `cleanup_device_registry()` & `cleanup_duplicated_devices()` run async to prevent startup delays
- Only master config entry (first loaded) performs cleanup to avoid race conditions
- Checks `is_config_entry_master()` before operating on registries

## Testing & Validation

**No built-in test framework configured.** For manual validation:
1. Start Home Assistant with xtend_tuya installed
2. Add integration via UI: _Settings → Devices & Integrations → Xtend Tuya_
3. Check logs for `LOGGER.debug()` entries (indicates successful phases)
4. Verify devices appear in Entity Registry with correct categories

**Common Issues**:
- Device not appearing → Check `device_map` in DeviceWatcher logs
- Wrong entity count → Verify descriptor registration in `setup_entity_parsers()`
- Virtual states not working → Ensure `apply_init_virtual_states()` ran (phase timing)

## Files to Know

| File | Purpose |
|------|---------|
| `__init__.py` | Main integration entry; orchestrates setup phases |
| `const.py` | Constants, enums (XTDPCode, VirtualStates), country configs |
| `config_flow.py` | User auth & device selection flows |
| `entity.py` | Base XTEntity class; descriptor management |
| `multi_manager/multi_manager.py` | Central orchestrator |
| `multi_manager/managers/tuya_iot/init.py` | Tuya IoT source manager |
| `multi_manager/managers/tuya_sharing/init.py` | Tuya Sharing source manager |
| `multi_manager/shared/multi_virtual_state_handler.py` | Virtual data point synthesis |
| `multi_manager/shared/multi_device_listener.py` | Entity update dispatcher |
| `{sensor,switch,camera,etc}.py` | Platform implementations |

---

**Last Updated**: Dec 2024 | **Version**: 4.2.6 | **Branch**: alpha
