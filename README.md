# Homelab Container Version Control

A controlled, observable and reversible way to manage Docker image versions across the homelab.

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

The first production scope is the Docker estate on **TestServer** and **ids-01**.

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

## Documentation

- [Architecture](docs/architecture.md)
- [Project plan and timeline](docs/project-plan.md)
- [Secrets management](docs/secrets-management.md)
- [Operating model](docs/operating-model.md)
- [Image version policy](policy/image-version-policy.md)
- [Rollback policy](policy/rollback-policy.md)

## Repository layout

Planned structure:

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

## Current status

Repository bootstrap and planning are in progress. No automated production deployment will be enabled until the inventory, secrets foundation, validation gate and rollback controls are complete.
