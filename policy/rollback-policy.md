# Rollback Policy

## Objective

Every production image change must have a known and reproducible rollback path before deployment starts.

## Required pre-deployment evidence

Record:

- host;
- stack/service;
- current Git revision;
- current running image reference;
- current image ID;
- current repo digest where available;
- candidate image reference/digest;
- relevant persistent-data backup status;
- service-specific compatibility notes.

## Rollback image retention

Do not prune the previous known-good image as part of the deployment change.

The deployment workflow must retain or be able to repull the exact previous digest until the new version has passed its acceptance window.

## Rollback decision

Rollback when required health or smoke checks fail, or when logs show an unacceptable configuration/schema/runtime regression.

For stateful services, do not blindly downgrade across a data/schema migration. Follow the service-specific recovery procedure and restore data if required.

## Rollback workflow

1. Stop further rollout.
2. Capture failure evidence without exposing secrets.
3. Restore the previous desired image declaration or deploy the recorded previous digest.
4. Restore compatible configuration/secrets.
5. Restore data only if required by the service recovery plan.
6. Start the service.
7. Run health and application smoke checks.
8. Verify runtime digest against the intended rollback state.
9. Record outcome and follow-up action.

## Critical services

DNS, monitoring data stores, security platforms and other stateful/availability-critical services require an explicit service-specific rollback/runbook before production rollout.

## Acceptance

A service is not considered successfully migrated into the controlled deployment model until at least one rollback path has been reviewed; pilot services should include an actual controlled rollback test.
