<img src="custom_components/myxplora/brand/icon.png" alt="myXplora" width="88" align="left" />

# myXplora — Home Assistant integration

A custom [Home Assistant](https://www.home-assistant.io/) integration that
supervises **Xplora® kids' watches** — battery, charging, online status,
steps, and last-known location — from the Xplora cloud, using a deliberately
**passive, low-frequency** polling strategy that stays clear of the rate
limiting that retired the original community integration.

[![hacs](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz/)
[![HA min](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![license](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

> **Unofficial.** This is a reverse-engineered client for the Xplora cloud API,
> for personal use with your own account and watches. It is not affiliated with,
> endorsed by, or supported by Xplora®. See [Disclaimer](#disclaimer).

---

## Why this exists

The well-known [`Ludy87/xplora_watch`](https://github.com/Ludy87/xplora_watch)
integration was **archived (read-only) in November 2025** — the maintainer cited
Xplora IP-banning the polling clients. The stock behaviour polled frequently and
sent **active locate commands** (a GPS ping to the watch) on every cycle, which
is the loudest, most flaggable, most battery-draining pattern possible.

myXplora takes the opposite approach:

- **Passive reads only.** It reads each watch's last self-reported snapshot
  (`WatchLastLocate`) — it **never** sends an active locate/track command to the
  watch. Location is last-known (typically 15–35 min stale), not a live fix.
- **Slow on purpose.** Default scan interval is **90 minutes** (floor 30 min).
  Battery state-of-charge does not move fast enough to need minute-level polling.
- **Minimal footprint.** One `watches` query plus one `WatchLastLocate` per
  watch per cycle, login amortised — no per-getter fan-out, no active locates.

This keeps the request volume and device impact low, which is the whole point.

## Entities (per watch)

Each watch becomes one HA **device** named `<watch> Watch <model>` (e.g.
`Alex Watch XGO3`), so entity ids include the model — e.g.
`binary_sensor.alex_watch_xgo3_charging`. The device page shows manufacturer,
model, and firmware version.

| Entity | Platform | Source field |
| ------ | -------- | ------------ |
| Battery | sensor (%) | `battery` |
| Charging | binary_sensor | `isCharging` |
| Online | binary_sensor (connectivity) | `onlineStatus` |
| Steps | sensor | `step` |
| Distance | sensor (m) | `distance` |
| In safe zone | binary_sensor | `isInSafeZone` |
| Safe zone | sensor | `safeZoneLabel` |
| Locate type | sensor | `locateType` (GPS/WIFI/LBS) |
| Location reported | sensor (timestamp) | `tm` |
| Battery reported | sensor (timestamp) | `batteryTm` |
| Location | device_tracker | `lat` / `lng` / `rad` |

## Installation

You need **Home Assistant 2024.12.0 or newer**. Pick one of the methods below,
then continue to [Configuration](#configuration).

### Option A — GPM (recommended)

[GPM (GIT Package Manager)](https://github.com/tomasbedrich/gpm) installs custom
integrations from any git repository by HTTP URL — no GitHub/HACS account
required.

1. **Install GPM** (once), then restart Home Assistant:
   ```bash
   wget -O - https://raw.githubusercontent.com/tomasbedrich/gpm/refs/heads/main/install/install.sh | bash -
   ```
2. Go to **Settings → Devices & Services → Add Integration → GPM**.
3. When prompted, choose **Integration** and enter the repository URL:
   ```
   https://gitlab.com/erik.osvaldsson/ha-xplora
   ```
4. GPM clones the latest tagged release and links `custom_components/myxplora`
   into your config. **Restart Home Assistant.**

GPM adds an *update* entity, so you'll be notified when a new tag is published
and can update from the UI.

### Option B — HACS (custom repository)

HACS works against the **GitHub** mirror.

1. In HACS, open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/erikosvaldsson/ha-xplora` with category
   **Integration**.
3. Install **myXplora** from HACS, then **restart Home Assistant**.

### Option C — Manual

1. Copy the `custom_components/myxplora/` folder from this repo into your Home
   Assistant `config/custom_components/` directory.
2. **Restart Home Assistant.**

## Configuration

1. Go to **Settings → Devices & Services → Add Integration → myXplora**.
2. Sign in with the **same account you use in the Xplora app** — either
   **email + password** *or* **phone (with country code) + password**. If both
   are provided, email is used.
3. All watches on the account are discovered automatically; each becomes its own
   device with the entities listed above.

### Options

Open the integration's **Configure** dialog to adjust the **scan interval**.
It defaults to **90 minutes** and has a **30-minute floor** — keep it slow on
purpose to stay under the rate-limit radar.

## Notes & caveats

- **Unofficial, reverse-engineered client.** Behaviour can change without notice
  if Xplora alters their cloud API.
- **App key rotation.** Auth uses the current Xplora **V2** app key/host, since
  the key bundled in the upstream `pyxplora-api` library is dead. If logins
  suddenly start failing with `invalid_auth`, Xplora most likely rotated the
  app key and it will need to be re-extracted and updated in
  [`custom_components/myxplora/_v2.py`](custom_components/myxplora/_v2.py).
- **Location is last-known, not live.** A live fix would require an active
  locate command, which this integration deliberately never sends.
- **Personal use.** Use with your own account and your own watches. Do not scale
  this, redistribute keys, or hammer the API.

## Development

This repo also contains `src/xplora_eval/` — a small [uv](https://docs.astral.sh/uv/)
CLI harness used to evaluate the API and validate the passive/slow-poll approach
before the integration was built (`uv sync`, then `uv run xplora-eval`). It is
developer tooling and is not required to use the integration.

## Disclaimer

Xplora® is a registered trademark of its respective owner. This project is an
independent, unofficial integration and is **not affiliated with, endorsed by,
or supported by Xplora**. It interacts with an undocumented cloud API that is
subject to change or access restrictions at any time. Use at your own risk and
within Xplora's terms of service. The author accepts no liability for banned
accounts, blocked IPs, or any other consequence of use.

## License

[GPL-3.0](LICENSE) © Erik Osvaldsson
