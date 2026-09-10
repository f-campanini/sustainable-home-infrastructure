# Sustainable Home Infrastructure

A reproducible, local-first infrastructure stack for home automation, energy monitoring, time-series analysis and local CCTV.

The project uses Infrastructure as Code so the server can be rebuilt and maintained from a Linux control machine.

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
│   ├── inventory/
│   │   ├── hosts.yml
│   │   └── hosts.example.yml
│   ├── templates/
│   │   ├── compose.yml.j2
│   │   └── mosquitto.conf.j2
│   ├── secrets.yml
│   └── site.yml
├── reporting/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── entrypoint.sh
│   ├── app.py
│   ├── influx.py
│   └── scheduler.py
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
```

They must not be committed.

## Control Machine

A Linux workstation or laptop is used to run Ansible.

Install the required tools:

```bash
sudo apt update
sudo apt install -y git pipx openssh-client
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
- Docker
- Docker Compose plugin
- SSH access

16 GB RAM is recommended when Home Assistant, InfluxDB and Frigate share the same machine.

## SSH Setup

Generate an SSH key if necessary:

```bash
ssh-keygen -t ed25519
```

Install it on the server:

```bash
ssh-copy-id USER@SERVER_IP
```

Test:

```bash
ssh USER@SERVER_IP
```

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

Test:

```bash
ansible all -m ping
```

Expected:

```text
SUCCESS
pong
```

## Privilege Escalation

The Ansible account must be able to perform administrative operations.

A simple bootstrap configuration is:

```text
SERVER_USER ALL=(ALL) NOPASSWD: ALL
```

Create it using:

```bash
sudo visudo -f /etc/sudoers.d/ansible
sudo chmod 440 /etc/sudoers.d/ansible
sudo visudo -cf /etc/sudoers.d/ansible
```

Test:

```bash
ansible homeserver -b -m command -a "whoami"
```

Expected:

```text
root
```

A broad `NOPASSWD` configuration is convenient during bootstrap and can later be restricted.

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

## Deployment

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

Frigate may currently be deployed through its own Compose project.

## Local Services

| Service | Default local port |
|---|---:|
| Home Assistant | 8123 |
| Mosquitto | 1883 |
| InfluxDB | 8086 |
| Reporting | 8090 |
| Frigate | 8971 |

These interfaces should remain on the trusted LAN or be reached remotely through a VPN.

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

It contains a Gunicorn-served Flask application and an APScheduler process for periodic report generation. Both use InfluxDB as the data source.

The web interface is available at:

```text
http://SERVER_IP:8090
```

Health check:

```text
http://SERVER_IP:8090/health
```

A healthy response confirms that the application can communicate with InfluxDB.

Generated charts and reports are stored under:

```text
/srv/reporting/output
```

The reporting application uses `influxdb-client`, `pandas`, `matplotlib`, Flask, Gunicorn and APScheduler.

## Frigate

Frigate provides local RTSP camera processing and recording.

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

Future work includes whole-house electricity monitoring, solar production monitoring, grid import/export measurement, automated energy reports, charging-cost analysis, server performance monitoring, NAS storage, SMART monitoring, UPS integration, secure VPN remote access, improved Ansible idempotency and integration of Frigate deployment into the main Ansible repository.

## License

This repository is licensed under the MIT License.

The repository contains original configuration, automation and documentation for integrating independent open-source projects. Third-party projects remain subject to their own licenses.
