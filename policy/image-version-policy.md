# Image Version Policy

## Status

Stage 1 policy foundation. Enforcement automation is not yet enabled.

## Intent

Every production or BAU container must have an explicit, reviewable and reproducible version strategy. Git-controlled Compose is authoritative; runtime state does not silently redefine desired state.

## Declaration classes

### Registry image — preferred

Use a human-readable release tag and immutable digest where the publisher and update workflow support both:

```yaml
image: vendor/service:1.2.3@sha256:<digest>
```

The tag supports review; the digest fixes the exact artifact.

### Version-tagged

An explicit release or date tag without a digest is provisionally compliant when:

- the tag is immutable in practice or registry history is monitored;
- the service has a recorded rollback image ID/digest;
- digest pinning is not yet supported by the update workflow.

### Digest-pinned

A digest-only declaration is reproducible but less readable. It must retain release/version context in the change record.

### Floating

The following are floating:

- `latest`;
- `stable`, `edge`, `main`, `master` or similar moving channels;
- an untagged image reference;
- a vendor channel whose content may change without the declaration changing.

Floating references are non-compliant unless covered by an active exception.

### Local build

A Compose `build:` service is assessed through source provenance rather than registry-tag drift.

A compliant local build requires:

- authoritative build context and Dockerfile;
- clean source worktree;
- source Git commit;
- build timestamp and image ID;
- OCI `org.opencontainers.image.revision` label matching the source commit;
- reproducible build arguments by name, with no secret values recorded;
- rollback image ID retained until acceptance.

Until these controls are implemented, local builds are reported separately as provenance-unverified, not as registry-image drift.

## Compliance states

| State | Meaning |
|---|---|
| `compliant` | Declaration satisfies its class and runtime matches desired state |
| `floating-exception` | Moving reference is covered by an active exception |
| `drift` | Runtime image/reference differs from Git desired state |
| `local-build-unverified` | Local build lacks required provenance evidence |
| `unmanaged` | Running container has no authoritative declaration |
| `exception-expired` | A required exception has passed its review date |

## Change classification

| Change | Default class | Required review |
|---|---|---|
| Digest change under the same tag | Routine | Full validation; treat as a real image change |
| Patch release | Routine | Normal validation and rollback evidence |
| Minor release | Elevated when compatibility risk exists | Release notes and compatibility review |
| Major release | Elevated | Explicit migration, data and rollback review |
| Stateful/schema-changing image | Elevated | Current backup and service recovery plan |
| Security emergency | Emergency | Accelerated review, but never omit desired state or rollback evidence |

## Downgrades

Downgrades are denied by default and governed by [Downgrade Policy](downgrade-policy.md).

A tag comparison alone is insufficient where tags are not valid semantic versions. Validation should compare exact current/candidate references and require explicit operator approval when ordering cannot be established safely.

## Update authorities

- Renovate proposes Git changes.
- WUD supplies an independent runtime update signal.
- Vendor advisories may trigger manual proposals.
- None of these sources may directly replace production containers outside the guarded deployment workflow.

## Exceptions

All exceptions must be recorded in `policy/exceptions.yml` and include:

- host/project/service scope;
- exception type;
- rationale and risk;
- owner;
- compensating controls;
- approval date;
- review/expiry date;
- rollback method.

Expired or incomplete exceptions are non-compliant.

## Initial Stage 1 decisions

- New normal registry services should use explicit release tags.
- Digest pinning is the preferred end state where reliable update metadata exists.
- Vendor-managed multi-container stacks, especially Greenbone Community Edition, require vendor-model review before mass pinning.
- DNS, security, stateful monitoring and data-store images are elevated changes.
- Local builds require provenance controls before automated rebuild/deployment.
