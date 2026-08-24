# Homelab Container Version Control

A controlled, observable and reversible way to manage Docker and Kubernetes image versions across the homelab.

## Goals

This project establishes end-to-end control from the version declared in Compose through validation, deployment, runtime verification, drift detection and rollback.

The operating model is:

- **Git / Compose is the source of truth** for the desired container version.
- **Renovate proposes updates** through pull requests rather than changing running containers directly.
- **Jenkins validates candidate changes** before deployment.
- **Trivy provides vulnerability scanning** for candidate images.
- **WUD remains an independent update signal**, not the deployment authority.
- **Prometheus / Grafana reports runtime drift and compliance**.
- **SOPS + age protects secrets stored with deployment configuration**, while Docker Compose secrets are preferred over sensitive environment variables where supported.
- **Deployments are staged, health-checked and reversible**.

## Why this project exists

Recent maintenance exposed two important risks:

1. A running container can be newer than its Compose declaration, creating a silent downgrade risk during recreation.
2. Runtime update tooling can detect changes, but without an authoritative Git-controlled declaration there is no complete audit trail or guaranteed rollback point.

The project is designed to prevent unexpected Compose-to-runtime downgrades and make every image change reproducible.

## Initial scope

The first production scope is the Docker estate on **TestServer** and **ids-01**. The operating model now also covers Kubernetes workloads on **k3s-node-01**.

Initial deliverables:

1. Inventory Compose-declared and actually running images, tags and digests.
2. Detect and report declared-vs-running drift.
3. Define image pinning and exception policies.
4. Introduce controlled image-update pull requests.
5. Add CI validation and vulnerability checks.
6. Introduce secrets-management standards before deployment automation goes live.
7. Add guarded, staged deployment and rollback procedures.
8. Export compliance metrics to Prometheus and Grafana.

## Staged go-live

The project will be introduced in phases rather than enabling automated deployment immediately.

- **Stage 0 — Discovery and baseline:** inventory, drift detection and secrets inventory only.
- **Stage 1 — Git control:** standardise Compose declarations and remove uncontrolled floating versions.
- **Stage 2 — Secrets foundation:** SOPS + age, Compose secrets where supported, Jenkins credential handling, backup and recovery of decryption keys.
- **Stage 3 — Update proposals:** Renovate opens controlled PRs; no automatic deployment.
- **Stage 4 — Validation gate:** Jenkins validates Compose, architecture, downgrade risk and Trivy results.
- **Stage 5 — Pilot deployment:** guarded deployment to low-risk services with health checks and rollback.
- **Stage 6 — Production rollout:** extend the process to critical services after pilot acceptance.
- **Stage 7 — Observability and optimisation:** Grafana compliance dashboards, alerts and policy tuning.

## Proven pilot pattern

The Engineering Portfolio deployment on TestServer is being used as the first real-world guarded-deployment pattern.

The deployment workflow now distinguishes Docker `running` from application readiness, waits for `/healthz` with a bounded retry loop, fails early on Docker `unhealthy`, runs route smoke tests and keeps maintenance mode active on failure.

The associated maintenance-page stack has also been captured in this repository. Its Nginx fallback was proven after container recreation to serve the maintenance page for real application routes and unknown paths instead of returning 404.

See [Maintenance Page Pilot](pilot/maintenance-page/README.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Project plan and timeline](docs/project-plan.md)
- [Secrets management](docs/secrets-management.md)
- [Operating model](docs/operating-model.md)
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

```text
homelab-container-version-control/
├── README.md
├── renovate.json
├── docs/
│   ├── architecture.md
│   ├── project-plan.md
│   ├── secrets-management.md
│   └── operating-model.md
├── policy/
│   ├── image-version-policy.md
│   ├── rollback-policy.md
│   └── exceptions.yml
├── pilot/
│   └── maintenance-page/
│       ├── README.md
│       ├── docker-compose.yml
│       └── nginx/
│           └── default.conf
├── inventory/
│   ├── ids-01.yml
│   └── testserver.yml
├── scripts/
│   ├── inventory-images.sh
│   ├── check-drift.sh
│   ├── check-downgrade.sh
│   └── deploy-stack.sh
├── monitoring/
│   └── docker-version-metrics.sh
└── jenkins/
    └── Jenkinsfile
```


## Kubernetes compliance extension

The same desired-versus-running control model is now operational on `k3s-node-01` through the authoritative [kubernetes-homelab](https://github.com/jrwroberts1976/kubernetes-homelab) repository.

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

## DietPi operational-state extension

The same source-control principles now cover the adjacent DNS and backup services on **DietPi** without treating the host as part of the Docker container count.

Completed on **23 August 2026**:

- 14 operational scripts and the Pi-hole blocked-query alert application captured from the live host;
- 18 custom systemd service and timer units recorded;
- five active Pi-hole adlists exported as declarative recovery input;
- effective Unbound local overrides stored;
- safe environment templates added while live credentials, databases, TLS keys, generated metrics and backup state remain excluded;
- shell, Python, systemd, whitespace and secret-content validation passed;
- adoption merged into `home-lab-docs/main` through [PR #16](https://github.com/jrwroberts1976/home-lab-docs/pull/16).
- non-destructive recovery rehearsal reconstructed 38 files and 14 executables with matching hashes, validated systemd units and preserved secret exclusion; the tested runbook was merged through [PR #17](https://github.com/jrwroberts1976/home-lab-docs/pull/17).

This extends recovery and audit coverage for critical DNS operations while preserving the rule that Git stores desired state and source—not runtime databases or plaintext secrets.

## Current status

Stage 0 completed on **23 August 2026**.

The final estate contains **61 containers** across ids-01 and TestServer:

- ids-01: 31 Compose-managed containers with no detected reference drift;
- TestServer: 30 Compose-managed containers, comprising 25 registry-image services and five local builds;
- zero unmanaged containers;
- zero registry-image drift.

The TestServer baseline and subsequent BirdNET adoption, obsolete ASUS exporter retirement, and inactive Training Platform retirement are merged into the authoritative `docker-env/main` branch.

The names-only secret-delivery inventory assessed all 30 TestServer containers. Four services currently receive sensitive configuration through environment variables; no values or secret-file contents were recorded.

Stage 1 completed on **23 August 2026**, ahead of its original planning window. Registry-image policy is reconciled: TestServer has 2 digest-compliant and 23 version-tagged services; ids-01 has 11 version-tagged services and 20 Greenbone containers covered by approved exception `EX-2026-001`. There is no registry-image drift, unmanaged container or unapproved floating reference.

Local-build provenance is also reconciled. BirdNET exporter, CrowdSec exporter, Engineering Portfolio and the Projects site all report `revision-match` against clean authoritative source. Jenkins remains the sole documented `no-git-source` exception. Guarded image adoptions passed container-health, HTTP or monitoring validation, and explicit rollback images remain retained.

**Docker Stage 2 — Secrets foundation is in progress.** The first production Compose-secret pilot is complete: Grafana SMTP on `ids-01` now uses a host-backed Docker Compose secret, authenticated successfully and delivered a test notification. All 303 retired plaintext Compose copies were removed. The K3s extension has completed automated inventory, central Prometheus ingestion and Grafana compliance alerting. GitOps reconciliation and preventive admission policy remain future Kubernetes work. Automated production deployment remains disabled until secrets recovery, validation and later rollout gates are satisfied.

See [Stage 0 baseline findings](docs/stage0-baseline-findings.md) and the [project tracker](https://github.com/jrwroberts1976/homelab-container-version-control/issues/1).
