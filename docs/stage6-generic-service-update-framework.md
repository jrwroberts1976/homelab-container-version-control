# Stage 6 generic registry-service update framework

Status: source-only framework ready for merge review

Date: 2026-08-27

## Goal

Generalise the successful Stage 5 `maintenance-page` pilot into a reusable, allow-listed framework for low/medium-risk registry-image services without widening Jenkins or TestServer authority.

Stage 6 does not make arbitrary containers deployable. A service is eligible only when a reviewed service-update manifest exists and all manifest, live-runtime, candidate, authority and one-shot execution gates pass.

## Proven Stage 5 boundary retained

Stage 5 proved the full human-approved flow:

1. permanent read-only inspection identity;
2. exact Git/config/current/candidate/rollback validation;
3. Jenkins human approval;
4. post-approval reinspection and zero-drift comparison;
5. separate executor credential bound only after approval/drift proof;
6. one-shot arm;
7. exact service-scoped Compose deployment with `--no-deps --no-build --pull never --force-recreate`;
8. health and protected-state validation;
9. rollback only through the reviewed path when required;
10. disarm by removing the enable file;
11. consumed update ID cannot be reused.

Stage 6 preserves those boundaries.

## Stage 6 v1 scope

Stage 6 v1 supports reviewed `registry-image` services on TestServer only.

Eligible services must be low or medium risk and must not require privileged mode, Docker socket access, host device access, arbitrary shell/Docker/Compose arguments, control-plane mutation, or Jenkins self-deployment.

Local-build services remain a separate future class because their provenance and rebuild semantics differ from registry images.

## Service update manifest

`config/service-update-manifest.schema.json` defines reviewed service-specific authority and invariants:

- target service/container/host;
- Compose project, service, path and image override variable;
- exact `docker-env` authority revision and Compose SHA;
- version comparison scheme;
- exact immutable rollback identity and local rollback image ID;
- exact remote candidate index/platform/config identities;
- OS/architecture;
- networks, published ports, mounts and bind-mount hashes;
- non-privileged/no-device/no-Docker-socket constraints;
- Docker-health or HTTP health strategy;
- Jenkins/DinD protection;
- all-other-container unchanged invariant;
- mandatory approval, reinspection, one-shot and rollback semantics.

The manifest is reviewed input. It is not proof that live state currently matches it.

## Dynamic inspection evidence

The existing Stage 4 deployment-plan concepts remain the dynamic evidence layer. Inspection must compare the live host and clean Git authority against the reviewed service manifest and emit machine-readable evidence.

Jenkins must never infer deployment authority solely from the manifest file being present.

## Version selection rule

Moving tags such as `latest` are discovery hints only and are never deployment identities.

Candidate selection must resolve an explicit version, apply the configured version scheme, prove it is an upgrade where ordering is defined, resolve immutable registry index/platform/config digests, verify target OS/architecture and OCI version metadata where available, and reject stale `latest`, downgrade, same-version/digest and ordering-unknown cases according to policy.

Dashy discovery demonstrated why this matters: the cached `latest` image was Dashy 4.5.10 while the running service was already 4.5.13. The explicit stable candidate is 4.6.0.

## Candidate acquisition boundary

Stage 6 separates candidate discovery from candidate acquisition.

A reviewed candidate may be remote during manifest review. Before `arm`:

- the exact candidate immutable reference must be acquired by a separate reviewed step;
- the resulting local image/platform identity must be verified against the manifest;
- deployment itself must still use `--pull never`;
- the executor must not receive arbitrary pull/image arguments.

The acquisition implementation is intentionally not introduced by this first framework PR.

## Compose image override

A generic helper must not edit Compose YAML and must not accept caller-supplied image references.

Each onboarded service therefore declares a reviewed environment-variable override in its authoritative Compose file. The helper may set only the manifest-pinned variable to the manifest-pinned immutable candidate or rollback reference.

For Dashy the merged authoritative declaration is:

```yaml
image: "${DASHY_IMAGE:-lissy93/dashy:4.5.13}"
```

With `DASHY_IMAGE` unset, current behaviour remains exactly 4.5.13.

`docker-env` PR #18 was source-validated and merged as:

- authority commit: `f659d556365e47288fc99aeb74a1a5a78c2f1852`;
- authoritative Dashy Compose SHA256: `54d18c2d78fb80d04649271d5422cb886777f9b8ed5d4ef41d50217462876010`.

The Dashy Stage 6 manifest pins those exact values.

## Generic execution flow

For one reviewed service/update manifest:

1. validate manifest schema and cross-field/security invariants;
2. validate exact clean Git authority and Compose SHA;
3. resolve and verify explicit remote candidate identity;
4. acquire exact candidate through the separately reviewed acquisition path;
5. prove candidate is local with exact platform/image identity;
6. run read-only inspection and archive pre-approval artifact;
7. present exact service/current/candidate/rollback identities to the human approver;
8. block on Jenkins `input`;
9. repeat inspection and require critical state to match;
10. only then bind executor credential;
11. arm one exact update ID;
12. deploy only the manifest service using internally constructed Compose arguments;
13. wait for the manifest health contract;
14. prove Jenkins/DinD unchanged and all unrelated container IDs/restart counts unchanged;
15. if deployment fails, use only the reviewed rollback path when preconditions permit;
16. disarm after proven candidate success or proven rollback success;
17. archive exact evidence.

## Dashy first generic service

Reviewed discovery baseline:

- service/container: `dashy`;
- Compose project/service: `dashboards/dashy`;
- current version: `4.5.13`;
- rollback index digest: `sha256:8bef3c7bf607de54bbcd4bc3733c481b06c0053b9d12ea781e3bd29457b8b6a4`;
- rollback local ARM64 image ID: `sha256:417b161fc4c22a4dc6759110f6794c880c72a91e4b8c64e1d653605c2726b3ee`;
- candidate version: `4.6.0`;
- candidate index digest: `sha256:40e3b27369002d4bce12cdffd5136b05924e1a7ea4e0d971a890557045fb1d59`;
- candidate ARM64 manifest: `sha256:cb6a9839b13481e8f96104482fed6e30f7aba186fa636a43a14cb2cb31b72e92`;
- candidate config digest: `sha256:f7c93e5961154c8ee4a4bce7f4448d30b9ee46def5ed8eb3ebef3d111370de99`;
- candidate source revision: `d707730b454a35c52187e824879386e1eb30f869`;
- platform: `linux/arm64`;
- network: `homelab_apps`;
- published ports: none;
- user: `node`;
- privileged: false;
- devices: none;
- Docker socket: none;
- one RW bind mount at `/app/user-data/conf.yml`;
- config SHA256: `03d8e2c988c949ae298b2ea76867759d359b5272a14e4b1f1bef33f2e71a96aa`;
- Docker healthcheck present and healthy at discovery;
- Jenkins and Jenkins-DinD explicitly protected.

No Dashy 4.6.0 image was pulled and no live container was changed during discovery or PR source validation.

## Static validator

`scripts/validate-stage6-service-manifest.py` is dependency-free for mandatory cross-field/security checks and optionally performs full JSON Schema validation when the `jsonschema` Python package is available.

It rejects invalid or mismatched immutable references, candidate/rollback repository mismatch, same candidate/rollback digest, semver downgrade or same-version candidates, non-Linux/ARM64 identities in Stage 6 v1, privileged/device/Docker-socket service shapes, bind mounts without a pinned SHA-256 invariant, weakened Compose execution flags, missing Jenkins/DinD protection, missing unrelated-container protection, and weakened approval/reinspection/one-shot/rollback requirements.

The source validation run on TestServer passed both JSON Schema validation and Stage 6 cross-field/security invariants.

## Permanent exclusions

Stage 6 v1 does not onboard Jenkins or Jenkins-DinD, registry control plane, Kubernetes control plane, Pi-hole/Unbound, router/switch/network control plane, Greenbone/OpenVAS control plane, Prometheus/Grafana/Loki/Alloy monitoring control plane, Nginx Proxy Manager or authentication control plane in the initial rollout, Docker-socket consumers, privileged/device-access services, or arbitrary container/image/path selection.

## Current status and next gates

Completed source gates:

1. Dashy runtime/current/candidate discovery;
2. explicit 4.5.13 -> 4.6.0 version proof;
3. immutable 4.6.0 index/ARM64/config identity proof;
4. source-only `DASHY_IMAGE` prerequisite review;
5. `docker-env` PR #18 source validation;
6. PR #18 merge as `f659d556365e47288fc99aeb74a1a5a78c2f1852`;
7. Dashy manifest repinned to merged authority and Compose SHA;
8. Stage 6 schema, manifest and security validator source review.

Remaining gates before a live Dashy update:

1. merge the generic Stage 6 framework PR;
2. design and review the narrowly scoped candidate-acquisition path;
3. acquire exact Dashy 4.6.0 candidate and prove local immutable/platform identity;
4. build generic inspection/helper/transition source around the manifest contract;
5. rehearse installation with zero live-container changes;
6. create and validate the Jenkins Stage 6 approval pipeline;
7. perform a separately approved Dashy 4.5.13 -> 4.6.0 live proof;
8. archive and document terminal evidence.
