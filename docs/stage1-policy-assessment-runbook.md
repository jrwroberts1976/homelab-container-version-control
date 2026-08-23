# Stage 1 Policy Assessment Runbook

## Purpose

Convert a Stage 0 container inventory into a read-only policy classification.

The assessment does not inspect secret values, contact registries, pull images, alter Compose files or restart containers.

## Input

Use the TSV produced by `scripts/inventory-images.sh`.

## Run

```bash
scripts/assess-image-policy.sh \
  /var/tmp/container-inventory-testserver-final.tsv \
  > /var/tmp/image-policy-testserver.tsv
```

Repeat for ids-01 using its current inventory.

## Classification

| State | Meaning |
|---|---|
| `compliant-digest` | Digest-pinned declaration with no detected drift |
| `compliant-version-tag` | Explicit version tag with no detected drift |
| `exception-required` | Floating reference must be pinned or approved |
| `local-build-unverified` | Requires source/OCI provenance assessment |
| `drift` | Runtime differs from authoritative desired state |
| `unmanaged` | No authoritative Compose source |
| `policy-review` | Classification is not recognised by current policy |

This first pass deliberately does not auto-approve exceptions. It identifies the services that need an operator decision.

## Summary command

```bash
awk -F '\t' '
  NR == 1 { next }
  { count[$13]++ }
  END {
    for (state in count)
      print state, count[state]
  }
' /var/tmp/image-policy-testserver.tsv |
sort
```

## Review list

```bash
awk -F '\t' '
  NR == 1 ||
  $13 != "compliant-digest" &&
  $13 != "compliant-version-tag"
' /var/tmp/image-policy-testserver.tsv |
column -t -s $'\t'
```

## Acceptance

Before Stage 1 closes:

- every floating reference is pinned or linked to an approved exception;
- every local build has a documented provenance disposition;
- no unmanaged or drifted service remains;
- exceptions include owner, review date, compensating controls and rollback method.
