# Project Plan and Timeline

## Project objective

Establish end-to-end container image version control across the Docker estate on TestServer and ids-01 and the Kubernetes estate on k3s-node-01, with Git-controlled desired state, safe update proposals, security validation, staged deployment, deterministic rollback and runtime compliance monitoring.

## Planning approach

Target dates are planning windows, not reasons to bypass controls. Each stage has an exit gate. If a gate is not satisfied, the project remains in that stage until it is safe to proceed.

Project start: **21 August 2026**
Target initial production completion: **16 October 2026**

## Timeline

| Stage | Target window | Current status | Outcome | Go/no-go gate |
|---|---|---|---|---|
| 0. Discovery & baseline | 21–28 Aug | **Complete — 23 Aug** | Complete image + secrets inventory; identify drift/floating tags | Passed: every in-scope service identified; no unknown critical runtime |
| 1. Git control & policy | 29 Aug–4 Sep | **Complete — 23 Aug, ahead of plan** | Desired versions, pinning rules, exceptions, local-build provenance and rollback policy defined | Passed: authoritative sources mapped; registry and local-build compliance verified |
| 2. Secrets foundation | 5–11 Sep | **Next** | SOPS + age established; secret migration pilot; key backup/recovery tested | No plaintext repo secrets; recovery test passes |
| 3. Update proposals | 12–18 Sep | Planned | Renovate configured to create controlled Docker image PRs | PRs are accurate; no automatic production deployment |
| 4. Validation gate | 19–25 Sep | Planned | Jenkins validates Compose, downgrade risk, architecture, policy and Trivy results | Candidate changes reliably pass/fail before deployment |
| 5. Pilot go-live | 26 Sep–2 Oct | Pattern proven; formal gate pending | Guarded deployment of selected low-risk services | Health and rollback tests pass for pilot services |
| 6. Production rollout | 3–9 Oct | Planned | Extend process to critical/BAU services in controlled batches | Critical service rollback and recovery demonstrated |
| 7. Observability & closure | 10–16 Oct | Planned | Grafana/Prometheus compliance view, alerting, runbooks and handover | Runtime drift visible; operational runbook accepted |


## Kubernetes extension timeline

The Kubernetes workstream applies the same controls without changing the Docker stage gates.

| Stage | Completed | Outcome | Evidence |
|---|---|---|---|
| K0. Ownership and baseline | 23 Aug 2026 | K3s, Helm and application desired-state ownership recorded | `kubernetes-homelab` main branch and Stage 0 inventory |
| K1. Image policy and provenance | 23 Aug 2026 | Active declarations classified; pinned images correlated with runtime digests | 3 digest-pinned and 13 version-tagged active instances |
| K2. Automated compliance metrics | 23 Aug 2026 | Five-minute inventory export through node-exporter | `k3s-image-compliance.timer`, scrape error `0` |
| K3. Central monitoring | 23 Aug 2026 | Compliance series ingested by Prometheus on ids-01 | target up, success `1`, drift `0`, fresh timestamp |
| K4. Alerting | Next | Grafana-managed stale, failure, drift and readiness alerts | Pending controlled rule deployment |
| K5. GitOps and admission policy | Planned | Continuous reconciliation and preventive policy | Future stage |

See [K3s Stage 1 compliance monitoring](k3s-stage1-compliance.md).

## Stage 0 — Discovery and baseline

### Deliverables

- Inventory every running container on TestServer and ids-01.
- Identify Compose project, service and source file.
- Record declared image/tag/digest.
- Record running image/tag/image ID/digest.
- Classify drift.
- Identify floating tags (`latest`, `stable`, unversioned and other policy-defined cases).
- Identify containers not managed by Compose.
- Build a secrets inventory without recording secret values.
- Identify current `.env`, environment-variable, file and credential-store usage.

### Exit criteria

- 100% of in-scope running containers represented in the inventory.
- Critical services have a known Compose source and rollback starting point.
- Secret locations and delivery methods are known.

### Completion status

Stage 0 passed on **23 August 2026**.

Final evidence:

- 61 containers inventoried across both hosts;
- zero unmanaged containers;
- zero registry-image drift;
- five TestServer local builds classified by source provenance;
- TestServer names-only secret-delivery inventory completed across 30 containers;
- authoritative TestServer Compose baseline merged;
- obsolete stopped services retired only after replacement or route validation.

## Stage 1 — Git control and policy

### Deliverables

- Define tag/digest pinning policy.
- Define approved exceptions.
- Define downgrade policy.
- Define previous-known-good/rollback metadata.
- Decide how existing host Compose files are represented or synchronised with Git.
- Add repository controls to prevent accidental plaintext secret commits.

### Exit criteria

- Git representation exists for all pilot services.
- Policy can distinguish compliant, floating, drifted and unmanaged services.
- Downgrade protection can be tested against a known mismatch scenario.

### Completion status

Stage 1 passed on **23 August 2026**, ahead of its original planning window.

Final evidence:

- TestServer registry estate reconciled to 2 digest-pinned and 23 version-tagged services;
- ids-01 reconciled to 11 version-tagged services and 20 Greenbone containers covered by approved exception `EX-2026-001`;
- zero registry-image drift, unmanaged containers or unapproved floating references;
- BirdNET exporter, CrowdSec exporter, Engineering Portfolio and Projects site rebuilt with OCI source/revision labels;
- all four managed local builds report `revision-match`;
- Jenkins retained as the sole documented `no-git-source` exception;
- authoritative configuration and application source consolidated into default `main` branches;
- guarded adoptions completed with health, HTTP, monitoring and rollback verification;
- explicit previous-known-good images retained after successful adoption.

Stage 2 is now the next active gate. Automated production deployment remains disabled until secrets recovery, validation and later rollout gates pass.

## Stage 2 — Secrets foundation

### Deliverables

- Install/configure SOPS + age operating model.
- Generate approved age recipient/identity.
- Store only encrypted SOPS files in Git.
- Establish offline backup of age private identity.
- Test recovery/decryption from backup.
- Migrate pilot-service secrets to Docker Compose secrets where supported.
- Configure Jenkins credential handling for deployment/decryption.
- Document environment-variable exceptions.

### Exit criteria

- No project-managed production secret exists in plaintext Git.
- Age recovery test passes.
- Pilot secrets can be delivered without manual plaintext copying.
- Jenkins does not expose secrets in logs/artifacts.

## Stage 3 — Renovate update proposals

### Deliverables

- Configure Renovate Docker/Compose management.
- Start with PR-only operation.
- Separate major changes from lower-risk tag/digest updates.
- Configure digest pinning where appropriate.
- Suppress unsuitable/non-production tag families.
- Compare Renovate proposals with WUD findings.

### Exit criteria

- Renovate produces accurate candidate PRs for pilot services.
- No automatic merge or deployment path can bypass review/validation.

## Stage 4 — Jenkins validation gate

### Candidate pipeline

1. Checkout candidate Git revision.
2. Validate repository policy.
3. Run `docker compose config` validation.
4. Compare current runtime against proposed desired state.
5. Reject accidental downgrade unless explicitly authorised.
6. Pull/inspect candidate manifest and architecture.
7. Run Trivy image scan.
8. Validate required secrets are available without printing them.
9. Produce a deployment plan showing current, candidate and rollback versions.

### Exit criteria

- Known-good candidate passes.
- Deliberate malformed Compose change fails.
- Deliberate downgrade fails.
- Vulnerability/policy failure produces a clear gate result.

## Stage 5 — Pilot go-live

### Suggested pilot order

Start with low-impact services whose failure does not remove core DNS, monitoring storage or network access. Candidate services should be selected from the actual Stage 0 inventory.

### Deployment guard

The deployment wrapper must:

- capture current image ID/tag/digest;
- validate desired version;
- materialise secrets securely;
- pull candidate;
- update only the intended service/stack;
- wait for Docker health;
- run application-level smoke checks;
- present/execute rollback if acceptance fails;
- record deployment result.

### Exit criteria

- At least two pilot services upgraded using the controlled process.
- At least one rollback test completed successfully.
- No plaintext secret residue left by the pipeline.

## Stage 6 — Production rollout

### Approach

Roll out by service criticality, not all at once.

Suggested sequence:

1. remaining low-risk utility/UI services;
2. monitoring front-end/exporter services;
3. stateful monitoring services;
4. security tooling;
5. DNS/resilience services.

Critical services receive explicit pre-change backup and service-specific rollback checks.

### Exit criteria

- All in-scope services have an explicit version-control policy.
- Critical services have tested rollback/recovery steps.
- No unexpected Compose/runtime drift remains.

## Stage 7 — Observability and closure

### Metrics

Initial metrics should include:

- `homelab_docker_image_drift`
- `homelab_docker_image_pinned`
- `homelab_docker_image_floating`
- `homelab_docker_image_managed`
- `homelab_docker_secret_policy_compliant`
- `homelab_docker_inventory_last_success_timestamp`
- `k3s_image_inventory_success`
- `k3s_image_inventory_timestamp_seconds`
- `k3s_image_workload_container_ready`
- `k3s_image_digest_drift`
- `k3s_image_assessment_instances`

### Grafana

Create a Docker Version Control dashboard showing:

- host/service;
- desired version;
- running version;
- digest match;
- update signal;
- drift state;
- secret-policy state;
- last successful deployment;
- rollback version.

### Closure criteria

- Docker and Kubernetes runtime drift produce visible alerts.
- Inventory refresh is automated.
- Update, deploy and rollback runbooks are documented.
- Secrets recovery procedure has been tested.
- Pilot lessons have been incorporated into policy.

## Initial backlog

### P0 — required before deployment automation

- Build TestServer/ids-01 inventory collector.
- Define desired-vs-runtime comparison.
- Define downgrade detection.
- Inventory secrets and current `.env` usage.
- Establish SOPS + age key management and recovery.
- Define rollback metadata and backup requirements.

### P1 — controlled change workflow

- Renovate configuration.
- Jenkins validation pipeline.
- Trivy candidate-image checks.
- Deployment wrapper.
- Pilot service selection and test plan.

### P2 — observability and scale-out

- Prometheus textfile metrics.
- Grafana dashboard and alerts.
- WUD/Renovate correlation.
- Policy exception reporting.
- Evaluate central secrets platform if justified.

## Key risks

| Risk | Mitigation |
|---|---|
| Compose file older than runtime causes downgrade | Pre-deploy runtime/desired comparison; deny downgrade by default |
| Floating tag changes unexpectedly | Pin version and preferably digest; documented exceptions only |
| Secret committed to Git | SOPS-only encrypted files, ignore rules, review/CI checks |
| Loss of age private key | Separate offline backup and tested recovery |
| CI logs expose credentials | Jenkins credentials masking; no debug echo; post-job cleanup |
| Candidate image is vulnerable/incompatible | Trivy + architecture + policy gate |
| Deployment breaks service | Staged rollout, health checks, previous image retained, tested rollback |
| WUD/Renovate gives unsuitable version candidate | Git review + policy filters; neither tool deploys directly |

## Definition of done

The initial project is complete when every in-scope service on TestServer and ids-01 has:

- a known authoritative declaration;
- an explicit pinning policy;
- a known running tag/digest;
- automated drift visibility;
- a controlled update path;
- validation before deployment;
- a reproducible rollback path;
- secrets handled under the agreed policy or a documented exception.
