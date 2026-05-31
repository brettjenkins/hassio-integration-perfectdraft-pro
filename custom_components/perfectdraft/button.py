"""Button entities for PerfectDraft."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, keg_changed_signal
from .coordinator import PerfectDraftDataUpdateCoordinator
from .sensor import _device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PerfectDraft button entities."""
    coordinator: PerfectDraftDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PerfectDraftKegResetButton(coordinator)])


class PerfectDraftKegResetButton(
    CoordinatorEntity[PerfectDraftDataUpdateCoordinator], ButtonEntity
):
    """Button that marks the current keg as freshly changed as of now."""

    _attr_has_entity_name = True
    _attr_translation_key = "mark_keg_changed"
    _attr_icon = "mdi:keg"

    def __init__(
        self,
        coordinator: PerfectDraftDataUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self._machine_id = (coordinator.data or {}).get("_machine_id", "unknown")
        self._attr_unique_id = f"{self._machine_id}_mark_keg_changed"
        self._attr_device_info = _device_info(coordinator)

    async def async_press(self) -> None:
        """Tell the freshness sensor to set the keg insertion date to now."""
        async_dispatcher_send(self.hass, keg_changed_signal(self._machine_id))
