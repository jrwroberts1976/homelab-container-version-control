# Stage 0 Baseline Findings

Baseline date: **23 August 2026**

Scope:

- `ids-01`
- `TestServer`

Collector: `scripts/inventory-images.sh` from PR #4.

The collector is read-only. No images were pulled and no containers were restarted or recreated during discovery.

## Estate summary

| Host | Containers | Compose-resolved | Local builds | Unmanaged | Reference drift |
|---|---:|---:|---:|---:|---:|
| ids-01 | 31 | 31 | 0 | 0 | 0 |
| TestServer | 32 | 28 | 3 | 1 | 3 |
| **Total** | **63** | **59** | **3** | **1** | **3** |

## ids-01 findings

- All 31 containers have a current Compose source.
- No declared-versus-running image drift was detected.
- No unmanaged containers were detected.
- 11 declarations use explicit version tags.
- 20 declarations use floating references.
- Most floating references belong to the vendor-supplied Greenbone Community Edition stack.

The Greenbone floating references require policy review. They must not be mass-pinned without checking the vendor's supported update and feed-container model.

## TestServer findings

- 28 registry-image services resolve from current Compose configuration.
- Three services are Compose-managed local builds.
- One container is not currently associated with Compose metadata.
- One service is digest-pinned.
- 24 services use explicit version tags.
- Four services use floating declarations.
- Three services have confirmed image-reference drift.

## Confirmed silent-downgrade risks

The current Compose declarations are older than the image references used to create the running containers.

| Service | Compose file | Current declaration | Running creation reference | Running image ID | Runtime health |
|---|---|---|---|---|---|
| Dozzle | `stacks/management/docker-compose.yml` | `amir20/dozzle:v10.7.1` | `amir20/dozzle:v10.7.2` | `sha256:f1480337d833...` | running; no healthcheck |
| LibreSpeed | `stacks/availability/docker-compose.yml` | `ghcr.io/librespeed/speedtest:6.1.0` | `ghcr.io/librespeed/speedtest:6.2.1` | `sha256:2378d760d872...` | running; healthy |
| Homepage | `stacks/dashboards/docker-compose.yml` | `ghcr.io/gethomepage/homepage:v1.12.2` | `ghcr.io/gethomepage/homepage:v2.0.0` | `sha256:c6194a6fea8a...` | running; healthy |

Recreating any of these stacks from the current Compose files may downgrade the service.

### Required response

Until reconciliation is complete:

- do not run an unreviewed `docker compose up -d` against these stacks;
- do not treat the running version as automatically approved;
- retain the current running image IDs as rollback evidence;
- review release compatibility, particularly the Homepage major-version difference;
- update desired state only through a reviewed change.

## Local-build services

These services use Compose `build:` rather than a registry image declaration:

- `projects-jrwroberts-co-uk`
- `crowdsec-exporter`
- `asus-exporter`

Image-tag drift is not sufficient for local builds. A later collector must record:

- build context;
- Dockerfile path;
- source Git commit;
- whether the source worktree was dirty;
- build timestamp and image ID;
- relevant build arguments without secret values.

## Unmanaged container

`birdnet-exporter` has no current Compose project/service metadata.

Required investigation:

1. identify its Dockerfile/build context;
2. locate the intended Compose service;
3. determine whether it is an orphan from an earlier project recreation;
4. bring it under an authoritative Compose source or record an approved exception.

## Source-control readiness finding

The TestServer Docker repository at `/home/james/docker` contains extensive tracked and untracked changes.

The modified files include all three drifted Compose files:

- `stacks/management/docker-compose.yml`
- `stacks/availability/docker-compose.yml`
- `stacks/dashboards/docker-compose.yml`

There are also many backup/autosync files and unrelated stack changes.

This is a deployment-automation blocker. Automation must not overwrite or broadly commit this worktree. Reconciliation must:

1. preserve unrelated modifications;
2. change only the exact approved image line;
3. validate the affected Compose file;
4. show a narrow diff before commit;
5. separate backup/generated files through repository hygiene rules;
6. establish a clean authoritative Git baseline before Renovate is enabled.

## Stage 0 status

Image discovery is substantially complete, but Stage 0 remains open.

Remaining exit-gate work:

- reconcile the three TestServer reference-drift findings;
- map `birdnet-exporter`;
- add local-build provenance collection;
- review floating-image exceptions;
- complete the secrets delivery-method inventory;
- establish a clean Git baseline for the host Compose repository.
