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

For a fresh Ubuntu 24.04/26.04 host, complete the bootstrap procedure in README first.
The control machine needs the `ansible.posix.authorized_key` module (included in
the full Ansible installation documented there).

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

If `bootstrap_passwordless_sudo: false`, add `--ask-become-pass` to privileged
commands throughout this document.

## Bootstrap Validation

From `ansible/`, preview the bootstrap using initial SSH and sudo credentials:

```bash
ansible-playbook bootstrap.yml --syntax-check
ansible-playbook bootstrap.yml --check --diff --ask-pass --ask-become-pass
```

Omit password flags when existing key authentication/passwordless sudo is already
available. Preview should preserve existing SSH keys and show only the intended
managed sudo rule. On a fresh host, check mode cannot start or test Docker before
installation; complete validation after the approved bootstrap run:

```bash
ansible homeserver -m ping
ansible homeserver -b -a "visudo -cf /etc/sudoers"
ansible homeserver -b -a "stat -c '%a %U:%G' /etc/sudoers.d/ansible"
ansible homeserver -b -a "docker info"
ansible homeserver -b -a "docker compose version"
```

Expected: key-based connectivity, valid sudoers syntax, `440 root:root`, a
reachable Docker daemon and an installed Compose plugin. Open a new connection
to verify access independently of the original session. Re-run bootstrap with
the same inputs; it should report no changes. Existing Docker installations must
not be replaced, and no application container should restart. An existing Docker
installation without Compose must fail before SSH/sudo configuration is changed.

## Playbook Syntax

```bash
ansible-playbook site.yml --syntax-check --ask-vault-pass
```

Expected: `playbook: site.yml`.

The full syntax check requires access to `secrets.yml` through Vault. Before any
server-changing task, the full deployment also checks the private Frigate Vault
file using `tasks/frigate-preflight.yml`. Missing files, plaintext input, an invalid
Vault password or missing top-level camera configuration must fail before the main
stack changes. A syntax check alone does not exercise that runtime preflight.

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

Frigate is managed by `frigate.yml` in its own Compose project, imported by
`site.yml`. It should also be present after a full deployment.

## Runtime Secret Permissions

After deploying through Ansible, inspect metadata without printing secret values:

```bash
ansible homeserver -b -a "stat -c '%a %u:%g %n' /srv/secrets /srv/secrets/influxdb_username /srv/secrets/influxdb_password /srv/secrets/influxdb_token /srv/mosquitto/config /srv/mosquitto/config/password_file"
```

Expect `/srv/secrets` to be `700 0:0`, its three files `640 0:1000`, the Mosquitto
configuration directory `750 0:1883` and its password file `640 0:1883` (unless
service GIDs were explicitly overridden). Verify readability using the actual
service identity rather than Docker exec's default root identity:

```bash
ansible homeserver -b -a "docker exec --user 1000:1000 influxdb test -r /run/secrets/influxdb_username"
ansible homeserver -b -a "docker exec --user 1000:1000 influxdb test -r /run/secrets/influxdb_password"
ansible homeserver -b -a "docker exec --user 1000:1000 influxdb test -r /run/secrets/influxdb_token"
ansible homeserver -b -a "docker exec --user 0:0 reporting test -r /run/secrets/influxdb_token"
ansible homeserver -b -a "docker exec --user 1883:1883 mosquitto test -r /mosquitto/config/password_file"
```

Each should return exit code 0 with no secret output. An ordinary host account
without sudo should fail to read the InfluxDB files through `/srv/secrets`, even
if its GID is 1000. An unrelated user outside GID 1883 must not be able to read the
Mosquitto password file. Do not test denial using root or a Docker administrator.

After the next approved container restart, confirm InfluxDB startup, reporting
health and MQTT authentication still work. Permission changes must preserve the
existing credentials and token. Validate fresh-image startup in isolation with
dummy secrets when changing image versions or service GIDs; do not loosen
permissions or print credentials to troubleshoot access.

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

A healthy response should indicate JSON `status: pass`. A handled connection
failure returns JSON `status: fail`, still with HTTP 200; checking only HTTP status
is insufficient. This does not prove token authorization, sensor freshness or audit
availability. Test real historical queries and audit records separately.

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

Error responses currently always include the exception traceback, shown in the
collapsible `Technical details` section; this is not gated by a development setting.

### Reporting Audit

Verify that the audit bucket exists:

```text
reporting_audit
```

After generating a chart, query the audit bucket and confirm that a `query_audit` record is created with a request ID, status, query characteristics, result point count and execution time.

Audit records must not contain credentials, API tokens or raw sensor values.

The regression suite simulates an audit outage on successful, invalid, empty and
failed queries. PNG responses and JSON diagnostics must remain available; no HTML
500 should replace them. Expect `Query audit failed request_id=...` in application
logs with no audit exception text. Successful audit writes are synchronous; outages
can leave missing audit records and are not automatically backfilled.

### Reporting Artifact Persistence

Generate a chart and note its query ID. Through Ansible, confirm a non-empty PNG
exists at `/srv/reporting/output/generated/<query-id>.png`, replacing the placeholder
with that ID:

```bash
ansible homeserver -b -a "stat /srv/reporting/output/generated/<query-id>.png"
```

The saved PNG should match the image returned by that request. Generate another
chart and verify it creates a separate file without overwriting the first. Invalid
queries and queries with no data should not create PNGs. A storage-write failure
must return an error rather than a successful PNG response; simulate that only in
an isolated test environment. Files should survive the next normal reporting
container replacement because storage is mounted from the host.

The local suite also simulates an interrupted copy and a failed rename. No partial
`.png` or temporary file should remain after a caught error, and an existing
complete destination must be preserved. A hard kill can leave `.tmp` files; verify
that normal retention cleanup includes those once expired. New PNGs are owner-only
(`0600`), readable by the current root reporting process and privileged Ansible.

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

Scheduled InfluxDB health checks should appear at startup and according to
`REPORT_INTERVAL_MINUTES` (15 minutes by default), in this format:

```text
InfluxDB health: status=<status> message=<message>
```

The status and message come from the same health helper used by `/health`.
When the health request fails, expect `status=fail` with its error message.
Neither a successful response nor a handled connection failure should produce
`KeyError: 'version'` or `Scheduled InfluxDB check failed`.

### Scheduled Report Tests

Run the local regression suite with the reporting dependencies installed, from
the repository root:

```bash
PYTHONPATH=reporting MPLBACKEND=Agg python -m unittest discover -s reporting/tests -v
```

These tests use temporary output directories and mocked InfluxDB queries; they
exercise real chart rendering, persistence and APScheduler execution without
connecting to the server.

After deploying the configured schedules through Ansible, confirm a startup log
such as `Scheduled report daily_power: daily at 00:05 (Europe/Rome)`. At that time,
expect `Scheduled report daily_power: saved ...` for each sensor with numeric
data. Confirm non-empty PNGs in `/srv/reporting/output/generated/` with names
starting `scheduled-daily_power-report-`. The default report covers the preceding
24 hours with 15-minute averages; it is not a calendar-day energy total.

For a live acceptance check, set a job to a nearby future daily time in private
inventory and deploy it through Ansible. Do not change the server clock or edit
the running container. Check sensor selection, separate output files on subsequent
runs, and continued health-check logs. Restore the desired schedule through Ansible.

Verify missing-data sensors are skipped and one failed sensor does not prevent
others from generating. Invalid schedule names, times, JSON or query options must
fail at scheduler startup. Setting `reporting_schedules: []` should leave only the
health job. Report generation is not run at startup, and runs missed during
container downtime are not backfilled. Scheduled reports use logs, not the
interactive query-audit bucket, to report their results.

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

From `ansible/`, validate the standalone playbook and preview changes:

```bash
ansible-playbook frigate.yml --syntax-check
ansible-playbook frigate.yml --check --diff --ask-vault-pass
```

The encrypted `frigate.vault.yml` must contain the complete private configuration
under `frigate_config`. Secret contents and diffs must not appear in task output.
An unencrypted variables file must be rejected before server configuration changes.
Syntax checking alone does not validate camera settings. Check mode skips runtime
validators and container reconciliation.

After reviewing the proposal, deploy through Ansible:

```bash
ansible-playbook frigate.yml --ask-vault-pass
```

The playbook validates candidate configuration before installation and waits for
container health after deployment. The strict parser must reject invalid input
rather than accept a safe-mode fallback; it runs in a temporary container with no
network and no live data mounts. Changed camera configuration causes a restart;
changed runtime settings can recreate the container. Existing media and database
files must remain in place. Do not run `compose down`, remove the container, rename
private camera identifiers or move recordings as part of adoption.

Check project and container status:

```bash
ansible homeserver -b -a "docker compose --project-name frigate --file /srv/frigate/compose.yml ps"
ansible homeserver -b -a "docker ps --filter name=frigate"
```

Logs:

```bash
ansible homeserver -b -a "docker logs --tail 100 frigate"
```

Inspect logs privately: they may contain camera identifiers or stream details.
Verify login at `https://SERVER_IP:8971`, camera streams, live view, recording
creation, existing recordings, retention and hardware acceleration if configured.
GPU device mapping alone does not prove hardware decoding is enabled.

Run the standalone playbook again. With identical inputs and a healthy container,
it should report no changes and keep the same container identity. The main stack's
existing always-changed tasks are outside this Frigate idempotency check.

Confirm the container mounts `/srv/frigate/config` at `/config` and
`/srv/frigate/media` at `/media/frigate`. Port 5000 must remain unpublished.
For the remote path configured by `site.yml`, separately verify Frigate
authentication through the onion address and that Nginx listens only on loopback
port 8972, as described below.

Check render devices:

```bash
ls -l /dev/dri
```

## Frigate Remote Access

Run the following read-only checks from `ansible/`. They do not deploy changes or
restart services. Review outputs privately because logs can contain private
addresses and camera details.

First verify Frigate locally, then the loopback proxy, then Tor:

```bash
ansible homeserver -b -a "docker ps --filter name=frigate"
ansible homeserver -b -a "nginx -t"
ansible homeserver -b -a "systemctl status tor nginx --no-pager"
ansible homeserver -b -a "ss -ltnp"
```

Confirm the Nginx listener is `127.0.0.1:8972`, not `0.0.0.0:8972` or `[::]:8972`.
On Ubuntu, the `tor` unit can be a wrapper; inspect the actual instance and its
bootstrap log as well:

```bash
ansible homeserver -b -a "systemctl status tor@default --no-pager"
ansible homeserver -b -a "journalctl -u tor@default -n 100 --no-pager"
```

Test HTTP reachability without credentials. Frigate's local self-signed
certificate is deliberately not verified in this diagnostic, matching the proxy:

```bash
ansible homeserver -b -m ansible.builtin.uri -a 'url=https://127.0.0.1:8971/ validate_certs=false follow_redirects=none status_code=200,301,302,401,403'
ansible homeserver -b -m ansible.builtin.uri -a 'url=http://127.0.0.1:8972/ follow_redirects=none status_code=200,301,302,401,403'
```

These checks accept a login page, redirect or authentication rejection. They prove
HTTP reachability only. A connection error points to the listener or container;
a proxy `502` points to the Nginx-to-Frigate connection. Inspect logs as needed:

```bash
ansible homeserver -b -a "tail -n 100 /var/log/nginx/error.log"
ansible homeserver -b -a "docker logs --tail 100 frigate"
ansible homeserver -b -a "cat /var/lib/tor/frigate/hostname"
```

Finally open `http://ONION_ADDRESS.onion` in a fresh Tor Browser session:

- Confirm that viewing cameras and recordings requires Frigate login.
- Sign in and check live view, recordings and navigation.
- Check playback independently: the onion mapping does not forward RTSP or
  WebRTC ports, even though HTTP/WebSocket requests are proxied.
- If local proxy checks pass but the onion address is unreachable, check Tor
  bootstrap/connectivity and the exact hostname before changing Frigate.

The current templates do not configure Tor client authorization. A reachable
login page is expected for anyone possessing the address; authenticated access
to private content must still be enforced by Frigate. Make any configuration fix
in Ansible and deploy it through the playbook, rather than editing server files.

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
- [ ] generated chart PNGs persist under their query IDs and match the returned images
- [ ] missing historical data produces a human-readable message
- [ ] query audit records are written to `reporting_audit`
- [ ] reporting cleanup timer is active
- [ ] `publish_queue` is excluded from automatic cleanup
- [ ] APScheduler runs scheduled jobs
- [ ] configured daily report jobs save PNGs without a browser request
- [ ] Frigate live streams work
- [ ] Frigate recordings are created
