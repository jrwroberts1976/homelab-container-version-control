# Stage 6 candidate acquisition boundary

Status: source-only review

Date: 2026-08-27

## Purpose

Stage 6 separates candidate discovery from candidate acquisition so deployment remains `--pull never`.

The acquisition step may add exactly one reviewed image to the local Docker image cache. It must not deploy, restart, recreate, stop, remove or otherwise mutate any container.

## Caller boundary

The caller supplies only a reviewed service name such as `dashy`.

The helper resolves the manifest from the fixed root-owned path:

```text
/etc/homelab-stage6/services/<service>.json
```

The caller cannot supply:

- image repository;
- tag;
- digest;
- manifest path;
- Compose path;
- Docker arguments;
- shell command.

The service name must match `^[a-z0-9][a-z0-9-]*$` and can select only a root-owned installed manifest.

## Manifest preconditions

Before any pull, the helper requires:

- root execution;
- root-owned, non-symlink manifest;
- accepted root-owned manifest mode;
- exact installed Stage 6 manifest validator;
- valid Stage 6 registry-image manifest;
- manifest service matches the requested service;
- candidate acquisition mode is `separate-reviewed-step`;
- candidate must be local before arm;
- deployment pulling remains prohibited;
- immutable reference exactly equals repository + index digest;
- candidate index/platform/config digests are valid SHA-256 values;
- target platform is `linux/arm64`.

## Runtime preconditions

Before pulling the candidate, the helper snapshots all container IDs, restart counts and running states.

The target service must still be running the manifest-pinned rollback local image ID. For Docker-health services, the target must be healthy before acquisition.

## Only allowed mutation

The only mutating Docker command is internally constructed from the reviewed manifest:

```text
docker pull "$IMMUTABLE_REF"
```

Moving tags such as `latest` are not accepted as deployment or acquisition authority. The manifest already pins an immutable `repository@sha256:...` reference.

The helper contains no Compose command and no container create/run/start/restart/stop/rm/exec operation.

## Post-pull verification

After pulling the exact immutable candidate, the helper verifies:

- the image can be inspected by the exact immutable reference;
- local image ID equals the reviewed OCI config digest;
- local OS equals the manifest platform OS;
- local architecture equals the manifest platform architecture;
- local RepoDigests contains the exact immutable candidate reference;
- every container ID/restart/running state is unchanged;
- target service remains on the exact rollback image;
- Docker-health target remains healthy where applicable.

It then emits a machine-readable JSON acquisition artifact containing the reviewed candidate/index/platform/config identities and the resulting local image ID.

## Identity / sudo design

Installation and remote invocation are intentionally not part of this source PR.

The intended later host boundary is:

- dedicated non-login/no-Docker-group acquisition service account;
- public-key-only forced SSH command if Jenkins initiates acquisition;
- exact sudo rule only for the acquisition helper;
- no `NOPASSWD: ALL`;
- no direct Docker or Compose executable in sudoers;
- no general shell;
- source restriction to the Jenkins validation network when remote execution is enabled.

Acquisition may occur before human deployment approval because it changes only the local image cache. Human approval remains mandatory before any arm/deploy action.

## Dashy first candidate

The reviewed Dashy manifest pins:

- rollback version `4.5.13`;
- rollback index digest `sha256:8bef3c7bf607de54bbcd4bc3733c481b06c0053b9d12ea781e3bd29457b8b6a4`;
- rollback local image ID `sha256:417b161fc4c22a4dc6759110f6794c880c72a91e4b8c64e1d653605c2726b3ee`;
- candidate version `4.6.0`;
- candidate index digest `sha256:40e3b27369002d4bce12cdffd5136b05924e1a7ea4e0d971a890557045fb1d59`;
- candidate ARM64 manifest `sha256:cb6a9839b13481e8f96104482fed6e30f7aba186fa636a43a14cb2cb31b72e92`;
- candidate config digest `sha256:f7c93e5961154c8ee4a4bce7f4448d30b9ee46def5ed8eb3ebef3d111370de99`;
- platform `linux/arm64`.

Before this acquisition PR is installed or run, source validation must prove the helper and guard match the reviewed branch exactly.

## Failure semantics

Any failure before `docker pull` leaves the image cache and containers unchanged.

A failure after `docker pull` may leave the exact reviewed candidate image cached locally, but it must not mutate containers. The helper fails closed and does not attempt deployment or cleanup.

Leaving a verified or partially verified candidate image in cache is safer than improvising image-removal commands, and the later arm gate must independently prove the exact local candidate identity before deployment authority can be activated.

## Current status

This branch is source-only. It does not:

- install the helper;
- change sudo/SSH/accounts/credentials;
- pull Dashy 4.6.0;
- edit live Compose files;
- restart or recreate containers;
- arm deployment authority;
- run Jenkins.
