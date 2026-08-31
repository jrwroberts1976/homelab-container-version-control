# Operating Model

## Change flow

The Stage 6 target flow for a reviewed Docker/Compose registry-image service is:

1. A new image version is detected by Renovate, WUD or manual/vendor review.
2. The candidate/version is represented by reviewed Git-controlled Stage 6 data; WUD remains a signal rather than deployment authority.
3. Jenkins resolves the reviewed service/host route and validates the manifest/framework source.
4. Jenkins uses a dedicated restricted candidate-acquisition identity to pull the exact immutable candidate into the target host image cache.
5. Candidate acquisition verifies local image/config ID, RepoDigest and platform and proves that no running container state changed.
6. Jenkins performs the first read-only pre-approval inspection and proves authority, rollback, candidate, runtime, health and protected-container identities.
7. An authorised operator reviews the exact evidence and explicitly approves the deployment.
8. Jenkins performs a second read-only inspection and requires exact zero drift.
9. Only after approval and zero drift does Jenkins expose the full deployment executor credential.
10. The exact one-shot update is armed.
11. Only the reviewed service is recreated using the already-local immutable candidate with `--no-deps --no-build --pull never --force-recreate`.
12. Health, runtime and protected-container acceptance checks run.
13. A reviewed rollback is performed only if candidate acceptance fails.
14. One-shot deployment authority is disarmed at the reviewed terminal state.
15. A successful candidate is promoted into durable immutable Git Compose authority.
16. The merged authority is synchronised to the live/root-owned authority checkouts without recreating the already-healthy service.
17. The estate catalogue and Stage 6 steady-state manifest are generated/promoted from reviewed evidence.
18. The reviewed steady-state data is installed through the approved root-owned path.
19. A final read-only steady-state inspection proves authority/runtime/health agreement.
20. Jenkins archives non-secret evidence and reports the explicit terminal result.

A routine fresh update is fully complete only at:

```text
SUCCESS_CLOSED
```

## Source of truth

Git-controlled Compose configuration is authoritative.

A running container that differs from Git is not automatically accepted as the new desired state. The difference must be investigated and either:

- Git is deliberately updated to reflect an approved runtime state; or
- runtime is brought back to the approved Git state.

Stage 6 adds an important closure rule: after a reviewed successful deployment, the exact immutable runtime candidate must be promoted into the durable Compose authority rather than leaving an older default behind.

The estate catalogue and installed steady-state manifest must then agree with that authority and runtime before the update is considered fully closed.

## Update sources

### Renovate

Primary controlled proposal mechanism for supported Git image declarations where configured.

### WUD

Independent runtime update signal and cross-check. WUD must not automatically replace production images.

A WUD error is an unavailable/failed discovery signal, not evidence that no update exists.

### Manual/vendor advisory

Used when a release requires explicit operational review, security urgency or registry tooling does not provide a usable signal.

## Jenkins reviewed target selection

The normal operator interface should select from reviewed installed services rather than accept arbitrary container names, image references or manifest paths.

The desired selector is generated from governed Git-controlled estate data and resolves internally to:

- service/container identity;
- host;
- update manifest;
- steady-state manifest where present;
- reviewed SSH route/host-key pin;
- credential routes;
- current and proposed version information.

Live `docker ps` output may be used for reconciliation, but must not become an unrestricted execution selector.

## Candidate acquisition authority

Candidate acquisition mutates only the local Docker image cache and occurs before human approval.

It must use a separate restricted identity from the full deployment executor.

The acquisition helper may:

- read the installed reviewed Stage 6 manifest;
- pull the exact immutable candidate referenced there;
- inspect image identity/platform metadata;
- inspect running container state to prove it did not change.

It must not:

- accept an arbitrary caller-supplied image/digest/path;
- run Compose;
- arm an update;
- recreate/restart/remove a container;
- deploy or roll back a service.

The full executor credential remains unavailable until after human approval and exact zero-drift reinspection.

## Change classes

### Routine

Patch/digest change with no documented breaking change. Still requires candidate identity validation, human review where the Stage 6 manifest requires it, deployment acceptance and final closure.

### Elevated

Minor/major version changes, stateful services, schema migrations, authentication/networking changes, writable-Docker-socket workloads, privileged/device-backed services, control-plane services or security-tool changes. Requires explicit review and service-specific rollback/backup controls. Generic framework limits must not be broadly weakened merely to onboard these services.

### Emergency

Urgent security or availability remediation. May use an accelerated review path only if separately designed and approved, but must still preserve exact desired state, rollback evidence and post-change validation.

## Deployment rules

- Deploy one reviewed service scope at a time unless a coordinated change has a separately reviewed contract.
- Never use `docker compose up -d` as an unreviewed production version change once the guarded workflow is live.
- Deployment uses the exact already-verified local immutable candidate and `--pull never`.
- Keep the previous image locally until acceptance and closure pass.
- Do not prune rollback images as part of the same change.
- Critical/stateful services require current backup/restore confidence before upgrade.
- DNS and core monitoring changes follow lower-risk service proof and service-specific controls.
- Closure stages must not recreate an already-proven healthy candidate.
- A historical Jenkins failure after a successful deployment is not by itself a reason to redeploy or roll back; determine whether the failure is deployment acceptance or post-deployment closure.

## Closed-state verification

An already-completed service may be verified through a non-mutating `VERIFY_CLOSED` or equivalent action.

This path checks the governed catalogue/steady-state/authority/runtime/health state without acquiring or deploying a new candidate.

Recommended successful result:

```text
SUCCESS_VERIFIED_CLOSED
```

This is the correct model for testing a corrected framework against a service such as Dozzle whose one-shot deployment has already been consumed.

## Secrets rules

- Encrypted source only in Git.
- Decrypt only when necessary.
- Prefer Compose secret files.
- Plaintext `.env` secret files are migration exceptions, not the target state.
- Jenkins must not archive decrypted secrets.
- Failed jobs must clean temporary secret material.
- Restricted Stage 6 SSH credentials remain narrowly scoped by function and fixed host route.

## Drift response

When drift is detected:

1. identify whether Git authority, installed Stage 6 state or runtime changed;
2. determine whether the runtime state was authorised;
3. inspect service health, consumed/arm state and recent deployment history;
4. if the runtime is an approved healthy candidate with incomplete closure, resume the reviewed closure path without unnecessary recreation;
5. otherwise reconcile runtime to Git or submit a reviewed Git change that formally adopts the approved runtime version;
6. record the cause if the drift resulted from bypassing the controlled process.

## Rollback trigger

Rollback should be initiated when a required deployment acceptance condition fails, including:

- exact candidate image identity is wrong;
- container health remains unhealthy;
- required HTTP/DNS/port health check fails;
- required runtime invariant changes unexpectedly;
- protected/unrelated containers changed;
- dependent service breaks;
- logs show migration/configuration errors;
- security or policy check identifies an unacceptable regression.

A later authority/catalogue/steady-state bookkeeping failure after the exact candidate already passed deployment acceptance is **not** automatically a rollback trigger. It is a closure failure and should resume safely without recreating the healthy service.

## Evidence retained per change

The end-to-end workflow should record, without secret values:

- Git/framework revision;
- reviewed service manifest identity/hash;
- host/service route;
- previous version/immutable image/local image ID;
- candidate version/immutable image/index/platform/config identity;
- candidate-acquisition result and proof of no container mutation;
- pre-approval inspection artifact;
- approving operator;
- post-approval zero-drift artifact;
- exact update ID;
- deployment/rollback result;
- health/runtime/protected-container acceptance evidence;
- disarm/consumed evidence;
- promoted Compose authority revision and SHA;
- catalogue/steady-state promotion revision;
- final read-only steady-state result;
- explicit terminal result state.

No secret values are included in deployment evidence.

## Explicit terminal states

The current recommended state model is:

```text
SUCCESS_CLOSED
SUCCESS_VERIFIED_CLOSED
DEPLOYED_BUT_CLOSURE_INCOMPLETE
ROLLED_BACK_CLOSED
PRE_DEPLOYMENT_FAILED
MANUAL_REVIEW_REQUIRED
```

A container merely being `running` is not a Stage 6 success criterion.
