# Dozzle 10.9.0 Stage 6 deployment proof

## Status

On **03 September 2026**, Jenkins job `stage6-generic-service-update` build **#34** successfully deployed Dozzle from `10.8.0` to `10.9.0` on TestServer using the reviewed generic Stage 6 update path.

The deployment result was:

```text
STAGE 6 dozzle RESULT: DEPLOYED EXACT CANDIDATE AND DISARMED
Finished: SUCCESS
```

This proves the deployment portion of the Stage 6 contract. Durable Compose authority, catalogue and steady-state promotion remain separate closure work until explicitly completed and verified.

## Reviewed transition

Rollback/current identity before deployment:

```text
version: 10.8.0
configured image: amir20/dozzle@sha256:243666b0593ff33ed1373901575236f0d6bed8a2d6b451cdae4345969a7b6d5c
local image ID: sha256:eca1774c3ff18eb6ff177d0d557b2ff37da5df6f7c617450b4eca48327f20ce8
```

Reviewed candidate:

```text
version: 10.9.0
immutable image: amir20/dozzle@sha256:7f01a2504f89788b60ad0efddd94472fd66f9a225c708356cdb815d9d8abd184
platform manifest: sha256:dedcf5fc948e8eb5a325182d2743a59d8540e4a6ca740e0c064826e0e86c1fa9
local/config image ID: sha256:88b0c06d1a3c881893d2162afa4b19d1b91262e1ae92a90e661d8ccc2a5549d9
platform: linux/arm64
```

Reviewed Stage 6 manifest:

```text
config/services/dozzle-10.9.0.json
```

## Proven Jenkins sequence

Build #34 proved:

1. reviewed manifest present and schema/cross-field validation passed;
2. source dependencies and pinned TestServer host key passed;
3. first read-only pre-approval inspection passed;
4. Jenkins proved exact rollback/candidate identities and `deployment=false` before approval;
5. explicit human approval was granted;
6. a second read-only inspection exactly matched the pre-approval critical state;
7. the executor credential became reachable only after approval and zero-drift proof;
8. the exact Dozzle update was armed;
9. the exact local immutable candidate was deployed;
10. host-side runtime and health invariants passed;
11. rollback was skipped because deployment acceptance passed;
12. one-shot execution authority was disarmed;
13. Jenkins finished successfully.

## Container recreation boundary

Stage 6 does **not** restart or recreate the target container during normal preparation and review stages.

These stages are non-recreating:

```text
manifest preparation / validation
candidate cache acquisition
pre-approval inspection
human approval
post-approval read-only reinspection
zero-drift assertion
executor preflight
arm
post-deployment closure / VERIFY_CLOSED
```

The target container is recreated only by the actual deployment operation, equivalent to:

```text
docker compose up -d --no-deps --no-build --pull never --force-recreate dozzle
```

For build #34 that recreation switched the running Dozzle container from the reviewed 10.8.0 rollback image to the reviewed 10.9.0 immutable candidate.

## Post-deployment verification

Independent TestServer verification after Jenkins completed showed:

```text
running=true
image_id=sha256:88b0c06d1a3c881893d2162afa4b19d1b91262e1ae92a90e661d8ccc2a5549d9
configured_image=amir20/dozzle@sha256:7f01a2504f89788b60ad0efddd94472fd66f9a225c708356cdb815d9d8abd184
restart=unless-stopped
```

The exact image gates passed and Dozzle logged:

```text
Dozzle version v10.9.0
Connected to Docker
Accepting connections on :8080
```

## Target framework synchronization lesson

The first 10.9.0 attempt failed safely before approval because the installed TestServer Stage 6 validator was older than the reviewed repository validator.

Repository validator SHA-256:

```text
85aa0c1e3bfe7fa92fd2acd98195d1f96fb622f36a0d08b1a9361f74ad06cc8d
```

The stale target validator still required rollback `configured_image` to be a tagged image and rejected the valid chained-update immutable rollback reference.

The reviewed validator was synchronized to:

```text
/usr/local/libexec/homelab-stage6-validate-service-manifest
```

and its hash was required to match the repository source before the clean update was retried.

Operational rule: **reviewed target-side Stage 6 framework components must be synchronized or hash-proven before a deployment inspection is trusted.** Do not weaken manifest validation to work around target framework drift.

## Preparation reset proof

Before the successful clean run, the earlier 10.9.0 target-preparation state was reset while leaving live Dozzle 10.8.0 untouched. The 10.9.0 candidate was removed from the target image cache, the prior installed transition manifest was restored, the reviewed validator was synchronized, and preparation was then repeated in the correct order.

This proved that cache/manifest preparation is separable from container mutation.

## Remaining closure

Build #34 proves **deployment success and disarm**, not final durable Stage 6 closure.

The remaining closure contract is:

1. promote the exact successful 10.9.0 immutable image into Git Compose authority;
2. synchronize authority without recreating the healthy container;
3. promote the estate catalogue to 10.9.0;
4. generate, review and install the 10.9.0 steady-state manifest;
5. run non-mutating `VERIFY_CLOSED`;
6. require the final closed-state evidence to match authority, catalogue, runtime and health.

Until those stages are complete, do not label the 10.9.0 transition `SUCCESS_CLOSED`.

## BAU improvements identified

The successful update also identified follow-up framework hardening:

- propagate the trimmed `STAGE6_MANIFEST` value into missing-manifest preparation;
- automate/formalize target manifest synchronization;
- automate/formalize target validator/inspector synchronization or preflight hash proof;
- move exact target candidate acquisition into the intended restricted Jenkins path;
- add deterministic host selection beyond the current TestServer default;
- preserve separate candidate-acquisition and deployment authority boundaries.

None of these changes should weaken immutable refs, `--pull never`, explicit approval, zero-drift inspection, one-shot execution or rollback controls.
