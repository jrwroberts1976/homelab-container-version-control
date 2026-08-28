# Stage 6 generic Jenkins service-update pipeline

## Goal

Use one Jenkins approval pipeline for every Stage 6 eligible registry-image service. Adding a service/update must require reviewed data in a service manifest, not a new service-specific Jenkinsfile.

## Pipeline

`Jenkinsfile.stage6-service-update` accepts one parameter:

- `STAGE6_MANIFEST`: a reviewed manifest filename under `config/services`.

The filename must match the pipeline allow-list and cannot contain a path separator or traversal sequence. The pipeline resolves it only beneath the fixed `config/services` directory, runs the Stage 6 schema/cross-field validator, and then derives the service, update ID, authority revision, Compose SHA, rollback identity, candidate identity, platform and health contract from the manifest.

No image reference, digest, Compose path or service name is accepted as an independent Jenkins execution argument.

## Preserved security ordering

The generic pipeline keeps the proven Stage 6 sequence:

1. checkout reviewed source;
2. validate the selected manifest and generic framework source;
3. run the first read-only inspection with only the inspector credential;
4. prove the installed manifest and inspector match reviewed source;
5. archive the full critical state;
6. require explicit human approval;
7. run a second read-only inspection;
8. require exact zero drift;
9. only then bind the executor credential;
10. arm the exact manifest-derived update ID;
11. deploy the exact manifest candidate through the root-owned generic helper;
12. use only the reviewed rollback path on an eligible deployment failure;
13. disarm after a proven terminal result;
14. archive the evidence.

The executor credential remains unavailable before the zero-drift gate.

## Health is manifest-driven

The pipeline does not assume one service health mechanism.

- `docker-health` manifests compare the inspection/execution result with the manifest expected health state.
- `http` manifests compare with the Stage 6 `http-<status>` result derived from the manifest expected HTTP status.

This allows the same pipeline to handle different eligible service health contracts without service-specific code.

## Semantic version and configured image are separate identities

Stage 6 must not assume that an application's semantic version is identical to its Docker tag.

For example, Prometheus uses semantic version `3.13.1` while the reviewed configured Docker image is `prom/prometheus:v3.13.1`. The service manifest therefore carries these facts independently:

- `versions.rollback.version` — semantic application version used for ordering and policy;
- `versions.rollback.configured_image` — exact tagged image expected in Compose and Docker `Config.Image` while the rollback baseline is live;
- `versions.rollback.immutable_ref` — digest-pinned rollback identity used for immutable execution;
- candidate semantic version, immutable index/platform identity and local config digest as separate reviewed facts.

The generic inspector and Jenkins baseline checks compare Compose/runtime state with the reviewed `configured_image`. They must not construct a Docker tag by concatenating `image_repository` and semantic `version`.

## Candidate acquisition is separate from deployment

A candidate must already be locally available and cryptographically verified before deployment authority is armed.

The reviewed preparation step should:

- resolve the approved version/tag externally to the deployment transaction;
- verify the immutable index and required platform manifest;
- acquire the exact immutable candidate;
- verify local image ID, platform and repository digest;
- capture creation/revision metadata where available;
- leave the running workload unchanged and one-shot authority disarmed.

Deployment runs with Compose pull policy `never`. An absent candidate must fail closed rather than trigger a deployment-time pull.

## Runtime exceptions remain narrow reviewed contracts

The generic framework supports ordinary services with `runtime.docker_socket_allowed=false` and requires zero Docker socket mounts in that case.

A narrow extension now supports services such as Homepage that require the Docker socket. The reviewed contract is deliberately restrictive:

- `risk_class=medium`;
- `runtime.docker_socket_allowed=true`;
- exactly one bind from `/var/run/docker.sock` to `/var/run/docker.sock`;
- `rw=false`;
- `source_kind=socket`;
- the host source must be a Unix socket;
- writable, alternate-path, duplicate, low-risk and policy/mount mismatch cases are rejected.

A read-only bind does not make the Docker API read-only. The capability therefore remains a medium-risk exception rather than a general safe-default mount.

## Source guard

`scripts/validate-stage6-generic-jenkins-pipeline.py` rejects service/image hard-coding, unsafe manifest/service selectors, missing approval/zero-drift gates, premature executor credentials, direct Docker/sudo/shell authority, raw executor-key use and weakened execution-result assertions.

Run the full source review with:

```bash
bash scripts/validate-stage6-generic-jenkins-service-update.sh
```

The regression suite also verifies runtime JSON canonicalization and the positive/negative Docker socket contract.

## Existing service-specific Jenkinsfiles

Existing Dashy-specific Stage 6 Jenkinsfiles remain historical pilot/smoke evidence. They are not the template for onboarding additional services. New eligible services should use the generic pipeline plus a reviewed manifest.

## Validated generic pilots

### Prometheus

Prometheus `3.13.1 -> 3.13.2` proved the generic manifest model and HTTP health strategy.

Build #6 deployed the exact candidate and the workload remained healthy, but Jenkins reported historical `FAILURE` because equivalent published-port JSON objects were compared without canonical key ordering. The executor comparison was fixed by canonicalizing JSON before equality checks. Recovery preserved the already-running candidate, retained consumed evidence and removed one-shot authority without recreating the container.

This incident is important evidence that Stage 6 failed visibly on an artifact-validation defect without losing the immutable deployment state, and that recovery could be performed without ad-hoc container mutation.

### Homepage

Homepage `2.0.0 -> 2.1.2` proved a second generic workload class:

- `docker-health` rather than HTTP health;
- `risk_class=medium`;
- no published ports;
- three persistent directory binds;
- one exact read-only `/var/run/docker.sock` bind under the reviewed socket exception;
- immutable candidate acquired before deployment.

Jenkins Build #8 completed successfully. The pipeline proved the pre-approval fail-closed state, accepted explicit approval, performed a second exact zero-drift inspection, exposed executor credentials only after zero drift, armed the exact update, deployed the immutable candidate, validated host-side invariants and health, skipped rollback because deployment succeeded, disarmed one-shot authority and archived artifacts.

Independent host-side verification confirmed Homepage v2.1.2 running healthy with restart count zero, the exact immutable candidate image ID/ref, the socket contract retained, `homepage_armed=false`, consumed evidence present, and protected Jenkins/Jenkins-DinD/Prometheus state unchanged.

## Estate-wide orchestration direction

The intended operating model is one generic update front end rather than one update script per service.

The caller should supply only high-level intent, conceptually:

```text
service=<service>
version=<desired application version>
hosts=<approved target hosts>
action=inspect|prepare|deploy|rollback
```

The caller must not supply arbitrary Compose paths, image digests, shell fragments, health URLs or Docker arguments. Those values remain derived from reviewed service/host definitions and manifests.

Where the same service runs on multiple servers, Stage 6 should converge them on the same approved application version wherever the upstream image supports every required architecture. Platform-specific immutable digests may differ between `linux/amd64` and `linux/arm64`; application version consistency is the desired estate-level invariant.

The long-term front end should therefore be able to express intent such as:

```text
homelab-update --service prometheus --version 3.13.2 --hosts TestServer,ids-01 --action inspect
```

while preserving the existing read-only inspection, human approval, zero-drift, one-shot authority, immutable execution, health validation and rollback controls behind that interface.

Kubernetes workloads should eventually use the same high-level service/version intent and desired-version catalogue, but select a Kubernetes rollout backend rather than the Docker Compose execution backend.

See `docs/stage6-estate-updater-contract.md` for the full front-end contract.

## Stage 6 completion criterion

Stage 6 is not considered complete after proving only a small number of pilots. Before moving on to unrelated infrastructure work, every actively used container/workload in scope must be classified and have a documented update path.

The estate-wide completion report should identify, for each service and host:

- current and desired application version;
- architecture/platform;
- reviewed immutable image identity;
- update backend (Docker Compose or Kubernetes);
- inspection/approval state;
- health validation method;
- rollback method;
- status as managed/tested, intentionally manual/pinned, unsupported pending framework work, or obsolete/removable.

The preferred steady state is one desired application version per service across all applicable hosts, with only justified platform or service exceptions documented.

## Checkpoint — 28 August 2026

By the final checkpoint on 28 August 2026:

- Prometheus `3.13.2` is live and healthy after the Build #6 false-negative was understood and the JSON canonicalization defect fixed;
- the socket-capable framework is merged, regression-tested and installed from reviewed source;
- Homepage `2.1.2` is live and healthy after successful generic Jenkins Build #8;
- Homepage is disarmed with consumed evidence retained;
- the medium-risk read-only Docker socket workload class has been proven end-to-end;
- protected Jenkins/Jenkins-DinD state remained unchanged during the Homepage pilot;
- no Stage 6 deployment is left partially armed.

The next development focus is the estate-wide workload coverage matrix and the high-level read-only `homelab-update ... --action inspect` front end, followed by a second Docker host (`ids-01`) and cross-architecture desired-version reporting.
