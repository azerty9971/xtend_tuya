"""Smart Cover Control for XT Tuya Covers.

This module provides intelligent percentage-based control for covers when the device's
native percentage control doesn't work properly. It uses time-based calculations to
simulate precise position control.
"""

from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from enum import Enum

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.const import STATE_OPEN, STATE_OPENING, STATE_CLOSING, STATE_CLOSED

from .const import LOGGER, XTDPCode
from .multi_manager.multi_manager import XTDevice


class CoverMovementState(Enum):
    """Cover movement states."""
    STOPPED = "stopped"
    OPENING = "opening"
    CLOSING = "closing"
    UNKNOWN = "unknown"


@dataclass
class CoverTimingConfig:
    """Configuration for cover timing."""
    full_open_time: float = 60.0  # seconds for full open/close cycle
    full_close_time: float = 60.0  # seconds for full open/close cycle (same as open)
    position_tolerance: int = 1  # percentage tolerance for position matching (very tight for accuracy)


@dataclass
class CoverState:
    """Current state of the cover."""
    position: int = 0  # 0-100 percentage
    target_position: int | None = None
    movement_state: CoverMovementState = CoverMovementState.STOPPED
    movement_start_time: float | None = None
    movement_start_position: int = 0
    last_update_time: float = field(default_factory=time.time)


class SmartCoverController:
    """Smart controller for a single cover."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: XTDevice,
        device_manager,  # MultiManager type
        cover_entity_id: str,
        control_dp: str,
        timing_config: CoverTimingConfig | None = None,
    ) -> None:
        """Initialize the smart cover controller."""
        self.hass = hass
        self.device = device
        self.device_manager = device_manager
        self.cover_entity_id = cover_entity_id
        self.control_dp = control_dp
        self.timing_config = timing_config or CoverTimingConfig()
        self.state = CoverState()
        self.positioning_enabled = False  # Smart positioning disabled by default
        self._update_task_running = False  # Flag to prevent multiple update tasks
        self._updating_position = False  # Flag to prevent recursive position updates

        # Storage for persistence
        store_key = f"xtend_tuya_smart_cover_{device.id}_{control_dp}"
        self._store = Store(
            hass,
            1,
            store_key,
        )
        LOGGER.info(f"Created Store for {device.id}_{control_dp} with key: {store_key}")

        # Track control DP changes
        self._unsubscribe_callbacks: list[Callable] = []

        # Command confirmation tracking (simplified)
        self._command_confirmations: dict[str, float] = {}  # command -> timestamp when confirmed

        # Smart positioning state tracking
        self._smart_positioning_active = False  # Flag to indicate if we're in smart positioning mode
        self._last_sent_command = None  # Track the last command we sent for smart positioning
        self._last_sent_command_time = None  # When we sent the last command

        # Precise timing for positioning
        self._movement_timer = None  # Single precise timer for movement
        self._movement_start_time = None  # When current movement started
        self._watchdog_timer = None  # Safety timer to auto-stop stuck movements

        # Position tracking
        self._device_has_position_dp = False  # Whether device has a real position DP
        self._initial_setup_complete = False  # Whether initial setup is done

    def _safe_create_task(self, coro) -> None:
        """Safely create an async task from any thread."""
        try:
            # Always use the thread-safe method for MQTT callbacks
            def schedule_task():
                try:
                    self.hass.async_create_task(coro)
                except Exception as schedule_error:
                    LOGGER.error(f"{self.device.name}: Failed to schedule async task: {schedule_error}")

            # Schedule on the main thread safely
            self.hass.loop.call_soon_threadsafe(schedule_task)

        except Exception as e:
            LOGGER.error(f"{self.device.name}: Unexpected error creating async task: {e}")

    async def async_setup(self) -> None:
        """Set up the smart cover controller."""
        LOGGER.info(f"Setting up smart cover controller for {self.device.id}_{self.control_dp}")

        # Set up status monitoring via HA dispatcher
        self._setup_status_monitoring()

        # Load stored state
        stored_data = None
        try:
            stored_data = await self._store.async_load()

            if stored_data:
                if "state" in stored_data:
                    state_data = stored_data["state"]
                    self.state = CoverState(
                        position=state_data.get("position", 0),
                        target_position=state_data.get("target_position"),
                        movement_state=CoverMovementState(state_data.get("movement_state", "stopped")),
                        last_update_time=state_data.get("last_update_time", time.time()),
                    )

                if "timing_config" in stored_data:
                    timing_data = stored_data["timing_config"]
                    self.timing_config = CoverTimingConfig(
                        full_open_time=timing_data.get("full_open_time", 60.0),
                        full_close_time=timing_data.get("full_close_time", 60.0),
                        position_tolerance=timing_data.get("position_tolerance", 1),
                    )

                self.positioning_enabled = stored_data.get("positioning_enabled", False)
            else:
                LOGGER.debug(f"No stored data for {self.device.id}_{self.control_dp}, using defaults")
        except Exception as e:
            LOGGER.error(f"Error loading stored data for {self.device.id}_{self.control_dp}: {e}")
            stored_data = None

        # Initialize current position - priority order:
        # 1. Stored state (from previous session)
        # 2. Device status (from Tuya device)
        # 3. Default to 0
        stored_position = self.state.position
        device_position = self._get_position_from_device_status()
        has_stored_state = stored_data is not None and "state" in stored_data

        if has_stored_state:
            if (device_position is not None and
                abs(device_position - stored_position) > 5):
                LOGGER.warning(
                    f"{self.device.name}: Device position ({device_position}%) differs from "
                    f"stored ({stored_position}%), using stored"
                )
        elif device_position is not None:
            self.state.position = device_position
            await self._save_state()
        else:
            if stored_data is None:
                self.state.position = 0

        # Mark initial setup as complete
        self._initial_setup_complete = True
        await self._save_state()

        control_dp_value = str(self.control_dp)
        LOGGER.info(
            f"Smart cover controller initialized for {self.device.name} "
            f"(DP: {control_dp_value}) at position {self.state.position}%, "
            f"positioning_enabled={self.positioning_enabled}"
        )

    def _setup_status_monitoring(self) -> None:
        """Set up monitoring of device status changes via HA dispatcher."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        from homeassistant.core import callback as ha_callback

        signal = f"tuya_entry_update_{self.device.id}"

        @ha_callback
        def _on_dispatcher_update(updated_status_properties=None, dp_timestamps=None):
            """Convert dispatcher update to status change format."""
            if not updated_status_properties:
                return
            status_updates = []
            for dp_code in updated_status_properties:
                value = self.device.status.get(dp_code)
                if value is not None:
                    status_updates.append({"code": dp_code, "value": value})
            if status_updates:
                self._on_device_status_change(self.device.id, status_updates)

        unsub = async_dispatcher_connect(self.hass, signal, _on_dispatcher_update)
        self._unsubscribe_callbacks.append(unsub)

    def _on_device_status_change(self, device_id: str, status_updates: list) -> None:
        """Handle device status changes from Tuya."""
        try:
            if device_id != self.device.id:
                return

            LOGGER.debug(f"{self.device.name}: Received status updates: {status_updates}")

            # Handle both string and enum comparison for this controller's specific DP
            control_dp_value = self.control_dp.value if hasattr(self.control_dp, 'value') else str(self.control_dp)
            LOGGER.debug(f"{self.device.name} ({control_dp_value}): Processing status updates for control DP: {control_dp_value}")

            for update in status_updates:
                code = update.get("code")
                value = update.get("value")

                LOGGER.debug(f"{self.device.name} ({control_dp_value}): Processing status update - code: {code} ({type(code)}), value: {value} ({type(value)})")

                # ONLY process updates that match THIS controller's specific control DP
                if not (code == self.control_dp or code == control_dp_value):
                    LOGGER.debug(f"{self.device.name} ({control_dp_value}): Ignoring status update for different DP: {code}")
                    continue

                LOGGER.info(f"{self.device.name} ({control_dp_value}): Processing status update for OUR control DP - code: {code}, value: {value}")

                # COMMAND CONFIRMATION TRACKING (always track, regardless of positioning_enabled)
                if True:  # This was: if code == self.control_dp or code == control_dp_value:
                    current_time = time.time()

                    # Record command confirmation
                    self._command_confirmations[value] = current_time
                    LOGGER.info(f"{self.device.name}: Device confirmed command '{value}' (code: {code})")

                    # Handle stop command confirmations
                    if value == "stop":
                        LOGGER.info(f"{self.device.name}: Stop command confirmed by device")
                        # Check if this is our smart positioning stop command
                        if (self._smart_positioning_active and
                            self._last_sent_command == "stop" and
                            self._last_sent_command_time is not None and
                            current_time - self._last_sent_command_time < 5.0):
                            LOGGER.info(f"{self.device.name}: Our smart positioning stop confirmed - completing operation")
                            self._stop_movement(current_time)
                        # Ensure movement is actually stopped for any other case
                        elif self.state.movement_state != CoverMovementState.STOPPED:
                            LOGGER.info(f"{self.device.name}: Stopping movement due to device stop confirmation")
                            self._stop_movement(current_time)

                    # MOVEMENT TRACKING (only if smart positioning is enabled)
                    if self.positioning_enabled:
                        LOGGER.info(f"{self.device.name}: Control DP {self.control_dp} changed to: {value}")

                        # Check if this is a confirmation of the exact command we just sent for smart positioning
                        is_our_command_confirmation = (
                            self._smart_positioning_active and
                            self._last_sent_command == value and
                            self._last_sent_command_time is not None and
                            current_time - self._last_sent_command_time < 5.0  # Only within 5 seconds of sending
                        )

                        if is_our_command_confirmation:
                            LOGGER.info(f"{self.device.name}: Status update is confirmation of our smart positioning '{value}' command - ignoring for manual control")
                            # Don't treat our own stop command confirmations as manual operations
                            if value == "stop":
                                LOGGER.debug(f"{self.device.name}: Ignoring stop confirmation as manual operation - this is our scheduled stop")
                                continue  # Skip manual control handling for our own stop
                        else:
                            # This is either:
                            # 1. A manual operation (not during smart positioning)
                            # 2. A different command during smart positioning (manual override)
                            # 3. Our command confirmation but too late (probably manual)
                            if self._smart_positioning_active:
                                if value != self._last_sent_command:
                                    LOGGER.info(f"{self.device.name}: Manual override detected during smart positioning - '{value}' (we sent '{self._last_sent_command}')")
                                else:
                                    LOGGER.info(f"{self.device.name}: Late confirmation or manual '{value}' - treating as manual operation")
                            else:
                                LOGGER.info(f"{self.device.name}: Manual operation detected - '{value}'")

                            # Handle as manual control - this will calculate position and update state
                            self._handle_control_change(value)

            # POSITION SYNC (only if smart positioning is enabled) - check ALL updates for position DPs
            if self.positioning_enabled:
                for update in status_updates:
                    code = update.get("code")
                    value = update.get("value")

                    position_dps = {
                        XTDPCode.CONTROL: XTDPCode.PERCENT_STATE,
                        XTDPCode.CONTROL_2: XTDPCode.PERCENT_STATE_2,
                        XTDPCode.CONTROL_3: XTDPCode.PERCENT_STATE_3,
                    }

                    expected_position_dp = position_dps.get(self.control_dp)
                    if code == expected_position_dp and isinstance(value, (int, float)):
                        LOGGER.info(f"{self.device.name} ({control_dp_value}): Position DP {expected_position_dp} changed to: {value}%")
                        self._sync_position_from_device(int(value))

        except Exception as e:
            LOGGER.error(f"{self.device.name}: Error in status change handler: {e}")

    def _handle_control_change(self, control_value: str) -> None:
        """Handle changes to the control DP."""
        # Only process if smart positioning is enabled
        if not self.positioning_enabled:
            return

        current_time = time.time()

        # If we were in smart positioning and this is a manual override, we need to:
        # 1. Clear any running timer
        # 2. Calculate where we were when the manual command was issued
        # 3. Update our position to that calculated position
        # 4. Start tracking the new manual movement from there
        was_smart_positioning = self._smart_positioning_active

        if was_smart_positioning:
            # Clear the precise movement timer
            self._clear_movement_timer()
            # Calculate current position based on time elapsed
            self._update_position_from_movement(current_time)

        if control_value == "open":
            if self.state.movement_state != CoverMovementState.OPENING:
                if was_smart_positioning:
                    LOGGER.info(f"{self.device.name}: Manual open override during smart positioning - calculated position: {self.state.position}%")
                else:
                    LOGGER.info(f"{self.device.name}: Manual open detected - starting movement tracking")

                self._start_movement(CoverMovementState.OPENING, current_time, 100)

        elif control_value == "close":
            if self.state.movement_state != CoverMovementState.CLOSING:
                if was_smart_positioning:
                    LOGGER.info(f"{self.device.name}: Manual close override during smart positioning - calculated position: {self.state.position}%")
                else:
                    LOGGER.info(f"{self.device.name}: Manual close detected - starting movement tracking")

                self._start_movement(CoverMovementState.CLOSING, current_time, 0)

        elif control_value == "stop":
            if self.state.movement_state != CoverMovementState.STOPPED:
                if was_smart_positioning:
                    LOGGER.info(f"{self.device.name}: Manual stop during smart positioning - calculated final position: {self.state.position}%")
                else:
                    LOGGER.info(f"{self.device.name}: Manual stop detected - calculated final position: {self.state.position}%")

                self._stop_movement(current_time)

        # If this was a manual override of smart positioning, clear the smart positioning state
        if was_smart_positioning:
            LOGGER.info(f"{self.device.name}: Smart positioning overridden by manual '{control_value}' - switching to manual mode")
            self._smart_positioning_active = False
            self._last_sent_command = None
            self._last_sent_command_time = None

    def _sync_position_from_device(self, reported_position: int) -> None:
        """Sync controller position with device-reported position."""
        # Only process if smart positioning is enabled
        if not self.positioning_enabled:
            return

        # If position differs significantly from our tracked position, sync it
        if abs(self.state.position - reported_position) > self.timing_config.position_tolerance:
            LOGGER.info(
                f"{self.device.name}: Syncing position from device: "
                f"{self.state.position}% -> {reported_position}%"
            )

            # If we were moving but device reports a different position, assume manual stop
            was_moving = self.state.movement_state != CoverMovementState.STOPPED

            self.state.position = reported_position
            self.state.last_update_time = time.time()

            # If we were tracking movement but got a position update, stop movement tracking
            if was_moving:
                LOGGER.info(f"{self.device.name}: Position sync detected during movement - stopping movement tracking")
                self.state.movement_state = CoverMovementState.STOPPED
                self.state.movement_start_time = None
                self.state.target_position = None
                self._update_task_running = False

            # Save the updated state
            self._safe_create_task(self._save_state())

    def _clear_movement_timer(self) -> None:
        """Clear any running movement timer."""
        if self._movement_timer is not None:
            try:
                self._movement_timer.cancel()
                LOGGER.debug(f"{self.device.name}: Cleared movement timer")
            except Exception as e:
                LOGGER.warning(f"{self.device.name}: Error clearing movement timer: {e}")
            finally:
                self._movement_timer = None

    def _clear_watchdog_timer(self) -> None:
        """Clear the watchdog safety timer."""
        if self._watchdog_timer is not None:
            try:
                self._watchdog_timer.cancel()
                LOGGER.debug(f"{self.device.name}: Cleared watchdog timer")
            except Exception as e:
                LOGGER.warning(f"{self.device.name}: Error clearing watchdog timer: {e}")
            finally:
                self._watchdog_timer = None

    def _start_watchdog_timer(self, movement_state: CoverMovementState) -> None:
        """Start a safety watchdog timer to auto-stop stuck movements.

        This prevents covers from being stuck in 'opening...' or 'closing...' state
        if the device never reports a stop status.
        """
        self._clear_watchdog_timer()

        # Use the full travel time + 20% margin as the watchdog timeout
        if movement_state == CoverMovementState.OPENING:
            max_time = self.timing_config.full_open_time * 1.2
        elif movement_state == CoverMovementState.CLOSING:
            max_time = self.timing_config.full_close_time * 1.2
        else:
            return

        def watchdog_triggered():
            """Auto-stop movement if it exceeds maximum expected travel time."""
            if self.state.movement_state != CoverMovementState.STOPPED:
                LOGGER.warning(
                    f"{self.device.name}: Watchdog triggered - movement stuck in "
                    f"'{self.state.movement_state.value}' for >{max_time:.0f}s, forcing stop"
                )
                # Update position to the physical limit
                if self.state.movement_state == CoverMovementState.OPENING:
                    self.state.position = 100
                elif self.state.movement_state == CoverMovementState.CLOSING:
                    self.state.position = 0
                self._stop_movement(time.time())

        self._watchdog_timer = self.hass.loop.call_later(max_time, watchdog_triggered)
        LOGGER.debug(f"{self.device.name}: Watchdog timer set for {max_time:.0f}s")

    def _start_movement(
        self,
        movement_state: CoverMovementState,
        start_time: float,
        target_position: int | None = None
    ) -> None:
        """Start a movement operation."""
        # Clear any existing timer first
        self._clear_movement_timer()

        # Update position based on any previous movement
        self._update_position_from_movement(start_time)

        self.state.movement_state = movement_state
        self.state.movement_start_time = start_time
        self._movement_start_time = start_time  # Also store in precise timer field
        self.state.movement_start_position = self.state.position
        if target_position is not None:
            self.state.target_position = target_position

        LOGGER.debug(f"{self.device.name}: Started {movement_state.value} movement from {self.state.position}% at {start_time}")

        # Start watchdog timer to auto-stop if device never reports stop
        self._start_watchdog_timer(movement_state)

    def _stop_movement(self, stop_time: float) -> None:
        """Stop the current movement."""
        # Clear any running timers
        self._clear_movement_timer()
        self._clear_watchdog_timer()

        # For smart positioning, trust the precise timer - don't recalculate position
        if self._smart_positioning_active:
            LOGGER.info(f"{self.device.name}: Smart positioning stop - keeping timer-set position {self.state.position}%")
        else:
            # For manual movements, calculate position based on movement time
            if (self.state.movement_start_time is not None and
                self.state.movement_state != CoverMovementState.STOPPED):

                elapsed_time = stop_time - self.state.movement_start_time

                if self.state.movement_state == CoverMovementState.OPENING:
                    # Calculate position based on opening time
                    full_time = self.timing_config.full_open_time
                    position_change = (elapsed_time / full_time) * 100
                    new_position = min(100, self.state.movement_start_position + position_change)

                elif self.state.movement_state == CoverMovementState.CLOSING:
                    # Calculate position based on closing time
                    full_time = self.timing_config.full_close_time
                    position_change = (elapsed_time / full_time) * 100
                    new_position = max(0, self.state.movement_start_position - position_change)
                else:
                    new_position = self.state.position

                self.state.position = int(new_position)

                LOGGER.info(
                    f"{self.device.name}: Manual movement stopped at {self.state.position}% "
                    f"(elapsed: {elapsed_time:.1f}s)"
                )

        self.state.last_update_time = stop_time
        self.state.movement_state = CoverMovementState.STOPPED
        self.state.movement_start_time = None
        self._movement_start_time = None
        self.state.target_position = None
        self._update_task_running = False  # Stop any update task

        # Clear smart positioning flag when movement stops
        if self._smart_positioning_active:
            LOGGER.info(f"{self.device.name}: Smart positioning completed - returning to normal mode")
            self._smart_positioning_active = False
            self._last_sent_command = None
            self._last_sent_command_time = None

        # Save state
        self._safe_create_task(self._save_state())

    def _update_position_from_movement(self, current_time: float) -> None:
        """Update position based on movement time."""
        if (self.state.movement_start_time is None or
            self.state.movement_state == CoverMovementState.STOPPED):
            return

        elapsed_time = current_time - self.state.movement_start_time
        previous_position = self.state.position

        if self.state.movement_state == CoverMovementState.OPENING:
            # Calculate position based on opening time
            full_time = self.timing_config.full_open_time
            position_change = (elapsed_time / full_time) * 100
            new_position = min(100, self.state.movement_start_position + position_change)

        elif self.state.movement_state == CoverMovementState.CLOSING:
            # Calculate position based on closing time
            full_time = self.timing_config.full_close_time
            position_change = (elapsed_time / full_time) * 100
            new_position = max(0, self.state.movement_start_position - position_change)

        else:
            return

        new_position_int = int(new_position)

        # Only update if position changed significantly (at least 1%)
        if abs(new_position_int - previous_position) >= 1:
            self.state.position = new_position_int
            self.state.last_update_time = current_time

            LOGGER.debug(
                f"{self.device.name}: Position updated to {self.state.position}% "
                f"(elapsed: {elapsed_time:.1f}s)"
            )

    async def _send_stop_and_update_state(self, stop_time: float) -> None:
        """Send stop command to device and update internal state."""
        try:
            LOGGER.info(f"{self.device.name}: Sending stop command to device at position {self.state.position}%")
            await self._send_stop_command()
            self._stop_movement(stop_time)
        except Exception as e:
            LOGGER.error(f"{self.device.name}: Failed to send stop command: {e}")
            # Still update internal state even if command failed
            self._stop_movement(stop_time)

    def _schedule_position_updates(self) -> None:
        """Schedule periodic position updates during movement."""
        if self._update_task_running:
            return  # Already running

        self._update_task_running = True

        async def update_position() -> None:
            try:
                last_reported_position = self.state.position
                while self.state.movement_state != CoverMovementState.STOPPED and self._update_task_running:
                    previous_position = self.state.position
                    self._update_position_from_movement(time.time())

                    # Only report to HA if position changed significantly (more than 1%)
                    if abs(self.state.position - last_reported_position) >= 1.0:
                        last_reported_position = self.state.position
                        # Position change will be handled by the cover entity's property access

                    await asyncio.sleep(2.0)  # Wait 2 seconds between updates (reduced frequency)
            except Exception as e:
                LOGGER.error(f"{self.device.name}: Error in position update task: {e}")
            finally:
                self._update_task_running = False

        # Use the thread-safe task creation method
        self._safe_create_task(update_position())

    async def async_set_cover_position(self, position: int) -> None:
        """Set cover to a specific position using smart timing."""
        LOGGER.info(f"{self.device.name}: Setting position to {position}%")

        # Update current position if we're moving
        current_time = time.time()
        self._update_position_from_movement(current_time)

        # Get the most accurate current position from device status or our internal state
        # DO NOT query HA cover entity to avoid circular reference
        device_position = self._get_position_from_device_status()

        # Prioritize our stored state over device status interpretation
        # Only use device position if we don't have a reliable stored position
        if (device_position is not None and
            isinstance(device_position, (int, float)) and
            hasattr(self, '_device_has_position_dp') and
            self._device_has_position_dp):
            # Device has a real position DP (not just control DP interpretation)
            current_position = device_position
            # Update our internal state if significantly different
            if abs(self.state.position - device_position) > self.timing_config.position_tolerance:
                LOGGER.info(f"{self.device.name}: Updating position from {self.state.position}% to device position {device_position}%")
                self.state.position = device_position
        else:
            # Use our calculated/stored position - it's more reliable
            current_position = self.state.position
            if device_position is not None:
                LOGGER.debug(f"{self.device.name}: Ignoring device position {device_position}% (likely control DP interpretation), using calculated position {current_position}%")
            else:
                LOGGER.info(f"{self.device.name}: No device position available, using calculated position {current_position}%")

        LOGGER.info(f"{self.device.name}: Moving from {current_position}% to {position}%")

        # Check if we're already at the target position
        if abs(current_position - position) <= self.timing_config.position_tolerance:
            LOGGER.info(f"{self.device.name}: Already at target position {position}%")
            return

        # Stop any existing movement first
        if self.state.movement_state != CoverMovementState.STOPPED:
            await self._send_stop_command()
            await asyncio.sleep(0.5)  # Wait for stop command to take effect

        # Update our state with the corrected current position
        self.state.position = current_position
        self.state.target_position = position

        # Mark that we're starting smart positioning
        self._smart_positioning_active = True
        LOGGER.info(f"{self.device.name}: Starting smart positioning mode - target: {position}%")

        # Determine movement direction and send command
        movement_success = False
        if position > current_position:
            # Opening
            movement_success = await self._send_open_command()
            if movement_success:
                movement_time = ((position - current_position) / 100) * self.timing_config.full_open_time
                self._start_movement(CoverMovementState.OPENING, current_time, position)
            else:
                LOGGER.error(f"{self.device.name}: Failed to send open command - aborting movement")
                # Clear smart positioning flag on failure
                self._smart_positioning_active = False
                self._last_sent_command = None
                self._last_sent_command_time = None
                return
        else:
            # Closing
            movement_success = await self._send_close_command()
            if movement_success:
                movement_time = ((current_position - position) / 100) * self.timing_config.full_close_time
                self._start_movement(CoverMovementState.CLOSING, current_time, position)
            else:
                LOGGER.error(f"{self.device.name}: Failed to send close command - aborting movement")
                # Clear smart positioning flag on failure
                self._smart_positioning_active = False
                self._last_sent_command = None
                self._last_sent_command_time = None
                return

        LOGGER.info(f"{self.device.name}: Moving from {current_position}% to {position}% (estimated time: {movement_time:.1f}s)")

        # Check if this is a full open (100%) or full close (0%) operation
        is_full_operation = (position == 100 or position == 0)

        if is_full_operation:
            # For full open/close, don't send stop command - let device reach physical limits
            def position_update_only():
                """Update position without sending stop command for full operations."""
                try:
                    LOGGER.info(f"{self.device.name}: Full {('open' if position == 100 else 'close')} timer triggered - updating position to {position}% without stop command")
                    self.state.position = position  # Set exact target position

                    # Update state without sending stop command
                    async def update_state_only():
                        try:
                            self._stop_movement(time.time())
                            LOGGER.info(f"{self.device.name}: Position updated to {position}% - device will stop naturally at physical limit")
                        except Exception as e:
                            LOGGER.error(f"{self.device.name}: Error updating state for full operation: {e}")

                    # Schedule the state update
                    self._safe_create_task(update_state_only())

                except Exception as e:
                    LOGGER.error(f"{self.device.name}: Error in full operation position update: {e}")

            # Create timer for position update only
            self._movement_timer = self.hass.loop.call_later(movement_time, position_update_only)
            LOGGER.info(f"{self.device.name}: Set position update timer for {movement_time:.1f}s (full {('open' if position == 100 else 'close')} - no stop command)")
        else:
            # Set PRECISE timer to stop at exact position (Homebridge approach)
            def precise_stop():
                """Precise stop callback executed at exact time."""
                try:
                    LOGGER.info(f"{self.device.name}: Precise timer triggered - stopping at target {position}%")
                    self.state.position = position  # Set exact target position

                    # Send stop command and update state
                    async def stop_and_update():
                        try:
                            await self._send_stop_command()
                            self._stop_movement(time.time())
                        except Exception as e:
                            LOGGER.error(f"{self.device.name}: Error in precise stop: {e}")
                            # Still update state even if stop command fails
                            self._stop_movement(time.time())

                    # Schedule the stop command
                    self._safe_create_task(stop_and_update())

                except Exception as e:
                    LOGGER.error(f"{self.device.name}: Error in precise stop callback: {e}")

            # Create the precise timer (like Homebridge setTimeout)
            self._movement_timer = self.hass.loop.call_later(movement_time, precise_stop)
            LOGGER.info(f"{self.device.name}: Set precise timer for {movement_time:.1f}s to stop at {position}%")

    async def _send_open_command(self) -> bool:
        """Send open command to the device."""
        return await self._send_command("open")

    async def _send_close_command(self) -> bool:
        """Send close command to the device."""
        return await self._send_command("close")

    async def _send_stop_command(self) -> bool:
        """Send stop command to the device with retry."""
        # Convert control_dp to string for consistent logging
        control_dp_value = self.control_dp.value if hasattr(self.control_dp, 'value') else str(self.control_dp)

        # Stop commands are critical - try up to 3 times
        for attempt in range(3):
            try:
                LOGGER.info(f"{self.device.name} ({control_dp_value}): Sending stop command (attempt {attempt + 1}/3)")
                success = await self._send_command("stop")
                if success:
                    LOGGER.info(f"{self.device.name} ({control_dp_value}): Stop command confirmed")
                    return True
                else:
                    LOGGER.warning(f"{self.device.name} ({control_dp_value}): Stop command not confirmed (attempt {attempt + 1})")
                    if attempt < 2:  # Don't wait after last attempt
                        await asyncio.sleep(1.0)  # Quick retry for stop
            except Exception as e:
                LOGGER.error(f"{self.device.name} ({control_dp_value}): Stop command failed (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(1.0)

        LOGGER.error(f"{self.device.name} ({control_dp_value}): Stop command failed after 3 attempts")
        return False

    async def _send_command(self, command: str) -> bool:
        """Send command to the device with basic confirmation."""
        try:
            # Convert control_dp to string if it's an enum
            control_dp_value = self.control_dp.value if hasattr(self.control_dp, 'value') else str(self.control_dp)

            LOGGER.info(f"{self.device.name} ({control_dp_value}): Sending command '{command}' to DP '{control_dp_value}'")

            # Track the command for smart positioning confirmation filtering
            if self._smart_positioning_active:
                self._last_sent_command = command
                self._last_sent_command_time = time.time()
                LOGGER.debug(f"{self.device.name} ({control_dp_value}): Tracking smart positioning command '{command}' sent at {self._last_sent_command_time}")

            # Send the command - use the string value for the actual command
            commands = [{"code": control_dp_value, "value": command}]
            await self.hass.async_add_executor_job(
                self.device_manager.send_commands, self.device.id, commands
            )
            LOGGER.debug(f"{self.device.name} ({control_dp_value}): Command '{command}' sent successfully to DP '{control_dp_value}'")

            # For stop commands, wait for confirmation
            if command == "stop":
                confirmation_received = await self._wait_for_command_confirmation(command, 3.0)
                if confirmation_received:
                    LOGGER.info(f"{self.device.name} ({control_dp_value}): Stop command '{command}' confirmed by device")
                    return True
                else:
                    LOGGER.warning(f"{self.device.name} ({control_dp_value}): Stop command '{command}' not confirmed by device")
                    return False

            # For open/close commands, just return success after sending
            return True

        except Exception as e:
            LOGGER.error(f"{self.device.name} ({control_dp_value}): Failed to send command '{command}': {e}")
            return False

    async def _wait_for_command_confirmation(self, command: str, timeout: float) -> bool:
        """Wait for device to confirm command execution."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if we received confirmation for this command
            if command in self._command_confirmations:
                confirm_time = self._command_confirmations[command]

                # Only accept recent confirmations (within last 10 seconds)
                if time.time() - confirm_time < 10.0:
                    self._command_confirmations.pop(command)  # Clean up
                    return True

            # Wait a bit before checking again
            await asyncio.sleep(0.2)

        return False


    def cleanup(self) -> None:
        """Clean up resources and callbacks."""
        # Clear command tracking
        self._command_confirmations.clear()

        # Clear timers
        self._clear_movement_timer()
        self._clear_watchdog_timer()

        # Unregister callbacks
        for unsubscribe in self._unsubscribe_callbacks:
            try:
                unsubscribe()
            except Exception as e:
                LOGGER.error(f"{self.device.name}: Error unregistering callback: {e}")
        self._unsubscribe_callbacks.clear()

    def get_current_position(self) -> int:
        """Get the current estimated position."""
        # Prevent recursive calls
        if self._updating_position:
            return self.state.position

        try:
            self._updating_position = True
            # Update position based on any ongoing movement
            self._update_position_from_movement(time.time())

            # For better UX during movement, return the target position if we just started moving
            # This prevents the UI slider from jumping back to the old position
            if (self.state.target_position is not None and
                self.state.movement_start_time is not None and
                time.time() - self.state.movement_start_time < 2.0):  # Within first 2 seconds
                return self.state.target_position

        finally:
            self._updating_position = False

        return self.state.position

    def _get_current_position_from_hass(self) -> int | None:
        """Get current position from Home Assistant cover entity."""
        try:
            # Get the cover entity state from Home Assistant
            cover_state = self.hass.states.get(self.cover_entity_id)
            if cover_state and cover_state.attributes:
                current_position = cover_state.attributes.get('current_position')
                if current_position is not None:
                    LOGGER.debug(f"{self.device.name}: Got current position from HA: {current_position}%")
                    return int(current_position)
        except Exception as e:
            LOGGER.warning(f"{self.device.name}: Failed to get current position from HA: {e}")
        return None

    def _get_position_from_device_status(self) -> int | None:
        """Get position from device status DPs."""
        try:
            # Map control DP to position DP
            position_dps = {
                XTDPCode.CONTROL: XTDPCode.PERCENT_STATE,
                XTDPCode.CONTROL_2: XTDPCode.PERCENT_STATE_2,
                XTDPCode.CONTROL_3: XTDPCode.PERCENT_STATE_3,
            }

            position_dp = position_dps.get(self.control_dp)
            LOGGER.debug(f"{self.device.name}: Checking device status for position (DP: {position_dp})")

            if position_dp and position_dp in self.device.status:
                device_position = self.device.status[position_dp]
                LOGGER.debug(f"{self.device.name}: Raw device position value: {device_position} (type: {type(device_position)})")
                if isinstance(device_position, (int, float)):
                    device_pos_int = int(device_position)
                    LOGGER.info(f"{self.device.name}: Device reports position: {device_pos_int}%")
                    # Mark that device has a real position DP
                    self._device_has_position_dp = True
                    return device_pos_int
                else:
                    LOGGER.debug(f"{self.device.name}: Device position value is not numeric: {device_position}")

            # Mark that device doesn't have a reliable position DP
            self._device_has_position_dp = False

            # Check control DP for open/close status as fallback - but mark it as unreliable
            control_value = self.device.status.get(self.control_dp)
            LOGGER.debug(f"{self.device.name}: Control DP {self.control_dp} value: {control_value}")

            # Only use control DP interpretation during initial setup, not during operations
            if not hasattr(self, '_initial_setup_complete'):
                if control_value == "open":
                    LOGGER.debug(f"{self.device.name}: Control shows 'open' - assuming 100% (initial setup only)")
                    return 100  # Assume fully open
                elif control_value == "close":
                    LOGGER.debug(f"{self.device.name}: Control shows 'close' - assuming 0% (initial setup only)")
                    return 0   # Assume fully closed
            else:
                LOGGER.debug(f"{self.device.name}: Ignoring control DP interpretation '{control_value}' - using stored position instead")

            LOGGER.debug(f"{self.device.name}: No usable position data in device status")

        except Exception as e:
            LOGGER.warning(f"{self.device.name}: Failed to get position from device status: {e}")
        return None

    def set_timing_config(self, full_open_time: float, full_close_time: float) -> None:
        """Update timing configuration."""
        self.timing_config.full_open_time = max(1.0, full_open_time)
        self.timing_config.full_close_time = max(1.0, full_close_time)

        # Only save if initial setup is complete to avoid overwriting stored state during initialization
        if getattr(self, '_initial_setup_complete', False):
            # Save the updated config
            self.hass.async_create_task(self._save_state())
            LOGGER.info(f"{self.device.name}: Saved updated timing configuration")
        else:
            LOGGER.info(f"{self.device.name}: Timing config updated during initialization - will save after setup complete")

        LOGGER.info(
            f"{self.device.name}: Updated timing - Open: {full_open_time}s, "
            f"Close: {full_close_time}s"
        )

    async def _save_state(self) -> None:
        """Save current state to storage."""
        # Encode the data manually
        data = {
            "state": {
                "position": self.state.position,
                "target_position": self.state.target_position,
                "movement_state": self.state.movement_state.value,
                "last_update_time": self.state.last_update_time,
            },
            "timing_config": {
                "full_open_time": self.timing_config.full_open_time,
                "full_close_time": self.timing_config.full_close_time,
                "position_tolerance": self.timing_config.position_tolerance,
            },
            "positioning_enabled": self.positioning_enabled,
        }
        LOGGER.debug(f"Saving state for {self.device.id}_{self.control_dp}")

        try:
            await self._store.async_save(data)
            LOGGER.debug(f"Successfully saved state for {self.device.id}_{self.control_dp}")
        except Exception as e:
            LOGGER.error(f"Failed to save state for {self.device.id}_{self.control_dp}: {e}")

    async def async_cleanup(self) -> None:
        """Clean up the controller."""
        # Save final state
        await self._save_state()

        # Remove callbacks
        for callback in self._unsubscribe_callbacks:
            callback()
        self._unsubscribe_callbacks.clear()


class SmartCoverManager:
    """Manager for all smart cover controllers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the smart cover manager."""
        self.hass = hass
        self.controllers: dict[str, SmartCoverController] = {}

    def register_cover(
        self,
        device: XTDevice,
        device_manager,  # MultiManager type
        cover_entity_id: str,
        control_dp: str,
        timing_config: CoverTimingConfig | None = None,
    ) -> SmartCoverController:
        """Register a cover for smart control."""
        controller_key = f"{device.id}_{control_dp}"

        if controller_key in self.controllers:
            return self.controllers[controller_key]

        controller = SmartCoverController(
            self.hass, device, device_manager, cover_entity_id, control_dp, timing_config
        )

        self.controllers[controller_key] = controller

        # Initialize the controller asynchronously - don't wait here to avoid blocking
        self.hass.async_create_task(controller.async_setup())

        LOGGER.info(f"Registered smart cover controller for {device.name} ({control_dp})")

        return controller

    async def get_or_create_controller(
        self,
        device,
        device_manager,
        cover_entity_id: str,
        control_dp: str,
        timing_config: CoverTimingConfig | None = None
    ) -> SmartCoverController:
        """Get an existing controller or create and fully initialize a new one."""
        controller_key = f"{device.id}_{control_dp}"

        if controller_key in self.controllers:
            return self.controllers[controller_key]

        controller = SmartCoverController(
            self.hass, device, device_manager, cover_entity_id, control_dp, timing_config
        )

        self.controllers[controller_key] = controller

        # Initialize the controller and wait for completion
        await controller.async_setup()

        LOGGER.info(f"Registered and initialized smart cover controller for {device.name} ({control_dp})")

        return controller

    def get_controller(self, device_id: str, control_dp: str) -> SmartCoverController | None:
        """Get a controller for a specific device and control DP."""
        controller_key = f"{device_id}_{control_dp}"
        return self.controllers.get(controller_key)

    async def async_cleanup(self) -> None:
        """Clean up all controllers."""
        for controller in self.controllers.values():
            await controller.async_cleanup()
        self.controllers.clear()
