# Stage 5 Jenkins human-approval pipeline

Status: source-only review

Date: 2026-08-27

## Purpose

Add a dedicated Jenkins pipeline for the single `maintenance-page` Stage 5 pilot without modifying the existing Stage 4 `Jenkinsfile` or installing live execution sudo authority.

The key control is credential sequencing. Jenkins may use the permanent inspection credential before approval, but the executor credential must not be bound until all of the following are true:

1. first remote inspection succeeded;
2. exact current/candidate/rollback/Git-authority/health/protected-state values were independently asserted;
3. Jenkins `input` was approved by `james`;
4. a second remote inspection succeeded;
5. the second inspection exactly matched the first on critical state;
6. deployment was still disabled in that second inspection artifact.

Only after those checks may the executor credential enter scope.

## Source separation

The Stage 4 root `Jenkinsfile` remains unchanged. The pilot uses:

- `Jenkinsfile.stage5-maintenance-page-pilot`
- `scripts/validate-stage5-jenkins-human-approval-pipeline.sh`

The Stage 5 implementation merged at `a7fb8258b2d7a401e4bb494846b8a764e95aa0fc` is treated as the frozen core source baseline. The pilot pins exact hashes for the authority gate, inspector, deployment helper, transition helper, executor wrapper and execution policy.

## Jenkins sequence

### 1. Checkout and preflight

The pipeline checks the exact reviewed implementation hashes and pinned TestServer host-key fingerprint.

### 2. First inspection

Jenkins binds only `homelab-stage5-testserver-inspector` and sends literal:

```text
inspect maintenance-page
```

The artifact must prove:

- exact pilot ID;
- TestServer host;
- exact docker-env authority commit;
- current runtime equals rollback digest;
- exact candidate and rollback immutable digests and image IDs;
- both images are local Linux/ARM64;
- health passes;
- protected Jenkins and Jenkins-Docker identities are captured;
- approval is required and not granted;
- deployment is not allowed and not performed;
- deploy and rollback commands are disabled.

A critical-state subset is written to an artifact for later byte-semantic comparison.

### 3. Human approval

The pipeline blocks on one Jenkins `input` step for at most 60 minutes. The submitter is restricted to `james` and the approver identity is recorded.

No executor credential has been referenced or bound at this point.

### 4. Second inspection and drift check

Jenkins re-binds only the inspection credential and repeats literal `inspect maintenance-page`.

The second artifact must still show deployment disabled and must match the first critical-state artifact exactly for pilot, image, runtime, health and protected Jenkins/DinD identities.

Any drift fails closed before the executor credential is bound.

### 5. Arm

Only after the second drift gate does Jenkins first bind `homelab-stage5-testserver-executor` and send literal:

```text
arm maintenance-page
```

The returned transition artifact must match the exact pilot and execution-policy SHA256 `e8c629e34d16a02b2dc9a979dbe50da47dace810875bbc3296cead6285af2bc5` and report `result=armed` with no deployment performed.

### 6. Deploy

Jenkins sends literal:

```text
deploy maintenance-page
```

The helper artifact must report the exact candidate/rollback identities, `deployment.allowed=true`, `deployment.performed=true`, and `result=success`.

The host helper remains responsible for the actual exact service-scoped Compose action and protected-container/health invariants. Jenkins does not receive Docker or Compose authority.

### 7. Recovery

If deploy returns non-zero, Jenkins sends only literal:

```text
rollback maintenance-page
```

If rollback succeeds, the rollback artifact must prove the exact rollback identity and Jenkins proceeds to disarm.

If rollback fails, the pipeline stops and deliberately leaves execution armed for controlled manual recovery. It does not improvise Docker commands and it does not automatically remove the reviewed recovery path.

### 8. Disarm

After proven deploy success or proven rollback success, Jenkins sends literal:

```text
disarm maintenance-page
```

The transition artifact must report execution activation false and the expected terminal current digest.

## Explicit exclusions

The pilot exposes no Jenkins parameter for service, image, digest, path, host or command. It contains no direct Docker/Compose invocation, sudo invocation, arbitrary shell forwarding or arbitrary remote command construction.

Jenkins self-deployment remains excluded.

## Current live state during source review

At the time this source branch is created:

- Stage 5 execution components are staged on TestServer;
- executor account and restricted SSH transport are proven;
- executor Jenkins key fingerprint is `SHA256:0mY135q5LD0cNgH9UlSwz0IWW7GHOZfEdvWU8YpyPr0`;
- executor sudo authority is still absent;
- enable file is absent;
- active policy remains inspection-ready;
- maintenance-page remains the rollback digest;
- no Stage 5 deployment has been performed.

The live four-command executor sudo surface must not be installed until this pipeline source has passed static review and Jenkins declarative syntax validation.
