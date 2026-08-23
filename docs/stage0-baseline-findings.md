# Stage 0 Baseline Findings

Baseline completed: **23 August 2026**

## Scope and safety

Stage 0 covered the Docker estates on `ids-01` and `TestServer`.

The following read-only collectors were used:

- `scripts/inventory-images.sh` for Compose ownership, declared images and runtime drift;
- `scripts/local-build-provenance.sh` for local-build source provenance;
- `scripts/secret-delivery-inventory.sh` for names-only secret-delivery classification.

The collectors do not pull or build images, restart containers, print secret values, or read secret-file contents.

## Final estate summary

| Host | Containers | Registry-image services | Local builds | Unmanaged | Registry-image drift |
|---|---:|---:|---:|---:|---:|
| ids-01 | 31 | 31 | 0 | 0 | 0 |
| TestServer | 30 | 25 | 5 | 0 | 0 |
| **Total** | **61** | **56** | **5** | **0** | **0** |

The earlier 63-container discovery snapshot changed during controlled cleanup:

- `birdnet-exporter` was adopted into the `birdnet-go` Compose project;
- the obsolete stopped `asus-exporter` container was retired after its systemd/textfile replacement was verified;
- the inactive `training-platform` container and Compose definition were retired with recovery documentation.

No active service was removed without replacement or pre-retirement validation.

## Image reconciliation

Three TestServer declarations were older than their verified running creation references:

| Service | Previous declaration | Reconciled declaration |
|---|---|---|
| Dozzle | `amir20/dozzle:v10.7.1` | `amir20/dozzle:v10.7.2` |
| LibreSpeed | `ghcr.io/librespeed/speedtest:6.1.0` | `ghcr.io/librespeed/speedtest:6.2.1` |
| Homepage | `ghcr.io/gethomepage/homepage:v1.12.2` | `ghcr.io/gethomepage/homepage:v2.0.0` |

The reconciliation changed desired state only. Compose validation passed, no containers were restarted, and the final inventory reports zero registry-image drift.

## Compose ownership and cleanup

### BirdNET exporter

The previously unmanaged `birdnet-exporter` was rebuilt and recreated through the authoritative `birdnet-go` Compose definition.

Acceptance evidence:

- Compose project: `birdnet-go`;
- Compose service: `birdnet-exporter`;
- Prometheus target `birdnet-exporter:9105`: up;
- BirdNET metrics preserved;
- prior image retained with a rollback tag;
- temporary stopped rollback container removed after validation.

### ASUS exporter

The stopped Docker `asus-exporter` was superseded by `asus-router-temp.timer` and node-exporter textfile metrics.

Before retirement:

- the systemd collector was healthy and running every minute;
- all three routers reported `asus_router_up = 1`;
- Prometheus exposed the replacement metrics;
- no alert or dashboard depended on the old exporter.

The obsolete Compose service, scrape job and stopped container were removed. The previous image remains rollback-tagged.

### Training Platform

The stopped `training-platform` container had no listener, no Nginx Proxy Manager route, and its public path returned HTTP 404.

Its active Compose definition was removed, a retirement/recovery document was committed to `docker-env`, and the previous image remains rollback-tagged.

## Local-build provenance

Five active Compose local builds remain:

| Service | State | Source assessment |
|---|---|---|
| `projects-jrwroberts-co-uk` | running | source clean; no OCI revision label |
| `crowdsec-exporter` | running | source clean; no OCI revision label |
| `birdnet-exporter` | running | source clean; no OCI revision label |
| `engineering-portfolio` | running | source dirty; no OCI revision label |
| `jenkins` | running | build source not associated with a Git worktree; image revision label present |

These are not treated as tag drift. Stage 1 must define provenance and revision-label requirements for local builds.

## Secret-delivery inventory

The corrected names-only collector was validated against all 30 TestServer containers.

| Delivery classification | Containers |
|---|---:|
| Environment variable | 4 |
| No sensitive method detected | 26 |
| Compose secret | 0 |
| Sensitive mount | 0 |
| Sensitive build argument | 0 |

Environment-variable names detected:

| Service | Name |
|---|---|
| `autokuma` | `AUTOKUMA__KUMA__PASSWORD` |
| `librespeed` | `PASSWORD` |
| `duckdns` | `TOKEN` |
| `cloudflare-ddns` | `CLOUDFLARE_API_TOKEN` |

No values were recorded. Public `PUBLIC_GRAFANA_*` build arguments were correctly excluded after host validation.

These four services are inputs to Stage 2 migration planning; environment delivery remains an explicit exception until application support and migration impact are assessed.

## Git baseline

The authoritative TestServer Docker baseline was merged into `docker-env/main` through PR #1.

Subsequent controlled changes were merged separately:

- BirdNET exporter Compose adoption: docker-env PR #2;
- ASUS exporter retirement: docker-env PR #3;
- Training Platform retirement: docker-env PR #4.

The only residual top-level status item is the deliberately excluded dirty nested backup repository at `stacks/training-platform/training-platform-manager.backup`.

## Stage 0 exit decision

**Stage 0 passed on 23 August 2026.**

Exit evidence:

- every running container is represented in inventory;
- all running containers have authoritative Compose ownership;
- registry-image drift is zero;
- local builds have source-provenance classifications;
- TestServer secret-delivery methods were inventoried without recording values;
- rollback images were retained for controlled retirements;
- the authoritative TestServer Git baseline is merged.

Stage 1 now owns image-version policy, downgrade controls, exception records, local-build provenance rules and rollback metadata requirements.
