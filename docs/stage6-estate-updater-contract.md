# Stage 6 estate updater contract

## Purpose

Define the front-end contract for one controlled container-update workflow across the homelab while preserving the existing Stage 6 security boundaries.

The front end expresses high-level intent only. Reviewed repository data remains authoritative for every path, image identity, platform, health check and rollback action.

## Command contract

Target form:

```text
homelab-update --service <service> [--version <version>] [--hosts <host-list>] --action <action>
```

Required caller input:

- `--service`: approved logical service name;
- `--action`: one of `inspect`, `prepare`, `deploy`, `rollback`.

Optional caller input:

- `--version`: desired semantic application version. When omitted, resolve the service's reviewed desired version from the repository catalogue;
- `--hosts`: comma-separated approved target hosts. When omitted, resolve every reviewed host for that service.

The front end must reject unknown options, duplicate options, empty values, invalid service names, unknown hosts and unsupported actions.

## Inputs the caller must never control

The command line must not accept:

- Compose file paths;
- Compose project names;
- container names;
- arbitrary image references;
- image digests;
- Docker or Podman arguments;
- Kubernetes resource paths;
- shell fragments or commands;
- health-check commands/URLs;
- SSH usernames, key paths or sudo commands;
- rollback image identities.

Those values are resolved only from reviewed repository metadata and root-owned installed manifests.

## Desired-version rule

The preferred estate invariant is one approved semantic application version per service across every applicable host.

Example:

```text
prometheus desired version = 3.13.2

TestServer  linux/arm64 -> application version 3.13.2
ids-01     linux/amd64 -> application version 3.13.2
```

The platform-specific immutable digest may differ because a multi-architecture image can reference different manifests for `linux/arm64` and `linux/amd64`.

Version divergence is allowed only when documented as an explicit compatibility or platform exception.

## Repository model

The updater should resolve intent from reviewed data conceptually split into three layers.

### Desired-version catalogue

One reviewed desired application version per logical service.

Conceptual example:

```text
prometheus = 3.13.2
grafana = 13.2.0
loki = 3.7.7
```

The catalogue stores application intent, not arbitrary deployment commands.

### Service definition

Defines invariant service metadata such as:

- logical service name;
- upstream image repository;
- version/tag mapping rule where required;
- supported update backend;
- health-check type;
- allowed hosts;
- policy/exception metadata.

### Host/service manifest

Defines reviewed host-specific deployment facts such as:

- platform/architecture;
- Compose/Kubernetes identity;
- authority revision;
- reviewed configured image;
- immutable rollback identity;
- immutable candidate identity after preparation;
- mounts/ports/network expectations;
- protected/unrelated workloads;
- health contract.

## Action semantics

### `inspect`

Read-only across every selected host.

It must prove:

- selected service/host pair is reviewed;
- authority source matches the reviewed revision;
- live deployment definition matches reviewed source;
- runtime image/configuration matches the reviewed baseline;
- current application version is known;
- platform is known;
- health is acceptable;
- one-shot authority is not unexpectedly armed;
- no unrelated/protected workload drift is present.

No image pull, deployment, arm or file mutation is permitted.

### `prepare`

Resolve and acquire the candidate without changing the running workload.

It must:

- resolve the approved semantic version;
- map it to the reviewed configured image/tag format;
- verify upstream multi-architecture metadata;
- select the immutable platform manifest for each target host;
- acquire the image separately from deployment;
- verify local immutable identity;
- record candidate evidence for later approval;
- leave running containers/workloads unchanged and authority unarmed.

### `deploy`

Deployment remains human-approved and fail-closed.

The workflow must preserve the existing Stage 6 order:

1. pre-approval inspection;
2. evidence/archive generation;
3. explicit human approval;
4. post-approval inspection;
5. exact zero-drift proof;
6. executor credential availability only after zero drift;
7. one-shot arm for the exact reviewed update;
8. deploy the already-local immutable candidate;
9. health and unrelated-workload validation;
10. disarm after a proven terminal result.

No deployment-time image pull is allowed.

### `rollback`

Rollback must use only the reviewed immutable previous-known-good identity.

The caller cannot choose a rollback tag or digest. Eligibility remains controlled by the backend and manifest.

## Backend selection

The front end chooses a backend from reviewed metadata, never from a caller-provided command.

Initial backends:

- `docker-compose-stage6` for Docker Compose hosts such as TestServer and ids-01;
- future `kubernetes-stage6` for k3s-node-01.

Both backends must expose the same high-level action/result model even though their low-level deployment mechanics differ.

## Multi-host behaviour

A multi-host update is a coordinated set of host-specific transactions, not one shared unsafe transaction.

For each host the updater must maintain independent:

- inspection result;
- platform digest;
- candidate-acquisition evidence;
- approval/drift evidence;
- deployment result;
- health result;
- rollback eligibility/result.

A failure on one host must never cause uncontrolled mutation of another host. Results must identify exactly which hosts succeeded, failed, rolled back or were not attempted.

## Initial implementation order

1. Finish and prove Prometheus through the existing generic Stage 6 path.
2. Implement the front-end argument parser in read-only `inspect` mode only.
3. Make the front end resolve existing reviewed service manifests instead of duplicating service-specific logic.
4. Add `prepare` orchestration for candidate acquisition.
5. Route `deploy`/`rollback` through the existing guarded Stage 6 Jenkins/executor mechanisms rather than bypassing them.
6. Add ids-01 as the second Docker host.
7. Add desired-version catalogue enforcement and cross-host version reporting.
8. Add Kubernetes backend only after Docker coverage is proven.

## Minimum acceptance tests

Before the updater can be considered production-ready it must prove at least:

- unknown service fails before contacting a host;
- unknown host fails before contacting a host;
- invalid/duplicate action fails closed;
- arbitrary image/path/digest input cannot be supplied;
- read-only inspect causes zero runtime changes;
- same desired version resolves correct per-platform immutable digests on amd64 and arm64;
- post-approval drift prevents executor access/deployment;
- candidate absent at deploy time fails rather than pulling;
- one service can update without recreating unrelated containers;
- failed health check invokes only the reviewed rollback path when eligible;
- protected Jenkins/DinD workloads remain unchanged;
- final report clearly records per-host current, desired, deployed and rollback state.

## Definition of done

The estate updater is complete when every active in-scope workload is either:

1. managed and successfully tested through the generic updater;
2. explicitly documented as intentionally pinned/manual with a justified exception;
3. recorded as unsupported with framework work still required; or
4. approved as obsolete and removed.

No important workload should depend on an undocumented manual `docker pull` and recreation process.