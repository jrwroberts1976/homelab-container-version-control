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

For example, Prometheus uses semantic version `3.13.1` while the reviewed configured Docker image is `prom/prometheus:v3.13.1`. The service manifest therefore carries both facts independently:

- `versions.rollback.version` — application version used for version ordering and policy;
- `versions.rollback.configured_image` — exact tagged image expected in Compose and Docker `Config.Image`;
- `versions.rollback.immutable_ref` — digest-pinned rollback identity used for immutable execution.

The generic inspector and Jenkins baseline checks compare Compose/runtime state with the reviewed `configured_image`. They must not construct a Docker tag by concatenating `image_repository` and semantic `version`.

## Estate-wide orchestration direction

The intended operating model is one generic update front end rather than one update script per service.

The caller should supply only high-level intent, conceptually:

```text
service=<service>
version=<desired application version>
hosts=<approved target hosts>
action=inspect|prepare|deploy|rollback
```

The caller must not supply arbitrary Compose paths, image digests, shell fragments or Docker arguments. Those values remain derived from reviewed service/host definitions and manifests.

Where the same service runs on multiple servers, Stage 6 should converge them on the same approved application version wherever the upstream image supports every required architecture. Platform-specific immutable digests may differ between `linux/amd64` and `linux/arm64`; application version consistency is the desired estate-level invariant.

The long-term front end should therefore be able to express intent such as:

```text
homelab-update --service prometheus --version 3.13.2 --hosts TestServer,ids-01
```

while preserving the existing read-only inspection, human approval, zero-drift, one-shot authority, immutable execution, health validation and rollback controls behind that interface.

Kubernetes workloads should eventually use the same high-level service/version intent and desired-version catalogue, but select a Kubernetes rollout backend rather than the Docker Compose execution backend.

## Stage 6 completion criterion

Stage 6 is not considered complete after proving only Dashy and Prometheus. Before moving on to unrelated infrastructure work, every actively used container/workload in scope must be classified and have a documented update path.

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

## Source guard

`scripts/validate-stage6-generic-jenkins-pipeline.py` rejects service/image hard-coding, unsafe manifest/service selectors, missing approval/zero-drift gates, premature executor credentials, direct Docker/sudo/shell authority, raw executor-key use and weakened execution-result assertions.

Run the full source review with:

```bash
bash scripts/validate-stage6-generic-jenkins-service-update.sh
```

## Existing service-specific Jenkinsfiles

Existing Dashy-specific Stage 6 Jenkinsfiles remain historical pilot/smoke evidence. They are not the template for onboarding additional services. New eligible services should use the generic pipeline plus a reviewed manifest.

## Checkpoint — 28 August 2026

The generic TestServer Stage 6 control plane is installed and Dashy remains historical pilot evidence. Prometheus is the current second-service proof.

Current Prometheus baseline:

- running image: `prom/prometheus:v3.13.1`;
- container remained running with zero restart-count change during the preparation work;
- readiness endpoint returned HTTP 200;
- Stage 6 one-shot authority remained unarmed;
- reviewed Compose source and live Compose were reconciled without recreating Prometheus.

Pre-approval inspection exposed the semantic-version/Docker-tag modelling defect described above. The generic model fix was prepared and fully regression-tested. Pull request #54 contains the exact seven-file reviewed patch at commit `9c138a65307fdfafa803469f6c7a4a6765b7ae8d` and remains separate from this documentation change.

Next controlled sequence:

1. review and merge PR #54 only if its head and checks remain exact;
2. install the merged/pinned framework and manifest changes on TestServer;
3. rerun `inspect prometheus`;
4. if required, perform the separately reviewed candidate-acquisition step for `v3.13.2`;
5. reach `ready-for-human-review` before any arm/deploy action;
6. complete the Prometheus deployment/rollback proof before broad estate onboarding.
