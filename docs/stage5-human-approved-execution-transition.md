# Stage 5 human-approved execution transition

Status: source-only design review

Date: 2026-08-27

## Goal

Preserve the proven Stage 5 inspection-only boundary while adding a reviewed, one-shot path for Jenkins to perform exactly one human-approved `maintenance-page` container update.

The existing inspection identity remains permanently read-only. Execution uses a separate Jenkins SSH credential and separate TestServer service account so the inspection boundary already proven is not widened.

## Intended Jenkins flow

1. Bind `homelab-stage5-testserver-inspector`.
2. Run `inspect maintenance-page`.
3. Parse and independently assert pilot ID, current, candidate, rollback, Git authority, health and protected Jenkins/DinD state.
4. Present those exact identities to the approver.
5. Block on Jenkins `input`, restricted to `submitter: 'james'` for the first pilot.
6. Re-bind the inspection credential and repeat inspection.
7. Require the second artifact to match the first on all critical identities.
8. Only then bind `homelab-stage5-testserver-executor`.
9. Run literal `arm maintenance-page`.
10. Run literal `deploy maintenance-page`.
11. Parse and assert deployment result and final invariants.
12. Run literal `disarm maintenance-page` after proven success.
13. If deployment fails, use only the reviewed rollback path when its helper preconditions are satisfied; otherwise fail closed for manual recovery.

Jenkins receives no general shell, Docker socket, arbitrary Docker/Compose, arbitrary service, arbitrary digest, arbitrary path or arbitrary Git authority.

## Proven starting point

Current live state remains inspection-only:

- inspection account: `homelab-stage5-pilot`
- Jenkins inspection credential: `homelab-stage5-testserver-inspector`
- Jenkins source: `172.30.255.250`
- TestServer SSH destination: `172.30.255.249:22`
- forced command: `/usr/local/sbin/homelab-stage5-pilot-ssh`
- authority gate: `/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate`
- inspector: `/usr/local/libexec/homelab-stage5-maintenance-page-inspect`
- active policy mode: `inspection-ready`
- policy SHA256: `adcac66121b04d4b0b4f0a9962c5e75e5c9b3a801a5b28f222f04a6670973f6f`
- inspection sudo authority only
- deployment helper absent
- enable file absent
- deploy/rollback sudo authority absent
- candidate and rollback images both local Linux/ARM64
- live configuration equals pinned docker-env authority byte-for-byte
- maintenance-page remains exact rollback digest

Existing positive and negative inspection proofs are prerequisites and must continue to pass unchanged.

## Identity separation

### Permanent inspection identity

Keep `homelab-stage5-pilot` and `homelab-stage5-testserver-inspector` read-only.

The inspection wrapper continues to permit only:

- `ping`
- `inspect maintenance-page`

It must continue rejecting:

- `arm maintenance-page`
- `deploy maintenance-page`
- `rollback maintenance-page`
- `disarm maintenance-page`
- arbitrary shell/Docker commands

Its sudo authority remains exact `authority-gate inspect` only.

### Dedicated executor identity

Introduce only after source review:

- TestServer account: `homelab-stage5-executor`
- Jenkins credential: `homelab-stage5-testserver-executor`
- independent ED25519 key
- `restrict,from="172.30.255.250"`
- public-key-only SSH
- no password, TTY, forwarding, tunnel or user RC
- no Docker group membership
- forced command: `/usr/local/sbin/homelab-stage5-executor-ssh`

The executor wrapper may permit only:

- `ping`
- `arm maintenance-page`
- `deploy maintenance-page`
- `rollback maintenance-page`
- `disarm maintenance-page`

It explicitly rejects inspection; inspection remains bound to the read-only identity.

The Jenkins Pipeline must not bind the executor credential before the human approval step and the second drift-check inspection.

Human approval is a Jenkins workflow boundary, not an interactive host prompt.

## Why an explicit transition is required

Merged Stage 5 source intentionally separates phases:

- inspection requires `mode=inspection-ready` and enable file absent;
- deploy/rollback require `mode=execution-enabled`, exact helper and matching enable file.

Therefore widening the existing inspection sudo rule is rejected. A reviewed state transition and separate execution identity are required.

## State machine

### I0 — inspection-only

Current proven state. Active inspection policy exact; enable absent; all execution commands rejected.

Effective deployment authority: **false**.

### I1 — execution components staged, activation absent

Reviewed execution components may be installed root-owned without changing the active inspection policy or running container:

- deployment helper;
- transition helper;
- staged execution policy;
- root-owned state directory;
- executor account/key/wrapper and exact sudo surface after separate review.

During I1:

- active policy remains exact inspection-ready policy;
- enable file remains absent;
- inspection identity still passes its positive/negative proof;
- maintenance-page remains rollback;
- no container changes/restarts occur.

### A — armed after Jenkins approval

Only the executor literal `arm maintenance-page` reaches the transition helper.

Before state change the transition helper revalidates:

- root execution and exact installed path;
- root-owned/non-writable transition, active policy, staged policy, authority gate, deployment helper and inspector;
- active inspection policy SHA256 exactly `adcac66121b04d4b0b4f0a9962c5e75e5c9b3a801a5b28f222f04a6670973f6f`;
- exact installed authority-gate SHA256 `561499a0e327f02e4df7fdabf40ab1d0660dc5ed51622061c568f9deaaa4dbda`;
- exact installed deployment-helper SHA256 `a0df7b46aa01ffc9ef3fbf43cea43caeef34681ef22b759ae822ed2832cfc42a`;
- exact installed inspector SHA256 `64dc6526e66a9e6878ca23c1703a9d7bb11c82b7f60cf7b8aae714b2ed9cb213`;
- staged execution policy has no review placeholders;
- staged execution policy pins those same component hashes and a concrete 40-character implementation commit;
- pilot/service/host/docker-env authority/current/candidate/rollback/configuration identities are unchanged across inspection and execution policies;
- enable file absent;
- pilot consumed marker absent;
- docker-env authority checkout exact and clean;
- rollback digest currently running;
- candidate and rollback local Linux/ARM64;
- health passes.

The arm operation performs only:

1. copy the exact root-owned staged execution policy to a temporary active-policy path;
2. atomically rename it over the active policy;
3. create a root-owned `0600` enable file containing only the exact pilot ID;
4. verify the resulting active policy SHA256 equals the staged policy SHA256.

The staged execution policy SHA is calculated at arm time from the already root-controlled reviewed file. This intentionally avoids a circular hash dependency between policy and transition helper.

If arm fails after policy replacement begins, an `EXIT` rollback trap restores the original inspection policy and removes any partial enable file.

Arm emits JSON but performs no container mutation.

### D — deployed / pilot consumed

The existing helper consumes `${pilot_id}.consumed` before Compose mutation.

Deployment requires:

- valid armed state;
- current digest equals rollback;
- consumed marker absent;
- exact local ARM64 candidate/rollback;
- exact config/runtime checks;
- pre-mutation health.

The only container mutation remains internally constructed and service scoped:

```text
MAINTENANCE_PAGE_IMAGE=<policy candidate>
docker compose \
  --project-directory /home/james/docker/stacks/maintenance-page \
  -p maintenance-page \
  -f /home/james/docker/stacks/maintenance-page/docker-compose.yml \
  up -d \
  --no-deps \
  --no-build \
  --pull never \
  --force-recreate \
  maintenance-page
```

No caller-supplied Docker/Compose argument is permitted.

After mutation the helper proves candidate digest, runtime shape, health, Jenkins/DinD identity and unrelated-container identity invariants.

### R — rollback

Rollback is recovery for the exact consumed pilot only.

It requires the consumed marker, exact candidate currently running, local ARM64 rollback image, execution policy and matching enable file. The existing helper already enforces these central conditions.

### X — disarmed / terminal

After proven deploy success, or deploy failure followed by proven rollback success, executor invokes `disarm maintenance-page`.

Disarm requires:

- active policy byte-for-byte equals staged execution policy;
- matching root-owned enable file;
- consumed pilot marker exists;
- current runtime is either exact candidate or exact rollback.

It removes only the enable file. With enable absent, authority gate deploy/rollback cannot run.

A later version update uses a new pilot policy with the then-current image as the new rollback baseline.

If deploy and rollback both fail, Jenkins must not improvise Docker commands and must not automatically destroy the reviewed recovery state.

## Policy integrity model

Use two root-owned files:

- active policy: `/etc/homelab-stage5/maintenance-page.policy.json`;
- staged execution policy: `/etc/homelab-stage5/maintenance-page.execution-policy.json`.

The transition helper hard-pins the current inspection-policy SHA and exact installed gate/helper/inspector hashes.

The staged execution policy itself pins:

- authority-gate SHA256;
- deployment-helper SHA256;
- inspector SHA256;
- concrete implementation commit;
- exact docker-env authority commit;
- exact config hashes;
- exact immutable candidate/rollback identities;
- exact execution flags.

It deliberately does **not** contain the transition-helper or executor-wrapper hashes. Those source/install hashes are validated and documented separately. This avoids circular self-reference while preserving root-owned installed-file integrity.

## Executor sudo boundary

Only exact actions may be authorized:

```text
/usr/local/libexec/homelab-stage5-maintenance-page-transition arm
/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate deploy
/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate rollback
/usr/local/libexec/homelab-stage5-maintenance-page-transition disarm
```

No wildcard, shell, Docker executable or Compose executable may appear in executor sudo authority.

The inspection sudo rule remains unchanged.

## Jenkins failure handling

- **Before arm:** fail build; no execution state changed.
- **Arm failure:** do not deploy; verify policy/enable state and fail.
- **Deploy success:** assert artifact/invariants, archive evidence, disarm.
- **Deploy failure:** attempt only reviewed rollback when helper preconditions permit.
- **Rollback success:** assert rollback health/invariants, archive, disarm.
- **Rollback failure:** no improvised Docker and no automatic disarm; fail for manual recovery.

## Permanent exclusions

The pilot still excludes Jenkins self-deployment, Jenkins-Docker mutation, registry mutation, Kubernetes control plane, Pi-hole/Unbound, router/switch/network control plane, Greenbone control plane, Prometheus/Grafana/Loki control plane, arbitrary container selection, arbitrary image/digest input, arbitrary Compose paths and arbitrary shell/Docker commands.

Jenkins remains a permanent self-deployment exception.

## Proof order before live deployment

1. Source-only transition design reviewed.
2. Transition helper, executor wrapper, execution-policy template and static validator pass from exact clean branch head.
3. Fill staged execution policy component hashes only after source review; implementation commit is resolved from merged authority during controlled installation preparation.
4. Re-run source validation and record exact transition/wrapper/policy hashes.
5. Host installation rehearsal from exact clean source.
6. Stage execution components while active policy remains inspection-only; prove existing inspection path still passes and no container changes.
7. Create dedicated executor identity and prove source restriction/forced-command/sudo boundaries.
8. Add source-only Jenkins approval pipeline and prove executor credential is not in scope before `input`.
9. Negative proof using inspection identity remains unchanged.
10. Human approval in Jenkins.
11. Repeat read-only inspection and drift comparison.
12. Bind executor credential.
13. Arm exact pilot.
14. Deploy exactly one maintenance-page update.
15. Verify exact candidate/health/protected-state invariants.
16. Disarm after proven success.
17. Archive and document evidence.
18. Exercise rollback only when required or in a separately approved rollback proof.

## Current status

This branch is source-only. No host file, account, SSH trust, sudo rule, Jenkins credential/job, policy, enable file or container has been changed by this design work. No Stage 5 deployment has been performed.
