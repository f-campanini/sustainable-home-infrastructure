# Testing and Troubleshooting

Test the system from the data source toward the final consumer.

```text
Device
  |
  v
Network
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

Do not troubleshoot a downstream component before confirming its upstream source works.

## Ansible Connectivity

```bash
cd ansible
ansible all -m ping
```

Expected: `SUCCESS` and `pong`.

Test privilege escalation:

```bash
ansible homeserver -b -m command -a "whoami"
```

Expected: `root`.

## Playbook Syntax

```bash
ansible-playbook site.yml --syntax-check --ask-vault-pass
```

Expected: `playbook: site.yml`.

## Deployment

```bash
ansible-playbook site.yml --ask-vault-pass
```

The playbook should complete without failed tasks.

## Docker

Check containers:

```bash
ansible homeserver -b -a "docker ps"
```

Expected core services:

```text
homeassistant
mosquitto
influxdb
reporting
```

Frigate may also be present if deployed through its separate Compose project.

## Mosquitto

Check logs:

```bash
ansible homeserver -b -a "docker logs --tail 100 mosquitto"
```

Authentication test:

```bash
docker exec -it mosquitto mosquitto_sub \
  -h localhost \
  -p 1883 \
  -u USERNAME \
  -P 'PASSWORD' \
  -t 'test/#'
```

If it waits silently instead of returning an authentication error, authentication succeeded.

Inspect MQTT traffic:

```bash
docker exec -it mosquitto mosquitto_sub \
  -h localhost \
  -u USERNAME \
  -P 'PASSWORD' \
  -v \
  -t '#'
```

For Tasmota telemetry only:

```bash
docker exec -it mosquitto mosquitto_sub \
  -h localhost \
  -u USERNAME \
  -P 'PASSWORD' \
  -v \
  -t 'tele/#'
```

## Home Assistant

Open `http://SERVER_IP:8123` and verify the MQTT integration is connected.

Energy-monitoring devices should expose relevant entities such as power, energy, voltage, current and power factor.

## Bluetooth

Verify:

```bash
ls -l /run/dbus
```

The Home Assistant container configuration should include:

```text
/run/dbus:/run/dbus:ro
```

If Home Assistant reports `DBus service not found`, check the D-Bus mount and host Bluetooth service.

## InfluxDB

Check status:

```bash
ansible homeserver -b -a "docker ps --filter name=influxdb"
```

Check logs:

```bash
ansible homeserver -b -a "docker logs --tail 100 influxdb"
```

Check version:

```bash
ansible homeserver -b -a "docker exec influxdb influx version"
```

Expected configuration:

```text
Organization: home
Bucket: homeassistant
```

## Home Assistant to InfluxDB

Run:

```flux
from(bucket: "homeassistant")
  |> range(start: -15m)
  |> limit(n: 20)
```

Rows should be returned when Home Assistant is sending data.

Power data:

```flux
from(bucket: "homeassistant")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "W")
```

Energy data:

```flux
from(bucket: "homeassistant")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "kWh")
```

Voltage data:

```flux
from(bucket: "homeassistant")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "V")
```

## Reporting Container

Check:

```bash
ansible homeserver -b -a "docker ps --filter name=reporting"
```

Check logs:

```bash
ansible homeserver -b -a "docker logs --tail 100 reporting"
```

Expected components include Gunicorn, Flask and APScheduler.

## Reporting Health Test

Open:

```text
http://SERVER_IP:8090/health
```

A healthy response should indicate `status: ok` and successful communication with InfluxDB.

## Reporting Web Test

Open:

```text
http://SERVER_IP:8090/
```

The reporting landing page should load.

## Scheduler Test

Check logs:

```bash
ansible homeserver -b -a "docker logs --tail 100 reporting"
```

Scheduled InfluxDB health checks should appear according to the configured interval.

## Full Energy Pipeline

Device to Mosquitto:

```bash
docker exec -it mosquitto mosquitto_sub \
  -h localhost \
  -u USER \
  -P 'PASSWORD' \
  -v \
  -t 'tele/#'
```

Mosquitto to Home Assistant: confirm corresponding entities exist in Home Assistant.

Home Assistant to InfluxDB:

```flux
from(bucket: "homeassistant")
  |> range(start: -15m)
```

InfluxDB to reporting: open `http://SERVER_IP:8090/health`.

The complete data path is healthy when all boundaries pass.

## Tasmota Telemetry

Check the configured telemetry interval using `TelePeriod` in the Tasmota console.

A common energy-monitoring configuration is:

```text
TelePeriod 60
```

## Frigate

Check:

```bash
docker ps --filter name=frigate
```

Logs:

```bash
docker logs --tail 100 frigate
```

Verify that camera streams, live view, recordings, retention and hardware acceleration work as configured.

Check render devices:

```bash
ls -l /dev/dri
```

## Network Segmentation

IoT devices can reside on a different subnet if they can reach the required services. For MQTT they need connectivity to TCP/1883 on the broker.

## Common Ansible Problems

A clean pipx installation can be created with:

```bash
pipx uninstall ansible
pipx install --include-deps ansible
```

For Vault-aware syntax checks use:

```bash
ansible-playbook site.yml --syntax-check --ask-vault-pass
```

For templates use:

```yaml
src: compose.yml.j2
```

rather than adding the `templates/` directory to the source path.

## MQTT Password Idempotency

If the playbook rewrites the MQTT password file on every execution, Mosquitto may restart unnecessarily. A future improvement should detect whether the password changed and restart Mosquitto only after an actual configuration change.

## Useful Log Commands

```bash
ansible homeserver -b -a "docker logs --tail 100 homeassistant"
ansible homeserver -b -a "docker logs --tail 100 mosquitto"
ansible homeserver -b -a "docker logs --tail 100 influxdb"
ansible homeserver -b -a "docker logs --tail 100 reporting"
ansible homeserver -b -a "docker logs --tail 100 frigate"
```

## Acceptance Checklist

- [ ] Ansible connectivity succeeds
- [ ] privilege escalation succeeds
- [ ] playbook syntax check succeeds
- [ ] playbook deployment succeeds
- [ ] required containers remain running
- [ ] MQTT clients authenticate
- [ ] MQTT telemetry reaches Mosquitto
- [ ] Home Assistant discovers expected entities
- [ ] Home Assistant writes measurements to InfluxDB
- [ ] InfluxDB queries return current measurements
- [ ] reporting `/health` succeeds
- [ ] Flask web application responds
- [ ] APScheduler runs scheduled jobs
- [ ] Frigate live streams work
- [ ] Frigate recordings are created
