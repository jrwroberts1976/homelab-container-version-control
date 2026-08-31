# Homelab Container Version Control

A controlled, observable and reversible way to manage Docker and Kubernetes image versions across the homelab.

## Goals

This project establishes end-to-end control from the version declared in Compose through validation, candidate acquisition, deployment, runtime verification, durable authority, drift detection and rollback.

The operating model is:

- **Git / Compose is the source of truth** for the desired container version.
- **Renovate proposes updates** through pull requests rather than changing running containers directly.
- **Jenkins validates and, for reviewed Stage 6 services, performs guarded deployment** after explicit approval and zero-drift proof.
- **Candidate images are exact and immutable**; the target model has Jenkins acquire and verify them before approval through a restricted image-cache-only credential.
- **Trivy provides vulnerability scanning** for candidate images where defined by policy.
- **WUD remains an independent update signal**, not the deployment authority.
- **Prometheus / Grafana reports runtime drift and compliance**.
- **SOPS + age protects secrets stored with deployment configuration**, while Docker Compose secrets are preferred over sensitive environment variables where supported.
- **Deployments are staged, health-checked, reversible and durably closed back into Git authority/catalogue/steady state**.

## Why this project exists

Recent maintenance exposed two important risks:

1. A running container can be newer than its Compose declaration, creating a silent downgrade risk during recreation.
2. Runtime update tooling can detect changes, but without an authoritative Git-controlled declaration there is no complete audit trail or guaranteed rollback point.

Stage 6 testing added a third lesson:

3. A successfully deployed healthy container is still not fully closed if Git Compose authority, the estate catalogue or the steady-state record remains behind the runtime.

The project is designed to prevent unexpected Compose-to-runtime downgrades and make every image change reproducible and evidence-backed.

## Initial scope

The first production scope is the Docker estate on **TestServer** and **ids-01**. The operating model also covers Kubernetes workloads on **k3s-node-01** through related Git-owned controls.

Initial deliverables:

1. Inventory Compose-declared and actually running images, tags and digests.
2. Detect and report declared-vs-running drift.
3. Define image pinning and exception policies.
4. Introduce controlled image-update pull requests.
5. Add CI validation and vulnerability checks.
6. Introduce secrets-management standards before deployment automation goes live.
7. Add guarded, staged deployment and rollback procedures.
8. Export compliance metrics to Prometheus and Grafana.
9. Close successful updates back into durable Git authority, catalogue and steady-state evidence.

## Staged go-live

The project has been introduced in phases rather than enabling unrestricted automated deployment.

- **Stage 0 — Discovery and baseline:** inventory, drift detection and secrets inventory only.
- **Stage 1 — Git control:** standardise Compose declarations and remove uncontrolled floating versions.
- **Stage 2 — Secrets foundation:** SOPS + age, Compose secrets where supported, Jenkins credential handling, backup and recovery of decryption keys.
- **Stage 3 — Update proposals:** Renovate opens controlled PRs; no automatic deployment.
- **Stage 4 — Validation gate:** Jenkins validates Compose, architecture, downgrade risk and security evidence.
- **Stage 5 — Pilot deployment:** guarded deployment to low-risk services with health checks and rollback.
- **Stage 6 — Production rollout:** generic reviewed service updates on TestServer/ids-01 with explicit approval, zero drift, target-only recreation, rollback and durable closure.
- **Stage 7 — Observability and optimisation:** Grafana compliance dashboards, alerts and policy tuning.

## Proven Stage 6 pattern — 31 August 2026

The generic Stage 6 path is now real and has performed reviewed production-style service updates.

Proven controls include:

- reviewed service-update manifests;
- fixed TestServer/ids-01 SSH routes and host-key pins;
- read-only pre-approval inspectors;
- explicit human approval;
- exact post-approval zero-drift proof;
- deployment executor binding only after approval and zero drift;
- one-shot arm/deploy/disarm state;
- target-only `docker compose up -d --no-deps --no-build --pull never --force-recreate`;
- Docker health, fixed HTTP and internal Docker-network `container-http` health;
- protected-container ID/restart checks;
- reviewed rollback.

### Loki 3.7.7

The ids-01 Loki `3.7.7` update proved the generic multi-host Jenkins deployment/disarm path and protected Grafana/Prometheus invariants.

It also exposed the original closure gap: runtime deployment succeeded while Git Compose authority, catalogue and steady-state metadata remained stale.

### Dozzle 10.8.0

Dozzle was requalified as a generic TestServer Stage 6 service with:

- a read-only Docker socket;
- no published host port;
- reviewed `container-http` health on `homelab_apps:8080/`;
- an explicitly reviewed empty Docker runtime user.

Jenkins build #13 successfully deployed the exact immutable 10.8.0 candidate after human approval and zero-drift proof. A later disarm step failed because the transition helper had not yet implemented `container-http` terminal health.

That framework gap was fixed. The already-deployed service was disarmed without recreation, its exact immutable Compose authority was promoted, the catalogue and steady-state record were promoted/installed, and the final read-only steady-state inspection passed.

Dozzle final service state:

```text
SUCCESS_CLOSED
```

The historical Jenkins build remains a closure-incomplete failure because those recovery/closure steps occurred after the build. The consumed Dozzle update must not be redeployed simply to create a green historical Jenkins result.

### Next Jenkins qualification

Before the next fresh update the pipeline must gain:

1. a dedicated restricted candidate-acquisition SSH identity/forced command;
2. Jenkins-owned exact immutable candidate pull/verification before approval;
3. proof that candidate acquisition changes only the local image cache and no container state;
4. a non-mutating `VERIFY_CLOSED` path for already-completed services;
5. a clean Dozzle `SUCCESS_VERIFIED_CLOSED` Jenkins proof without recreation;
6. automatic authority/catalogue/steady-state closure inside the same fresh-update workflow.

TestServer Alloy has passed read-only requalification evidence collection and is intended to be the first fresh update after those Jenkins changes. Its `1.19.2` candidate was not intentionally pulled or deployed during the 31 August closeout.

See [Stage 6 end-to-end service-update automation](docs/stage6-end-to-end-automation.md).

## Proven pilot pattern

The Engineering Portfolio deployment on TestServer established the earlier guarded-deployment pattern.

The deployment workflow distinguishes Docker `running` from application readiness, waits for `/healthz` with a bounded retry loop, fails early on Docker `unhealthy`, runs route smoke tests and keeps maintenance mode active on failure.

The associated maintenance-page stack has also been captured in this repository. Its Nginx fallback was proven after container recreation to serve the maintenance page for real application routes and unknown paths instead of returning 404.

See [Maintenance Page Pilot](pilot/maintenance-page/README.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Project plan and timeline](docs/project-plan.md)
- [Secrets management](docs/secrets-management.md)
- [Operating model](docs/operating-model.md)
- [Stage 6 end-to-end service-update automation](docs/stage6-end-to-end-automation.md)
- [Image version policy](policy/image-version-policy.md)
- [Downgrade policy](policy/downgrade-policy.md)
- [Rollback policy](policy/rollback-policy.md)
- [Policy exception registry](policy/exceptions.yml)
- [Maintenance Page Pilot](pilot/maintenance-page/README.md)
- [Stage 0 inventory runbook](docs/stage0-inventory-runbook.md)
- [Stage 0 baseline findings](docs/stage0-baseline-findings.md)
- [Stage 1 policy assessment runbook](docs/stage1-policy-assessment-runbook.md)
- [Stage 1 registry-image findings](docs/stage1-registry-image-findings.md)
- [K3s Stage 1 compliance monitoring](docs/k3s-stage1-compliance.md)

## Repository layout

The repository now includes the original policy/inventory tooling plus generic Stage 6 manifests, steady-state definitions, Jenkins pipelines and reviewed host-side helpers.

Key current locations include:

```text
config/estate-updater-catalog.json
config/services/
config/steady-state/
config/service-update-manifest.schema.json
config/steady-state-manifest.schema.json
Jenkinsfile.stage6-service-update
ops/testserver/
ops/ids01/
scripts/validate-stage6-service-manifest.py
scripts/validate-stage6-steady-state-manifest.py
docs/stage6-end-to-end-automation.md
```

## Kubernetes compliance extension

The same desired-versus-running control model is operational on `k3s-node-01` through the authoritative [kubernetes-homelab](https://github.com/jrwroberts1976/kubernetes-homelab) repository.

Completed on **23 August 2026**:

- Git-owned, digest-pinned desired state for whoami and Homelab Defender;
- pinned K3s, MetalLB and kube-state-metrics installation inputs;
- read-only correlation of workload declarations with active pod image IDs;
- ownership classification for Helm, K3s-packaged and kubectl-managed workloads;
- automated five-minute Prometheus textfile export through node-exporter;
- central ingestion by Prometheus on `ids-01`;
- 16 active container instances assessed: 3 digest-pinned and 13 explicitly version-tagged;
- zero floating images, digest drift, unknown ownership or unready active containers.

Grafana is the notification control plane. On **24 August 2026**, four Git-managed K3s compliance rules were deployed for inventory failure, stale evidence, digest drift and unready containers. All four evaluated as `inactive` with health `ok` after the direct Prometheus queries were corrected to use instant evaluation.

## K3s datastore secret encryption

Completed on **25 August 2026**:

- persistent `--secrets-encryption` desired state merged into `kubernetes-homelab/main`;
- AES-CBC encryption enabled for the K3s SQLite datastore;
- a root-only pre-rotation recovery point validated with SQLite `quick_check` and checksums;
- the staged `prepare`, restart, `rotate`, restart, `reencrypt`, restart workflow completed;
- all 14 existing Kubernetes Secrets re-encrypted successfully;
- final state verified as `Enabled`, `reencrypt_finished`, with matching server hashes;
- Secret API access, workload health and datastore integrity passed after the final restart.

Recovery-sensitive datastore, token and encryption-configuration material remains outside Git.

## DietPi operational-state extension

The same source-control principles cover the adjacent DNS and backup services on **DietPi** without treating the host as part of the Docker container count.

Completed on **23 August 2026**:

- 14 operational scripts and the Pi-hole blocked-query alert application captured from the live host;
- 18 custom systemd service and timer units recorded;
- five active Pi-hole adlists exported as declarative recovery input;
- effective Unbound local overrides stored;
- safe environment templates added while live credentials, databases, TLS keys, generated metrics and backup state remain excluded;
- shell, Python, systemd, whitespace and secret-content validation passed;
- adoption merged into `home-lab-docs/main` through [PR #16](https://github.com/jrwroberts1976/home-lab-docs/pull/16);
- non-destructive recovery rehearsal reconstructed 38 files and 14 executables with matching hashes, validated systemd units and preserved secret exclusion; the tested runbook was merged through [PR #17](https://github.com/jrwroberts1976/home-lab-docs/pull/17).

This extends recovery and audit coverage for critical DNS operations while preserving the rule that Git stores desired state and source—not runtime databases or plaintext secrets.

## Current status

Stage 0 and Stage 1 remain completed foundations. Stage 2 secrets work and the Kubernetes extensions remain part of the broader programme, but Docker Stage 6 is now an active production-rollout workstream rather than a future disabled capability.

The controlled deployment core is proven on Loki and Dozzle. Dozzle is the first service in this session to reach full runtime + immutable Compose authority + catalogue + installed steady-state closure.

The next engineering checkpoint is deliberately **not** another manual container update. It is to complete the Jenkins security/BAU path:

```text
restricted candidate acquisition
        |
        v
Dozzle VERIFY_CLOSED proof
        |
        v
fresh Alloy end-to-end SUCCESS_CLOSED proof
```

Unrestricted automated deployment remains out of scope. All Stage 6 mutation continues to require reviewed manifests, fixed routes, explicit approval, exact zero drift and bounded host-side authority.

See [Stage 6 end-to-end service-update automation](docs/stage6-end-to-end-automation.md) for the current contract and [the project tracker](https://github.com/jrwroberts1976/homelab-container-version-control/issues/1) for the wider programme.
