# Stage 6 estate coverage matrix — 28 August 2026

## Scope

This checkpoint records the live update-control estate across the three active execution domains:

| Host | Runtime | Platform | Active scope |
| --- | --- | --- | ---: |
| TestServer | Docker Compose | linux/arm64 | 30 running containers |
| ids-01 | Docker Compose | linux/amd64 | 17 running containers |
| k3s-node-01 | k3s/containerd | linux/arm64 | 11 long-running Deployment/DaemonSet controllers |

The inventories were collected read-only. No image pull, container recreation, Kubernetes rollout, Compose change, Stage 6 arm or deployment was performed.

The matrix uses transitional coverage states while onboarding is in progress:

- `managed-tested` — already proven through the guarded generic update path;
- `pending-onboarding` — likely fits an existing reviewed framework class but still needs a manifest/health/authority proof and a controlled pilot;
- `pending-framework` — requires a new or extended reviewed runtime/backend contract before onboarding;
- `pinned-manual` — intentionally kept outside the generic updater until a dedicated safe control path exists;
- `platform-managed` — lifecycle belongs to k3s/Helm/platform management rather than a normal application update transaction.

The final estate definition of done remains stricter: every active workload must ultimately be managed/tested, intentionally manual with reason, unsupported with explicit framework work, or removed.

## Cross-host priorities

### Prometheus

Prometheus is the strongest next cross-host proof:

- TestServer: application version `3.13.2`, already proven through generic Stage 6 on linux/arm64;
- ids-01: configured image `prom/prometheus:v3.13.1` on linux/amd64.

This gives the estate updater a useful same-service/multi-architecture case without introducing a new runtime class.

### Blackbox Exporter

Both Docker hosts currently run `prom/blackbox-exporter:v0.28.0` on different architectures. This is a good read-only desired-version/reporting test before any update is needed.

### cAdvisor

Both Docker hosts run `ghcr.io/google/cadvisor:0.60.5`, but both are privileged/device-backed. They must not be treated as ordinary registry-image workloads merely because the versions match.

### Loki

The hosts intentionally do not currently match:

- TestServer: `grafana/loki:2.9.6`;
- ids-01: `grafana/loki:3.7.6`.

Do not automatically converge this pair until configuration/storage compatibility and intended topology are reviewed.

### WUD

Both hosts use `getwud/wud:8`, but runtime risk differs:

- TestServer: writable Docker socket;
- ids-01: read-only Docker socket.

The ids-01 instance may fit the already-proven medium-risk read-only socket contract. The TestServer instance must remain outside that contract unless separately hardened or a new explicit higher-risk policy is reviewed.

## TestServer — Docker Compose / linux/arm64

| Service | Current image | Coverage | Class / reason |
| --- | --- | --- | --- |
| alloy | `grafana/alloy:v1.18.0` | pending-onboarding | medium-risk read-only Docker socket candidate |
| authelia | `authelia/authelia:4.39.20` | pending-onboarding | standard registry-image candidate |
| autokuma | digest-pinned AutoKuma 2.0.0 | pending-onboarding | medium-risk read-only Docker socket candidate |
| birdnet-exporter | local image | pending-framework | local-build provenance/execution class |
| birdnet-go | `ghcr.io/tphakala/birdnet-go:20260716` | pending-framework | device-backed workload |
| blackbox-exporter | `prom/blackbox-exporter:v0.28.0` | pending-onboarding | standard registry-image candidate; cross-host reporting case |
| cadvisor | `ghcr.io/google/cadvisor:0.60.5` | pending-framework | privileged + device-backed |
| cloudflare-ddns | `favonia/cloudflare-ddns:1.17.0` | pending-onboarding | standard registry-image candidate |
| crowdsec | `crowdsecurity/crowdsec:v1.7.8` | pending-onboarding | registry image; requires reviewed health/authority contract |
| crowdsec-exporter | local image | pending-framework | host-network + local-build class |
| dashy | digest-pinned 4.6.0 | managed-tested | historical Stage 6 pilot evidence |
| dozzle | `amir20/dozzle:v10.7.2` | pending-onboarding | medium-risk read-only Docker socket candidate |
| duckdns | LinuxServer digest/tag build | pending-onboarding | standard registry-image candidate |
| engineering-portfolio | local image | pending-framework | local-build provenance/execution class |
| filebrowser | `filebrowser/filebrowser:v2.63.23` | pending-onboarding | registry image with persistent data |
| homepage | digest-pinned 2.1.2 | managed-tested | generic Stage 6 + Docker-health + medium-risk read-only socket pilot |
| jenkins | local `homelab-jenkins:lts-jdk21` | pending-framework | local build and update-control-plane workload |
| jenkins-docker | `docker:dind` | pinned-manual | privileged update-control-plane dependency; dedicated controller-update path required |
| librespeed | `ghcr.io/librespeed/speedtest:6.2.1` | pending-onboarding | standard registry-image candidate |
| loki | `grafana/loki:2.9.6` | pending-framework | stateful/log-store compatibility review before generic rollback |
| maintenance-page | digest-pinned nginx | pending-onboarding | simple registry image; authority/health review required |
| node-exporter | `prom/node-exporter:v1.12.1` | pending-onboarding | standard registry-image candidate |
| npm | `jc21/nginx-proxy-manager:2.15.0` | pending-framework | proxy-critical/stateful workload |
| portainer | `portainer/portainer-ce:2.44.0` | pending-framework | writable Docker socket |
| portainer_agent | `portainer/agent:2.44.0` | pending-framework | writable Docker socket |
| projects-jrwroberts-co-uk | local image | pending-framework | local-build provenance/execution class |
| prometheus | digest-pinned 3.13.2 | managed-tested | generic Stage 6; TestServer arm64 proof |
| smokeping | `linuxserver/smokeping:latest` | pending-framework | floating `latest` must be replaced by reviewed immutable identities before onboarding |
| uptime-kuma | `louislam/uptime-kuma:1.23.16` | pending-onboarding | registry image with persistent data |
| wud | `getwud/wud:8` | pending-framework | writable Docker socket on TestServer |

### TestServer authority note

The Jenkins Compose project currently exposes two historical Compose working-directory labels, including a `/var/tmp/...` path from the prior Python-enabled Jenkins image work. No Stage 6 authority manifest should adopt a temporary worktree path. Jenkins/Jenkins-DinD onboarding must first normalize and prove the intended persistent authority path.

### Steady-state inspection note

A successful Stage 6 deployment does not make its consumed transition manifest a reusable steady-state inspection contract. The current generic Stage 6 inspector is intentionally pre-approval oriented and expects the live container to match the manifest's reviewed rollback identity. After a successful deployment, the live workload matches the candidate identity instead.

Therefore `managed-tested` and `inspect-ready` are separate states. Homepage is managed/tested at 2.1.2 but its consumed `2.0.0 -> 2.1.2` transition manifest must not be fed back into the unchanged pre-approval inspector. The estate updater needs a dedicated steady-state inspection contract before any host-contact adapter is enabled.

## ids-01 — Docker Compose / linux/amd64

| Service | Current image | Coverage | Class / reason |
| --- | --- | --- | --- |
| blackbox-exporter | `prom/blackbox-exporter:v0.28.0` | pending-onboarding | standard registry-image candidate; cross-host reporting case |
| cadvisor | `ghcr.io/google/cadvisor:0.60.5` | pending-framework | privileged + device-backed |
| grafana | `grafana/grafana:13.2.0` | pending-framework | stateful application; migration/rollback contract required |
| greenbone-gsad | `registry.community.greenbone.net/community/gsad:stable` | pending-framework | coupled Greenbone suite |
| greenbone-gvmd | `registry.community.greenbone.net/community/gvmd:stable` | pending-framework | coupled Greenbone suite + state/database coordination |
| greenbone-nginx | `registry.community.greenbone.net/community/nginx:latest` | pending-framework | coupled suite + floating tag |
| greenbone-openvasd | `registry.community.greenbone.net/community/openvas-scanner:stable` | pending-framework | coupled Greenbone suite |
| greenbone-ospd-openvas | `registry.community.greenbone.net/community/ospd-openvas:stable` | pending-framework | coupled Greenbone suite |
| greenbone-pg-gvm | `registry.community.greenbone.net/community/pg-gvm:stable` | pending-framework | coupled suite + database/migration risk |
| greenbone-redis-server | Greenbone redis-server floating/default tag | pending-framework | coupled Greenbone suite |
| loki | `grafana/loki:3.7.6` | pending-framework | stateful/log-store compatibility review |
| nebula-sync | `ghcr.io/lovelaze/nebula-sync:v0.11.2` | pending-onboarding | standard registry-image candidate |
| pihole-secondary | `pihole/pihole:2026.07.2` | pending-framework | DNS-critical/stateful service |
| pihole2-unbound | `debian:13-slim` | pending-framework | coupled DNS service with application supplied through configuration rather than image version alone |
| prometheus | `prom/prometheus:v3.13.1` | pending-onboarding | highest-priority amd64/cross-host generic proof; desired 3.13.2 |
| restic-server | `restic/rest-server:0.14.0` | pending-framework | backup-critical/stateful endpoint |
| wud | `getwud/wud:8` | pending-onboarding | medium-risk read-only Docker socket candidate |

### Greenbone transient containers

The inventory also found stopped Greenbone feed/config/migration/job containers. They are not counted as 17 active long-running containers. Their lifecycle is part of the Greenbone suite and must be modelled together rather than treated as independent generic services.

## k3s-node-01 — k3s/containerd / linux/arm64

### User / monitoring workloads

| Namespace | Controller | Current image | Coverage | Authority / class |
| --- | --- | --- | --- | --- |
| demo | Deployment `whoami` | digest-pinned `traefik/whoami@sha256:c4717...` | pending-framework | direct Kubernetes manifest; first simple Kubernetes backend candidate |
| homelab-defender-test | Deployment `homelab-defender` | `192.168.2.220:5000/homelab-defender:15` | pending-framework | local-registry Kubernetes workload |
| monitoring | Deployment `kube-state-metrics` | `registry.k8s.io/...:v2.19.1` | pending-framework | Helm-managed monitoring workload |

The `whoami` Deployment generation and active ReplicaSet both use the exact digest-pinned image. The earlier Pod table display of `:latest` was presentation/normalization only; live Pod specs and image IDs match the reviewed digest.

### k3s platform-managed components

| Namespace | Controller | Coverage | Authority |
| --- | --- | --- | --- |
| kube-system | Deployment `coredns` | platform-managed | k3s server manifest |
| kube-system | Deployment `local-path-provisioner` | platform-managed | k3s server manifest |
| kube-system | Deployment `metrics-server` | platform-managed | k3s server manifest set |
| kube-system | Deployment `traefik` | platform-managed | Helm release `traefik` managed by k3s |

These should normally move with k3s/platform lifecycle controls, not an arbitrary per-container updater.

### MetalLB — network-critical Helm suite

| Namespace | Controller | Risk | Coverage |
| --- | --- | --- | --- |
| metallb-system | Deployment `metallb-controller` | network-critical Helm suite | pinned-manual |
| metallb-system | DaemonSet `metallb-frr-k8s` | hostNetwork | pinned-manual |
| metallb-system | DaemonSet `metallb-speaker` | hostNetwork | pinned-manual |
| metallb-system | Deployment `metallb-frr-k8s-statuscleaner` | hostNetwork | pinned-manual |

These require a dedicated Kubernetes/Helm network-critical contract before any updater may mutate them.

### Kubernetes transient/platform jobs

`helm-install-traefik` and `helm-install-traefik-crd` are completed k3s platform jobs. They are inventory evidence, not independent long-running application update targets.

### ArgoCD note

An `argocd` namespace exists, but the cluster currently reports no `argoproj.io` CRDs and therefore no ArgoCD Application resources. Do not claim GitOps/ArgoCD authority for current workloads until that changes.

## First implementation sequence

1. Keep all three hosts in the reviewed estate catalogue from the first commit.
2. Implement only caller-input validation and read-only routing-plan generation first; no host contact.
3. Add a steady-state TestServer inspection contract before host contact. The existing Stage 6 inspector is a transition/pre-approval inspector and deliberately expects the live rollback image, so it must not be reused unchanged after a consumed deployment.
4. Add ids-01 read-only inspection transport/authority and prove Prometheus 3.13.2 on amd64 only after the same steady-state distinction is explicit.
5. Add a Kubernetes read-only inspection adapter for `k3s-node-01`, beginning with digest-pinned `demo/whoami`.
6. Expand workload classes only through explicit reviewed contracts and regression tests.

The Kubernetes backend is therefore represented from day one even though its mutation path remains deliberately unimplemented until the Docker and read-only Kubernetes inspection controls are proven.
