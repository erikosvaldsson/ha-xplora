# Changelog

All notable changes to the **myXplora** Home Assistant integration are
documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-06

### Changed
- **Renamed integration: domain `xplora_soc` → `myxplora`, name "Xplora SoC" →
  "myXplora".** The integration outgrew its battery-only "SoC" name — it now
  exposes location, activity, device info, and connectivity. The new domain and
  name avoid a collision with the community `xplora_watch` integration, so both
  can be installed side by side.
- Renamed the internal research harness package `xplora_soc_eval` → `xplora_eval`
  (CLI `xplora-soc-eval` → `xplora-eval`).

### Breaking
- The domain change is **not auto-migrated**: an existing `xplora_soc` config
  entry will fail to load after upgrading. Delete the old entry and re-add the
  integration as **myXplora** (re-entering your credentials).

## [0.1.1] - 2026-06-05

### Added
- Device now reports **model** (`groupName`, e.g. `XGO3`), **manufacturer**
  (`brand`), and **firmware** (`osVersion`) — shown on the HA device page. All
  read from the same passive `watches` query (no extra requests).

### Changed
- The watch **model is included in the device name** (e.g. `Alex Watch XGO3`),
  so it flows into entity ids — e.g. `binary_sensor.alex_watch_xgo3_charging`.
  This changes entity ids versus 0.1.0 (no installs yet, so no migration needed).

## [0.1.0] - 2026-06-05

Initial release.

### Added
- Home Assistant integration (`custom_components/myxplora`) — config-flow,
  cloud-polling, installable via HACS or GPM.
- Sign in with the Xplora account (email **or** phone + country code).
- One HA device per watch, with entities sourced from a single **passive**
  `WatchLastLocate` read:
  - **Battery** (%), **Charging**, **Online** (connectivity)
  - **Steps**, **Distance**
  - **In safe zone**, **Safe zone** label
  - **Locate type** (GPS/WiFi/cell), **Location reported** / **Battery reported**
    timestamps
  - **Location** device_tracker (last-known position; not a live fix)
- Deliberately slow polling — default 90 min, adjustable in options (floor
  30 min) — to stay clear of Xplora's rate-limiting/IP ban.
- Targets the current Xplora **V2** app key/host; **never** sends an active
  locate/track command.
- Token reuse with a single self-healing re-login on expiry; capped login
  retries to protect the login surface.

### Notes
- Unofficial, reverse-engineered client for personal use with your own account.
- If logins start failing (`invalid_auth`), the V2 app key was likely rotated —
  re-extract it and update `custom_components/myxplora/_v2.py`.

[Unreleased]: https://gitlab.com/erik.osvaldsson/ha-xplora/-/compare/v0.2.0...main
[0.2.0]: https://gitlab.com/erik.osvaldsson/ha-xplora/-/compare/v0.1.1...v0.2.0
[0.1.1]: https://gitlab.com/erik.osvaldsson/ha-xplora/-/compare/v0.1.0...v0.1.1
[0.1.0]: https://gitlab.com/erik.osvaldsson/ha-xplora/-/tags/v0.1.0
