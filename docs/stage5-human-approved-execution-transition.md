# Stage 5 human-approved execution transition

Status: source-only design review

Date: 2026-08-27

## Goal

Preserve the proven Stage 5 inspection-only boundary while adding a reviewed, one-shot path for Jenkins to perform exactly one human-approved `maintenance-page` container update.

The intended pilot flow is:

1. Jenkins performs the existing remote `inspect maintenance-page` operation.
2. Jenkins parses and independently validates the returned inspection artifact.
3. Jenkins presents the exact current, candidate and rollback identities to a human approver.
4. Jenkins blocks on the Pipeline `input` step; only the Jenkins user `james` may approve the pilot.
5. After approval, Jenkins immediately repeats the read-only inspection and requires all critical identities to match the pre-approval artifact.
6. Jenkins invokes one reviewed `arm maintenance-page` transition.
7. Jenkins invokes one reviewed `deploy maintenance-page` action.
8. The root helper verifies the exact candidate, rollback, Git authority, configuration, runtime shape, protected Jenkins/DinD state and HTTP health before and after mutation.
9. If deployment succeeds, Jenkins records the result and removes the transient execution activation.
10. If deployment fails after activation, rollback remains available only for the same consumed pilot. Jenkins attempts the exact reviewed rollback path when it is safe to do so; if rollback cannot be proven safe, execution remains fail-closed for manual recovery rather than improvising.

Jenkins must never receive general shell, Docker socket, arbitrary Docker/Compose, arbitrary service-name, arbitrary digest, arbitrary path, or arbitrary Git authority.

## Proven starting point

The current host is inspection-only and has already passed the live execution-transition preflight.

Current installed state:

- account: `homelab-stage5-pilot`
- Jenkins credential: `homelab-stage5-testserver-inspector`
- Jenkins source identity: `172.30.255.250`
- TestServer SSH destination: `172.30.255.249:22`
- forced command: `/usr/local/sbin/homelab-stage5-pilot-ssh`
- authority gate: `/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate`
- inspector: `/usr/local/libexec/homelab-stage5-maintenance-page-inspect`
- policy mode: `inspection-ready`
- inspection sudo authority only
- deployment helper absent
- execution enable file absent
- deploy sudo authority absent
- rollback sudo authority absent
- candidate and rollback images both local as Linux/ARM64
- live configuration matches the pinned docker-env authority byte-for-byte
- maintenance-page remains on the exact rollback digest

The existing Stage 5 positive and negative remote proofs are accepted prerequisites and must not be invalidated by this transition.

## Sequencing gap found during review

The merged source intentionally separates inspection and execution:

- `inspect` requires `mode=inspection-ready` and requires the enable file to be absent;
- `deploy|rollback` requires `mode=execution-enabled`, an exact root-owned helper and a matching root-owned enable file.

The installed inspection helper also requires `mode=inspection-ready` and fails if the enable file exists.

Therefore a single Jenkins pipeline cannot safely move directly from the current inspection state to deployment merely by widening sudo. An explicit reviewed transition is required between human approval and deployment.

## Required state machine

The pilot must have explicit states rather than inferred authority.

### I0 — inspection-only

This is the current proven state.

Required:

- active policy = exact `inspection-ready` policy;
- enable file absent;
- deployment helper may remain absent during the currently proven phase;
- wrapper permits only `ping` and `inspect maintenance-page`;
- deployment requests are rejected.

Effective deployment authority: **false**.

### I1 — execution components staged but inactive

Before any human-approved execution test, reviewed execution files may be installed root-owned while effective deployment authority remains absent.

Required:

- exact reviewed deployment helper installed root:root and non-writable by non-root;
- exact reviewed execution-transition helper installed root:root and non-writable by non-root;
- exact reviewed execution policy staged at a separate root-only path;
- state directory root:root and non-writable by non-root;
- active policy remains the exact inspection-ready policy;
- enable file absent;
- existing inspection path still passes;
- deploy/rollback remain rejected.

Effective deployment authority: **false**.

This state must be proven before any `arm` command is made reachable from Jenkins.

### A — armed after human approval

The only allowed transition from I1 to A is the reviewed literal command:

`arm maintenance-page`

The arm helper runs as root through exact sudo authority and accepts no user-supplied path, digest, service, policy or pilot identifier.

Before changing state it must revalidate:

- root execution and exact installed paths;
- exact hashes of the authority gate, arm helper, deployment helper and staged execution policy;
- current active policy hash equals the accepted inspection-ready policy;
- enable file absent;
- pilot consumed marker absent;
- exact clean root-owned docker-env authority checkout;
- exact docker-env authority commit;
- exact authority/live configuration hashes;
- exact rollback digest is current;
- exact candidate and rollback images are local Linux/ARM64;
- current runtime shape and health pass;
- Jenkins and Jenkins-Docker protected identities are available.

The arm operation then performs only two controlled state changes:

1. atomically replace the active policy with the exact pre-reviewed `execution-enabled` policy;
2. atomically create the root-owned enable file containing only the policy-pinned pilot ID.

The arm result must emit machine-readable JSON identifying the pilot and confirming activation. It must not mutate a container.

Effective deployment authority: **true for the exact pilot only**.

### D — deployed / pilot consumed

The existing deployment helper already consumes `${pilot_id}.consumed` before the Compose mutation.

Deployment is allowed only when:

- state A is active;
- current runtime digest is the exact rollback digest;
- consumed marker does not yet exist;
- candidate and rollback are exact/local/ARM64;
- configuration and runtime shape match policy;
- health passes before mutation.

The only mutation primitive remains the internally constructed service-scoped command:

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

- the maintenance-page container was recreated;
- exact candidate digest is current;
- runtime shape is unchanged;
- HTTP health and marker pass;
- Jenkins and Jenkins-Docker identities/restart counters are unchanged;
- unrelated container identities are unchanged.

### R — rollback

Rollback is recovery for the exact consumed pilot, not a general second deployment mechanism.

It is allowed only when:

- the pilot consumed marker exists;
- the exact candidate digest is current;
- the exact rollback image remains local Linux/ARM64;
- execution policy and enable file remain valid for the same pilot.

The existing helper already enforces these core conditions and uses the same one-service Compose command class with the policy-pinned rollback digest.

After rollback it must prove exact rollback digest, runtime shape, health and protected-state invariants.

### X — disarmed / terminal

Execution activation must not remain indefinitely after a successful pilot.

A reviewed literal command:

`disarm maintenance-page`

must remove only the transient execution activation after one of these outcomes:

- deployment success and final Jenkins assertions pass; or
- deployment failure followed by proven rollback success.

The disarm helper must remove the enable file atomically and leave no general deployment path usable.

For the first pilot it may leave the execution policy as a terminal record, because the current candidate is no longer the old rollback baseline after successful deployment. A later version update must create a new policy/pilot with the newly running image as the new rollback identity.

If deployment and rollback both fail, Jenkins must **not** automatically disarm and thereby destroy the reviewed recovery path. The job must fail loudly and preserve state for manual recovery.

## Jenkins approval boundary

The Jenkins Pipeline must use the installed `pipeline-input-step` capability.

The approval stage must:

- occur only after the first inspection artifact has passed all assertions;
- display the exact service, pilot ID, current digest, candidate digest, rollback digest and health state;
- use `submitter: 'james'` for the first pilot;
- make no host-side execution change before approval;
- immediately repeat inspection after approval and require the critical identity fields to be unchanged before arming.

Human approval is a Jenkins workflow boundary. The host wrapper does not attempt to implement an interactive approval prompt.

The Stage 5 SSH key remains source-restricted to Jenkins `172.30.255.250`, and the TestServer host key remains strictly pinned in Jenkins.

## Execution-capable forced-command wrapper

The reviewed execution wrapper must remain literal and allow-list only:

- `ping`
- `inspect maintenance-page`
- `arm maintenance-page`
- `deploy maintenance-page`
- `rollback maintenance-page`
- `disarm maintenance-page`

Everything else must return non-zero.

The wrapper must not parse or forward arbitrary arguments.

Each privileged action must map to one exact sudo command. Jenkins receives no direct sudo command, no shell and no Docker access.

## Sudo boundary

The final pilot sudoers entry may authorize only exact reviewed binaries/actions such as:

```text
/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate inspect
/usr/local/libexec/homelab-stage5-maintenance-page-transition arm
/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate deploy
/usr/local/libexec/homelab-stage5-maintenance-page-authority-gate rollback
/usr/local/libexec/homelab-stage5-maintenance-page-transition disarm
```

No wildcard command line, shell, Docker executable or Compose executable may appear in the Stage 5 account sudo authority.

## Policy transition model

Do not edit policy fields in place from unreviewed input.

The recommended first-pilot model is two exact root-owned files:

- active inspection policy: `/etc/homelab-stage5/maintenance-page.policy.json`;
- staged execution policy: `/etc/homelab-stage5/maintenance-page.execution-policy.json`.

The transition helper must pin both expected SHA256 values and copy/rename only the exact reviewed staged execution policy into the active path.

The execution policy must contain:

- `mode=execution-enabled`;
- same immutable pilot ID;
- same service/host/project/Compose path;
- same exact docker-env authority commit and checkout;
- same configuration hashes;
- same candidate and rollback immutable digests;
- exact authority gate/helper/inspector/transition hashes;
- `inspection.allowed=true`;
- `deployment.allowed=true`;
- `deployment.performed=false`;
- `deploy_command_enabled=true`;
- `rollback_command_enabled=true`.

The enable file provides the second independent activation condition and must contain only the exact policy pilot ID.

## Jenkins failure handling

The Pipeline must distinguish failure phases.

### Failure before arm

No deployment authority has been activated. Fail the build. No rollback command is needed.

### Arm failure

No deployment may be attempted. Fail the build and verify enable/policy state.

### Deploy success

Parse and assert the deployment artifact, run final health/invariant checks, archive artifacts, then disarm.

### Deploy failure

Attempt rollback only if the host-side rollback preconditions can be satisfied by the reviewed helper. Capture both deployment and rollback output.

If rollback succeeds, verify rollback identity/health and disarm.

If rollback fails, do not improvise with Docker commands and do not automatically destroy the activation state. Fail the build for manual recovery.

## Permanent exclusions

The first Stage 5 execution pilot must continue to exclude:

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

1. Source-only execution-transition branch reviewed.
2. Static validator proves wrapper and transition helpers contain no arbitrary shell/argument forwarding.
3. Exact hashes pinned into the staged execution policy.
4. Host installation rehearsal from a clean exact Git checkout.
5. Install execution components while remaining in I1; prove current inspection path still passes and deploy/rollback/arm are still unreachable.
6. Jenkins source-only Pipeline review with `input` approval and second inspection drift check.
7. Negative proof before approval: arm/deploy/rollback rejected.
8. Human approval in Jenkins.
9. Arm exact pilot.
10. Execute exactly one maintenance-page deployment.
11. Verify exact candidate, health and protected-state invariants.
12. Disarm immediately after proven success.
13. Archive evidence and document result.
14. If required, prove exact rollback path under the same consumed pilot.

## Current status

This document changes source documentation only.

No host file is installed or modified by this commit.

No sudo authority is changed.

No Jenkins job is changed.

No enable file is created.

No policy is activated.

No container is changed.

No Stage 5 deployment is performed.
