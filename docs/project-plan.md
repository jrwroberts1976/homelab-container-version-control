# Project Plan and Timeline

## Project objective

Establish end-to-end container image version control across the Docker estate on TestServer and `ids-01` and the Kubernetes estate on `k3s-node-01`, with Git-controlled desired state, safe update proposals, security validation, exact immutable candidate acquisition, staged deployment, deterministic rollback, durable post-deployment closure and runtime compliance monitoring.

## Planning approach

Target dates are planning windows, not reasons to bypass controls. Each stage has an exit gate. If a gate is not satisfied, the project remains active in that stage until it is safe to proceed.

Project start: **21 August 2026**  
Target initial production completion: **16 October 2026**

The implementation has progressed faster than the original calendar, but the stage names must represent actual capability rather than dates. In particular, Stage 6 is **active**, not complete, until the full Jenkins-owned candidate-acquisition and automatic authority/catalogue/steady-state closure path is proven in one fresh update.

## Timeline

| Stage | Original target window | Current status | Outcome / remaining gate |
|---|---|---|---|
| 0. Discovery & baseline | 21–28 Aug | **Complete — 23 Aug** | Estate, ownership, drift and secrets baseline established. |
| 1. Git control & policy | 29 Aug–4 Sep | **Complete — 23 Aug** | Desired-state ownership, pinning policy, exceptions and local-build provenance established. |
| 2. Secrets foundation | 5–11 Sep | **Active foundation** | Four Compose-secret pilots and K3s datastore encryption complete; broader SOPS/age recovery and remaining secret-policy work continue. |
| 3. Update proposals | 12–18 Sep | **Partially implemented / not current gate** | WUD provides independent update signals; Renovate/PR automation remains a proposal mechanism, never deployment authority. |
| 4. Validation gate | 19–25 Sep | **Substantially proven** | Reviewed manifests, schema/security validation, exact identity checks and fail-closed inspection are operational. |
| 5. Pilot go-live | 26 Sep–2 Oct | **Proven pattern** | Guarded low-risk deployment, health and rollback controls established through earlier pilots and Stage 6 service tests. |
| 6. Production rollout | 3–9 Oct | **ACTIVE — real deployments proven 31 Aug** | Generic TestServer/ids-01 Jenkins deployment core proven; candidate acquisition and full automatic closure still need integration. |
| 7. Observability & optimisation | 10–16 Oct | **Partly operational / ongoing** | Compliance/monitoring foundations exist; final BAU dashboarding, runbooks and policy tuning continue after Stage 6 closes. |

## Current Stage 6 checkpoint — 31 August 2026

### Generic controls already proven

The current Stage 6 framework supports:

- reviewed service-update manifests and schemas;
- fixed TestServer and `ids-01` host routes;
- strict host-key pinning;
- dedicated read-only inspector credentials;
- exact authority/rollback/candidate/runtime identity validation;
- explicit human approval;
- post-approval read-only reinspection and exact zero-drift comparison;
- deployment executor binding only after approval and zero drift;
- exact one-shot arm/deploy/disarm state;
- selected-service-only recreation with `--no-deps --no-build --pull never --force-recreate`;
- Docker health, fixed HTTP and Docker-network `container-http` health;
- protected-container identity/restart checks;
- reviewed rollback paths;
- steady-state validation/inspection primitives.

### Loki 3.7.7

The `ids-01` Loki `3.7.7` update proved the generic multi-host Jenkins deployment/disarm path.

The service deployed successfully and remained healthy with protected Grafana and Prometheus containers unchanged.

That run exposed the original closure gap: runtime deployment could succeed while durable Compose authority, the estate catalogue and steady-state records remained stale.

### Dozzle 10.8.0

Dozzle was requalified as a generic Stage 6 TestServer service despite previously lacking a Docker healthcheck or published host port.

Narrow reviewed framework extensions added:

- `container-http` health on a reviewed Docker network;
- support for an explicitly reviewed empty Docker runtime user;
- `container-http` terminal health in the transition/disarm helper.

Jenkins build #13 successfully deployed the exact immutable Dozzle 10.8.0 candidate after approval and zero-drift proof. It later failed at disarm because the transition helper did not yet include the new health strategy.

The application itself had passed deployment acceptance. After the transition-helper fix was reviewed, Dozzle was disarmed without recreation, immutable Compose authority was promoted, the catalogue and steady-state definition were promoted/installed, and final read-only verification passed.

Final service state:

```text
SUCCESS_CLOSED
```

This service must not be redeployed merely to make historical Jenkins build #13 green.

## Immediate Stage 6 implementation plan

Before any fresh service update:

1. add a dedicated candidate-acquisition SSH identity/forced command;
2. allow that identity to invoke only the reviewed candidate-acquisition helper for a reviewed service;
3. move exact immutable candidate pull/verification into Jenkins before human approval;
4. prove candidate acquisition mutates only the local image cache and leaves all containers unchanged;
5. keep the full executor credential unavailable until after approval and zero drift;
6. retain `--pull never` during deployment;
7. add a non-mutating `VERIFY_CLOSED` / equivalent action;
8. run that action against already-closed Dozzle without recreation;
9. require `SUCCESS_VERIFIED_CLOSED`;
10. only then resume TestServer Alloy;
11. use Alloy as the first fresh candidate intended to prove Jenkins-owned candidate acquisition plus automatic authority/catalogue/steady-state closure in one run;
12. require final `SUCCESS_CLOSED` before declaring the BAU flow proven.

## Stage 0 — Discovery and baseline

### Exit status

**Complete — 23 August 2026.**

Proven baseline included:

- 61 containers inventoried across TestServer and `ids-01` at the original baseline;
- zero unmanaged containers at that checkpoint;
- zero registry-image reference drift;
- local-build provenance classification;
- TestServer secret-delivery inventory;
- authoritative Compose ownership mapping;
- deliberate retirement of obsolete services only after replacement/route validation.

The estate continues to evolve, so the live catalogue/inventory remains the operational source for current service count and state rather than this historical baseline number.

## Stage 1 — Git control and policy

### Exit status

**Complete — 23 August 2026.**

Established:

- tag/digest pinning policy;
- approved exceptions;
- downgrade policy;
- previous-known-good/rollback metadata;
- authoritative source mapping;
- local-build provenance evidence;
- controls against accidental plaintext secret commits.

These controls became prerequisites for the later Stage 6 reviewed manifests and authority gates.

## Stage 2 — Secrets foundation

### Completed milestones

The initial Docker Compose-secret work successfully covered:

- Grafana SMTP on `ids-01`;
- Cloudflare DDNS on TestServer;
- DuckDNS on TestServer;
- AutoKuma on TestServer using a controlled startup wrapper where the application release did not natively support the documented file-secret syntax.

The unused Uptime Kuma SMTP block was separately proven unused and retired rather than migrated unnecessarily.

K3s datastore secret encryption was completed on 25 August with persistent encryption enabled and all existing Secrets re-encrypted.

### Remaining gate

- complete the wider SOPS + age encrypted-source/recovery operating model;
- retain tested offline key recovery;
- ensure Jenkins secret handling/log masking remains safe across the workflows that require credentials;
- document justified application exceptions.

Stage 6 service-update credentials are treated separately by function: inspector, candidate acquisition and deployment executor must remain distinct authority levels.

## Stage 3 — Update proposals

### Role

Candidate discovery/proposal sources may include:

- Renovate-controlled PRs;
- WUD update signals;
- manual/vendor advisories.

None may directly change a running production service.

WUD is an independent signal. A WUD error means discovery is unavailable/failed and must not be interpreted as “no update”.

## Stage 4 — Jenkins validation gate

### Current proven validation

For Stage 6 registry-image services the validation path now includes:

1. checkout reviewed framework source;
2. validate the service manifest against schema and cross-field/security rules;
3. resolve only reviewed host/credential routes;
4. verify framework trust pins;
5. verify authority revision and Compose hash;
6. verify rollback/candidate immutable identities and platform;
7. verify runtime/network/mount/user/privilege/restart policy;
8. verify service-specific health strategy;
9. verify protected-container state;
10. fail closed before deployment authority if any gate differs.

### Remaining validation enhancement

Candidate acquisition will be moved into Jenkins before approval using a dedicated restricted credential, producing a structured artifact and proving zero container mutation during the image-cache pull.

Trivy/security scanning remains applicable where defined by service policy; it must not be invented as a universal gate when a reviewed service contract does not yet specify it.

## Stage 5 — Pilot go-live

The earlier Engineering Portfolio/maintenance-page work proved guarded deployment fundamentals: bounded readiness checks, maintenance fallback, rollback and application-level verification.

Those lessons were subsequently incorporated into the generic Stage 6 model rather than treated as the final production implementation.

## Stage 6 — Production rollout

### Current approach

Roll out by reviewed runtime capability and risk, not simply by service name or historical deferral.

Previously skipped services must be re-tested against the **current** framework. Dozzle demonstrated that a narrow reviewed extension can convert an old blocker into a managed service without weakening global security policy.

Current categories requiring extra care include:

- privileged/device-backed services;
- writable-Docker-socket services;
- control-plane services such as Jenkins/DinD;
- stateful/database services;
- service/container identity mismatches;
- local builds;
- floating-tag or migration-required workloads.

These are not permanent exclusions, but they require explicit controls rather than broad generic relaxations.

### Next candidate

TestServer Alloy has passed its read-only requalification checkpoint. Existing health endpoints `/-/ready` and `/-/healthy` return HTTP `200`.

The observed update is `1.18.0 -> 1.19.2`.

The 31 August session deliberately stopped before candidate acquisition or deployment. Alloy remains held until the Jenkins candidate-acquisition and Dozzle `VERIFY_CLOSED` path is proven.

## Stage 7 — Observability and closure

### Closure model

Stage 7 observability is not a substitute for Stage 6 per-update closure. A successful fresh update reaches `SUCCESS_CLOSED` only after:

- exact candidate deployment acceptance;
- disarm;
- immutable Compose authority promotion;
- live/root-owned authority synchronisation without unnecessary recreation;
- estate catalogue promotion;
- steady-state generation/validation/installation;
- final read-only steady-state verification.

Recommended terminal states:

```text
SUCCESS_CLOSED
SUCCESS_VERIFIED_CLOSED
DEPLOYED_BUT_CLOSURE_INCOMPLETE
ROLLED_BACK_CLOSED
PRE_DEPLOYMENT_FAILED
MANUAL_REVIEW_REQUIRED
```

### Monitoring/metrics direction

Relevant compliance visibility includes or may include:

- desired vs running immutable image identity;
- managed/coverage state;
- inventory freshness/success;
- drift state;
- update signals;
- last successful deployment/closure;
- rollback identity;
- K3s image inventory/readiness/drift metrics.

Grafana remains the preferred visible operational surface for compliance and alerting.

## Kubernetes extension timeline

The Kubernetes workstream applies the same desired-state principles without reusing Docker mutation mechanics.

| Stage | Completed | Outcome |
|---|---|---|
| K0. Ownership and baseline | 23 Aug 2026 | K3s, Helm and application desired-state ownership recorded. |
| K1. Image policy and provenance | 23 Aug 2026 | Active declarations classified and pinned images correlated with runtime digests. |
| K2. Automated compliance metrics | 23 Aug 2026 | Five-minute image inventory export through node-exporter. |
| K3. Central monitoring | 23 Aug 2026 | Compliance series ingested by Prometheus on `ids-01`. |
| K4. Alerting | 24 Aug 2026 | Grafana-managed stale, failure, drift and readiness rules deployed. |
| K5. GitOps and admission policy | Planned | Continuous reconciliation/preventive policy remains future work. |
| K6. Datastore secret encryption | 25 Aug 2026 | Persistent AES-CBC encryption enabled and existing Secrets re-encrypted. |

See [K3s Stage 1 compliance monitoring](k3s-stage1-compliance.md).

## DietPi operational-state extension

DietPi remains adjacent critical infrastructure rather than part of the Docker/Kubernetes image totals.

Completed milestones include:

- Git capture of operational scripts, alert application, custom systemd units, Pi-hole adlists and Unbound overrides;
- safe exclusion of live credentials/databases/keys/generated metrics/backup state;
- non-destructive recovery rehearsal with hash/mode/syntax/systemd validation.

This work follows the same source-control/recovery principles without pretending the DietPi host is a Stage 6 Docker target.

## Key risks

| Risk | Mitigation |
|---|---|
| Compose file older than runtime causes downgrade | Authority gate; immutable promotion after successful deployment; deny unreviewed downgrade. |
| Floating tag changes unexpectedly | Version/digest policy and documented exceptions. |
| Secret committed to Git | SOPS/encrypted-source policy, ignore rules and review/CI checks. |
| Loss of encryption private key | Separate offline backup and tested recovery. |
| CI logs expose credentials | Dedicated Jenkins credentials, masking, no debug echo, cleanup. |
| Candidate image is wrong platform/identity | Exact immutable candidate acquisition and local identity/platform verification. |
| Candidate pull changes running service | Candidate-acquisition helper snapshots all container state and fails on mutation. |
| Powerful executor exposed before approval | Separate candidate-acquisition credential; executor bound only after approval + zero drift. |
| Deployment breaks service | Target-only staged deployment, health/runtime checks, previous image retained, reviewed rollback. |
| Closure fails after healthy deployment | Do not automatically roll back solely for metadata failure; disarm and resume idempotent closure without recreation. |
| WUD/Renovate gives unsuitable version candidate | Git-reviewed service policy; neither tool deploys directly. |
| Previously deferred service remains invisible forever | Re-test against current framework; document exact blocker or narrow reviewed extension. |

## Definition of done

The initial Docker production-control objective is complete when every in-scope service has either:

- a proven governed Stage 6 update/steady-state path appropriate to its risk/runtime class; or
- an explicit reviewed exception/migration/pin/retirement decision with a documented blocker and revisit condition.

For a routine managed registry-image service, the BAU path is complete when an operator can:

```text
select reviewed service
        |
        v
Jenkins acquires exact candidate safely
        |
        v
review + approve
        |
        v
Jenkins proves zero drift
        |
        v
Jenkins deploys/verifies/rolls back as needed
        |
        v
Jenkins closes authority/catalogue/steady state
        |
        v
final read-only verification
        |
        v
SUCCESS_CLOSED
```

Manual SSH remains a documented exceptional recovery/diagnostic path rather than normal update operation.

## Next checkpoint

The exact restart point after 31 August is:

```text
1. implement restricted Jenkins candidate acquisition
2. implement non-mutating VERIFY_CLOSED
3. verify already-closed Dozzle through Jenkins -> SUCCESS_VERIFIED_CLOSED
4. resume Alloy
5. prove first fresh complete Jenkins run -> SUCCESS_CLOSED
6. continue requalifying previously deferred services
```

See [Stage 6 end-to-end service-update automation](stage6-end-to-end-automation.md) for the detailed contract.
