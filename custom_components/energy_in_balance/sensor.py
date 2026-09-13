"""Sensors for Energy in Balance."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SiteSnapshot
from .const import DOMAIN
from .coordinator import EnergyInBalanceCoordinator


@dataclass(frozen=True, kw_only=True)
class EnergyInBalanceSensorEntityDescription(SensorEntityDescription):
    """Describe a snapshot-backed sensor."""

    value_fn: Callable[[SiteSnapshot], float | str | None]


SENSORS: tuple[EnergyInBalanceSensorEntityDescription, ...] = (
    EnergyInBalanceSensorEntityDescription(
        key="solar_power",
        translation_key="solar_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:solar-power",
        value_fn=lambda data: data.solar_power_w,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:battery-charging",
        value_fn=lambda data: data.battery_power_w,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="battery_charge_power",
        translation_key="battery_charge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:battery-plus",
        value_fn=lambda data: data.battery_charge_power_w,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="battery_discharge_power",
        translation_key="battery_discharge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:battery-minus",
        value_fn=lambda data: data.battery_discharge_power_w,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.battery_soc,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:transmission-tower",
        value_fn=lambda data: data.grid_power_w,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="grid_import_power",
        translation_key="grid_import_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:transmission-tower-import",
        value_fn=lambda data: data.grid_import_power_w,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="grid_export_power",
        translation_key="grid_export_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:transmission-tower-export",
        value_fn=lambda data: data.grid_export_power_w,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="house_power",
        translation_key="house_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:home-lightning-bolt",
        value_fn=lambda data: data.house_power_w,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="solar_energy",
        translation_key="solar_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.solar_energy_kwh,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="battery_charge_energy",
        translation_key="battery_charge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.battery_charge_energy_kwh,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="battery_discharge_energy",
        translation_key="battery_discharge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.battery_discharge_energy_kwh,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="grid_import_energy",
        translation_key="grid_import_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.grid_import_energy_kwh,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="grid_export_energy",
        translation_key="grid_export_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.grid_export_energy_kwh,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="spot_price",
        translation_key="spot_price",
        native_unit_of_measurement="SEK/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        icon="mdi:cash",
        value_fn=lambda data: data.spot_price,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="fcr_revenue_today",
        translation_key="fcr_revenue_today",
        native_unit_of_measurement="SEK",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        icon="mdi:sine-wave",
        value_fn=lambda data: data.fcr_revenue_today,
    ),
    EnergyInBalanceSensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.battery_capacity_kwh,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy in Balance sensors."""
    _ = hass
    coordinator = entry.runtime_data
    async_add_entities(
        EnergyInBalanceSensor(coordinator, description) for description in SENSORS
    )


class EnergyInBalanceSensor(
    CoordinatorEntity[EnergyInBalanceCoordinator], SensorEntity
):
    """A snapshot-backed Energy in Balance sensor."""

    entity_description: EnergyInBalanceSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EnergyInBalanceCoordinator,
        description: EnergyInBalanceSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        data = coordinator.data
        self._attr_unique_id = f"{data.site_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(data.site_id))},
            name=data.display_name,
            manufacturer=data.inverter_brand or "Checkwatt",
            model=data.inverter_model or "Energy in Balance",
            serial_number=data.serial,
        )

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        if self.entity_description.key != "battery_soc":
            return None
        data = self.coordinator.data
        return {
            "price_zone": data.price_zone,
            "operation_preference": data.operation_preference,
            "fcr_services": data.fcr_services,
            "last_seen_inverter": data.last_seen_inverter,
            "last_seen_logger": data.last_seen_logger,
            "retailer": data.retailer,
            "dso": data.dso,
            "online": data.online,
            "fcr_revenue_week": data.fcr_revenue_week,
            "inverter_power_w": data.inverter_power_w,
        }
