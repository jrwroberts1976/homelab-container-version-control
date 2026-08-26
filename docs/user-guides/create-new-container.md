# User Guide — Create a New Docker Container

## Purpose

Use this guide when adding a new Docker service to the managed homelab estate.

The objective is not merely to make a container run. The new service must have:

- a Git-owned desired state;
- an explicit image/version strategy;
- known configuration inputs;
- safe secret delivery;
- ownership and provenance metadata;
- read-only validation evidence;
- a health/smoke-test definition; and
- a known rollback path before deployment is permitted.

## Current Stage 4 rule

At the current project stage, complete the Git and validation work and then stop.

```text
deployment.allowed=false
deployment.performed=false
```

The deployment section later in this guide becomes active only after the Stage 5 human approval/deployment boundary is reviewed and enabled.

---

## 1. Decide who owns the service

Before writing Compose, decide which repository is authoritative.

Normal TestServer services should normally be owned by:

```text
jrwroberts1976/docker-env
```

Use an external Git authority when the service is built from its own application repository, as with the Engineering Portfolio and Projects site.

Use a platform exception only when there is a documented reason the Compose/source cannot yet be Git-owned. Platform exceptions must fail closed and must not silently gain deployment authority.

## 2. Choose the image strategy

### Registry image

Prefer an explicit release tag:

```yaml
services:
  example:
    image: vendor/example:1.2.3
```

Where the publisher/update workflow supports it, prefer a readable tag plus immutable digest:

```yaml
services:
  example:
    image: vendor/example:1.2.3@sha256:<digest>
```

Do not introduce `latest`, `stable`, `edge`, `main`, `master` or another moving channel unless an explicit policy exception is justified and recorded.

If the vendor uses a non-SemVer scheme, record the appropriate version scheme in `config/version-schemes.yml`.

### Local build

A local build must have an authoritative build context and Dockerfile and must carry reproducible provenance.

Use build arguments by **name**, not secret value:

```yaml
build:
  context: .
  args:
    BUILD_REVISION: ${BUILD_REVISION:-unknown}
    BUILD_CREATED: ${BUILD_CREATED:-unknown}
    BUILD_SOURCE: ${BUILD_SOURCE:-https://github.com/<owner>/<repo>}
```

The resulting image should expose OCI source/revision/created metadata in accordance with the local-build provenance policy.

## 3. Create the Compose declaration in Git

Create the service in the authoritative repository before creating the running container.

Record at minimum:

- service name;
- container name where explicitly required;
- image or build source;
- restart policy;
- networks;
- ports;
- persistent volumes;
- healthcheck where supported;
- non-secret environment/configuration names; and
- secret references.

Do not copy runtime-generated databases, caches, logs or other mutable state into Git.

## 4. Handle configuration and secrets

Separate ordinary configuration from sensitive configuration.

### Non-secret configuration

Normal non-sensitive values may be declared in Compose or referenced from a safe `.env` source when required.

Record the variable names in the master container/configuration inventory.

### Secrets

Never commit plaintext secret values.

Where application support permits, prefer a Compose secret backed by a protected runtime file:

```yaml
services:
  example:
    secrets:
      - example_api_token

secrets:
  example_api_token:
    file: /home/james/docker/secrets/example-api-token
```

If the secret needs Git-backed recovery, store the recovery source encrypted with SOPS + age in the authoritative repository.

Add a names-only readiness rule to `config/secret-readiness.yml` when the service must prove that encrypted recovery material and the protected runtime secret match.

The inventory and validation output may record:

- secret identifier;
- source key name;
- encrypted source path;
- runtime path;
- required permissions; and
- readiness result.

They must not record the secret value.

## 5. Register ownership and exceptions

The normal TestServer defaults are already defined in `config/service-ownership.yml`.

Add an override when the service is:

- an external-Git local build;
- a local build with special provenance handling;
- owned by a different source repository; or
- a platform exception.

If the service requires a policy exception, add it to `policy/exceptions.yml` with rationale, risk, owner, compensating controls, review/expiry date and rollback method.

## 6. Register local-build provenance when applicable

For a local-build service, add the required source/build relationship to `config/local-build-provenance.yml`.

The Stage 4 validator must be able to establish the source repository, revision and build-input relationship without rebuilding or deploying the service.

## 7. Validate Compose before runtime change

From the authoritative clean Git checkout, run the appropriate Compose validation.

Typical check:

```bash
docker compose config >/dev/null
```

For a multi-file stack, pass the exact authoritative Compose files used by the service.

Do not run `docker compose up`, `docker pull`, `docker restart` or manual container recreation merely to test the declaration during Stage 4 onboarding.

## 8. Add the service to the master inventory

Update:

```text
docs/testserver-container-configuration-inventory.md
```

Record:

- container/service name;
- Compose stack;
- desired image/build;
- registry/local/platform classification;
- variable/configuration names;
- secret-delivery names only;
- Git authority; and
- management state.

A service is not fully onboarded if it is running but missing from the inventory/ownership model.

## 9. Open/review the Git change

Use the normal Git review process.

Before merge, verify that the change contains no:

- plaintext secrets;
- runtime database/state files;
- accidental `.env` secret values;
- unrelated stack changes; or
- floating image declarations without an approved exception.

## 10. Run the Stage 4 validation path

After the service is represented by authoritative Git desired state, the validation path should establish as applicable:

```text
ownership
comparison / candidate identity
architecture
Trivy security result
secret readiness
local-build provenance
non-secret deployment plan
```

The generated plan must retain:

```text
deployment.allowed=false
deployment.performed=false
```

A missing ownership source, uncertain version ordering, failed security check, missing secret, provenance failure or platform exception must stop the path rather than be guessed around.

## 11. Define deployment acceptance before Stage 5

Before the new service may enter the future controlled deployment model, document:

- expected container health state;
- application readiness check;
- HTTP/TCP/DNS/functional smoke test as applicable;
- dependent-service checks;
- observation/acceptance window;
- exact previous/rollback image or source revision where applicable; and
- data backup/restore requirements if stateful.

For a brand-new service with no previous image, rollback usually means removing only the newly introduced service and restoring the previously verified surrounding stack/network state.

## 12. Stage 5 deployment — not currently enabled

When Stage 5 is explicitly enabled, the intended operator flow is:

```text
Git change
  -> validation passes
  -> deployment plan reviewed
  -> human approval
  -> deploy only the approved service/scope
  -> health/readiness checks
  -> functional smoke tests
  -> acceptance window
  -> success OR rollback
```

Do not grant broad Docker deployment authority merely to make onboarding easier.

## Completion checklist

A new container is ready for managed deployment only when all applicable items are complete:

- [ ] Git authority identified.
- [ ] Compose desired state committed/reviewable.
- [ ] Explicit version/digest strategy defined.
- [ ] No unapproved floating image reference.
- [ ] Non-secret configuration names recorded.
- [ ] Secrets use protected delivery and no plaintext secret is committed.
- [ ] SOPS recovery/readiness registered where required.
- [ ] Ownership rule resolves correctly.
- [ ] Local-build provenance resolves correctly where applicable.
- [ ] Compose validation passes.
- [ ] Master inventory updated.
- [ ] Stage 4 validation passes or intentionally blocks with a documented exception.
- [ ] Health/readiness/smoke checks defined.
- [ ] Rollback path defined.
- [ ] Stateful backup/restore evidence available where required.
- [ ] Deployment remains disabled until Stage 5 approval.
