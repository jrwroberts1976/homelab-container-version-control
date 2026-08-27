# Stage 6 generic execution boundary

Status: source-only implementation under review

Date: 2026-08-27

## Purpose

This slice introduces the execution-side state machine that follows a successful Stage 6 generic pre-approval inspection. It preserves the proven Stage 5 ordering boundary while keeping service selection, image identities, Compose paths and rollback identities under reviewed root-owned manifest control.

This PR is source-only. It does not install execution helpers, create a Stage 6 executor account, add sudo rules, create SSH credentials, arm Dashy, deploy Dashy, or roll back Dashy.

## Components

- `ops/testserver/homelab-stage6-transition` — root-only arm/disarm state transition helper.
- `ops/testserver/homelab-stage6-execute` — root-only deploy/rollback helper.
- `ops/testserver/homelab-stage6-executor-ssh` — future forced-command boundary, initially allow-listed only for literal Dashy actions.
- `scripts/validate-stage6-execution-boundary.py` — static source guard for the three execution components.

## Generic root helper boundary

The transition and execution helpers accept only:

```text
ACTION SERVICE
```

They do not accept image references, Compose paths, Git revisions, health URLs, Docker arguments or shell fragments from the caller. The service name resolves to a reviewed root-owned manifest under `/etc/homelab-stage6/services`.

All deployment identities and execution parameters are therefore manifest-derived.

## Jenkins boundary remains narrower than the generic helpers

The future Jenkins executor identity is intentionally not given arbitrary service selection.

The first executor wrapper source permits only these exact literal commands:

```text
ping
arm dashy
deploy dashy
rollback dashy
disarm dashy
```

LibreSpeed or any later service requires a separate reviewed wrapper/sudo onboarding change. This preserves the requirement that Jenkins does not receive arbitrary service/path/digest arguments.

No executor account, authorized key, sudo rule or Jenkins credential is created by this PR.

## One-shot update identity

The state machine derives one deterministic one-shot ID from the reviewed service name and full candidate index digest:

```text
stage6-<service>-<candidate-index-sha256-without-prefix>
```

For a given reviewed candidate digest this ID cannot be reused after the consumed marker exists.

State paths are fixed below:

```text
/var/lib/homelab-stage6/state/<service>/enable
/var/lib/homelab-stage6/state/<service>/<update-id>.consumed
```

The enable file is root-owned mode `0600` and contains only the exact update ID.

## State machine

### I0 — inspected, not armed

The generic inspector has emitted `result=ready-for-human-review`, but no enable file exists and deployment authority is false.

### A — armed

`arm SERVICE` requires:

- root execution from the exact installed transition path;
- secure root-owned validator, inspector, execution helper and manifest;
- unconsumed update ID;
- no existing enable file;
- a fresh successful generic inspection proving the target still equals the exact rollback state, candidate/rollback identities are local, runtime/health pass, approval remains external, and deployment remains disabled in the inspection artifact.

Arm creates only the root-owned state directory and exact enable file. It performs no container mutation.

### D — deploy

`deploy SERVICE` requires:

- exact armed update ID;
- candidate not already consumed;
- clean Git authority and exact live/authority Compose SHA;
- exact local rollback and candidate identities;
- another fresh generic inspection immediately before mutation;
- exact rollback still current.

Immediately before Compose mutation the helper atomically creates the consumed marker. The only Compose mutation is internally constructed from manifest values:

```text
<IMAGE_VARIABLE>=<candidate immutable ref>
docker compose \
  --project-directory <manifest project directory> \
  -p <manifest project> \
  -f <manifest Compose file> \
  up -d \
  --no-deps \
  --no-build \
  --pull never \
  --force-recreate \
  <manifest service>
```

No image pull occurs during deployment.

After recreate the helper verifies exact candidate image/config identity, network/port/mount/user/privilege/device/Docker-socket invariants, bind-mount hashes and the service health contract. It snapshots all containers before and after and requires every unrelated container ID, restart count and running state to remain unchanged.

A successful deploy leaves the update armed until an explicit terminal `disarm` action.

### R — rollback

Rollback is only available after the exact update ID has been consumed and while the exact candidate image/configuration is current.

Rollback uses the same service-scoped Compose command and flags with the manifest-pinned immutable rollback reference. It then proves rollback image/runtime/health and all unrelated-container invariants.

A rollback does not delete the consumed marker. The reviewed update ID remains permanently consumed.

### X — disarmed

`disarm SERVICE` requires the exact enable value.

If the update is unconsumed, disarm is permitted only while the exact rollback image remains current and healthy, allowing a safe cancellation after arm but before deploy.

If the update is consumed, disarm is permitted only when the target is the exact candidate or rollback image and the terminal health contract passes. This prevents silently disarming a failed or indeterminate deployment state.

Disarm removes only the enable file. The consumed marker, when present, remains.

## Failure semantics

The design fails closed:

- an arm failure creates no container mutation;
- once consumed, the exact update cannot be retried as a fresh deployment;
- a failed candidate recreate leaves the update armed/consumed for reviewed rollback or manual recovery;
- rollback requires exact candidate-current preconditions;
- disarm refuses unhealthy or indeterminate consumed states;
- no helper pulls images or accepts moving tags.

## Static guard

The source guard requires fixed manifest/authority/state roots, fixed action interfaces, one-shot state checks, fresh inspection before deploy, exact Compose flags, full unrelated-container comparison, and a Dashy-only forced-command wrapper.

It rejects image pull, general Docker lifecycle commands, Compose build/pull/down, Git mutation, sudo inside root helpers, eval, shell `-c`, moving `:latest` authority and caller-supplied third arguments.

The wrapper itself contains exactly four literal sudo execution lines for Dashy and no variable service/action expansion.

## Human approval ordering

This source does not implement the Jenkins pipeline. The later Jenkins slice must preserve the already-proven ordering:

1. pre-approval generic inspection;
2. human approval;
3. second generic inspection;
4. exact critical/full-state zero-drift comparison;
5. only then bind the executor credential;
6. `arm dashy`;
7. `deploy dashy`;
8. verify execution result;
9. rollback if eligible on failure;
10. `disarm dashy` after proven terminal state.

The host-side `arm` also performs a fresh inspection, adding defense in depth without replacing the Jenkins human-approval and post-approval drift gates.

## Not included in this PR

- host installation of transition/execution helpers;
- Stage 6 state directory creation;
- executor Unix account;
- SSH authorized key;
- forced-command installation;
- sudo policy;
- Jenkins credential;
- Jenkins pipeline;
- any live `arm`, `deploy`, `rollback` or `disarm` action;
- any Dashy container recreation.
