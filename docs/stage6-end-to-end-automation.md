# Stage 6 end-to-end service-update automation

## Objective

A Stage 6 update is not complete when the new container merely starts successfully.

The target operating model is one Jenkins workflow that carries a reviewed update from pre-deployment inspection through immutable deployment, durable Git authority, estate catalogue promotion, steady-state installation and final read-only verification.

Normal BAU operation must not require manual SSH, manual Compose editing, manual catalogue editing or a separate closure runbook.

Human approval remains part of the safety model. Manual shell follow-up does not.

## End-to-end completion contract

A routine Jenkins service-update run may report full success only after all applicable stages complete:

1. checkout reviewed source;
2. validate the reviewed Stage 6 update manifest and framework source;
3. resolve the exact reviewed host route, host-key pin and credentials;
4. perform the first read-only inspection;
5. prove manifest, authority, rollback, candidate, runtime and health identities;
6. require explicit human approval;
7. perform a second read-only inspection;
8. prove exact zero drift;
9. only then expose the executor credential;
10. arm the exact one-shot update;
11. recreate only the reviewed target service with the exact local immutable candidate using `--no-deps --no-build --pull never --force-recreate`;
12. verify the exact candidate, target health and runtime invariants;
13. prove unrelated/protected containers are unchanged;
14. roll back only through the reviewed rollback path when deployment acceptance fails;
15. disarm one-shot execution authority;
16. promote the successful candidate into the Git-controlled Compose authority as the new durable default;
17. validate and merge the narrow authority change;
18. synchronise the merged authority checkout/live Compose declaration without recreating an already-healthy service;
19. generate or update the Stage 6 steady-state manifest from reviewed deployment evidence;
20. update `config/estate-updater-catalog.json` automatically as part of the pipeline;
21. validate the updated catalogue and steady-state manifest;
22. commit/merge the reviewed catalogue and steady-state changes;
23. install the reviewed catalogue and steady-state manifest through the approved root-owned installation path;
24. run the read-only steady-state inspector/front end and require `steady-state-verified` with mutation/deployment disabled;
25. archive deployment, authority, catalogue and steady-state evidence;
26. report the final pipeline result.

A healthy deployment with unfinished authority, catalogue or steady-state closure is therefore not a fully completed Stage 6 update.

## Jenkins target selector

The normal Jenkins operator interface should use a dropdown of reviewed installed Docker services rather than requiring an operator to type a manifest filename.

Example labels:

```text
ids-01 / loki
ids-01 / prometheus
ids-01 / grafana
TestServer / homepage
TestServer / prometheus
```

The dropdown must be generated from reviewed Git-controlled estate data, not from unrestricted live `docker ps` output.

A separate reconciliation process may compare the live Docker inventory with the catalogue and raise missing/unreviewed entries, but a live container list must not become an arbitrary execution selector.

The selected dropdown value must resolve internally to reviewed data including:

- host;
- service/container identity;
- backend;
- transition/update manifest;
- steady-state manifest;
- host route and host-key pin;
- inspector/executor credentials;
- current and desired version information.

If the selected target is missing reviewed metadata or is outside the supported Stage 6 contract, Jenkins must fail closed before any executor credential is exposed.

The intended operator experience is therefore conceptually:

```text
Service: [ ids-01 / loki                 v]
Action:  [ update                         v]
```

The pipeline resolves the reviewed manifest automatically. The operator should not need to type a filename such as `loki-ids01-3.7.7.json`.

## Container recreation

The normal Stage 6 deployment already recreates the target service once using the equivalent of:

```text
docker compose up -d --no-deps --no-build --pull never --force-recreate <reviewed-service>
```

The target must be derived from reviewed data. Jenkins must not accept an arbitrary container name, Compose path, image reference or shell fragment.

Authority and catalogue closure stages must not recreate the already-proven healthy container again.

If a future standalone `recreate-current` action is added, it must use the same reviewed target selector, approval, zero-drift, protected-container and health gates and recreate only the exact reviewed current immutable image.

## Durable Compose authority promotion

After a successful deployment, the new immutable image must become the durable Git-controlled Compose default.

For a registry-image service, the authority promotion must replace the old default with the exact successful immutable reference. A service must not remain dependent on an environment override or an old default after a successful routine update.

Automation must prove:

- the pre-deployment authority commit and Compose SHA match the reviewed update manifest;
- the intended authority change is narrow and target-specific;
- the resulting Compose render resolves to the exact deployed immutable candidate;
- the authority change is reviewed/merged before it is treated as durable;
- live authority synchronisation does not recreate the already-proven service.

## Catalogue promotion is part of the script

`config/estate-updater-catalog.json` is part of the control plane and must be updated automatically by the end-to-end Jenkins workflow.

The catalogue must not be left stale after a successful deployment.

For the deployed host/service entry, the automation should derive values from reviewed/verified evidence rather than from operator-entered free text. At minimum it must update as applicable:

- `desired_version` at the service level;
- host `current_version`;
- host `configured_image` to the exact immutable deployed image;
- `coverage` to the appropriate managed state;
- `inspect_ready`;
- transition/update `manifest` reference where retained by the catalogue contract;
- `steady_state_manifest` reference;
- blockers/status fields that are no longer applicable after successful onboarding.

The catalogue update stage must:

1. load the current reviewed catalogue;
2. select only the exact reviewed service/host entry chosen by Jenkins;
3. derive the new version/image/manifest fields from verified deployment and authority evidence;
4. reject unexpected changes to unrelated catalogue entries;
5. validate the complete catalogue with the estate-updater catalogue validator;
6. generate a reviewable Git diff;
7. commit/merge the catalogue change through the approved repository workflow;
8. install/synchronise the merged root-owned catalogue used by `homelab-update`;
9. run a final read-only `homelab-update ... --action inspect` or equivalent steady-state inspection;
10. require the final evidence to match the newly promoted catalogue state.

A successful deployment followed by a stale catalogue must produce an incomplete-closure result, not full success.

## Steady-state promotion

After authority promotion, the successful candidate becomes the new desired steady state.

The steady-state manifest should be generated from the reviewed update manifest plus verified post-deployment evidence rather than by copying identities manually.

The steady-state record should pin at least:

- authority repository, commit, Compose path and Compose SHA;
- service/host/container/Compose identity;
- desired semantic version;
- immutable image/index digest/local image ID;
- platform and metadata verification mode;
- networks, ports, mounts, user and restart policy;
- privilege/socket/device policy;
- required content hashes;
- health strategy;
- protected containers.

The catalogue and steady-state manifest must agree before final closure.

## Failure handling after deployment

Post-deployment closure failures must be distinguished from application deployment failures.

If the exact candidate has already passed health and runtime invariants but a later Git authority, catalogue or steady-state step fails, automation must not automatically roll back a healthy service solely because bookkeeping/closure failed.

Instead it must:

1. preserve the successful runtime and consumed deployment evidence;
2. leave one-shot execution authority disarmed;
3. mark the run `DEPLOYED_BUT_CLOSURE_INCOMPLETE` or equivalent;
4. identify the exact failed closure stage;
5. support an idempotent reviewed resume path that does not recreate the service unnecessarily.

## Jenkins result states

Recommended explicit outcomes:

- `SUCCESS_CLOSED` — deployment, authority, catalogue and steady-state verification complete.
- `DEPLOYED_BUT_CLOSURE_INCOMPLETE` — candidate is healthy and disarmed, but authority/catalogue/steady-state closure needs automated resume.
- `ROLLED_BACK_CLOSED` — candidate failed acceptance and reviewed rollback plus closure completed.
- `PRE_DEPLOYMENT_FAILED` — runtime was not changed.
- `MANUAL_REVIEW_REQUIRED` — a fail-closed state exists that cannot safely resume automatically.

Only `SUCCESS_CLOSED` represents a fully completed routine update.

## No-manual-follow-up principle

Normal BAU operation should require only:

1. select the reviewed service from the Jenkins dropdown;
2. select/confirm the reviewed proposed version where applicable;
3. review the pre-deployment evidence;
4. approve the exact deployment.

Jenkins and reviewed Git-controlled helpers should perform everything else through final catalogue/steady-state verification.

Manual SSH remains a diagnostic and exceptional recovery tool, not a normal deployment step.

## Loki 3.7.7 lesson — 31 August 2026

The ids-01 Loki 3.7.7 generic deployment proved the multi-host execution path and exposed the remaining closure gap.

The successful Jenkins run correctly:

- loaded the reviewed Loki 3.7.7 update manifest;
- routed to ids-01 with the pinned host key and dedicated credentials;
- proved the pre-approval fail-closed state;
- required explicit human approval;
- performed exact zero-drift reinspection;
- exposed the executor credential only after zero drift;
- armed the exact candidate;
- recreated only Loki with the local immutable 3.7.7 image;
- passed host-side runtime, health and protected-container invariants;
- skipped rollback because deployment succeeded;
- disarmed one-shot authority.

Independent verification confirmed Loki running the exact immutable 3.7.7 image with restart count zero and `/ready` returning `ready`, while Grafana and Prometheus remained running with restart count zero.

The subsequent inspection showed that the Git-controlled ids-01 Compose authority still defaulted to 3.7.6, `config/estate-updater-catalog.json` still carried stale Loki state, and no Loki steady-state manifest existed. That proved deployment success and end-to-end update completion were not yet equivalent.

The required framework completion is therefore to automate authority promotion, authority synchronisation, steady-state generation, catalogue promotion, installation and final read-only verification inside the Jenkins workflow itself.
