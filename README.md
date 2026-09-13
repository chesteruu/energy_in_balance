# Energy in Balance for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration for [Energy in Balance](https://energyinbalance.se/dashboard) (Checkwatt). It logs in with your portal email and password, then creates sensors for live solar, battery, grid, and house power.

There is no public API. The client uses the same `api.checkwatt.se` calls the dashboard uses: HTTP Basic login, then a short-lived JWT. This is unofficial and not affiliated with Checkwatt or Energy in Balance. Those endpoints can change without notice.

## Sensors

| Sensor | Unit | Notes |
| --- | --- | --- |
| Solar power | W | Live PV production |
| Battery power | W | Signed: negative while charging |
| Battery charge / discharge power | W | Split of the signed battery value |
| Battery state of charge | % | Also carries site attributes (FCR, last seen, DSO) |
| Grid power | W | Signed: negative while exporting |
| Grid import / export power | W | Split of the signed grid value |
| House power | W | `solar + battery + grid` using EIB signs |
| Solar / battery / grid energy | kWh | Lifetime totals for the Energy dashboard |
| Battery charge / discharge energy | kWh | Lifetime totals |
| Spot price | SEK/kWh | Current price-zone interval |
| FCR-D revenue today | SEK | Provisional portal estimate |

Live power refreshes every 60 seconds. Energy, spot price, and revenue refresh about every 15 minutes.

## Install with HACS

1. In Home Assistant open **HACS**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/chesteruu/energy_in_balance` as category **Integration**.
4. Find **Energy in Balance**, download it, and restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for **Energy in Balance**.
6. Sign in with the same email and password you use at [energyinbalance.se](https://energyinbalance.se).

Home Assistant stores those credentials so it can refresh the JWT. If that is not acceptable, do not add the integration.

### Manual install

```bash
cd /config
mkdir -p custom_components
git clone https://github.com/chesteruu/energy_in_balance.git /tmp/energy_in_balance
cp -R /tmp/energy_in_balance/custom_components/energy_in_balance custom_components/
```

Restart Home Assistant, then add the integration as above.

HACS copies `custom_components/energy_in_balance/` into your config automatically.

## Energy dashboard

After the first energy totals arrive:

- Grid consumption → **Grid import energy**
- Return to grid → **Grid export energy**
- Solar production → **Solar energy**
- Battery in / out → **Battery charge energy** / **Battery discharge energy**

**Spot price** is the raw area price. It does not include retailer markup or VAT handling.

## Options

**Configure** the integration to change the poll interval (30–600 seconds, default 60). Keep it conservative; this is an unofficial portal API.

## Local API probe

Exercise the client without Home Assistant:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# edit .env with your Energy in Balance email and password
set -a && source .env && set +a
python scripts/probe.py
```

`.env` is gitignored. Do not commit it.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Related

[faanskit/ha-checkwatt](https://github.com/faanskit/ha-checkwatt) is an existing community integration for the same portal, focused more on FCR income. This repository maps the current dashboard live-power endpoints (`/ems/energyflow`, `/SiteMeasurements`, yearly energy series) onto Home Assistant sensors.

## License

MIT. See [LICENSE](LICENSE).
