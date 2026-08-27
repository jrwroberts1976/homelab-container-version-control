# Stage 6 Jenkins inspector smoke pipeline

Status: source-only Jenkins read-only smoke contract under review

Date: 2026-08-27

## Purpose

Prove the Jenkins-managed `homelab-stage6-testserver-inspector` credential can reach the already-proven Stage 6 inspector transport and obtain the generic Dashy inspection artifact before any Stage 6 executor credential is created.

This is intentionally narrower than the later human-approval deployment pipeline.

## Proven Jenkins job pattern

The existing Stage 5 pilot job is a lightweight Pipeline from SCM using:

- repository: `https://github.com/jrwroberts1976/homelab-container-version-control.git`;
- branch specification: `*/main`;
- script path: `Jenkinsfile.stage5-maintenance-page-pilot`.

The Stage 6 smoke job should copy that SCM arrangement and use script path:

`Jenkinsfile.stage6-dashy-inspector-smoke`

## Credential boundary

The pipeline binds exactly one credential:

`homelab-stage6-testserver-inspector`

The bound username must be exactly:

`homelab-stage6-inspector`

The Stage 6 executor credential must not exist in the smoke pipeline source and must remain absent from Jenkins during the live smoke proof.

## Remote command surface

The pipeline sends only two literal remote commands through the forced-command inspector transport:

1. `ping`;
2. `inspect dashy`.

Both SSH calls use `-n` and `</dev/null`, `IdentitiesOnly=yes`, `BatchMode=yes`, password and keyboard-interactive authentication disabled, strict host-key checking, and the existing pinned TestServer known-hosts file.

The smoke pipeline contains no `arm dashy`, `deploy dashy`, `rollback dashy`, `disarm dashy`, transition helper or execution helper call.

## Read-only artifact gates

The returned inspection must prove:

- schema version `1`;
- artifact `service-update-inspection`;
- mode `stage6-preapproval-inspect`;
- service `dashy` on `TestServer`;
- current state is exact rollback baseline `lissy93/dashy:4.5.13`;
- rollback immutable reference and local ARM64 image identity are exact;
- candidate immutable reference, local ARM64 image identity, platform manifest and source revision are exact;
- runtime invariants pass;
- Docker health is healthy;
- human approval is required and not granted;
- deployment is not allowed and not performed;
- result is `ready-for-human-review`.

The full returned artifact and a validated evidence subset are archived by Jenkins.

## Safety properties

This source-only pipeline:

- does not create or modify Jenkins credentials;
- does not create the Stage 6 executor credential;
- does not contain a Jenkins human approval input;
- does not arm an update;
- does not create an enable or consumed marker;
- does not call the Stage 6 transition or execution helpers;
- does not recreate Dashy or any other container;
- does not pull an image;
- does not mutate Git authority or the live Compose tree.

The source guard `scripts/validate-stage6-jenkins-inspector-smoke.sh` enforces the credential, remote-command, SSH stdin-isolation, immutable-identity, CPS-safe JSON parsing, health and deployment-false requirements.

## Live validation sequence

After source review and merge:

1. create a Jenkins Pipeline-from-SCM job using the proven Stage 5 SCM settings and the Stage 6 smoke script path;
2. verify the Stage 6 executor credential remains absent;
3. record Dashy, Jenkins and Jenkins-DinD container identities/restart counts and prove Stage 6 state absent;
4. run the smoke job once;
5. require Jenkins `SUCCESS`;
6. inspect archived ping and inspection evidence;
7. prove the inspection result is `ready-for-human-review` with deployment false;
8. prove Stage 6 state is still absent and every container is unchanged;
9. only after this proof move on to the full Stage 6 human-approval pipeline source review.

No executor credential should be created as part of this smoke proof.
