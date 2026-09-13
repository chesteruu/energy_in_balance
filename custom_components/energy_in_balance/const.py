"""Constants for the Energy in Balance integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "energy_in_balance"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
SLOW_SCAN_INTERVAL = timedelta(minutes=15)
REQUEST_TIMEOUT = 20

CONF_SCAN_INTERVAL = "scan_interval"

API_BASE = "https://api.checkwatt.se"
API_ORIGIN = "https://energyinbalance.se"
API_AUDIENCE = "eib"

INSTALL_SOC = "SoC"
INSTALL_SOLAR = "Solar"
INSTALL_CHARGE = "Charging"
INSTALL_DISCHARGE = "Discharging"
INSTALL_IMPORT = "EDIEL_E17"
INSTALL_EXPORT = "EDIEL_E18"

MEASUREMENT_TYPES = (
    "SolarProductionPower",
    "BatteryChargePower",
    "BatteryDischargePower",
    "BoughtPower",
    "SoldPower",
    "Soc",
)
