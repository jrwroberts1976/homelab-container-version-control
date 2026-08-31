# Stage 6 end-to-end service-update automation

## Objective

A Stage 6 update is not complete when the new container merely starts successfully.

The target operating model is one Jenkins workflow that carries a reviewed update from candidate acquisition and pre-deployment inspection through immutable deployment, durable Git authority, estate catalogue promotion, steady-state installation and final read-only verification.

Normal BAU operation must not require manual SSH, manual `docker pull`, manual Compose editing, manual catalogue editing or a separate closure runbook.

Human approval remains part of the safety model. Manual shell follow-up does not.

## End-to-end completion contract

A routine Jenkins service-update run may report full success only after all applicable stages complete:

1. checkout reviewed source;
2. validate the reviewed Stage 6 update manifest and framework source;
3. resolve the exact reviewed host route, host-key pin and credentials;
4. resolve the exact immutable reviewed candidate from the manifest;
5. use a dedicated restricted candidate-acquisition credential to pull that exact immutable candidate into the target host image cache;
6. verify candidate local image/config ID, RepoDigest and platform and prove that no container identity/restart/running state changed during acquisition;
7. perform the first read-only inspection;
8. prove manifest, authority, rollback, candidate, runtime and health identities;
9. require explicit human approval;
10. perform a second read-only inspection;
11. prove exact zero drift;
12. only then expose the full deployment executor credential;
13. arm the exact one-shot update;
14. recreate only the reviewed target service with the exact already-local immutable candidate using `--no-deps --no-build --pull never --force-recreate`;
15. verify the exact candidate, target health and runtime invariants;
16. prove unrelated/protected containers are unchanged;
17. roll back only through the reviewed rollback path when deployment acceptance fails;
18. disarm one-shot execution authority;
19. promote the successful candidate into the Git-controlled Compose authority as the new durable default;
20. validate and merge the narrow authority change;
21. synchronise the merged authority checkout/live Compose declaration without recreating an already-healthy service;
22. generate or update the Stage 6 steady-state manifest from reviewed deployment evidence;
23. update `config/estate-updater-catalog.json` automatically as part of the pipeline;
24. validate the updated catalogue and steady-state manifest;
25. commit/merge the reviewed catalogue and steady-state changes;
26. install the reviewed catalogue and steady-state manifest through the approved root-owned installation path;
27. run the read-only steady-state inspector/front end and require the exact promoted authority/runtime/health state with mutation/deployment disabled;
28. archive candidate-acquisition, deployment, authority, catalogue and steady-state evidence;
29. report the final pipeline result.

A healthy deployment with unfinished authority, catalogue or steady-state closure is therefore not a fully completed Stage 6 update.

## Jenkins target selector

The normal Jenkins operator interface should use a dropdown of reviewed installed Docker services rather than requiring an operator to type a manifest filename.

Example labels:

```text
ids-01 / loki
ids-01 / prometheus
TestServer / homepage
TestServer / dozzle
TestServer / alloy
```

The dropdown must be generated from reviewed Git-controlled estate data, not from unrestricted live `docker ps` output.

A separate reconciliation process may compare the live Docker inventory with the catalogue and raise missing/unreviewed entries, but a live container list must not become an arbitrary execution selector.

The selected dropdown value must resolve internally to reviewed data including:

- host;
- service/container identity;
- backend;
- transition/update manifest;
- steady-state manifest where present;
- host route and host-key pin;
- inspector/candidate-acquisition/executor credential routes;
- current and desired version information.

If the selected target is missing reviewed metadata or is outside the supported Stage 6 contract, Jenkins must fail closed before any mutation-capable credential is exposed.

The intended operator experience is conceptually:

```text
Service: [ TestServer / alloy             v]
Action:  [ update                         v]
```

The pipeline resolves the reviewed manifest automatically. The operator should not need to type a filename such as `loki-ids01-3.7.7.json`.

## Candidate acquisition belongs inside Jenkins

Candidate acquisition is part of the intended BAU workflow, but it is not the same authority level as deployment.

The existing reviewed host-side candidate-acquisition helper has the correct basic safety contract:

- accepts only a reviewed service name;
- loads the root-owned installed Stage 6 service manifest;
- derives the candidate repository/digest from that manifest rather than caller input;
- pulls only the exact immutable manifest-pinned candidate reference;
- verifies expected local image/config ID;
- verifies OS/architecture and exact RepoDigest membership;
- snapshots container ID/restart/running state before and after the image-cache mutation;
- fails if any container state changes;
- does not run Compose;
- does not create, restart, recreate or remove containers.

The Jenkins stage should archive a structured candidate-acquisition artifact proving at minimum:

```text
service
candidate_ref
index_digest
platform_manifest_digest
config/local image ID
platform
container_mutation_performed=false
```

### Dedicated candidate-acquisition credential

Jenkins must **not** use the full Stage 6 deployment executor credential merely to pull the candidate before approval.

The deployment executor can arm, deploy, rollback and disarm. Binding that identity before human approval would weaken the existing control boundary even if the immediate command happened to be only a pull.

Instead, provide a dedicated candidate-acquisition SSH identity with a fixed forced-command wrapper whose allowed operation is conceptually:

```text
acquire <reviewed-service>
```

The wrapper must reject arbitrary images, digests, paths and shell fragments and invoke only the reviewed acquisition helper.

The full deployment executor remains unavailable until human approval and exact zero-drift reinspection have both passed.

### Deployment remains pull-free

After candidate acquisition succeeds, deployment must still use:

```text
--pull never
```

This guarantees that the post-approval recreation consumes the exact candidate already verified during acquisition rather than contacting the registry again inside the mutation stage.

## Container recreation

The normal Stage 6 deployment recreates the target service once using the equivalent of:

```text
docker compose up -d --no-deps --no-build --pull never --force-recreate <reviewed-service>
```

The target must be derived from reviewed data. Jenkins must not accept an arbitrary container name, Compose path, image reference or shell fragment.

Authority and catalogue closure stages must not recreate the already-proven healthy container again.

If a future standalone `recreate-current` action is added, it must use the same reviewed target selector, approval, zero-drift, protected-container and health gates and recreate only the exact reviewed current immutable image.

## Closed-state verification action

Jenkins needs a non-mutating verification action for a service that is already fully deployed and closed.

This is required for two reasons:

1. a post-deployment closure failure may be repaired later without recreating the already-good runtime;
2. a corrected Jenkins framework may need to prove that an already-closed service still matches authority/catalogue/steady state without violating a consumed one-shot update.

A reviewed action such as:

```text
VERIFY_CLOSED
```

should resolve the service from the governed catalogue and verify:

- service/host identity;
- catalogue `managed-tested`/desired state;
- installed steady-state manifest identity;
- reviewed root-owned/live Compose authority revision and Compose SHA;
- exact desired immutable configured image;
- exact local image ID and platform;
- runtime network/port/mount/user/privilege/restart invariants;
- service health;
- protected-container state;
- no active arm/deployment authority for a consumed update.

It must not:

- acquire or deploy a new candidate;
- recreate/restart the target;
- arm a consumed update;
- clear consumed/audit evidence;
- bind the full deployment executor unless an exceptional reviewed reason exists.

Recommended explicit successful result:

```text
SUCCESS_VERIFIED_CLOSED
```

This result is different from `SUCCESS_CLOSED`: it proves that an existing desired state remains closed without performing a fresh update.

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
- `inspect_ready` where that field remains part of the catalogue contract;
- transition/update `manifest` reference where retained;
- `steady_state_manifest` reference;
- blockers/status fields that are no longer applicable after successful onboarding.

The catalogue update stage must:

1. load the current reviewed catalogue;
2. select only the exact reviewed service/host entry chosen by Jenkins;
3. derive the new version/image/manifest fields from verified deployment and authority evidence;
4. reject unexpected changes to unrelated catalogue entries;
5. validate the complete catalogue;
6. generate a reviewable Git diff;
7. commit/merge the catalogue change through the approved repository workflow;
8. install/synchronise the merged root-owned catalogue where required;
9. run a final read-only steady-state inspection;
10. require the final evidence to match the newly promoted catalogue state.

A successful deployment followed by a stale catalogue must produce an incomplete-closure result, not full success.

`inspect_ready` must not be confused with deployment/update readiness. A service can be a valid reviewed Stage 6 update candidate even while its older catalogue entry has not yet been promoted into the steady-state inspection path.

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

If the exact candidate has already passed health and runtime invariants but a later disarm, Git authority, catalogue or steady-state step fails, automation must not automatically roll back a healthy service solely because bookkeeping/closure failed.

Instead it must:

1. preserve the successful runtime and consumed deployment evidence;
2. ensure one-shot execution authority is disarmed as soon as the reviewed terminal state permits;
3. mark the run `DEPLOYED_BUT_CLOSURE_INCOMPLETE` or equivalent;
4. identify the exact failed closure stage;
5. support an idempotent reviewed resume path that does not recreate the service unnecessarily.

## Jenkins result states

Recommended explicit outcomes:

- `SUCCESS_CLOSED` — fresh deployment, authority, catalogue and steady-state verification complete.
- `SUCCESS_VERIFIED_CLOSED` — no fresh deployment performed; an already-closed service passed complete non-mutating verification.
- `DEPLOYED_BUT_CLOSURE_INCOMPLETE` — candidate is healthy but disarm/authority/catalogue/steady-state closure needs reviewed resume.
- `ROLLED_BACK_CLOSED` — candidate failed acceptance and reviewed rollback plus closure completed.
- `PRE_DEPLOYMENT_FAILED` — runtime was not changed.
- `MANUAL_REVIEW_REQUIRED` — a fail-closed state exists that cannot safely resume automatically.

Only `SUCCESS_CLOSED` represents a fully completed routine fresh update.

## No-manual-follow-up principle

Normal BAU operation should require only:

1. select the reviewed service from the Jenkins dropdown;
2. review the exact candidate and pre-deployment evidence;
3. approve the exact deployment.

Jenkins and reviewed Git-controlled helpers should perform candidate acquisition and everything else through final catalogue/steady-state verification.

Manual SSH remains a diagnostic and exceptional recovery tool, not a normal deployment step.

## Loki 3.7.7 lesson — 31 August 2026

The ids-01 Loki 3.7.7 generic deployment proved the multi-host execution path and exposed the original closure gap.

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

Loki remains a future closure-reconciliation item. Its already-healthy 3.7.7 runtime should not be recreated merely to repair stale authority/catalogue metadata.

## Dozzle 10.8.0 lesson — 31 August 2026

Dozzle was deliberately used to test whether a previously deferred service could be requalified against the generic framework rather than permanently excluded.

The live review established that Dozzle:

- uses a read-only Docker socket;
- has no published host port;
- has no Docker healthcheck;
- is reachable on the reviewed `homelab_apps` Docker network at container port 8080;
- returns HTTP `200` at `/`;
- legitimately has an empty Docker `Config.User`.

This drove narrow reviewed framework extensions for:

- `container-http` health in schema/validator/inspector/executor;
- an explicitly reviewed empty runtime user;
- `container-http` terminal health in the transition/disarm helper.

Jenkins build #13 then successfully performed the approval/zero-drift/deployment portion and deployed the exact Dozzle 10.8.0 candidate.

The build failed afterward at disarm with:

```text
FAIL: unsupported health strategy
```

The application deployment itself had passed. The historical build was therefore a deployment-success/closure-incomplete case rather than a reason to roll back Dozzle.

After the transition-helper fix was reviewed and installed, Dozzle was disarmed without recreation. The durable Compose authority was promoted to the exact immutable 10.8.0 reference, both authority checkouts were synchronised without container mutation, the catalogue was promoted, the steady-state manifest was generated/installed, and final read-only steady-state verification passed.

Final service outcome:

```text
SUCCESS_CLOSED
```

However, Dozzle has **not** produced a single clean Jenkins `SUCCESS_CLOSED` build because the later closure steps were recovered outside the historical build.

The correct next proof is therefore not to rerun the consumed Dozzle deployment. It is to implement `VERIFY_CLOSED` and require Jenkins to return:

```text
SUCCESS_VERIFIED_CLOSED
```

without recreating Dozzle.

## Alloy next-service checkpoint

TestServer Alloy has passed initial read-only requalification evidence collection.

Established health endpoints:

```text
http://192.168.2.220:12345/-/ready
http://192.168.2.220:12345/-/healthy
```

Both have been proven HTTP `200`.

WUD identified the TestServer Alloy update:

```text
1.18.0 -> 1.19.2
```

The 31 August session deliberately stopped before Alloy candidate acquisition or deployment.

Resume Alloy only after:

1. the dedicated Jenkins candidate-acquisition route is implemented;
2. Jenkins successfully verifies the already-closed Dozzle state non-mutatingly.

Alloy should then be the first fresh service intended to prove the entire updated BAU contract, including Jenkins-owned candidate pull and final `SUCCESS_CLOSED` closure.
