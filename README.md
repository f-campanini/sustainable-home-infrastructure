# Sustainable Home Infrastructure

A reproducible, local-first infrastructure stack for home automation, energy monitoring, time-series analysis and local CCTV.

The project uses Infrastructure as Code so the server can be rebuilt and maintained from a Linux control machine.

## Deployment Status

The sections below describe the working-tree implementation, not a guarantee that
every feature is already deployed. Last live inspection: **2026-09-19**.

| Change | Last verified deployment state |
|---|---|
| Scheduler health-response fix | Deployed and logging successful periodic checks |
| Tor/Nginx Frigate proxy | Deployed; local proxy and authentication checked |
| Interactive chart persistence and daily reports | Pending deployment |
| Audit-failure handling and atomic artifact writes | Pending deployment |
| Runtime secret-permission hardening | Pending deployment |
| Frigate adoption through Ansible | Pending; private Vault import required |
| Bootstrap workflow | Validated in check mode; not applied |

Update this dated status after deployment and acceptance checks. External onion
connectivity and authenticated playback were not verified by the local proxy check.

## Architecture

```text
IoT / energy devices
        |
        | MQTT
        v
    Mosquitto
        |
        v
 Home Assistant
        |
        v
    InfluxDB
        |
        v
 Python Reporting
   |         |
   |         +-- APScheduler
   |
   +-- Flask / Gunicorn
          |
          v
     Web reports


RTSP cameras
      |
      v
    Frigate
      |
      v
Local recordings
```

Future energy-monitoring expansion:

```text
Whole-house meter
       |
       v
Home Assistant
       |
       v
   InfluxDB
       |
       v
Energy analysis and reports
```

## Design Principles

The project follows these principles:

1. Keep home data local by default.
2. Prefer open-source software.
3. Avoid exposing management interfaces directly to the Internet.
4. Use Infrastructure as Code.
5. Keep credentials and private inventory out of Git.
6. Test every layer independently.
7. Public documentation describes the architecture, not the physical home.
8. Prefer simple and maintainable components over unnecessary complexity.

## Software Stack

| Component | Purpose |
|---|---|
| Ubuntu Server LTS | Host operating system |
| Docker | Container runtime |
| Docker Compose | Service orchestration |
| Ansible | Infrastructure deployment |
| Mosquitto | MQTT broker |
| Home Assistant | Device integration and automation |
| InfluxDB 2.x | Time-series database |
| Python | Data processing and report generation |
| Flask | Reporting web application |
| Gunicorn | WSGI application server |
| APScheduler | Periodic report generation |
| pandas | Time-series processing and aggregation |
| matplotlib | Server-side chart generation |
| Frigate | Local CCTV processing and recording |
| Git | Version control |

## Repository Layout

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
│   │   ├── ansible-sudoers.j2
│   │   ├── compose.yml.j2
│   │   ├── frigate-compose.yml.j2
│   │   ├── frigate-config.yml.j2
│   │   ├── frigate-onion-nginx.conf.j2
│   │   ├── mosquitto.conf.j2
│   │   ├── reporting-cleanup.sh.j2
│   │   ├── reporting-cleanup.service.j2
│   │   ├── reporting-cleanup.timer.j2
│   │   └── torrc.j2
│   ├── vars/
│   │   ├── frigate.yml
│   │   └── reporting.yml
│   ├── secrets.yml
│   └── site.yml
├── reporting/
│   ├── templates/
│   │   └── index.html
│   ├── tests/
│   │   ├── test_reporting.py
│   │   └── test_scheduled_reports.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── entrypoint.sh
│   ├── app.py
│   ├── artifact.py
│   ├── audit.py
│   ├── charts.py
│   ├── influx.py
│   ├── query_service.py
│   ├── scheduled_reports.py
│   └── scheduler.py
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── TESTING.md
├── HARDWARE.md
├── LICENSE
└── .gitignore
```

Private files include:

```text
ansible/inventory/hosts.yml
ansible/secrets.yml
ansible/frigate.vault.yml
```

They must not be committed.

## Control Machine

A Linux workstation or laptop is used to run Ansible.

Install the required tools on the control machine (these are not server changes):

```bash
sudo apt update
sudo apt install -y git pipx openssh-client sshpass
pipx ensurepath
pipx install --include-deps ansible
```

Verify:

```bash
ansible --version
```

## Server Requirements

Recommended minimum:

- Ubuntu Server 24.04 LTS or equivalent
- 4 CPU cores
- 8 GB RAM
- SSD or NVMe system storage
- SSH access to an existing account with sudo privileges
- Python 3 and sudo supplied by the server OS installation

16 GB RAM is recommended when Home Assistant, InfluxDB and Frigate share the same machine.

## SSH Setup

Generate an SSH key on the control machine if necessary:

```bash
ssh-keygen -t ed25519
```

Verify the initial SSH login and check the host-key fingerprint against a trusted
source before accepting it:

```bash
ssh USER@SERVER_IP
```

Use the account/password or initial key supplied during OS provisioning. Ansible
needs this initial access; it cannot bootstrap a machine with no reachable login.
Do not change server configuration in the SSH session. After configuring inventory
below, the bootstrap playbook installs your public key. Host-key checking remains
enabled in `ansible.cfg`.

## Ansible Inventory

Copy the public example:

```bash
cd ansible
cp inventory/hosts.example.yml inventory/hosts.yml
```

Configure:

```yaml
all:
  hosts:
    homeserver:
      ansible_host: SERVER_IP
      ansible_user: SERVER_USER
```

After bootstrap, test key-based connectivity:

```bash
ansible all -m ping
```

Expected:

```text
SUCCESS
pong
```

## Privilege Escalation

The existing SSH account must initially be able to use sudo with its password
(or already have passwordless sudo). From `ansible/`, preview the bootstrap:

```bash
ansible-playbook bootstrap.yml --syntax-check
ansible-playbook bootstrap.yml --check --diff --ask-pass --ask-become-pass
```

Then apply it through Ansible:

```bash
ansible-playbook bootstrap.yml --ask-pass --ask-become-pass
```

Omit `--ask-pass` if initial key authentication already works. Omit
`--ask-become-pass` if sudo is already passwordless. Password prompts are not saved;
any saved SSH or sudo passwords belong in Ansible Vault, never plaintext inventory.

The playbook supports Ubuntu 24.04 and 26.04 and performs these server changes:

- Installs the control machine's `~/.ssh/id_ed25519.pub` for `ansible_user`,
  preserving other authorized keys. Override `bootstrap_public_key_file` in
  private inventory for another public-key path; never supply a private key.
- Manages `/etc/sudoers.d/ansible` as `root:root`, mode `0440`, with `visudo`
  validation before replacement.
- Installs Ubuntu's `docker.io` and `docker-compose-v2` packages if Docker is
  absent, then enables and starts Docker. Ubuntu's Universe repository must be
  available. An existing Docker installation is preserved and its Compose plugin
  must already work; the playbook fails if it is missing rather than mixing
  package sources. Fix an incomplete existing installation through a separate
  Ansible change.

By default, the managed sudo rule grants `ansible_user` unrestricted passwordless
administration, matching the deployment commands in this guide. To require a
sudo password, set `bootstrap_passwordless_sudo: false` in private inventory and
use `--ask-become-pass` for subsequent privileged Ansible commands. This manages
only `/etc/sudoers.d/ansible`; other sudo rules can still grant passwordless access.
Existing content at that path is replaced by the validated rule, so review the
preview before applying it.

The bootstrap playbook is separate from `site.yml` and does not deploy containers.
Check mode previews access changes but cannot fully validate a fresh Docker install.
After bootstrap, test a new key-authenticated connection and sudo:

```bash
ansible homeserver -b -m command -a "whoami"
```

Expected:

```text
root
```

There are no manual `ssh-copy-id`, sudoers edits or server-side package-install
steps in this workflow. OS provisioning supplies only the initial access and
Ansible prerequisites; ongoing server configuration is managed through Ansible.

## Secrets

Create:

```text
ansible/secrets.yml
```

with:

```yaml
mqtt_username: homeassistant
mqtt_password: CHANGE_ME

influxdb_username: admin
influxdb_password: CHANGE_ME
```

Encrypt it immediately:

```bash
ansible-vault encrypt secrets.yml
```

Edit later:

```bash
ansible-vault edit secrets.yml
```

The InfluxDB API token is generated once on the server and reused by subsequent deployments.

Never commit `secrets.yml` or Vault password files.

Ansible restricts the deployed runtime files as follows:

| Path | Owner:group (numeric defaults) | Mode |
|---|---|---|
| `/srv/secrets` | `root:root` | `0700` |
| `/srv/secrets/influxdb_username` | `root:1000` | `0640` |
| `/srv/secrets/influxdb_password` | `root:1000` | `0640` |
| `/srv/secrets/influxdb_token` | `root:1000` | `0640` |
| `/srv/mosquitto/config` | `root:1883` | `0750` |
| `/srv/mosquitto/config/password_file` | `root:1883` | `0640` |

InfluxDB's entrypoint reads initialization secrets again after switching to its
service user, so those files need group read access. The root-only parent directory
prevents ordinary host users from accessing them even if a host account shares
GID 1000. Docker mounts the individual files inside the containers; InfluxDB can
read them as GID 1000 and reporting currently reads its token as root. Mosquitto
reads its password hashes as GID 1883, with directory traversal limited to that
group and root. Override `influxdb_container_gid` or `mosquitto_container_gid` in
private inventory only when the container identity has also changed.

Permissions are managed on the host because Compose file-backed secrets use bind
mounts; setting `uid`, `gid` or `mode` on the Compose secret does not remap them.
See [Docker's file-backed secret limitations](https://docs.docker.com/reference/compose-file/services/#secrets).
Root and users with Docker administration access remain able to access these
runtime secrets. Vault protects the deployment source, not the decrypted runtime
files. The generated InfluxDB token still resides on the server and reporting
still uses the admin token; Vault backup/import and a restricted reporting token
are separate changes, not provided by these permission settings.

## Deployment

Prepare both encrypted private files, `secrets.yml` and `frigate.vault.yml`, before
running the full playbook. A shared Frigate preflight checks file presence, Vault
encryption, decryption and required top-level configuration before the main play
changes server configuration. Frigate's detailed schema validation still occurs
in its deployment play. Missing prerequisites now fail before the main stack is
updated; standalone `frigate.yml` uses the same preflight.

From the `ansible` directory:

```bash
ansible-playbook site.yml --syntax-check --ask-vault-pass
```

Then deploy:

```bash
ansible-playbook site.yml --ask-vault-pass
```

Check containers:

```bash
ansible homeserver -b -a "docker ps"
```

The main stack should include:

```text
homeassistant
mosquitto
influxdb
reporting
```

Frigate is managed by `ansible/frigate.yml`, imported by `site.yml`, as a separate
Compose project named `frigate`. Prepare its private Vault configuration before
running the full deployment (see Frigate below).

## Local Services

| Service | Default local port |
|---|---:|
| Home Assistant | 8123 |
| Mosquitto | 1883 |
| InfluxDB | 8086 |
| Reporting | 8090 |
| Frigate | 8971 |

These interfaces should remain on the trusted LAN. The configured remote-access
path is a Tor onion service for Frigate only, described below. General VPN access
remains planned work.

Do not expose them directly to the Internet.

## MQTT

Home Assistant connects to the Mosquitto broker using:

```text
Broker: SERVER_IP
Port: 1883
Username: mqtt_username
Password: mqtt_password
```

Energy devices can publish measurements such as power, energy, voltage, current and power factor.

Typical Tasmota topics include:

```text
tele/device/SENSOR
tele/device/STATE
stat/device/...
```

A practical telemetry interval for energy monitoring is:

```text
TelePeriod 60
```

## InfluxDB

The deployment initializes:

```text
Organization: home
Bucket: homeassistant
```

InfluxDB is available locally at:

```text
http://SERVER_IP:8086
```

Retrieve the generated token when necessary:

```bash
ansible homeserver -b -a "cat /srv/secrets/influxdb_token"
```

Treat the output as a secret.

Home Assistant writes historical measurements into InfluxDB.

## Reporting Service

The reporting service is a continuously running Docker container.

It contains a Gunicorn-served Flask application and an APScheduler process. InfluxDB is the historical data source, while pandas and matplotlib are used for validation, processing and server-side chart generation.

The scheduler checks InfluxDB health at startup and every 15 minutes by default
(`REPORT_INTERVAL_MINUTES`). It logs the returned status and message, including
`status=fail` and the error message when the health request fails.

### Scheduled charts

The Ansible deployment also configures a daily report job at **00:05 Europe/Rome**.
It discovers power (`W`) sensors and saves one line chart per sensor for the
preceding 24 hours, using 15-minute averages. This is a rolling window, not an
exact calendar-day energy total. The first run is at the next scheduled time;
restarting the container does not generate an extra batch.

Defaults are in `ansible/vars/reporting.yml`. Override `reporting_schedules` in
private inventory under `homeserver` to select entities or set different daily
times. Use the exact entity identifiers shown by the Historical Explorer:

```yaml
reporting_schedules:
  - name: daily_power
    hour: 0
    minute: 5
    measurement: W
    entities: [sensor_example]
    range_name: 24h
    aggregation: 15m
    function: mean
    chart_type: line
```

An empty `entities: []` discovers sensors of the selected measurement at each run.
Use `reporting_schedules: []` to disable report jobs while retaining health checks.
Multiple entries are supported with unique names made of letters, digits, hyphens
or underscores. Query options are the same as the Historical Explorer. Ansible
passes the list as JSON in `REPORT_SCHEDULES`; a container without that variable
has no report jobs. Change schedules through Ansible and recreate reporting to
apply them. Schedules use the container's `TZ` setting.

Scheduled files are named `generated/scheduled-<name>-report-<timestamp>-<id>.png`
and follow the same retention policy as interactive charts. Logs identify the
saved file and sensor; query audit records currently cover interactive requests
only. Missing or non-numeric data is logged and skipped; other per-sensor failures
are logged without preventing reports for the remaining sensors.

Report jobs render one at a time. Delayed runs have a one-hour grace period and
overlapping executions of the same job are skipped. Schedules are held in memory:
missed runs during container downtime are not replayed after restart. Local clock
changes affect wall-clock schedules; avoid times in the daylight-saving transition
window. See [APScheduler's scheduling behavior](https://apscheduler.readthedocs.io/en/3.x/userguide.html#missed-job-executions-and-coalescing).

The web interface is available at:

```text
http://SERVER_IP:8090
```

Health check:

```text
http://SERVER_IP:8090/health
```

Read the JSON `status`, which is `pass` for a healthy InfluxDB response and `fail`
for a handled connection error. This endpoint returns HTTP 200 even for `fail`.
It checks InfluxDB health reachability, not token permissions, sensor freshness,
query results or audit writes; those require the separate checks in TESTING.md.

### Historical Explorer

The web interface includes a constrained Historical Explorer rather than exposing arbitrary Flux queries.

The current explorer supports:

- measurements such as power, energy, voltage and current
- selectable Home Assistant entities
- periods from 24 hours to 90 days
- raw, 5-minute, 15-minute, hourly and daily aggregation
- mean, minimum, maximum and sum functions
- line and bar charts

Historical queries explicitly select the numeric `value` field before aggregation. This prevents Home Assistant string metadata fields such as friendly name, device class and state class from being passed to numeric InfluxDB aggregate functions.

The application validates query parameters and historical data before rendering a chart. Expected conditions such as missing historical data or non-numeric values are presented as human-readable messages instead of generic HTTP error pages.

Error responses currently always include technical exception details, displayed
in a collapsible section of the interface; there is no development-only switch.
This reporting interface is intended for trusted LAN access, or a separately
configured VPN, and is not exposed by the Frigate onion proxy.

### Query Audit

Historical Explorer requests are audited separately from sensor measurements.

Sensor data is stored in:

```text
homeassistant
```

Query audit records are stored in:

```text
reporting_audit
```

Audit records include a request identifier, query characteristics, result size, execution time and status. Credentials, API tokens and raw sensor data must not be written to the audit log.

Writes are synchronous so successful writes complete before the client closes.
If the audit service fails, the application preserves the chart or its original
diagnostic response and logs `Query audit failed request_id=...` without exception
details. Auditing is best-effort during an outage: failed writes are not queued or
retried automatically and the corresponding audit record can be absent.

### Report Artifact Storage

Generated report artifacts are stored under:

```text
/srv/reporting/output
```

The storage lifecycle is divided into:

```text
generated/
publish_queue/
published/
```

`generated/` contains normal generated artifacts and can be cleaned automatically after the configured retention period.

Each successful Historical Explorer chart request saves its PNG as
`generated/<query-id>.png` before returning the same image to the browser. The
query ID shown in the interface and returned in the `X-Query-ID` response header
also identifies its audit record when audit storage is available. In the container, this directory is under
`REPORT_STORAGE_ROOT` (default `/data/reports`); the deployment mounts it from
`/srv/reporting/output`. A storage failure returns an error instead of reporting
successful chart generation.

PNG writes use an owner-only temporary file in `generated/`, followed by an atomic
rename. Readers do not see a partially written `.png`; caught write failures clean
up their temporary files and leave any existing destination intact. A hard process
termination may leave a `.tmp` file, which the existing retention cleanup also
removes once expired. New generated PNG files are mode `0600`.

`publish_queue/` contains artifacts explicitly selected for publication and must never be removed by the automatic cleanup job.

`published/` contains successfully published artifacts and can use a shorter retention period.

The cleanup process is implemented as a host systemd timer deployed through Ansible.

Future publication can use object storage, but public repository configuration must remain generic and must not contain private bucket names, credentials, domains or destination details.

The reporting application uses `influxdb-client`, `pandas`, `matplotlib`, Flask, Gunicorn and APScheduler.

## Frigate

Frigate provides local RTSP camera processing and recording.

Ansible manages its Compose file at `/srv/frigate/compose.yml` with project name
`frigate` and container name `frigate`. It preserves these persistent paths:

| Host path | Container path | Contents |
|---|---|---|
| `/srv/frigate/config` | `/config` | Configuration, database, authentication state and model cache |
| `/srv/frigate/media` | `/media/frigate` | Recordings and other media |

`/srv/frigate/storage` is not the recording path. Adopting an existing installation
must keep the database, media paths and private camera identifiers unchanged.
The playbook does not remove volumes, recordings or orphan containers.

Public runtime defaults are in `ansible/vars/frigate.yml`. They preserve the
existing deployment's privileged mode, render-device mapping, 512 MiB shared
memory, 1 GB temporary cache and 30-second shutdown grace period. GPU passthrough
alone does not enable FFmpeg hardware decoding; that is a separate configuration
choice. Change privileges or decoding settings in a separate, tested change.

Published ports are authenticated UI/API TCP/8971, RTSP TCP/8554, and WebRTC
TCP+UDP/8555. Internal unauthenticated port 5000 is not published. The UI is
available at `https://SERVER_IP:8971` when TLS is enabled. Keep these ports on
trusted networks. Existing Tor/Nginx templates proxy onion traffic through
`127.0.0.1:8972` to Frigate HTTPS on `127.0.0.1:8971`; deploying `frigate.yml`
alone does not change those host services.

### Private configuration

The complete Frigate configuration is stored under the `frigate_config` key in
the ignored, encrypted file `ansible/frigate.vault.yml`. This includes camera
identifiers, stream URLs, credentials, go2rtc settings and recording policies.
Use `frigate.vault.example.yml` as a structural example only. For adoption, import
the complete existing configuration instead of replacing it with the example.

From `ansible/`, create or edit the encrypted file:

```bash
ansible-vault create frigate.vault.yml
ansible-vault edit frigate.vault.yml
```

Inside the Vault editor, put the existing configuration under `frigate_config:`
and indent it by two spaces. Preserve the existing `version` field if present.
Use the same Vault password as `secrets.yml` for a single-password full deployment.
The playbook rejects an unencrypted variables file, suppresses secret diffs and
writes the runtime configuration with mode `0600`. Do not make permanent changes
through the Frigate UI; update Vault and deploy with Ansible.

### Deploy or adopt Frigate

From `ansible/`:

```bash
ansible-playbook frigate.yml --syntax-check
ansible-playbook frigate.yml --check --diff --ask-vault-pass
ansible-playbook frigate.yml --ask-vault-pass
```

Review the check-mode proposal before deploying. Check mode does not run Docker
configuration validators or prove that camera streams work. A real deployment
validates the Compose file and invokes Frigate's strict configuration parser in
an isolated container before installing its configuration. The parser runs without
migrations, model installation or safe-mode fallback, with no network and only the
candidate configuration mounted read-only. It reconciles the existing Compose project and
restarts Frigate when configuration changes, briefly interrupting recording.
Files with identical rendered contents do not trigger a configuration restart.

An image is pulled only when absent locally; Compose uses `--pull never`.
Routine adoption therefore reuses the cached image. An image upgrade is a separate
change: set `frigate_image` to the reviewed tag or digest. Extra vars can override
runtime defaults. Docker Engine and the Compose plugin must already be installed.

The full `site.yml` deployment imports this playbook after the main stack.
Use the standalone playbook above to deploy only Frigate.

Public configuration must use generic camera names such as `camera_1` and `camera_2`.

Never publish real camera addresses, credentials, unnecessary hardware model information, physical locations, MAC addresses or real camera names.

Example continuous recording configuration:

```yaml
record:
  enabled: true
  continuous:
    days: 2
```

Input roles are separate YAML entries:

```yaml
roles:
  - detect
  - record
```

Intel integrated graphics can be used for hardware acceleration when supported.

## Remote Access to Frigate

The main `ansible/site.yml` playbook installs Tor and Nginx unconditionally; there
is currently no enable/disable variable for this feature. The standalone
`frigate.yml` playbook manages only the CCTV container. Remote access follows:

```text
Tor Browser → onion service port 80
            → Nginx HTTP at 127.0.0.1:8972
            → Frigate HTTPS at 127.0.0.1:8971
```

This publishes Frigate through Tor, not through an inbound router port-forward.
It does not provide remote access to Home Assistant, MQTT, InfluxDB or reporting,
and it is not a general-purpose VPN. Frigate remains available locally without Tor.

### Configuration and deployment

| Repository template | Managed server file | Purpose |
|---|---|---|
| `ansible/templates/torrc.j2` | `/etc/tor/torrc` | Version 3 onion service and forwarding target |
| `ansible/templates/frigate-onion-nginx.conf.j2` | `/etc/nginx/sites-available/frigate-onion` | Loopback reverse proxy to Frigate |

Ansible enables the Nginx site using a symlink in `sites-enabled`, removes the
default Nginx site, validates configuration and restarts services through handlers
when their configuration changes. The Tor template replaces the complete `torrc`;
additional Tor settings must therefore also be represented in Ansible.

Use the full deployment procedure above, including both Vault files. There is no
remote-access-only playbook or task tag: running `site.yml` also deploys the main
stack and Frigate, so review its full scope before applying it. Do not configure
Tor or Nginx manually on the server.

### Connect

After Tor has initialized the onion service, retrieve its address with this
read-only command from `ansible/`:

```bash
ansible homeserver -b -a "cat /var/lib/tor/frigate/hostname"
```

Open `http://ONION_ADDRESS.onion` in Tor Browser, substituting the full hostname
returned above, and sign in with a Frigate account. The configured onion service
uses HTTP port 80; its upstream connection to Frigate uses HTTPS. The Tor Project
documents [hostname retrieval and Tor Browser access](https://community.torproject.org/onion-services/setup/).

The repository does not configure Tor client authorization. Anyone who knows the
address can reach the Frigate login interface; access control depends on Frigate
authentication being enabled. Client authorization would be a separate Ansible
change; see the [Tor client-authorization documentation](https://community.torproject.org/onion-services/advanced/client-auth/).

Keep the real onion address and identity keys out of public documentation and Git.
Tor maintains the identity under `/var/lib/tor/frigate/`; the playbook does not
back up or restore it. Any identity backup needs protected storage, such as
Ansible Vault. Losing that identity changes the address on regeneration.

### Transport boundaries

The Nginx proxy listens only on loopback port 8972 and forwards WebSocket upgrade
headers. It disables upstream TLS certificate verification for the local Frigate
endpoint. Internal unauthenticated Frigate port 5000 is not used by this proxy.
The existing LAN port mappings remain in place; Tor does not restrict them.

Only the HTTP/WebSocket path is proxied. RTSP port 8554 and WebRTC port 8555 are
not forwarded by this onion service, so verify live-view playback separately;
loading the login page alone does not prove every streaming mode works.
Layer-by-layer checks are in [TESTING.md](TESTING.md#frigate-remote-access).

## Network Segmentation

IoT devices do not need to be on the same subnet as the server. They only need network access to the services they use, such as outbound MQTT TCP/1883 to Mosquitto.

When an IoT network is behind NAT, several clients may appear to the MQTT broker with the same source address. They remain distinguishable by MQTT client ID and topic.

## Security

Do not commit passwords, API tokens, private inventory, MAC addresses, camera credentials, real camera names, physical locations, VPN keys, Wi-Fi credentials, serial numbers or unnecessary internal network details.

Before publishing changes:

```bash
git status
git diff --cached
```

Also inspect repository history when sensitive data may previously have been committed.

## Testing

Detailed validation and troubleshooting procedures are in `TESTING.md`.

The main data path is:

```text
Device
  |
  v
Mosquitto
  |
  v
Home Assistant
  |
  v
InfluxDB
  |
  v
Python Reporting
```

Each boundary should be tested independently.

## Planned Work

Future work includes whole-house electricity monitoring, solar production monitoring, grid import/export measurement, scheduled energy and cost summaries beyond historical charts, charging-cost analysis, server performance monitoring, NAS storage, SMART monitoring, UPS integration, secure VPN remote access, improved Ansible idempotency and optional object-storage publication of selected report artifacts.

## License

This repository is licensed under the MIT License.

The repository contains original configuration, automation and documentation for integrating independent open-source projects. Third-party projects remain subject to their own licenses.
