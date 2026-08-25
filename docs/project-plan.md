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
| 2. Secrets foundation | 5–11 Sep | **In progress — started 24 Aug** | Four Compose-secret pilots and K3s datastore encryption complete; SOPS + age identity recovery remains | No plaintext repo secrets; recovery test passes |
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
| K4. Alerting | 24 Aug 2026 | Grafana-managed stale, failure, drift and readiness alerts | Four Git-managed rules deployed; all evaluated `inactive` with health `ok` |
| K5. GitOps and admission policy | Planned | Continuous reconciliation and preventive policy | Future stage |
| K6. Datastore secret encryption | 25 Aug 2026 | Persistent AES-CBC encryption enabled; 14 existing Secrets re-encrypted | `kubernetes-homelab/main`; `reencrypt_finished`; matching hashes; recovery evidence validated |

See [K3s Stage 1 compliance monitoring](k3s-stage1-compliance.md).

## DietPi operational-state extension

DietPi is adjacent critical infrastructure rather than part of the Docker/Kubernetes image totals. Its operational source is controlled under the same desired-state, validation and secret-exclusion principles.

| Stage | Completed | Outcome | Evidence |
|---|---|---|---|
| D0. Ownership and discovery | 23 Aug 2026 | Pi-hole, Unbound, backup, monitoring and security automation mapped to the live host | Read-only source and systemd inventory |
| D1. Git adoption | 23 Aug 2026 | 14 operational scripts, alert application, 18 systemd units, five Pi-hole adlists and Unbound overrides captured | `home-lab-docs` PR #16, merge `17a574f` |
| D2. Secret separation | 23 Aug 2026 | Environment templates retained; live credentials, databases, keys, generated metrics and backup state excluded | Secret-content gate passed |
| D3. Recovery validation | 24 Aug 2026 | Non-destructive reconstruction of 38 files and 14 executables passed hash, mode, syntax, systemd, manifest and secret-exclusion gates | `home-lab-docs` PR #17; full clean-host secret restoration remains a future maintenance exercise |

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

## Progress update — 24 August 2026

Docker Stage 2 began with the successful Grafana SMTP Compose-secret pilot on `ids-01`.

Completed:

- rotated the previously exposed Gmail application password;
- migrated Grafana from a direct password declaration to `GF_SMTP_PASSWORD__FILE`;
- resolved non-root container access to the mounted secret;
- verified direct SMTP authentication and Grafana contact-point delivery;
- preserved Grafana health and all 29 alert rules during a Grafana-only recreation;
- removed direct password delivery from active Compose, `.env` and the runtime environment;
- permanently removed 303 retired Compose copies containing the rotated credential.

Next Stage 2 activities:

1. assess and migrate the remaining environment-delivered secrets;
2. implement the SOPS and age encrypted-source pattern;
3. document and test age identity backup and recovery;
4. validate Jenkins credential handling and log masking;
5. document exceptions for applications that cannot consume file secrets.

### Cloudflare DDNS Compose-secret pilot

The second Stage 2 pilot completed on 24 August 2026:

- migrated `CLOUDFLARE_API_TOKEN` from plaintext `.env` delivery to native `CLOUDFLARE_API_TOKEN_FILE` delivery;
- mounted the token read-only through Docker Compose secrets;
- retained the pinned image, zero restart count and successful DNS check;
- removed the obsolete plaintext `.env` file;
- confirmed no related plaintext declaration remained in the active stacks tree;
- merged the authoritative Compose declaration into `docker-env/main` at `e557f924`.

Subsequent review classified LibreSpeed as a false positive and retained AutoKuma as a genuine migration candidate.

### DuckDNS Compose-secret pilot

The third Stage 2 pilot completed on 24 August 2026:

- migrated the DuckDNS token from plaintext `.env` delivery to LinuxServer `FILE__TOKEN` delivery;
- mounted the token read-only through Docker Compose secrets;
- verified successful environment resolution and a live DuckDNS update request;
- preserved the pinned image, zero restart count and shared-stack isolation;
- removed the obsolete plaintext `.env` file;
- merged the authoritative declaration into `docker-env/main` at `1724f2ce`.

Subsequent review identified AutoKuma as the remaining genuine original candidate, classified LibreSpeed as an unused image-default false positive, and found the previously missed Uptime Kuma SMTP password because its runtime name ends in `_PASS` rather than `PASSWORD`.


### AutoKuma Compose-secret pilot

The fourth Stage 2 pilot completed on 24 August 2026:

- migrated the effective AutoKuma credential from duplicated `.env` declarations to the Compose secret `autokuma_kuma_password`;
- selected the only declaration matching the known-good runtime credential and excluded the stale duplicate without recording either value;
- confirmed that AutoKuma v2.0.0 does not implement the secret-file syntax described by later development documentation;
- introduced a controlled startup wrapper that reads `/run/secrets/autokuma_kuma_password`, exports `AUTOKUMA__KUMA__PASSWORD` inside the process and then executes AutoKuma;
- removed direct password delivery from Docker's configured environment;
- verified the read-only mount, zero restart count and successful AutoKuma authentication;
- preserved Uptime Kuma, LibreSpeed and Smokeping without recreation;
- normalised the shared environment file to retain only `AUTOKUMA_KUMA_USERNAME` and `KUMA_SMTP_PASSWORD`;
- merged the authoritative Compose declaration into `docker-env/main` at revision `ef31441`.

LibreSpeed requires no secret migration in its current standalone, telemetry-disabled mode: the observed eight-character `PASSWORD` equals the image default and has no Compose or stack-environment declaration.

Follow-up inspection proved that Uptime Kuma 1.23.16 contains no implementation references for the supplied `UPTIME_KUMA_SMTP_*` variables and has no notification records. The unused block and `KUMA_SMTP_PASSWORD` source were therefore retired. The Stage 0 collector must still be extended to recognise sensitive names ending in `_PASS`, because discovery and later usage classification are separate controls.


### Uptime Kuma unused SMTP retirement

The availability-stack SMTP review completed on 24 August 2026:

- confirmed that all six `UPTIME_KUMA_SMTP_*` variables reached the container but had zero implementation references in Uptime Kuma 1.23.16;
- confirmed the notification table contained zero rows;
- classified `KUMA_SMTP_PASSWORD` and the six derived runtime variables as unused configuration rather than an active secret-delivery path;
- removed the unused Compose environment block and the plaintext `KUMA_SMTP_PASSWORD` entry;
- recreated only Uptime Kuma and verified healthy status, zero restarts and zero remaining SMTP environment variables;
- preserved AutoKuma, LibreSpeed and Smokeping without recreation;
- merged the authoritative retirement into `docker-env/main` at revision `a4711b4`.

The shared availability `.env` now contains only `AUTOKUMA_KUMA_USERNAME`, which is a sensitive identifier rather than a secret. No genuine environment-delivered secret remains in that stack based on the completed source and runtime review.


### K3s datastore secret-encryption milestone

Completed on 25 August 2026:

- enabled persistent `--secrets-encryption` desired state on the single-server K3s cluster;
- captured a root-only recovery point containing a consistent SQLite backup and required recovery material;
- validated database integrity and recovery-file checksums before rotation;
- completed the staged key transition and re-encrypted all 14 existing Kubernetes Secrets;
- verified `Encryption Status: Enabled`, stage `reencrypt_finished` and matching server hashes;
- verified Secret API readability, healthy workloads and SQLite integrity after the final restart;
- merged the installation flag and operational documentation into `kubernetes-homelab/main` at revision `dd8cb32`.

This completes K3s datastore encryption at rest. SOPS + age for encrypted Git-managed application declarations, offline age-identity recovery and preventive admission policy remain future Stage 2 work.
