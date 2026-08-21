# Architecture

## Purpose

This project provides a controlled path from a container image version being proposed to that exact version being validated, deployed, observed and, if necessary, rolled back.

## Target architecture

```text
Upstream registries
      |
      | version/digest discovery
      v
Renovate ---------------------- WUD
   |                              |
   | pull request                 | independent runtime update signal
   v                              |
GitHub repository <--------------+
   |
   | desired state: Compose tag + digest
   v
Jenkins validation
   |-- docker compose config
   |-- image architecture check
   |-- downgrade protection
   |-- Trivy vulnerability scan
   |-- policy / exception checks
   |-- secrets readiness check
   v
Staged deployment guard
   |-- capture current image/digest
   |-- decrypt/materialise required secrets
   |-- pull candidate image
   |-- deploy selected service/stack
   |-- health verification
   |-- rollback if acceptance fails
   v
Docker hosts
   |-- TestServer
   `-- ids-01
   |
   | runtime inventory
   v
Node Exporter textfile metrics
   |
   v
Prometheus -> Grafana -> alerts
```

## Authorities

### Git / Compose

Git is the authoritative record of the version intended to run. A runtime change without a corresponding Git change is drift.

### Renovate

Renovate proposes image tag and digest changes through pull requests. It does not directly modify running containers.

### Jenkins

Jenkins is the validation gate. A candidate image must pass configuration, policy and security checks before it can progress to deployment.

### WUD

WUD remains an independent observer of available updates and the running Docker estate. It is not the source of truth and must not silently change production containers.

### Prometheus / Grafana

Monitoring reports whether the runtime matches the declared desired state and whether version-control policy is being followed.

## Version identity

The preferred production declaration is a readable tag plus immutable digest:

```yaml
image: example/image:1.2.3@sha256:<digest>
```

The tag communicates the intended release while the digest ensures reproducibility.

## Secrets architecture

Sensitive values are not committed in plaintext and are not embedded in Dockerfiles or normal Compose environment declarations when a secret-file mechanism is available.

Initial model:

```text
Git repository
  secrets/*.sops.yaml (encrypted)
          |
          | SOPS + age
          v
Jenkins / authorised operator
          |
          | decrypt only for deployment
          v
root-owned temporary materialisation
          |
          | Docker Compose secrets
          v
/run/secrets/<name> inside authorised service
```

The age private identity is never stored in Git. It is held as deployment credential material and backed up separately with tested recovery.

## Drift classes

The collector will distinguish at least:

- **Version drift** — Compose tag differs from running `Config.Image`.
- **Digest drift** — declared digest differs from running image digest.
- **Floating declaration** — `latest`, `stable`, unversioned or other explicitly classified floating tag.
- **Unmanaged runtime** — running container has no known authoritative Compose definition.
- **Compose-only service** — declared service is not running when expected.
- **Secret-policy exception** — service still depends on plaintext secret handling under an approved temporary exception.

## Deployment safety rules

1. Never recreate a production service before comparing declared and running versions.
2. Refuse an apparent downgrade by default.
3. Record the previous image ID and digest before change.
4. Validate Compose before pull/deploy.
5. Validate required secrets before deployment.
6. Deploy a limited pilot scope first.
7. Verify container health and application-level checks.
8. Keep rollback deterministic and immediately available.
9. Record exceptions in Git with rationale and review date.

## Initial hosts

- TestServer
- ids-01

Other container platforms can be added only after the initial operating model is stable.
