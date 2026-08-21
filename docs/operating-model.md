# Operating Model

## Change flow

1. A new image version is detected by Renovate, WUD or manual review.
2. The desired-state change is proposed in Git.
3. Jenkins validates configuration, policy, downgrade risk, image compatibility, vulnerabilities and secret readiness.
4. An authorised operator reviews the plan.
5. Deployment is performed through the guarded deployment workflow.
6. Health and application smoke checks run.
7. Runtime inventory confirms the deployed tag/digest matches Git.
8. Prometheus/Grafana reports compliance or drift.

## Source of truth

Git-controlled Compose configuration is authoritative.

A running container that differs from Git is not automatically accepted as the new desired state. The difference must be investigated and either:

- Git is deliberately updated to reflect an approved runtime state; or
- runtime is brought back to the approved Git state.

## Update sources

### Renovate

Primary controlled proposal mechanism for supported image declarations.

### WUD

Independent runtime update signal and cross-check. WUD must not automatically replace production images.

### Manual/vendor advisory

Used when a release requires explicit operational review, security urgency or registry tooling does not provide a usable signal.

## Change classes

### Routine

Patch/digest change with no documented breaking change. Still requires validation and health verification.

### Elevated

Minor/major version changes, stateful services, schema migrations, authentication/networking changes or security-tool changes. Requires explicit review and service-specific rollback planning.

### Emergency

Urgent security or availability remediation. May use an accelerated review path but must still record desired state, rollback point and post-change validation in Git.

## Deployment rules

- Deploy one stack/service scope at a time unless a coordinated change requires otherwise.
- Never use `docker compose up -d` as an unreviewed production version change once the guarded workflow is live.
- Keep the previous image locally until acceptance checks pass.
- Do not prune rollback images as part of the same change.
- Critical stateful services require a current backup/restore confidence check before upgrade.
- DNS and core monitoring changes are scheduled after lower-risk services have proven the workflow.

## Secrets rules

- Encrypted source only in Git.
- Decrypt only when necessary.
- Prefer Compose secret files.
- Plaintext `.env` secret files are migration exceptions, not the target state.
- Jenkins must not archive decrypted secrets.
- Failed jobs must clean temporary secret material.

## Drift response

When drift is detected:

1. identify whether Git or runtime changed;
2. determine whether the runtime state was authorised;
3. inspect service health and recent deployment history;
4. either reconcile runtime to Git or submit a Git change that formally adopts the runtime version;
5. record the cause if the drift resulted from bypassing the controlled process.

## Rollback trigger

Rollback should be initiated when any required acceptance condition fails, including:

- container health remains unhealthy;
- required port/HTTP/DNS smoke test fails;
- dependent service breaks;
- logs show migration/configuration errors;
- security or policy check identifies an unacceptable regression.

## Evidence retained per change

The deployment workflow should record:

- Git commit/PR;
- host/stack/service;
- previous tag/digest;
- candidate tag/digest;
- validation result;
- Trivy result summary;
- deployment timestamp;
- health/smoke-test result;
- rollback version;
- final runtime digest.

No secret values are included in deployment evidence.
