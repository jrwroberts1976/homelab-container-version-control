# Image Version Policy

## Policy intent

Every production/BAU container must have an explicit and reviewable image-version strategy.

## Preferred declaration

Use a human-readable release tag plus immutable digest where the registry/workflow supports it:

```yaml
image: vendor/service:1.2.3@sha256:<digest>
```

## Classification

### Compliant

- explicit release tag;
- digest pinned where required by policy;
- running image matches desired declaration.

### Floating exception

Examples include `latest`, `stable`, date-less channel tags or unversioned image references.

Floating declarations require:

- written rationale;
- owner;
- review date;
- rollback method;
- monitoring for digest change.

### Drift

Running image/tag/digest differs from the Git-controlled desired state.

Drift must be investigated. Runtime state must not silently redefine desired state.

## Upgrade policy

- Patch changes: normal validation path.
- Minor changes: normal validation plus release-note review where risk justifies it.
- Major changes: elevated change with explicit compatibility and rollback review.
- Digest-only change under the same tag: treated as a real image change and validated.

## Downgrade policy

Apparent downgrades are denied by default.

A downgrade requires explicit override plus:

- reason;
- known compatible state/data format;
- rollback target verification;
- service-specific risk review.

## WUD and Renovate

- WUD is an update signal for running containers.
- Renovate is the preferred mechanism for proposing controlled Git changes.
- Neither tool is permitted to bypass Git/validation and silently replace a production image.

## Exceptions

Exceptions are stored in Git and must include:

- service;
- exception type;
- rationale;
- risk;
- owner;
- review/expiry date.
