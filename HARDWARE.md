# Hardware Recommendations

This document describes generic hardware guidelines for running the Sustainable Home Infrastructure stack.

It deliberately avoids documenting the exact hardware, addresses or physical topology of a specific home.

## Server

A small business-class mini or micro PC is a practical platform.

Recommended characteristics:

- Intel or AMD x86-64 CPU
- at least 4 physical CPU cores
- 8 GB RAM minimum
- 16 GB RAM preferred
- 256 GB or larger SSD/NVMe for operating system and applications
- Gigabit Ethernet
- low idle power consumption
- quiet cooling
- support for additional storage

Intel integrated graphics are useful when Frigate hardware acceleration is required.

## Memory

For a basic installation consisting of Home Assistant, Mosquitto, InfluxDB and Python reporting, 8 GB can be sufficient.

When running CCTV workloads on the same machine, 16 GB provides substantially more headroom.

ECC memory is not required for this type of home deployment. Reliable backups, storage monitoring and clean shutdown protection are more important.

## System Storage

Use SSD or NVMe storage for Ubuntu, Docker, Home Assistant configuration, InfluxDB, application configuration, Python reporting and container metadata.

A capacity of approximately 256 GB is a reasonable starting point. Keep significant free space available for database growth and operating-system maintenance.

## CCTV Storage

Video recordings should ideally be stored separately from the operating-system volume.

Storage requirements depend on the number of cameras, codec, bitrate, resolution, frame rate, recording mode and retention period.

Do not size CCTV storage using theoretical maximum values alone. Measure actual storage consumption over several days and extrapolate from real recordings.

## Cameras

Recommended characteristics:

- local RTSP support
- ONVIF support when available
- H.264 or H.265
- PoE where practical
- local operation without mandatory cloud services
- configurable main and secondary streams

Public infrastructure documentation should use generic names such as `camera_1` and `camera_2`.

## Hardware Video Acceleration

Intel integrated graphics can provide efficient video decoding.

On Linux, inspect available devices with:

```bash
ls -l /dev/dri
```

A typical render device is:

```text
/dev/dri/renderD128
```

## Energy Monitoring

A useful monitoring architecture combines whole-house measurement with selected appliance measurements.

This allows calculation of:

```text
unmonitored load = whole-house load - sum(individually monitored loads)
```

Useful measurements include instantaneous power, cumulative energy, voltage, current, power factor, grid import, grid export and solar production.

## Plug-Level Energy Meters

Smart energy-monitoring plugs are suitable for appliances that use standard sockets.

Prefer devices that support local protocols such as MQTT, local HTTP APIs or other documented local integrations. Avoid requiring external cloud services when a local alternative is available.

## Whole-House Measurement

Whole-house monitoring normally requires DIN-rail energy meters, current-transformer clamp meters or compatible local energy meters.

Installation inside a mains distribution board should be performed by a qualified electrician.

## Solar Monitoring

A useful solar monitoring system should eventually expose solar generation, house consumption, grid import and grid export.

These values make it possible to calculate solar self-consumption, grid dependency, exported surplus, effective electricity cost, EV charging source and potential battery utilization.

Long-term measurements are more useful for battery sizing than isolated daily measurements.

## Network

Use wired Ethernet for infrastructure components when practical, especially the home server, PoE cameras, network switches and fixed infrastructure devices.

IoT devices may reside on a separate network provided they can reach the services they require.

## Switches

For camera installations, a PoE switch reduces cabling requirements.

Select sufficient PoE ports, total PoE power budget and Gigabit uplink capacity, and keep spare capacity for future devices.

## UPS

A UPS is recommended for the home server, core network switch, main router and storage devices.

Its primary purpose is clean shutdown and protection from short interruptions.

## SMART Monitoring

Storage health should be monitored using SMART.

Useful parameters include device temperature, media errors, reallocated sectors when applicable, NVMe percentage used, available spare and critical warnings.

Typical tools include `smartctl` and `nvme-cli`.

## Temperature Monitoring

Important values include CPU temperature, storage temperature, sustained load and thermal throttling.

## Server Performance Monitoring

Useful operating metrics include CPU utilization, load average, CPU iowait, RAM usage, swap usage, disk utilization, disk I/O, network throughput, container CPU usage, container memory usage, storage temperature and uptime.

These measurements can later be stored in a dedicated time-series bucket.

## Server Electricity Consumption

The server itself should be included in energy measurements.

A plug-level meter can measure instantaneous watts, daily kWh, monthly kWh and annual energy consumption.

## Reporting Workload

The Python reporting service has modest hardware requirements. Its main components are Flask, Gunicorn, APScheduler, pandas, matplotlib and the InfluxDB client.

Historical queries and static chart generation typically create short CPU bursts rather than continuous heavy utilization. Report artifacts can be kept on local storage with automated retention, while artifacts explicitly queued for publication should be protected from automatic cleanup.

## Storage Architecture

A useful long-term storage layout is:

```text
System SSD/NVMe
├── operating system
├── Docker
├── Home Assistant
├── InfluxDB
└── reporting application

Separate storage
├── CCTV recordings
└── future local file storage
```

## Reliability Priorities

Prioritize reliable storage, adequate free disk space, health monitoring, backups, UPS protection, low operating temperature and simple recovery procedures.

Complex enterprise redundancy is usually unnecessary for this workload.

## Power Efficiency

Prefer low idle consumption, efficient CPUs, hardware video acceleration, SSD storage for system workloads, sensible report-generation intervals and containers that remain idle when no work is required.

Actual wall-power measurements should be preferred over manufacturer TDP figures.

## Expansion Strategy

The initial server can host Home Assistant, Mosquitto, InfluxDB, Python reporting and Frigate.

If CCTV workloads or storage requirements grow substantially, Frigate can later move to a dedicated machine while the original server remains responsible for automation, telemetry and reporting.
