<img src="icon.png" alt="Xplora SoC" width="96" align="left" />

# Xplora SoC — Home Assistant integration

A custom integration that supervises Xplora® watches via **passive** polling of
the cloud API. It reads each watch's last self-reported `WatchLastLocate`
snapshot — it never sends an active locate/track command — so it stays well
clear of the rate-limiting/IP-ban that retired the original `xplora_watch`
integration. See [`../../FINDINGS.md`](../../FINDINGS.md) for the full story.

## Entities (per watch)

| Entity | Platform | Source field |
| ------ | -------- | ------------ |
| Battery | sensor (%) | `battery` |
| Charging | binary_sensor | `isCharging` |
| Online | binary_sensor (connectivity) | `watches.onlineStatus` |
| Steps | sensor | `step` |
| Distance | sensor (m) | `distance` |
| In safe zone | binary_sensor | `isInSafeZone` |
| Safe zone | sensor | `safeZoneLabel` |
| Locate type | sensor | `locateType` (GPS/WIFI/LBS) |
| Location reported | sensor (timestamp) | `tm` |
| Battery reported | sensor (timestamp) | `batteryTm` |
| Location | device_tracker | `lat`/`lng`/`rad` |

The location is **last-known**, not a live fix (a live fix would need an active
locate, which we deliberately avoid). It can be 15–35 min stale.

## Install

**HACS (custom repository):** add `https://gitlab.com/erik.osvaldsson/ha-xplora`
as an Integration repository, install, restart HA.

**Manual:** copy `custom_components/xplora_soc/` into your HA `config/custom_components/`
and restart.

Then **Settings → Devices & Services → Add Integration → Xplora SoC**, and sign
in with the same account you use in the Xplora app (email *or* phone + country
code). Scan interval defaults to 90 min and is adjustable in the integration's
options (floor 30 min — keep it slow on purpose).

## Notes

- Auth uses the current Xplora **V2** app key/host (the library's bundled key is
  dead). If logins start failing with `invalid_auth`, the key was likely
  rotated — re-extract per [`../../capture/CAPTURE.md`](../../capture/CAPTURE.md)
  and update `_v2.py`.
- Unofficial, reverse-engineered client for personal use with your own account.
