# User Guide — Update an Existing Docker Container

## Purpose

Use this guide when changing the image version or build revision of an existing managed Docker service.

The core rule is:

> Change Git desired state first. Do not update the running container first and reconcile Git afterward.

This prevents silent downgrade risk, preserves auditability and gives the deployment/rollback process an exact target.

## Current Stage 4 rule

The current platform can validate an update proposal and produce a deployment plan, but it must stop before deployment.

```text
deployment.allowed=false
deployment.performed=false
```

The Stage 5 deployment section in this guide is the intended future procedure and is not currently enabled.

---

## 1. Identify the authoritative service record

Start with:

```text
docs/testserver-container-configuration-inventory.md
```

Confirm:

- container/service name;
- Compose stack;
- current desired image/build;
- Git authority;
- image type;
- configuration/secret dependencies; and
- whether the service is a platform exception.

For normal TestServer services, the desired image declaration is usually in `jrwroberts1976/docker-env`.

Do not update a runtime container whose Git authority cannot be established.

## 2. Identify the update source

An update may be proposed by:

- Renovate;
- WUD;
- vendor/security advisory;
- manual maintenance review; or
- a new local-build source revision.

Renovate and WUD are proposal/signal sources only. They do not have authority to replace production containers directly.

## 3. Classify the change

Before changing Compose, determine the risk class.

### Routine

Examples:

- patch release;
- known immutable digest update under the same release tag.

### Elevated

Examples:

- minor release with compatibility risk;
- major release;
- stateful/schema-changing service;
- DNS/security/control-plane service;
- data store or monitoring store;
- vendor stack with coordinated component versions.

Elevated changes require release-note, compatibility, migration, backup and rollback review as applicable.

Do not infer version ordering where a tag scheme is opaque or non-standard. The update must fail closed if safe ordering cannot be established.

## 4. Review release and compatibility information

Before accepting a candidate, check as applicable:

- release notes/changelog;
- architecture support, especially `linux/arm64` on TestServer;
- breaking configuration changes;
- required environment-variable changes;
- secret-delivery changes;
- volume/data migration requirements;
- schema changes;
- dependency compatibility; and
- rollback/downgrade restrictions.

A major or stateful update must not proceed simply because the image exists for the target architecture.

## 5. Record the current known-good state

Before deployment is ever considered, the plan must be able to identify:

- current Git revision;
- current desired image declaration;
- current runtime creation reference;
- current image ID;
- current repo digest when available;
- relevant configuration revision/checksum without secret values;
- secret names/readiness only; and
- rollback image/source revision.

Do not prune the known-good image during the change.

## 6. Change the Git-controlled desired state

Modify only the authoritative Compose/source declaration.

Example registry-image update:

```yaml
image: vendor/example:1.2.3
```

to:

```yaml
image: vendor/example:1.2.4
```

Where digest pinning is used, update the digest as part of the same reviewed change.

For a local build, the update is normally a reviewed source revision that will later produce a new provenance-labelled image. Do not fake a registry version for a local build.

## 7. Update configuration metadata if required

If the new version introduces or removes configuration inputs:

- update Compose safely;
- update SOPS-backed recovery sources where secret names/schema change;
- update `config/secret-readiness.yml` if readiness rules change;
- update `config/local-build-provenance.yml` for build/provenance changes;
- update `config/version-schemes.yml` if the version scheme changes; and
- update the master container/configuration inventory.

Never add plaintext secret values to Git or deployment-plan output.

## 8. Validate Compose

From the clean authoritative Git checkout, run the appropriate validation.

Typical check:

```bash
docker compose config >/dev/null
```

Do not use `docker compose pull`, `docker compose up`, manual `docker pull`, restart or recreate as a Stage 4 validation shortcut.

## 9. Run the Stage 4 candidate validation

The managed validation path should establish:

```text
ownership
current -> candidate identity
upgrade/downgrade decision
architecture/manifest
Trivy result
secret readiness
local-build provenance where applicable
deployment-plan artifact
```

The candidate planner may inspect registry manifests/digests without pulling image layers.

Expected safe outcomes include:

- `same` / no change;
- valid upgrade ready for review; or
- a deliberate blocked result requiring operator investigation.

Examples of reasons to stop:

- downgrade detected;
- ordering unknown;
- same tag resolves to a different digest under a moving-channel policy;
- wrong/missing target architecture;
- HIGH/CRITICAL security gate failure under current policy;
- secret readiness failure;
- local-build provenance failure;
- dirty/untrusted Git authority; or
- platform exception requiring manual handling.

Do not bypass a blocked result by recreating the container manually.

## 10. Review the non-secret deployment plan

Before any future deployment, confirm the plan identifies the correct:

- host;
- Compose project/service;
- Git repository and revision;
- runtime image/digest;
- candidate image/digest/platform;
- gate results;
- decision; and
- proposed action.

During Stage 4 it must still report:

```text
deployment.allowed=false
deployment.performed=false
```

## 11. Special handling

### Stateful or schema-changing services

Require current backup evidence and a proven compatible restore/rollback path.

Do not blindly downgrade after a migration has changed stored data.

### Vendor-managed multi-container stacks

Treat coordinated vendor stacks as a unit where required. Do not independently pin/update components if doing so breaks the vendor-supported release model.

### Local builds

Require clean authoritative source, exact source revision and OCI provenance matching the image.

### Jenkins

Jenkins remains a platform exception:

```text
Jenkins may assess Jenkins
Jenkins may propose a Jenkins update
Jenkins must not automatically deploy or recreate Jenkins
```

Any Jenkins controller update requires a separately controlled/manual execution path with recovery evidence.

## 12. Stage 5 deployment — not currently enabled

Once the Stage 5 human-controlled boundary is explicitly enabled, the intended procedure is:

1. Confirm the reviewed Git revision and deployment plan.
2. Obtain human approval for the exact service/candidate.
3. Preserve the previous known-good image and rollback metadata.
4. Pull/prepare only the approved candidate.
5. Recreate/update only the approved service or explicitly approved coordinated stack.
6. Confirm runtime image/digest equals the approved candidate.
7. Run Docker health/readiness checks.
8. Run application-specific smoke tests.
9. Observe the service for the defined acceptance window.
10. Mark successful only after runtime and service behaviour are proven.
11. Roll back immediately if the pre-defined rollback criteria are met.

## 13. Rollback workflow

If acceptance fails:

1. Stop further rollout.
2. Preserve logs and inspection evidence without secret values.
3. Determine whether image-only rollback is safe for the current data/schema state.
4. Restore the previous Git-controlled declaration or recorded immutable digest/source revision.
5. Restore compatible configuration/secret delivery where required.
6. Restore data only under the service-specific recovery procedure.
7. Start only the affected service/approved stack.
8. Run health/readiness and functional smoke tests.
9. Confirm the runtime image/digest matches the rollback target.
10. Reconcile Git promptly if an emergency operational rollback temporarily changed live desired state.

## Completion checklist

An image/build update is ready for future controlled deployment only when all applicable items are complete:

- [ ] Authoritative service/Compose source confirmed.
- [ ] Update source identified.
- [ ] Risk class recorded.
- [ ] Release/compatibility notes reviewed.
- [ ] Target architecture supported.
- [ ] Configuration changes understood.
- [ ] Secret-delivery changes understood and safely represented.
- [ ] Stateful migration/backup implications reviewed.
- [ ] Current known-good image/digest/source revision recorded.
- [ ] Git desired-state change is narrow and reviewable.
- [ ] Compose validation passes.
- [ ] Master inventory updated if metadata changed.
- [ ] Ownership/comparison/architecture/security gates pass.
- [ ] Secret-readiness gate passes where required.
- [ ] Local-build provenance passes where applicable.
- [ ] Deployment plan reviewed.
- [ ] Health/readiness/smoke tests defined.
- [ ] Rollback target and trigger criteria defined.
- [ ] Deployment remains disabled until Stage 5 is explicitly enabled and approved.
