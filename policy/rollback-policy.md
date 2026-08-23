# Rollback Policy

## Objective

Every production image change must have a known, exact and reproducible rollback path before deployment begins.

Rollback is not `docker compose up` against an assumed older tag. It uses recorded Git, image, configuration, secret and data compatibility evidence.

## Required pre-deployment record

Each deployment plan must record:

| Field | Requirement |
|---|---|
| Change/PR | Git commit and pull request |
| Scope | Host, Compose project and service |
| Previous desired state | Git revision and image declaration |
| Previous runtime | Creation reference, image ID and repo digest when available |
| Candidate | Declaration, resolved image ID/digest and architecture |
| Configuration | Relevant configuration revision/checksum without secret values |
| Secrets | Required names and readiness result only |
| Data | Backup status, timestamp and restore-test status where stateful |
| Checks | Healthcheck and application smoke-test commands |
| Acceptance | Observation window and success criteria |
| Rollback | Exact image target and service-specific recovery notes |

The deployment must stop if required fields cannot be established.

## Image retention

- Do not prune the previous known-good image during the change.
- Apply a local rollback tag when registry repull cannot be guaranteed.
- Retain the previous image until the acceptance window passes and the deployment record is complete.
- Digest-pinned rollback references are preferred for registry images.
- Local builds require the previous image ID plus source revision evidence.

## Rollback triggers

Rollback or stop the rollout when:

- container health is `unhealthy` or readiness times out;
- required HTTP, TCP, DNS or functional smoke checks fail;
- a dependent service is materially degraded;
- logs show configuration, migration or schema failure;
- candidate/runtime digest does not match the approved plan;
- a security or policy gate reports an unacceptable regression;
- monitoring indicates sustained degradation during the acceptance window.

## Workflow

1. Stop further rollout.
2. Preserve logs, runtime inspection and validation evidence without secret values.
3. Decide whether image-only rollback is safe for the service's current data/configuration state.
4. Restore the previous Git-controlled declaration or exact recorded digest.
5. Restore compatible configuration and secret delivery.
6. Restore data only under the service-specific recovery procedure.
7. Start only the affected service/stack.
8. Run Docker health, readiness and application smoke checks.
9. Verify final runtime image ID/digest against the rollback record.
10. Update Git if the operational rollback changed the authoritative desired state.
11. Record outcome, cause and follow-up action.

## Stateful services

Do not blindly downgrade across a schema or data migration.

Stateful services require:

- current successful backup evidence;
- known compatible rollback version;
- documented data restore point;
- bounded outage expectations;
- service-specific restore verification.

DNS, monitoring stores, security platforms and control-plane services are elevated changes and require explicit operator review.

## Emergency rollback

An emergency rollback may use a retained previous image before a normal PR completes when availability or security requires immediate action.

It must still:

- use a recorded known-good target;
- avoid an unverified data downgrade;
- capture evidence;
- run acceptance checks;
- reconcile final desired state in Git promptly.

## Acceptance

A service enters the controlled deployment model only when its rollback metadata is complete and reviewed.

Stage 5 pilot acceptance additionally requires one deliberately exercised rollback with evidence that:

- the previous image was restored;
- service health and application checks passed;
- runtime matched the intended rollback target;
- no plaintext secret residue remained.
