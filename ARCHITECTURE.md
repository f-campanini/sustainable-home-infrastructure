# Architecture

## Purpose

This document describes the architecture of the Sustainable Home Infrastructure project.

It focuses on:

- system boundaries;
- major components;
- data flows;
- deployment responsibilities;
- security boundaries;
- architectural principles.

Implementation instructions belong in `README.md`.
Testing and troubleshooting procedures belong in `TESTING.md`.
Hardware guidance belongs in `HARDWARE.md`.
Instructions for AI coding agents belong in `AGENTS.md`.

---

## Architectural Principles

The project follows these principles:

1. **Infrastructure as code**
   Server configuration and deployment are managed through Ansible.

2. **Local-first operation**
   Core home services should continue to function without mandatory external cloud services.

3. **Open-source software**
   Infrastructure components should be open source unless explicitly documented otherwise.

4. **Minimal Internet exposure**
   Home services are not exposed directly to the public Internet.

5. **Separation of configuration and secrets**
   Public/reusable configuration is kept in the repository. Credentials and private infrastructure values are kept outside Git or protected with Ansible Vault.

6. **Small, understandable components**
   Prefer simple services with clear responsibilities over unnecessary architectural complexity.

7. **Observable data flows**
   Energy and infrastructure data should be traceable from the source device through collection, storage and reporting.

---

## High-Level Architecture

```text
                         CONTROL MACHINE
                      Linux workstation/laptop
                               |
                               | Ansible over SSH
                               v
+-------------------------------------------------------------------+
|                         HOME SERVER                               |
|                                                                   |
|  Ubuntu Server                                                    |
|                                                                   |
|  +----------------------- Main Docker stack -------------------+   |
|  |                                                            |   |
|  |  +------------+       +----------------+                   |   |
|  |  | Mosquitto  |<----->| Home Assistant |                   |   |
|  |  +------------+       +-------+--------+                   |   |
|  |                               |                            |   |
|  |                               v                            |   |
|  |                        +-------------+                     |   |
|  |                        |  InfluxDB   |                     |   |
|  |                        +------+------+                     |   |
|  |                               |                            |   |
|  |                               v                            |   |
|  |                        +-------------+                     |   |
|  |                        |  Reporting  |                     |   |
|  |                        |   service   |                     |   |
|  |                        +-------------+                     |   |
|  +------------------------------------------------------------+   |
|                                                                   |
|  +---------------- Separate CCTV stack -----------------------+   |
|  |                                                            |   |
|  |                        +-------------+                     |   |
|  |                        |   Frigate   |                     |   |
|  |                        +-------------+                     |   |
|  |                                                            |   |
|  +------------------------------------------------------------+   |
|                                                                   |
+-------------------------------------------------------------------+
          ^                         ^
          |                         |
          | MQTT / local APIs       | RTSP / local network
          |                         |
+----------------------+     +----------------------+
| IoT / energy devices |     |   CCTV cameras       |
|                      |     |                      |
| Tasmota and other    |     | local RTSP streams   |
| local devices        |     |                      |
+----------------------+     +----------------------+
```

---

## Repository Structure

The repository is organized around deployment automation, reporting code and documentation.
This is an abbreviated ownership view; README.md lists the individual templates
and reporting modules and records the last verified deployment state.

```text
home-infrastructure/
├── ansible/
│   ├── ansible.cfg
│   ├── bootstrap.yml
│   ├── frigate.yml
│   ├── frigate.vault.example.yml
│   ├── inventory/
│   │   ├── hosts.yml
│   │   └── hosts.example.yml
│   ├── tasks/
│   │   └── frigate-preflight.yml
│   ├── templates/
│   │   └── ... (service and host templates)
│   ├── vars/
│   │   ├── frigate.yml
│   │   └── reporting.yml
│   ├── secrets.yml
│   └── site.yml
├── reporting/
│   ├── templates/
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── entrypoint.sh
│   ├── app.py
│   ├── influx.py
│   ├── artifact.py
│   ├── audit.py
│   ├── charts.py
│   ├── query_service.py
│   ├── scheduled_reports.py
│   └── scheduler.py
├── README.md
├── ARCHITECTURE.md
├── TESTING.md
├── HARDWARE.md
├── AGENTS.md
├── LICENSE
└── .gitignore
```

Some files shown above may be intentionally excluded from Git because they contain private deployment information.

---

## Deployment Architecture

### Control Machine

A Linux workstation or laptop acts as the Ansible control machine.

Its responsibilities are:

- storing the checked-out Git repository;
- running Ansible;
- connecting to the home server over SSH;
- rendering configuration templates;
- deploying and updating services;
- performing administrative validation.

The control machine is not part of the continuously running home-service stack.

### Home Server

The home server runs Ubuntu Server and hosts the local services.

Docker is used as the application runtime.

Ansible is the authoritative mechanism for configuring the server and deploying the managed services.

Manual server-side configuration should not become a second source of truth.

---

## Main Application Stack

The main Docker stack contains the core automation, telemetry and reporting services.

### Mosquitto

Mosquitto is the local MQTT broker.

Its responsibilities are:

- receiving MQTT messages from local devices;
- providing the MQTT transport used by Home Assistant;
- keeping MQTT communication inside the local network where possible.

Typical sources include energy-monitoring devices running firmware such as Tasmota.

### Home Assistant

Home Assistant is the central integration layer for home devices.

Its responsibilities include:

- integrating local devices;
- consuming MQTT telemetry;
- exposing device entities;
- normalizing useful measurements;
- forwarding historical measurements to InfluxDB.

Home Assistant should prefer local integrations and local protocols where practical.

### InfluxDB

InfluxDB stores time-series measurements.

Its primary data source is Home Assistant.

Typical measurements include:

- power;
- energy;
- voltage;
- current;
- power factor;
- other home or infrastructure telemetry.

The current primary organization and bucket are:

```text
Organization: home
Bucket: homeassistant
```

InfluxDB is the historical data source for the reporting service.

### Reporting Service

The reporting service is a Python application running in Docker.

Its responsibilities include:

- querying InfluxDB;
- validating retrieved measurements;
- processing historical data;
- generating reports and charts;
- serving a local web interface;
- performing scheduled report-generation jobs.

The service uses a Flask/Gunicorn web application and APScheduler for periodic work.

Generated output is stored outside the container so it survives container replacement.

The reporting service must treat missing, malformed or incomplete telemetry as an expected condition and return useful diagnostic information rather than opaque HTTP errors where possible.

---

## Energy Data Flow

The main telemetry path is:

```text
Energy device
     |
     | MQTT / local integration
     v
Mosquitto
     |
     v
Home Assistant
     |
     | historical telemetry
     v
InfluxDB
     |
     | queries
     v
Python reporting service
     |
     v
Reports / charts / local web interface
```

This separation gives each component a clear responsibility:

- devices measure;
- MQTT transports messages;
- Home Assistant integrates and normalizes;
- InfluxDB stores history;
- the reporting service analyzes and presents data.

---

## Energy Monitoring Model

The architecture supports both:

- individual appliance measurements;
- whole-house measurements.

When both are available, the system can derive values such as:

```text
unmonitored load =
    whole-house consumption
    - sum(individually monitored loads)
```

The longer-term model should support measurements needed to understand:

- household consumption;
- solar production;
- grid import;
- grid export;
- solar self-consumption;
- exported surplus;
- EV charging;
- effective electricity cost;
- potential battery utilization.

Estimated values must remain distinguishable from physically measured values.

---

## CCTV Architecture

Frigate provides the local CCTV/NVR function.

It is architecturally separate from the main Home Assistant/MQTT/InfluxDB/reporting
stack. The repository manages it through `ansible/frigate.yml`, imported by
`site.yml`, in its own Docker Compose project named `frigate`.

Ansible owns `/srv/frigate/compose.yml` and `/srv/frigate/config/config.yml`.
The complete private camera configuration is sourced from the ignored Ansible
Vault file `ansible/frigate.vault.yml`. Runtime defaults remain public and generic.
The configuration directory also contains the persistent database and authentication
state; recordings reside in `/srv/frigate/media`. Adopting a running installation
preserves both paths and its private camera identifiers.

MQTT integration is optional and is controlled by the private Frigate configuration.
The deployment does not automatically connect Frigate to the telemetry pipeline.

```text
CCTV camera
     |
     | local RTSP stream
     v
  Frigate
     |
     +--> live view
     |
     +--> detection
     |
     +--> recordings
```

Camera streams must remain local and must not be exposed directly to the Internet.

Public repository content must not contain:

- real camera credentials;
- private camera addresses;
- unnecessary hardware identifiers;
- precise physical locations.

Generic camera identifiers should be used in public configuration and documentation.

Where supported, hardware video acceleration should be used to reduce CPU load.

---

## Storage Architecture

System/application data and CCTV recordings have different workload characteristics.

A preferred long-term layout is:

```text
System SSD / NVMe
├── operating system
├── Docker
├── Home Assistant
├── InfluxDB
├── Mosquitto configuration
└── reporting application

Separate persistent storage
├── CCTV recordings
└── future local file storage
```

Video retention should be sized using observed recording volume rather than theoretical maximum bitrate alone.

Persistent Docker data must not depend on the lifecycle of an individual container.

---

## Network Architecture

The system is designed around a trusted local network.

Infrastructure components should use wired Ethernet where practical.

IoT devices may be placed on a separate network or subnet.

They do not need unrestricted access to the home server. They only need access to the specific local services required for their function.

For example:

```text
IoT device
    |
    | TCP/1883
    v
Mosquitto
```

Network segmentation should therefore be based on required communication paths rather than requiring all devices to share the same subnet.

---

## Remote Access Boundary

Local service interfaces are not intended to be exposed directly to the public Internet.

This includes interfaces for:

- Home Assistant;
- Mosquitto;
- InfluxDB;
- the reporting service;
- Frigate.

The Internet connection must not be assumed to provide:

- a static IPv4 address;
- a publicly reachable IPv4 address;
- functional inbound port forwarding.

Remote access should therefore be implemented as a separate security layer rather than by directly publishing service ports.

The chosen remote-access mechanism must remain consistent with the project's local-first, open-source and minimal-exposure principles.

The current host configuration includes a Tor onion service for Frigate. Its
port 80 forwards to a loopback-only Nginx listener at `127.0.0.1:8972`, which
proxies to Frigate's HTTPS interface at `127.0.0.1:8971`. This path uses Frigate's
application authentication; the repository does not configure Tor client
authorization. Nginx disables upstream certificate verification for the local
Frigate endpoint. Tor/Nginx are managed separately from the Frigate container by
the main playbook, which currently installs them unconditionally. The standalone
Frigate playbook does not manage remote access. This remote path requires Tor, while local CCTV operation does
not. It requires no inbound router port forwarding.

The onion mapping exposes only Frigate's HTTP/WebSocket interface, not its RTSP
or WebRTC ports. Tor maintains its service identity under `/var/lib/tor/frigate/`;
automated identity backup and restoration are not implemented. Deployment and
access instructions are in `README.md`; layer-by-layer validation is in `TESTING.md`.

---

## Security Architecture

### Secrets

Secrets are not part of the public repository.

Examples include:

- passwords;
- API tokens;
- MQTT credentials;
- camera credentials;
- private inventory values;
- VPN or remote-access keys;
- Wi-Fi credentials.

Ansible Vault is used where secrets must be managed as part of the deployment process.

### Public vs Private Configuration

Reusable configuration should contain placeholders or generic values.

Deployment-specific values are maintained separately.

Examples of private files include:

```text
ansible/inventory/hosts.yml
ansible/secrets.yml
```

These must not be committed in plaintext.

### Service Exposure

Services should listen only where required and should remain accessible from trusted networks.

Direct public exposure is not the default architecture.

---

## Configuration Ownership

Configuration ownership should remain unambiguous.

```text
Ansible
  |
  +--> host configuration
  |
  +--> Docker deployment
  |
  +--> configuration templates
  |
  +--> service directories
  |
  +--> permissions
```

A manual change performed on the server for troubleshooting must not become the permanent configuration.

Once a working fix is identified, it should be represented in Ansible.

---

## Failure and Dependency Model

The telemetry pipeline has an explicit upstream-to-downstream dependency order:

```text
Device
  |
Network
  |
Mosquitto
  |
Home Assistant
  |
InfluxDB
  |
Reporting
```

A failure downstream should be investigated only after confirming that its upstream data source is functioning.

For example, an empty report should not immediately be treated as a reporting bug. The investigation should first determine whether:

1. the device produced data;
2. the network transported it;
3. Mosquitto received it;
4. Home Assistant exposed it;
5. Home Assistant wrote it to InfluxDB;
6. the reporting query selected the expected data.

Detailed procedures are maintained in `TESTING.md`.

---

## Documentation Boundaries

The documentation files have intentionally different responsibilities.

### `README.md`

Contains:

- project overview;
- installation;
- deployment;
- day-to-day usage;
- basic service information.

### `ARCHITECTURE.md`

Contains:

- system structure;
- component responsibilities;
- boundaries;
- dependencies;
- data flows;
- architectural principles.

It should explain **why the system is structured as it is**, without becoming an installation manual.

### `HARDWARE.md`

Contains:

- hardware recommendations;
- sizing guidance;
- storage recommendations;
- hardware-specific considerations.

### `TESTING.md`

Contains:

- validation commands;
- troubleshooting;
- component tests;
- acceptance checks.

### `AGENTS.md`

Contains:

- instructions for AI coding agents;
- development constraints;
- repository working practices;
- rules for modifying and testing the project.

`AGENTS.md` should refer to this document rather than duplicating the system architecture.

---

## Architectural Change Policy

Changes should update this document when they alter any of the following:

- major components;
- component responsibilities;
- service boundaries;
- deployment model;
- persistent storage model;
- major data flows;
- security boundaries;
- remote-access architecture;
- ownership of configuration.

Routine code fixes, dependency updates and minor configuration changes normally do not require an architecture update.

---

## Current Core Components

The current architecture consists of:

| Component | Role |
|---|---|
| Ansible | Deployment and configuration management |
| Docker / Docker Compose | Service runtime |
| Mosquitto | Local MQTT broker |
| Home Assistant | Device integration and automation |
| InfluxDB | Historical time-series storage |
| Python reporting service | Analysis, reporting and local presentation |
| Frigate | Local CCTV/NVR |
