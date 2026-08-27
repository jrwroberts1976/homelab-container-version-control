# Stage 5 human-approved execution transition

Status: source-only design review

Date: 2026-08-27

## Goal

Preserve the proven Stage 5 inspection-only boundary while adding a reviewed, one-shot path for Jenkins to perform exactly one human-approved `maintenance-page` container update.

The existing inspection identity must remain permanently read-only. Execution uses a separate Jenkins SSH credential and a separate TestServer service account so the inspection boundary already proven does not need to be widened.

The intended pilot flow is:

1. Jenkins binds the existing inspection credential and runs `inspect maintenance-page`.
2. Jenkins parses and independently validates the returned inspection artifact.
3. Jenkins presents the exact current, candidate and rollback identities to a human approver.
4. Jenkins blocks on Pipeline `input`; only Jenkins user `james` may approve the first pilot.
5. After approval, Jenkins repeats the read-only inspection with the inspection credential and requires all critical identities to match the pre-approval artifact.
6. Only after those checks does Jenkins bind the separate executor credential.
7. The executor invokes the literal `arm maintenance-page` transition.
8. The executor invokes the literal `deploy maintenance-page` action.
9. The root helper verifies the exact candidate, rollback, Git authority, configuration, runtime shape, protected Jenkins/DinD state and HTTP health before and after mutation.
10. On success Jenkins records the result and invokes `disarm maintenance-page`.
11. On deployment failure, rollback remains available only for the same consumed pilot. Jenkins may invoke only the reviewed literal rollback path; if rollback cannot be proven safe, the job fails closed for manual recovery rather than improvising.

Jenkins receives no general shell, Docker socket, arbitrary Docker/Compose, arbitrary service name, arbitrary digest, arbitrary path or arbitrary Git authority.

## Proven starting point

The current host is inspection-only and has passed the live execution-transition preflight.

Current installed state:

- inspection account: `homelab-stage5-pilot`
- Jenkins inspection credential: `homelab-stage5-testserver-inspector`
- Jenkins source identity: `172.30.255.250`
- TestServer SSH destination: `172.30.255.249:22`
- inspection forced command: `/usr/local/sbin/homelab-stage5-pilot-ssh`
- authority gate: `/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate`
- inspector: `/usr/local/libexec/homelab-stage5-maintenance-page-inspect`
- active policy mode: `inspection-ready`
- inspection sudo authority only
- deployment helper absent
- execution enable file absent
- deploy sudo authority absent
- rollback sudo authority absent
- candidate and rollback images both local as Linux/ARM64
- live configuration matches pinned docker-env authority byte-for-byte
- maintenance-page remains on the exact rollback digest

The existing positive and negative remote inspection proofs remain accepted prerequisites and must continue to pass unchanged.

## Identity separation

### Inspection identity — permanent read-only

Keep unchanged:

- TestServer account: `homelab-stage5-pilot`
- Jenkins credential: `homelab-stage5-testserver-inspector`
- source restriction: `172.30.255.250`
- forced wrapper permits only `ping` and `inspect maintenance-page`
- sudo permits only exact `authority-gate inspect`

The inspection identity must continue to reject:

- `arm maintenance-page`
- `deploy maintenance-page`
- `rollback maintenance-page`
- `disarm maintenance-page`
- arbitrary shell and Docker commands

### Execution identity — separate and narrowly scoped

Introduce only after source review:

- TestServer account: `homelab-stage5-executor`
- Jenkins credential: `homelab-stage5-testserver-executor`
- independent ED25519 key
- source restriction: `restrict,from="172.30.255.250"`
- public-key-only SSH
- no password
- no TTY
- no forwarding
- no tunnel
- no user RC
- no Docker group membership
- forced command: `/usr/local/sbin/homelab-stage5-executor-ssh`

The executor wrapper may allow only literal commands:

- `ping`
- `arm maintenance-page`
- `deploy maintenance-page`
- `rollback maintenance-page`
- `disarm maintenance-page`

It must reject `inspect maintenance-page`; inspection remains the responsibility of the read-only identity.

The Jenkins Pipeline must not bind the executor credential before the human `input` step and the second post-approval read-only drift check.

Human approval is a Jenkins workflow boundary rather than an interactive host prompt. The separate executor credential reduces accidental privilege crossover and preserves the previously proven inspection identity.

## Sequencing gap found during review

The merged source intentionally separates inspection and execution:

- `inspect` requires `mode=inspection-ready` and enable file absent;
- `deploy|rollback` requires `mode=execution-enabled`, an exact root-owned helper and a matching root-owned enable file.

The inspection helper itself also hard-requires `mode=inspection-ready` and fails when the enable file exists.

Therefore simply widening the existing inspection sudo rule is rejected. An explicit reviewed state transition and separate executor identity are required.

## Required state machine

### I0 — inspection-only

Current proven state.

Required:

- active policy = exact `inspection-ready` policy;
- enable file absent;
- inspection identity unchanged;
- all execution commands rejected.

Effective deployment authority: **false**.

### I1 — execution components staged, activation absent

Reviewed execution files may be installed root-owned without changing the active inspection policy or running container.

Required:

- exact reviewed deployment helper installed root:root and non-writable by non-root;
- exact reviewed transition helper installed root:root and non-writable by non-root;
- exact reviewed execution policy staged at a separate root-only path;
- root-owned state directory present;
- active policy remains exact `inspection-ready` policy;
- enable file remains absent;
- inspection identity and proof still pass unchanged;
- maintenance-page remains exact rollback digest;
- no container changes or restarts.

The dedicated executor account/credential may be staged only after its wrapper and sudo surface are separately reviewed. Jenkins must not bind that credential before approval.

### A — armed after human approval

The only transition from I1 to A is the executor literal command:

`arm maintenance-page`

The transition helper accepts no caller-supplied path, digest, service, policy or pilot identifier.

Before changing state it must revalidate:

- root execution and exact installed paths;
- root ownership/non-writability of transition/helper/policies;
- exact expected hash of the current inspection policy;
- exact expected hash of the staged execution policy;
- exact reviewed authority-gate and deployment-helper hashes;
- enable file absent;
- pilot consumed marker absent;
- exact clean root-owned docker-env authority checkout;
- exact docker-env authority commit;
- exact authority/live configuration hashes;
- exact rollback digest current;
- candidate and rollback images local Linux/ARM64;
- runtime shape and health pass;
- Jenkins and Jenkins-Docker protected identities available.

The arm operation then performs only these controlled state changes:

1. atomically replace the active policy with the exact pre-reviewed `execution-enabled` policy;
2. atomically create the root-owned enable file containing only the policy-pinned pilot ID.

It emits machine-readable JSON and does not mutate any container.

### D — deployed / pilot consumed

The existing deployment helper consumes `${pilot_id}.consumed` before Compose mutation.

Deployment is permitted only when:

- state A is valid;
- current runtime digest equals exact rollback digest;
- consumed marker does not yet exist;
- candidate and rollback are exact/local/ARM64;
- Git authority/configuration/runtime checks pass;
- health passes before mutation.

The only mutation primitive remains the internally constructed one-service command:

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

After mutation the helper must prove:

- maintenance-page container recreated;
- exact candidate digest current;
- runtime shape unchanged;
- HTTP health/marker pass;
- Jenkins and Jenkins-Docker identities/restart counters unchanged;
- unrelated container identities unchanged.

### R — rollback

Rollback is recovery for the exact consumed pilot, not a general deployment path.

It is allowed only when:

- pilot consumed marker exists;
- exact candidate digest is current;
- exact rollback image remains local Linux/ARM64;
- execution policy and enable file remain valid for the same pilot.

The existing helper already enforces these central rollback conditions and uses the same one-service Compose command class with the policy-pinned rollback digest.

### X — disarmed / terminal

Execution activation must not remain indefinitely after a successful pilot.

The literal command:

`disarm maintenance-page`

may run only after:

- deployment success and final Jenkins assertions pass; or
- deployment failure followed by proven rollback success.

Disarm removes the transient enable file. With the enable file absent, the authority gate cannot execute deploy or rollback even if the terminal execution policy remains active.

A later version update requires a new pilot policy in which the then-current image becomes the new rollback baseline.

If deployment and rollback both fail, Jenkins must not automatically destroy the reviewed recovery state. It must fail loudly for manual recovery.

## Jenkins approval pipeline

The installed Jenkins plugins already prove availability of:

- `pipeline-input-step`
- `credentials-binding`
- `ssh-credentials`
- `workflow-cps`
- `workflow-job`
- `workflow-basic-steps`

The Stage 5 Pipeline must:

1. checkout reviewed source;
2. bind only `homelab-stage5-testserver-inspector`;
3. run and parse pre-approval inspection;
4. independently assert exact pilot/service/authority/current/candidate/rollback/health/protected-state fields;
5. display those identities in the approval message;
6. block on `input(..., submitter: 'james')`;
7. bind the inspection credential again and repeat inspection;
8. require all critical fields to be unchanged;
9. only then bind `homelab-stage5-testserver-executor`;
10. arm the exact pilot;
11. deploy the exact pilot;
12. parse and assert the deployment result;
13. disarm on proven success;
14. archive inspection, arm, deployment and final-state artifacts.

The executor credential must never be in scope during the pre-approval stages.

## Executor forced-command wrapper

`/usr/local/sbin/homelab-stage5-executor-ssh` must map only exact literals:

```text
ping
arm maintenance-page
deploy maintenance-page
rollback maintenance-page
disarm maintenance-page
```

Everything else returns non-zero.

The wrapper must not parse or forward arbitrary arguments and must not call Docker directly.

## Executor sudo boundary

The executor sudoers entry may authorize only exact reviewed actions:

```text
/usr/local/libexec/homelab-stage5-maintenance-page-transition arm
/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate deploy
/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate rollback
/usr/local/libexec/homelab-stage5-maintenance-page-transition disarm
```

No wildcard command line, shell, Docker executable or Compose executable may appear in executor sudo authority.

The inspection account keeps its existing inspection-only sudoers entry unchanged.

## Policy transition model

Do not edit policy fields from caller input.

Use two exact root-owned files:

- active inspection policy: `/etc/homelab-stage5/maintenance-page.policy.json`;
- staged execution policy: `/etc/homelab-stage5/maintenance-page.execution-policy.json`.

The transition helper pins both expected SHA256 values and copies only the exact reviewed staged execution policy into the active path.

The execution policy must contain:

- `mode=execution-enabled`;
- same pilot ID/service/host/project/Compose path;
- same exact docker-env authority commit and checkout;
- same configuration hashes;
- same candidate and rollback immutable digests;
- exact authority gate/helper/inspector hashes;
- exact implementation commit;
- `inspection.allowed=true`;
- `deployment.allowed=true`;
- `deployment.performed=false`;
- `deploy_command_enabled=true`;
- `rollback_command_enabled=true`.

The enable file is the independent host-side activation condition and contains only the exact pilot ID.

## Jenkins failure handling

### Before arm

Fail build. No deployment state has changed.

### Arm failure

Do not deploy. Verify active policy/enable state and fail.

### Deploy success

Assert deployment artifact and final invariants, archive evidence, then disarm.

### Deploy failure

Attempt rollback only through the reviewed executor path and only if the helper's rollback preconditions are satisfied.

If rollback succeeds, verify rollback identity/health, archive evidence, then disarm.

If rollback fails, do not run improvised Docker commands and do not automatically disarm. Fail for manual recovery.

## Permanent exclusions

The first execution pilot continues to exclude:

- Jenkins controller self-deployment;
- Jenkins-Docker/DinD mutation;
- Docker registry mutation;
- Kubernetes control plane;
- Pi-hole/Unbound;
- router/switch/network control plane;
- Greenbone control plane;
- Prometheus/Grafana/Loki control plane;
- arbitrary container selection;
- arbitrary image/digest input;
- arbitrary Compose paths;
- arbitrary shell/Docker commands.

Jenkins remains a permanent self-deployment exception.

## Required proof order before live deployment

1. Source-only execution-transition design reviewed.
2. Add transition helper, executor wrapper, execution policy template and static validator on the source-only branch.
3. Static validator proves no arbitrary argument/shell/Docker authority leaks through wrappers.
4. Pin exact reviewed hashes.
5. Host installation rehearsal from a clean exact Git checkout.
6. Stage execution components while active policy remains inspection-only; prove existing inspection path still passes and no container changes.
7. Create dedicated executor account/key/Jenkins credential and prove its SSH/source/forced-command restrictions.
8. Add source-only Jenkins approval pipeline and validate the executor credential is not in scope before `input`.
9. Negative proof using inspection identity: arm/deploy/rollback/disarm remain rejected.
10. Human approval in Jenkins.
11. Repeat read-only inspection and drift comparison.
12. Bind executor credential.
13. Arm exact pilot.
14. Execute exactly one maintenance-page deployment.
15. Verify exact candidate, health and protected-state invariants.
16. Disarm after proven success.
17. Archive evidence and document result.
18. If required, prove exact rollback under the same consumed pilot.

## Current status

This branch is source-only.

No host file has been installed or modified by this design.

No account or Jenkins credential has been created.

No sudo authority has changed.

No Jenkins job has changed.

No enable file has been created.

No policy has been activated.

No container has changed.

No Stage 5 deployment has been performed.
