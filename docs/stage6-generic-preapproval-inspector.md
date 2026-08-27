# Stage 6 generic pre-approval inspector

Status: source-only implementation under review

Date: 2026-08-27

## Purpose

This component generalises the proven Stage 5 read-only inspection model into one allow-listed Stage 6 pre-approval inspector for reviewed TestServer registry-image services.

The inspector is intentionally inspection-only. It does not arm, deploy, roll back, pull images, edit Compose files, create credentials, or grant Jenkins execution authority.

## Fixed platform boundary

Stage 6 v1 is limited to TestServer and uses fixed platform roots:

- installed service manifests: `/etc/homelab-stage6/services`;
- installed manifest validator: `/usr/local/libexec/homelab-stage6-validate-service-manifest`;
- installed inspector: `/usr/local/libexec/homelab-stage6-inspect`;
- clean Git authority checkout: `/var/lib/homelab-stage6/authority/docker-env`;
- live runtime source root: `/home/james/docker`.

The caller supplies only one allow-listed service name. The inspector derives all paths, images, digests, runtime invariants and health requirements from the root-owned reviewed manifest.

## Authority validation

Before emitting inspection evidence the inspector requires:

1. root execution from the exact installed inspector path;
2. root-owned, non-symlink, non-group/other-writable inspector, validator and service manifest;
3. manifest validation succeeds;
4. the service/container/host/image type match Stage 6 v1 expectations;
5. the fixed root-owned `docker-env` authority checkout exists;
6. the authority checkout HEAD equals the manifest-pinned revision;
7. the authority checkout is clean;
8. the manifest live Compose path is below `/home/james/docker`;
9. the matching authority-relative Compose path remains inside the fixed authority checkout;
10. authority Compose SHA-256 equals the manifest pin;
11. live Compose SHA-256 equals the same manifest pin.

This makes Git authority and live source equality a mandatory inspection gate rather than an informational field.

## Image and Compose validation

The inspector verifies all three Compose render states without lifecycle execution:

- default rendering resolves to the rollback version tag;
- candidate override resolves exactly to the manifest candidate immutable reference;
- rollback override resolves exactly to the manifest rollback immutable reference.

Both immutable images must already be local. The inspector verifies:

- rollback local image ID;
- rollback OS/architecture;
- rollback RepoDigests contains the exact immutable reference;
- candidate local image ID equals the reviewed config digest;
- candidate OS/architecture;
- candidate RepoDigests contains the exact immutable reference;
- candidate OCI version label;
- candidate OCI revision label.

No image acquisition occurs in the inspector.

## Live runtime invariants

The pre-approval target must still be the exact rollback runtime. The inspector verifies:

- container running;
- exact rollback local image ID;
- configured image equals the rollback version tag;
- exact network membership;
- exact published-port bindings;
- exact mount shape;
- SHA-256 of every bind-mount source pinned by the manifest;
- configured container user;
- privileged state;
- read-only-rootfs state;
- restart policy;
- no device mappings;
- no Docker socket mount;
- manifest health contract.

The current Dashy manifest uses Docker health and therefore requires `healthy`.

## Drift evidence

The inspector captures all Docker containers, not only Jenkins and Jenkins-DinD. Each entry records:

- name;
- container ID;
- restart count;
- running state.

It also emits the manifest-defined protected-container subset.

This full baseline is designed for the later post-approval reinspection step, where Jenkins must prove zero relevant drift before any executor credential is bound.

## Machine-readable artifact

A successful inspection emits JSON with:

- `artifact: service-update-inspection`;
- `mode: stage6-preapproval-inspect`;
- service and host;
- manifest and inspector SHA-256 identities;
- clean Git authority revision and Compose SHA;
- exact current rollback state;
- exact rollback and candidate local identities;
- runtime/health pass state;
- protected container state;
- all-container baseline;
- `approval.required=true` and `approval.granted=false`;
- `deployment.allowed=false` and `deployment.performed=false`;
- `result: ready-for-human-review`.

The artifact is evidence only. It does not confer execution authority.

## Static source guard

`scripts/validate-stage6-inspector.py` enforces the read-only source boundary.

It requires the fixed manifest/validator/authority/live roots and service-only caller interface, and rejects mutating Docker/Compose/Git command surfaces including image pull, container lifecycle operations, Compose lifecycle operations, registry mutation, Git checkout/reset/clean/fetch/pull, `sudo`, `eval`, and shell `-c` execution.

The only Compose operation permitted is read-only `docker compose ... config` rendering.

## Installation and execution are separate gates

This source PR does not install the inspector or create the generic authority checkout. A later inactive-install validation must:

1. check out the exact merged source;
2. validate shell/Python syntax and the static guard;
3. create/verify the clean root-owned Stage 6 `docker-env` authority checkout at the manifest-pinned revision;
4. install the exact reviewed inspector root-owned and non-writable by group/other;
5. prove non-root direct execution fails closed;
6. prove no Stage 6 executor/sudo/Jenkins deployment authority exists;
7. run the inspector read-only and archive its JSON artifact;
8. prove all running container state is unchanged.

## Not included in this slice

This component does not implement:

- Jenkins human approval;
- post-approval zero-drift comparison;
- one-shot update IDs;
- arm/disarm state;
- executor SSH/sudo authority;
- deploy helper;
- rollback helper;
- post-deployment health transition;
- Jenkins pipeline changes.

Those remain separate reviewable Stage 6 slices built on the inspection artifact.
