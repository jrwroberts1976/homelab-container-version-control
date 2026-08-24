# Secrets Management

## Objective

Provide a controlled, recoverable way to supply container secrets without storing passwords, API tokens, private keys or other sensitive values in plaintext Git history or normal Compose environment declarations.

This is a mandatory go-live workstream for deployment automation.

## Initial technology choice

Use **SOPS + age** for encrypted secret files stored alongside deployment configuration.

Use **Docker Compose secrets** for delivery into containers where the application supports file-based secrets or `_FILE` conventions.

Use **Jenkins credentials** only for CI/deployment credentials and the minimum decryption material required by the pipeline.

Do not introduce Vault or Infisical in the first production stage. Reassess a central secrets platform after the simpler encrypted-Git model is proven and operationally understood.

## Principles

1. No plaintext secrets in Git.
2. No age private key in Git.
3. Prefer secret files over environment variables for sensitive values.
4. Grant each service access only to the secrets it needs.
5. Materialise plaintext only for the shortest practical period during deployment.
6. Set restrictive file permissions on decrypted material.
7. Never echo secret values in Jenkins logs.
8. Rotate exposed or migrated credentials where practical.
9. Back up decryption keys separately from the Git repository.
10. Test secret recovery before declaring the secrets workstream complete.

## Proposed repository pattern

```text
secrets/
├── README.md
├── ids-01/
│   └── <stack>.sops.yaml
└── testserver/
    └── <stack>.sops.yaml
```

Only encrypted SOPS files are committed.

Example encrypted source structure before encryption:

```yaml
secrets:
  api_token: "..."
  database_password: "..."
```

## Deployment pattern

```text
SOPS-encrypted file
      |
      | age identity supplied securely
      v
controlled decrypt step
      |
      v
root-owned temporary secret files (0600)
      |
      v
Docker Compose `secrets:`
      |
      v
/run/secrets/<secret_name>
```

After deployment, temporary plaintext material must be removed unless the service requires a host-backed secret file to remain available. Persistent host secret files must live outside the repository and use restrictive ownership/permissions.

## Applications that only support environment variables

Some containers do not support secret files. These are temporary policy exceptions.

For such services:

- keep the encrypted source in SOPS;
- decrypt/inject only at deployment time;
- do not commit generated `.env` files;
- avoid writing plaintext environment files to long-lived shared locations;
- document the exception and target remediation;
- remember that container environment values may be visible through container inspection to users with Docker access.

## Jenkins handling

Jenkins should hold only:

- the age decryption identity or a narrowly scoped mechanism to access it;
- registry credentials where private registries require them;
- deployment credentials/SSH keys if remote deployment is later introduced.

Pipelines must mask credentials and must not persist decrypted secret files in build artifacts or workspaces after completion.

## Key management

### age identity

The private age identity is a critical recovery asset.

Required controls:

- primary deployment copy stored with restrictive permissions;
- offline backup stored separately from the server and repository;
- recovery procedure documented;
- recovery tested before Stage 5 pilot deployment;
- key rotation procedure documented before production rollout.

### Recipient changes

When an age key is rotated or an authorised deployment identity changes, encrypted files must be re-encrypted to the approved recipient set.

## Secret inventory

Stage 0 must identify, per service:

- secret name/purpose;
- current storage location;
- current injection method;
- whether it is present in an `.env` file;
- whether the service supports Docker secret files;
- rotation impact;
- owner/source system;
- migration status.

Actual secret values must never be copied into the inventory.

## Stage 0 discovery result

The names-only collector was validated against all 30 TestServer containers on 23 August 2026.

The initial collector reported four services using environment-variable delivery:

| Service | Sensitive name |
|---|---|
| `autokuma` | `AUTOKUMA__KUMA__PASSWORD` |
| `librespeed` | `PASSWORD` |
| `duckdns` | `TOKEN` |
| `cloudflare-ddns` | `CLOUDFLARE_API_TOKEN` |

The remaining 26 containers had no sensitive delivery method detected by the collector. No Compose-secret, sensitive-mount or sensitive build-argument delivery was detected.

This is a delivery-method inventory, not proof that a name contains a valid or non-empty secret. Values and secret-file contents were intentionally excluded.

Stage 2 review found that LibreSpeed's `PASSWORD` is an unused image default in standalone, telemetry-disabled mode rather than a managed credential. It also found a genuine item missed by the original name matcher: Uptime Kuma consumes `KUMA_SMTP_PASSWORD` as `UPTIME_KUMA_SMTP_PASS`. Future discovery must recognise `_PASS` as well as `PASSWORD`, `TOKEN`, `SECRET` and `KEY`.

Each genuine environment-delivered item requires file-based delivery or a documented exception and must remain outside plaintext Git.

## Go-live gates

Deployment automation cannot progress to production until:

- all production secrets are inventoried;
- no known plaintext secrets are committed to the project repository;
- age private-key backup and recovery are tested;
- pilot services can consume secrets without manual plaintext copying;
- Jenkins can execute validation/deploy jobs without printing secret values;
- remaining environment-variable exceptions are explicitly documented.

## Future review: central secrets platform

After the initial SOPS + age operating model is stable, evaluate whether Infisical, Vault or another central secrets service would materially improve:

- dynamic secret rotation;
- central audit logs;
- short-lived credentials;
- service identity;
- multi-host secret distribution;
- operator access control.

A central platform should only be added if its operational value outweighs the availability and recovery dependency it introduces.

## Verified Compose-secret pilot: Grafana SMTP

The first production Docker Compose secret adoption was completed on `ids-01` on 24 August 2026.

Grafana now receives its Gmail application password through:

```text
GF_SMTP_PASSWORD__FILE=/run/secrets/grafana_smtp_password
```

The source file is maintained outside Git under `/home/james/docker/secrets`. The parent directory is mode `0700`. The file is mode `0444` so the non-root Grafana container can read the bind mount while other host users cannot traverse the protected directory.

Validation established that:

- the rotated credential authenticated directly with Gmail;
- Grafana resolved the `_FILE` setting successfully;
- the Grafana health endpoint remained healthy;
- the email contact-point test delivered successfully;
- no direct password remained in active Compose, `.env` or the container environment;
- all 29 alert rules survived the scoped Grafana recreation;
- 303 retired Compose copies containing the rotated password were removed.

This pilot proves the Compose-secret delivery pattern. It does not complete Stage 2: remaining environment-delivered secrets, SOPS and age recovery, Jenkins handling and recovery testing still require implementation.

### Grafana variable register

| Variable | Consumer | Delivery | Classification |
|---|---|---|---|
| `GF_SMTP_ENABLED` | Grafana | Compose environment | Configuration |
| `GF_SMTP_HOST` | Grafana | Compose environment | Configuration |
| `GF_SMTP_USER` | Grafana | Compose environment | Sensitive identifier |
| `GF_SMTP_FROM_ADDRESS` | Grafana | Compose environment | Sensitive identifier |
| `GF_SMTP_SKIP_VERIFY` | Grafana | Compose environment | Security configuration |
| `GF_SMTP_PASSWORD__FILE` | Grafana entrypoint | Runtime secret path | Secret reference |
| `GF_SMTP_PASSWORD` | Grafana runtime | Derived from mounted file | Secret |
| `GRAFANA_TOKEN` | Alert deployment tooling | Protected stack `.env` | Secret |

Secret path mapping:

- Host source: `/home/james/docker/secrets/grafana-smtp-password`
- Compose name: `grafana_smtp_password`
- Container mount: `/run/secrets/grafana_smtp_password`
- Grafana reference: `GF_SMTP_PASSWORD__FILE`

Only names, consumers and delivery locations are recorded. Secret values are excluded.

## Verified Compose-secret pilot: Cloudflare DDNS

The second production Compose-secret adoption was completed on `TestServer` on 24 August 2026.

The `favonia/cloudflare-ddns:1.17.0` container now consumes its token through:

```text
CLOUDFLARE_API_TOKEN_FILE=/run/secrets/cloudflare_api_token
```

Variable and path register:

| Item | Consumer or location | Classification |
|---|---|---|
| `CLOUDFLARE_API_TOKEN_FILE` | Cloudflare DDNS configuration | Secret reference |
| `CLOUDFLARE_API_TOKEN` | Derived internally from the mounted file | Secret |
| `cloudflare_api_token` | Docker Compose secret name | Secret reference |
| `/home/james/docker/secrets/cloudflare-api-token` | Host source, mode `0400` | Secret |
| `/run/secrets/cloudflare_api_token` | Read-only container mount | Secret |
| `DOMAINS` | Cloudflare DDNS | Configuration |
| `PROXIED` | Cloudflare DDNS | Configuration |
| `IP6_PROVIDER` | Cloudflare DDNS | Configuration |

Validation established that direct environment delivery was removed, the native `_FILE` interface loaded the token, the container retained image `1.17.0` with zero restarts, and the managed DNS record was already up to date.

The plaintext stack `.env` was removed. No related plaintext declaration remained under the active stacks tree. The desired-state change was merged into `jrwroberts1976/docker-env/main` at revision `e557f924`.

## Verified Compose-secret pilot: DuckDNS

The third production Compose-secret adoption was completed on `TestServer` on 24 August 2026.

LinuxServer DuckDNS now consumes its token through:

```text
FILE__TOKEN=/run/secrets/duckdns_token
```

Variable and path register:

| Item | Consumer or location | Classification |
|---|---|---|
| `FILE__TOKEN` | LinuxServer environment initialisation | Secret reference |
| `TOKEN` | DuckDNS runtime; derived from mounted file | Secret |
| `DUCKDNS_TOKEN` | Retired stack `.env` variable | Retired secret delivery |
| `duckdns_token` | Docker Compose secret name | Secret reference |
| `/home/james/docker/secrets/duckdns-token` | Host source, mode `0400` | Secret |
| `/run/secrets/duckdns_token` | Read-only container mount | Secret |
| `PUID` / `PGID` | LinuxServer runtime identity | Configuration |
| `TZ` | Container timezone | Configuration |
| `SUBDOMAINS` | Managed DuckDNS names | Sensitive identifier |
| `UPDATE_IP` | Address-family policy | Configuration |

Validation established that LinuxServer env-init resolved `TOKEN` from `FILE__TOKEN`, the DuckDNS request succeeded, the pinned image and zero restart count were retained, and Authelia and Nginx Proxy Manager were not recreated.

The plaintext stack `.env` was removed and the desired state was merged into `docker-env/main` at revision `1724f2ce`.


## Verified Compose-secret pilot: AutoKuma

The fourth production Compose-secret adoption completed on `TestServer` on 24 August 2026.

AutoKuma v2.0.0 does not implement the `@/run/secrets/...` file syntax described in later development documentation. A controlled Compose startup wrapper therefore reads the mounted secret, exports the runtime variable inside the container process and then replaces the shell with AutoKuma.

### AutoKuma variable and path register

| Item | Consumer or location | Delivery/status | Classification |
|---|---|---|---|
| `AUTOKUMA_KUMA_PASSWORD` | Retired shared stack `.env` variable | Removed after migration | Retired secret delivery |
| `AUTOKUMA__KUMA__PASSWORD` | AutoKuma v2.0.0 process | Exported by startup wrapper from mounted file; absent from Docker Config environment | Secret |
| `AUTOKUMA_KUMA_USERNAME` | Compose interpolation | Retained once after duplicate normalisation | Sensitive identifier |
| `AUTOKUMA__KUMA__USERNAME` | AutoKuma runtime | Derived from `AUTOKUMA_KUMA_USERNAME` | Sensitive identifier |
| `AUTOKUMA__KUMA__URL` | AutoKuma runtime | Compose environment | Configuration |
| `autokuma_kuma_password` | Docker Compose | Service attachment and top-level secret name | Secret reference |
| `/home/james/docker/secrets/autokuma-kuma-password` | TestServer host | Outside Git; protected parent directory; file readable by the container | Secret |
| `/run/secrets/autokuma_kuma_password` | AutoKuma container | Read-only Compose-secret mount | Secret |
| `KUMA_SMTP_PASSWORD` | Retired shared availability `.env` variable | Removed after proving the SMTP block unused | Retired unused secret source |
| `UPTIME_KUMA_SMTP_PASS` | Retired Uptime Kuma container variable | Removed; no implementation reference in version 1.23.16 | Retired unused configuration |

Validation established that:

- the only source declaration matching the known-good runtime credential was used and the stale duplicate was excluded;
- the first unsupported native-file attempt failed authentication and rolled back automatically;
- the compatibility wrapper subsequently authenticated successfully;
- Docker Config contains no direct `AUTOKUMA__KUMA__PASSWORD` entry;
- the secret mount is read-only and the wrapper command references the mounted file;
- AutoKuma remained running with zero restarts and no recent authentication errors;
- Uptime Kuma, LibreSpeed and Smokeping were not recreated;
- the desired state was merged into `docker-env/main` at revision `ef31441`.

Only variable names, consumers, paths and delivery methods are recorded. Credential values are excluded.

## LibreSpeed classification

LibreSpeed `ghcr.io/librespeed/speedtest:6.2.1` exposes a runtime `PASSWORD` value from the image, but the active stack declares neither `PASSWORD` nor a corresponding `.env` entry. The observed length matched the image default exactly, while `MODE=standalone` and `TELEMETRY=false`. It is therefore a Stage 0 discovery false positive and requires no secret migration in the current configuration.


## Retired configuration: Uptime Kuma SMTP environment block

A read-only source, entrypoint, runtime and database review on 24 August 2026 established that Uptime Kuma 1.23.16 does not consume the six SMTP environment variables present in the availability Compose file. The notification table also contained zero rows.

### Retired Uptime Kuma variable register

| Variable | Former consumer/location | Final status | Classification |
|---|---|---|---|
| `KUMA_SMTP_PASSWORD` | Shared availability `.env` | Removed | Retired unused secret source |
| `UPTIME_KUMA_SMTP_HOST` | Uptime Kuma Docker environment | Removed; no implementation reference | Retired unused configuration |
| `UPTIME_KUMA_SMTP_PORT` | Uptime Kuma Docker environment | Removed; no implementation reference | Retired unused configuration |
| `UPTIME_KUMA_SMTP_SECURE` | Uptime Kuma Docker environment | Removed; no implementation reference | Retired unused configuration |
| `UPTIME_KUMA_SMTP_USER` | Uptime Kuma Docker environment | Removed; no implementation reference | Retired sensitive identifier |
| `UPTIME_KUMA_SMTP_PASS` | Uptime Kuma Docker environment | Removed; no implementation reference | Retired unused secret delivery |
| `UPTIME_KUMA_SMTP_FROM` | Uptime Kuma Docker environment | Removed; no implementation reference | Retired sensitive identifier |

Validation established that:

- zero files under `/app` referenced `UPTIME_KUMA_SMTP`;
- the entrypoint provided no `_FILE`, `FILE__` or other relevant secret-file handling;
- the notification table contained zero rows;
- the scoped Uptime Kuma recreation returned healthy with zero restarts;
- the recreated container had zero `UPTIME_KUMA_SMTP_*` variables;
- AutoKuma, LibreSpeed and Smokeping retained their original container identities;
- the shared `.env` now contains only `AUTOKUMA_KUMA_USERNAME`;
- the retirement was merged into `docker-env/main` at revision `a4711b4`.

This finding reinforces a two-step inventory rule: first detect potentially sensitive names, including suffixes such as `_PASS`; then verify that the application actually consumes the declaration before designing a migration.
