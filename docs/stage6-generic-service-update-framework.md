# Stage 6 generic registry-service update framework

Status: source-only design and manifest review

Date: 2026-08-27

## Goal

Generalise the successful Stage 5 `maintenance-page` pilot into a reusable, allow-listed framework for low/medium-risk registry-image services without widening Jenkins or TestServer authority.

Stage 6 does not make arbitrary containers deployable. A service is eligible only when a reviewed service-update manifest exists and all manifest/runtime/authority gates pass.

## Proven starting point

Stage 5 proved the full human-approved flow for `maintenance-page`:

1. inspection through a permanent read-only identity;
2. exact Git/config/current/candidate/rollback validation;
3. Jenkins human approval;
4. post-approval reinspection and zero-drift comparison;
5. separate executor credential bound only after approval/drift proof;
6. one-shot arm;
7. exact service-scoped Compose deployment with `--no-deps --no-build --pull never --force-recreate`;
8. health and protected-state validation;
9. rollback only through the reviewed path when required;
10. disarm by removing the enable file;
11. consumed pilot cannot be reused.

Stage 6 preserves those boundaries.

## Stage 6 v1 scope

Stage 6 v1 supports reviewed `registry-image` services on TestServer only.

Eligible services must be low or medium risk and must not require:

- privileged mode;
- Docker socket access;
- host device access;
- arbitrary shell/Docker/Compose arguments;
- control-plane mutation;
- Jenkins self-deployment.

Local-build services remain a separate future class because their provenance/rebuild semantics differ from registry images.

## Two artifacts, two roles

### Service update manifest

`config/service-update-manifest.schema.json` defines static, reviewed service-specific authority and invariants:

- target service/container/host;
- Compose project, service, path and image override variable;
- exact `docker-env` authority revision and Compose SHA;
- version comparison scheme;
- exact immutable rollback identity and local rollback image ID;
- exact remote candidate index/platform/config identities;
- platform;
- networks, ports, mounts and mount hashes;
- non-privileged/no-device/no-Docker-socket constraints;
- health strategy;
- protected Jenkins/DinD state;
- all-other-container unchanged invariant;
- mandatory approval, reinspection, one-shot and rollback semantics.

The manifest is reviewed input. It is not proof that live state currently matches it.

### Deployment-plan / inspection artifact

The existing Stage 4 deployment-plan concepts remain the dynamic evidence layer. Inspection must compare the live host and clean Git authority against the reviewed service manifest and emit machine-readable evidence.

Jenkins must never infer deployment authority solely from the manifest file being present.

## Version selection rule

Moving tags such as `latest` are discovery hints only and are never deployment identities.

Candidate selection must:

1. resolve an explicit version;
2. apply the configured version scheme;
3. prove it is an upgrade where ordering is defined;
4. resolve immutable registry index/platform/config digests;
5. verify target OS/architecture and OCI version metadata where available;
6. reject stale `latest`, downgrade, same-version/digest and ordering-unknown cases according to policy.

The Dashy discovery proved why this is required: the cached `latest` image was Dashy 4.5.10 while the running service was already 4.5.13. The explicit current stable release was 4.6.0.

## Candidate acquisition boundary

Stage 6 separates candidate discovery from candidate acquisition.

A reviewed candidate may be remote during manifest review. Before `arm`:

- the exact candidate immutable reference must be acquired by a separate reviewed step;
- the resulting local image/platform identity must be verified against the manifest;
- deployment itself must still use `--pull never`;
- the executor must not receive arbitrary pull/image arguments.

The acquisition implementation is intentionally not introduced by the first manifest PR.

## Compose image override

A generic helper must not edit Compose YAML and must not accept caller-supplied image references.

Each onboarded service therefore declares a reviewed environment-variable override in its authoritative Compose file. The helper may set only the manifest-pinned variable to the manifest-pinned immutable candidate/rollback reference.

For Dashy the intended override is:

```yaml
image: "${DASHY_IMAGE:-lissy93/dashy:4.5.13}"
```

With the variable unset, current behaviour remains exactly 4.5.13.

The source-only prerequisite is `docker-env` PR #18. Until that PR is merged and the resulting authoritative commit and Compose SHA are pinned into the Dashy manifest, the Dashy Stage 6 manifest is **not executable authority**.

## Generic execution flow

For one reviewed service/update manifest:

1. validate manifest schema and cross-field/security invariants;
2. validate exact clean Git authority and Compose SHA;
3. resolve/verify explicit remote candidate identity;
4. acquire exact candidate through the separately reviewed acquisition path;
5. prove candidate is local with exact platform/image identity;
6. run read-only inspection and archive pre-approval artifact;
7. present exact service/current/candidate/rollback identities to the human approver;
8. block on Jenkins `input`;
9. repeat inspection and require critical state to match;
10. only then bind executor credential;
11. arm one exact update/pilot;
12. deploy only the manifest service using internally constructed Compose arguments;
13. wait for manifest health contract;
14. prove Jenkins/DinD unchanged and all unrelated container IDs/restart counts unchanged;
15. if deployment fails, use only the reviewed rollback path when preconditions permit;
16. disarm after proven candidate success or proven rollback success;
17. archive exact evidence.

## Dashy first generic service

Discovery baseline:

- service/container: `dashy`;
- Compose project/service: `dashboards/dashy`;
- current version: 4.5.13;
- current immutable index digest: `sha256:8bef3c7bf607de54bbcd4bc3733c481b06c0053b9d12ea781e3bd29457b8b6a4`;
- current local ARM64 image ID: `sha256:417b161fc4c22a4dc6759110f6794c880c72a91e4b8c64e1d653605c2726b3ee`;
- candidate version: 4.6.0;
- candidate immutable index digest: `sha256:40e3b27369002d4bce12cdffd5136b05924e1a7ea4e0d971a890557045fb1d59`;
- candidate ARM64 manifest: `sha256:cb6a9839b13481e8f96104482fed6e30f7aba186fa636a43a14cb2cb31b72e92`;
- candidate config digest: `sha256:f7c93e5961154c8ee4a4bce7f4448d30b9ee46def5ed8eb3ebef3d111370de99`;
- candidate source revision: `d707730b454a35c52187e824879386e1eb30f869`;
- platform: linux/arm64;
- network: `homelab_apps`;
- published ports: none;
- user: `node`;
- privileged: false;
- devices: none;
- Docker socket: none;
- one RW bind mount at `/app/user-data/conf.yml`;
- config SHA256: `03d8e2c988c949ae298b2ea76867759d359b5272a14e4b1f1bef33f2e71a96aa`;
- Docker healthcheck present and currently healthy;
- Jenkins and Jenkins-DinD remain explicitly protected.

No Dashy 4.6.0 image was pulled and no live container was changed during discovery.

## Static validator

`scripts/validate-stage6-service-manifest.py` is dependency-free for the mandatory cross-field/security checks and optionally performs full JSON Schema validation when the `jsonschema` Python package is available.

It rejects, among other cases:

- invalid/mismatched immutable references;
- candidate and rollback repository mismatch;
- same candidate/rollback digest;
- semver downgrade/same-version candidate;
- non-Linux/ARM64 identities in Stage 6 v1;
- privileged/device/Docker-socket service shapes;
- bind mounts without a pinned SHA-256 invariant;
- weakened Compose execution flags;
- missing Jenkins/DinD protection;
- missing all-other-container invariant;
- weakened human-approval/reinspection/one-shot/rollback requirements.

## Permanent exclusions

Stage 6 v1 does not onboard:

- Jenkins or Jenkins-DinD;
- registry control plane;
- Kubernetes control plane;
- Pi-hole/Unbound;
- router/switch/network control plane;
- Greenbone/OpenVAS control plane;
- Prometheus/Grafana/Loki/Alloy monitoring control plane;
- Nginx Proxy Manager or authentication control plane in the initial rollout;
- Docker-socket consumers;
- privileged/device-access services;
- arbitrary container/image/path selection.

## Source-only status and next gates

This first Stage 6 branch is intentionally source-only.

Before any live Dashy update:

1. review/merge `docker-env` PR #18;
2. update the Dashy manifest to the resulting `docker-env` authority commit and Compose SHA;
3. validate the generic schema/manifest from the exact merged Stage 6 source;
4. design/review the narrowly scoped candidate-acquisition path;
5. build generic inspection/helper/transition source around the manifest contract;
6. rehearse installation with zero live-container changes;
7. only then create/validate the Jenkins Stage 6 approval pipeline;
8. perform a separately approved Dashy 4.5.13 -> 4.6.0 live proof.
