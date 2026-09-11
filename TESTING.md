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

The reporting landing page and Historical Explorer should load.

Verify that the measurement selector loads available entities and test a known-good power sensor with combinations such as:

```text
24h / raw / line
24h / 15m / average / line
24h / 15m / minimum / line
24h / 15m / maximum / line
24h / 15m / sum / line
48h / 1h / average / line
7d / 1h / average / line
```

Also test at least one bar chart and more than one entity.

A successful query should render a PNG chart and display its query identifier.

### Historical Data Validation

Historical queries must filter the Home Assistant numeric field before applying InfluxDB aggregation:

```flux
|> filter(fn: (r) => r["_field"] == "value")
```

This is important because a Home Assistant measurement can also contain string fields such as:

```text
device_class_str
friendly_name_str
state_class_str
```

Without the numeric-field filter, InfluxDB aggregate functions such as `mean`, `min` or `max` can fail with string cursor or schema-collision errors.

Test a period for which a sensor has no data. The web interface should show a human-readable message rather than a generic 400 or 500 error page.

During development, the error display may also contain a collapsible `Technical details` section with the exception traceback.

### Reporting Audit

Verify that the audit bucket exists:

```text
reporting_audit
```

After generating a chart, query the audit bucket and confirm that a `query_audit` record is created with a request ID, status, query characteristics, result point count and execution time.

Audit records must not contain credentials, API tokens or raw sensor values.

### Reporting Artifact Cleanup

The report storage root should contain:

```text
generated/
publish_queue/
published/
```

The cleanup timer must remove only expired files from `generated/` and `published/`.

It must never automatically delete files from:

```text
publish_queue/
```

Check the timer with:

```bash
ansible homeserver -b -a "systemctl status reporting-cleanup.timer --no-pager"
```

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
- [ ] Historical Explorer loads available entities
- [ ] raw historical chart generation succeeds
- [ ] aggregated historical chart generation succeeds
- [ ] line and bar chart generation succeeds
- [ ] missing historical data produces a human-readable message
- [ ] query audit records are written to `reporting_audit`
- [ ] reporting cleanup timer is active
- [ ] `publish_queue` is excluded from automatic cleanup
- [ ] APScheduler runs scheduled jobs
- [ ] Frigate live streams work
- [ ] Frigate recordings are created
