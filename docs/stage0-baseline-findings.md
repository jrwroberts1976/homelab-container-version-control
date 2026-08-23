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

These three declarations were reconciled on **23 August 2026** to the verified running references. All three Compose files passed `docker compose config --quiet`, and the post-change inventory reported zero `yes-reference` findings. No containers were restarted during reconciliation.

The files remain uncommitted within the wider dirty TestServer Docker worktree and therefore still require a controlled baseline commit.

### Required response

Until the reconciled files are committed into the authoritative baseline:

- do not run an unreviewed `docker compose up -d` against these stacks;
- retain the current running image IDs as rollback evidence;
- review the complete stack diffs, which also contain prior pinning and Watchtower-removal work;
- preserve unrelated worktree changes;
- commit the approved desired state through a narrow, reviewed baseline change.

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

## Worktree hygiene progress

A non-destructive hygiene pass was completed on **23 August 2026**.

Targeted ignore rules were added for:

- `*.bak` and `*.bak-*`;
- `*.backup` and `*.backup-*`;
- `*.pre-*`;
- `*.autosync-*`;
- dated `engineering-portfolio-backup-*` trees;
- dated `engineering-portfolio-old-*` trees.

No files were deleted, staged or committed.

### Result

| Worktree category | Before hygiene | After hygiene |
|---|---:|---:|
| Total visible status entries | 394 | 31 |
| Backup/autosync artifacts removed from status | 310 | 0 visible |
| Archived portfolio-tree entries removed from status | 54 | 0 visible |
| Tracked modifications | 12 | 13, including `.gitignore` |
| Tracked deletions | 6 | 6 |
| Operational untracked candidates | 12 | 12 |

The remaining untracked candidates are:

- root maintenance enable/disable scripts;
- TestServer Alloy Compose source;
- `engineering-portfolio-git/`;
- Jenkins Dockerfile and Compose placeholders;
- maintenance-page scripts, change metadata and Nginx configuration;
- training-platform `.gitignore`;
- WUD Compose source.

### Jenkins placeholder finding

The untracked files below are both currently zero bytes:

- `stacks/jenkins/Dockerfile`;
- `stacks/jenkins/docker-compose.yml`.

They must not be committed as valid Jenkins deployment configuration. They require reconstruction from the active Jenkins deployment or removal from the staging manifest after confirming they are unused placeholders.

### Baseline-commit control

A broad `git add -A` remains prohibited. The baseline must use an explicit staging manifest after:

1. reviewing the six tracked training-document deletions;
2. checking the 12 operational candidates;
3. validating all changed Compose files;
4. checking for nested repositories;
5. checking for plaintext secrets;
6. deciding which duplicate maintenance scripts are authoritative.

## TestServer Git baseline commit

A controlled local baseline commit was created on **23 August 2026**:

- branch: `baseline/testserver-20260823`;
- commit: `ebc764c`;
- message: `Establish TestServer Docker configuration baseline`;
- files changed: 24;
- insertions: 837;
- deletions: 283.

The commit includes the approved Compose/configuration changes, worktree hygiene rules, full maintenance-page controls, Alloy and WUD Compose sources, and the training-page removals already reflected in the inner training repository.

Pre-commit controls passed:

- staged whitespace/error check;
- explicit path manifest;
- no broad `git add -A`;
- no secret-like staged filenames;
- affected Compose validation;
- no deployment or container restart.

The only remaining top-level status item is the pre-existing dirty nested repository at `stacks/training-platform/training-platform-manager.backup`. It was not staged.

The baseline branch has not yet been pushed or merged into the Docker repository's main branch.

## Stage 0 status

Image discovery is substantially complete, but Stage 0 remains open.

Remaining exit-gate work:

- commit the reconciled TestServer desired-state changes into the authoritative baseline;
- map `birdnet-exporter`;
- add local-build provenance collection;
- review floating-image exceptions;
- complete the secrets delivery-method inventory;
- establish a clean Git baseline for the host Compose repository.
