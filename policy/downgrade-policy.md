# Downgrade Policy

## Default rule

An apparent image downgrade is blocked unless an authorised exception is recorded for the specific change.

The control exists to prevent an older Compose declaration from silently replacing a newer running image during recreation.

## Inputs

The validation gate must record:

- host, Compose project and service;
- authoritative Git revision;
- current running creation reference;
- current image ID and repo digest when available;
- proposed image reference and resolved digest;
- comparison method and result;
- exception identifier when an override is requested.

## Comparison order

1. Exact digest match: no version change.
2. Valid semantic-version tags: compare parsed versions.
3. Date/version schemes with a documented parser: compare using that scheme.
4. Different or unparseable schemes: classify as `ordering-unknown`.
5. Local builds: compare source revision/provenance, not tag text.

Both `downgrade` and `ordering-unknown` are denied by default.

## Authorised downgrade

Approval requires:

- operational reason;
- exact target image/digest;
- confirmation that configuration and persistent data remain compatible;
- current backup/restore evidence for stateful services;
- defined health and application smoke tests;
- previous and candidate rollback points;
- time-bounded exception record;
- named approver/operator.

Emergency rollback to a previously recorded known-good image is allowed through the rollback workflow, but the event and final desired state must be reconciled in Git.

## Validation result

The policy check returns one of:

- `same`;
- `upgrade`;
- `downgrade-blocked`;
- `downgrade-authorised`;
- `ordering-unknown-blocked`;
- `local-build-provenance-required`.

A blocked result prevents deployment.

## Test cases required before Stage 4 exit

- current and candidate digests equal;
- patch upgrade;
- major upgrade;
- known semantic downgrade;
- tag scheme that cannot be ordered;
- digest change under the same floating tag;
- local build with matching revision evidence;
- local build with missing or dirty revision evidence.
