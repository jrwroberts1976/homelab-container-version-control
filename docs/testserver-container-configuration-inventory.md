# TestServer Container and Configuration Inventory

**Scope:** current 30-container TestServer Stage 4 estate  
**Purpose:** one names-only master table for desired image identity, Git ownership, non-secret configuration names, secret-delivery names, and current management classification.  
**Safety:** no plaintext secret values are recorded here. SOPS-backed entries list only secret names/recovery identities.

| # | Container | Compose stack / service | Desired image / build | Type | Variables / configuration names | Secret delivery (names only) | Git authority | Management state |
|---:|---|---|---|---|---|---|---|---|
| 1 | `alloy` | `alloy/alloy` | `grafana/alloy:v1.18.0` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 2 | `uptime-kuma` | `availability/uptime-kuma` | `louislam/uptime-kuma:1.23.16` | Registry image | `TZ` | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 3 | `autokuma` | `availability/autokuma` | `ghcr.io/bigboot/autokuma@sha256:8acbd3ad3ec8cb6c066aa0ee541154921283ec78159015937128541921c47974` | Registry image | `AUTOKUMA__KUMA__URL`, `AUTOKUMA__KUMA__USERNAME`; source key `AUTOKUMA_KUMA_USERNAME` | Compose secret `autokuma_kuma_password`; SOPS recovery key `AUTOKUMA_KUMA_PASSWORD`; runtime exports `AUTOKUMA__KUMA__PASSWORD` | `jrwroberts1976/docker-env` | Stage 4 secret-readiness validated |
| 4 | `smokeping` | `availability/smokeping` | `linuxserver/smokeping:latest@sha256:a0d1e57744a2217a0fe83b7828cffe2cbce16f44e59c858bead8ff41e7b63581` | Registry image, digest pinned | `PUID`, `PGID` | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 5 | `librespeed` | `availability/librespeed` | `ghcr.io/librespeed/speedtest:6.2.1` | Registry image | `MODE`, `TELEMETRY` | None in current Compose | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 6 | `birdnet-go` | `birdnet-go/birdnet-go` | `ghcr.io/tphakala/birdnet-go:20260716` | Registry image | `TZ` | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed; YYYYMMDD version policy |
| 7 | `birdnet-exporter` | `birdnet-go/birdnet-exporter` | `birdnet-go-birdnet-exporter:local` | Local build | Build args `BUILD_REVISION`, `BUILD_CREATED`, `BUILD_SOURCE` | None | `jrwroberts1976/docker-env` | Stage 4 local-build provenance validated |
| 8 | `cloudflare-ddns` | `cloudflare-ddns/cloudflare-ddns` | `favonia/cloudflare-ddns:1.17.0` | Registry image | `CLOUDFLARE_API_TOKEN_FILE`, `DOMAINS`, `PROXIED`, `IP6_PROVIDER` | Compose secret `cloudflare_api_token`; SOPS recovery key `CLOUDFLARE_API_TOKEN` | `jrwroberts1976/docker-env` | Stage 4 secret-readiness validated |
| 9 | `crowdsec` | `crowdsec/crowdsec` | `crowdsecurity/crowdsec:v1.7.8` | Registry image | `COLLECTIONS` | None in Compose | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 10 | `homepage` | `dashboards/homepage` | `ghcr.io/gethomepage/homepage:v2.0.0` | Registry image | `HOMEPAGE_ALLOWED_HOSTS`, `HOSTNAME`, `PORT` | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 11 | `dashy` | `dashboards/dashy` | `lissy93/dashy:4.5.13` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 12 | `maintenance-page` | `maintenance-page/maintenance-page` | `nginx:alpine` | Registry image, moving channel | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 policy-blocked for same-tag/different-digest ordering; manual review |
| 13 | `portainer` | `management/portainer` | `portainer/portainer-ce:2.44.0` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 14 | `portainer_agent` | `management/portainer_agent` | `portainer/agent:2.44.0` | Registry image | `CAP_HOST_MANAGEMENT` | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 15 | `dozzle` | `management/dozzle` | `amir20/dozzle:v10.7.2` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 reference validation service; no-change path proven |
| 16 | `filebrowser` | `management/filebrowser` | `filebrowser/filebrowser:v2.63.23` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 17 | `crowdsec-exporter` | `monitoring/crowdsec-exporter` | `monitoring-crowdsec-exporter:local` | Local build | Build args `BUILD_REVISION`, `BUILD_CREATED`, `BUILD_SOURCE` | None | `jrwroberts1976/docker-env` | Stage 4 local-build provenance validated |
| 18 | `prometheus` | `monitoring/prometheus` | `prom/prometheus:v3.13.1` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 19 | `loki` | `monitoring/loki` | `grafana/loki:2.9.6` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 20 | `node-exporter` | `monitoring/node-exporter` | `prom/node-exporter:v1.12.1` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 21 | `cadvisor` | `monitoring/cadvisor` | `ghcr.io/google/cadvisor:0.60.5` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 22 | `blackbox-exporter` | `monitoring/blackbox-exporter` | `prom/blackbox-exporter:v0.28.0` | Registry image | None in Compose | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 23 | `npm` | `proxy-auth/nginx-proxy-manager` | `jc21/nginx-proxy-manager:2.15.0` | Registry image | None in current Compose | Protected NPM recovery material exists in SOPS; values intentionally omitted | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 24 | `authelia` | `proxy-auth/authelia` | `authelia/authelia:4.39.20` | Registry image | `TZ` | None in Compose | `jrwroberts1976/docker-env` | Stage 4 read-only governed |
| 25 | `duckdns` | `proxy-auth/duckdns` | `lscr.io/linuxserver/duckdns:af6dcae5-ls86` | Registry image | `PUID`, `PGID`, `TZ`, `SUBDOMAINS`, `FILE__TOKEN`, `UPDATE_IP` | Compose secret `duckdns_token`; SOPS recovery key `DUCKDNS_TOKEN` | `jrwroberts1976/docker-env` | Stage 4 secret-readiness validated; opaque version policy |
| 26 | `wud` | `wud/wud` | `getwud/wud:8` | Registry image | `WUD_WATCHER_LOCAL_CRON`, `WUD_WATCHER_LOCAL_WATCHBYDEFAULT`, `WUD_TRIGGER_DOCKER_LOCAL_AUTO`, `WUD_TRIGGER_DOCKER_LOCAL_PRUNE`, `NODE_ENV` | None | `jrwroberts1976/docker-env` | Stage 4 read-only governed; integer version policy; WUD is signal only |
| 27 | `engineering-portfolio` | external Git `engineering-portfolio` | `james-roberts/engineering-portfolio:local` | Local build | Build args `PUBLIC_GRAFANA_SECURITY_DASHBOARD`, `PUBLIC_GRAFANA_PLATFORM_DASHBOARD`, `PUBLIC_GRAFANA_BIRDNET_DASHBOARD`, `BUILD_REVISION`, `BUILD_CREATED`, `BUILD_SOURCE`; runtime/Compose key `PORTFOLIO_PORT` | No secret values in Compose | `jrwroberts1976/engineering-portfolio` | Stage 4 exact-head local-build provenance validated |
| 28 | `projects-jrwroberts-co-uk` | external Git `projects-site` | `projects-jrwroberts-co-uk-projects-site:local` | Local build | Build args `BUILD_REVISION`, `BUILD_CREATED`, `BUILD_SOURCE` | None | `jrwroberts1976/projects-jrwroberts-co-uk` | Stage 4 exact-head local-build provenance validated |
| 29 | `jenkins` | platform exception `projects/jenkins` | Runtime image `homelab-jenkins:lts-jdk21` | Local build / platform exception | Runtime evidence includes `DOCKER_HOST`; complete Compose variable source is not Git-owned | Jenkins credentials are kept in Jenkins credential store, not this table | No Git source authority for controller Compose | Stage 4 platform exception: assess/propose only; Jenkins must not automatically recreate Jenkins |
| 30 | `jenkins-docker` / Compose service `docker` | platform exception `projects/docker` | Exact Git desired image reference not captured in the project authority | Registry image / platform exception | DinD/TLS runtime configuration is not Git-owned in the Stage 4 authority | No secret values recorded | No Git source authority for Jenkins/DinD Compose | Stage 4 platform exception; isolated DinD; no host Docker socket access |

## Interpretation

- The table reconciles to the Stage 4 TestServer estate: **30/30 containers accounted for**.
- Registry-image and local-build services remain read-only at Stage 4; this document does not grant deployment authority.
- `maintenance-page` remains deliberately fail-closed because `nginx:alpine` is a moving channel and the current policy will not guess version ordering from a changed digest.
- Jenkins controller and DinD remain explicit platform exceptions. Their runtime is visible to the project, but their Compose authority is not yet Git-owned.
- Secret values are never placed in this inventory. Current SOPS-backed readiness entries are represented by secret/recovery-key names only.
- The older Stage 0 cross-estate baseline also covers **31 containers on `ids-01`**, but that host does not yet have the same per-container configuration-variable table in the Stage 4 TestServer authority. It should be added as a separate source-backed extension rather than guessed into this table.
