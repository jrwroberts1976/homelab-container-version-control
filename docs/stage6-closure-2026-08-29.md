# Stage 6 production rollout closure — 29 August 2026

## Status

Stage 6 is **complete and closed** for the reviewed TestServer Docker estate.

The final closure audit returned:

```text
STAGE6_REVIEW_COMPLETE=true
STAGE6_NORMALIZATIONS_COMPLETED=7
STAGE6_NORMALIZATIONS_CONSUMED=7
STAGE6_FORMAL_DEFERRALS=13
STAGE6_UNREVIEWED_TAGGED_EXTERNAL_SERVICES=0
SMOKEPING_DEFERRED=true
SMOKEPING_AUTHORITY_RECONCILED=true
ROLLBACK_REQUIRED=false
STAGE6_CLOSED=true
```

This closure means every running non-local tagged external image on TestServer is either:

- running with an immutable digest reference; or
- formally deferred from the standard Stage 6 normalizer for a reviewed technical reason.

Local images remain outside this registry-image normalization count and retain their separate provenance/control model.

## Final authority state

The detached Stage 6 authority checkout was clean and exactly anchored to `origin/main` at closure.

| Item | Final value |
| --- | --- |
| Docker authority repository | `docker-env` |
| Final authority commit | `5dd8be5b7ca486670aab99d994511339b5b7147c` |
| Authority checkout mode | detached HEAD |
| Authority worktree | clean |
| Unreviewed tagged external services | `0` |
| Rollback required | `false` |

The detached authority checkout is intentional. Closure validation requires the checkout HEAD to equal the reviewed `origin/main` commit while remaining clean and detached.

## Completed and consumed image normalizations

Seven one-shot same-content tag-to-digest normalization contracts completed successfully. Each service has its installed normalization manifest, historical approval evidence and consumed marker preserved; each runtime remained running on the reviewed immutable target at closure.

| Service | Final immutable runtime reference |
| --- | --- |
| Authelia | `authelia/authelia@sha256:1b363e9279e742397966333f364e0876ae02bf5c876de73e83af6d48c57ff51b` |
| Blackbox Exporter | `prom/blackbox-exporter@sha256:e753ff9f3fc458d02cca5eddab5a77e1c175eee484a8925ac7d524f04366c2fc` |
| File Browser | `filebrowser/filebrowser@sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a` |
| LibreSpeed | `ghcr.io/librespeed/speedtest@sha256:705744f487048f209b4e389312ea82d4d5c36a76db3e5123b97d4b1649b724b5` |
| Loki | `grafana/loki@sha256:6ca6e2cd3b6f45e0eb298da2920610fde63ecd8ab6c595d9c941c8559d1d9407` |
| Node Exporter | `prom/node-exporter@sha256:1b4e4438faca4dd7e001dd445d161a4a2091b0fededa84093b3a8dfeae1f1be0` |
| Uptime Kuma | `louislam/uptime-kuma@sha256:431fee3be822b04861cf0e35daf4beef6b7cb37391c5f26c3ad6e12ce280fe18` |

The final audit proved `COMPLETE`, `consumed=true`, `immutable=true` and `running=true` for all seven.

### One-shot rule

Consumed normalization contracts are historical evidence and must not be executed again. Post-normalization verification uses independent runtime/steady-state checks rather than rerunning the pre-normalization inspector or executor.

## Formal deferrals

Thirteen running tagged services were reviewed and deliberately left outside the standard normalizer.

| Service | Final Stage 6 status | Reason |
| --- | --- | --- |
| Alloy | `DEFERRED_DOCKER_SOCKET_ACCESS` | Docker socket access is rejected by the standard normalization contract. |
| BirdNET-Go | `DEFERRED_DEVICE_ACCESS` | Explicit `/dev/snd` device access is rejected by the standard contract. |
| cAdvisor | `DEFERRED_PRIVILEGED_RUNTIME` | Privileged/device-backed runtime is outside the standard contract. |
| Cloudflare DDNS | `DEFERRED_UNSUPPORTED_HEALTH_STRATEGY` | No reviewed supported health strategy is available for the service. |
| CrowdSec | `DEFERRED_VOLATILE_FILE_BIND` | Read-only `/var/log/auth.log` file bind changed during the review sample, making SHA-based zero-drift validation unstable. |
| Dozzle | `DEFERRED_DOCKER_SOCKET_ACCESS` | Docker socket access is rejected by the standard normalization contract. |
| DuckDNS | `DEFERRED_UNSUPPORTED_HEALTH_STRATEGY` | Successful log activity exists, but no reviewed HTTP/container-health strategy exists in the normalizer. |
| Jenkins DinD | `DEFERRED_IDENTITY_MISMATCH` | Protected update-control-plane dependency and service/runtime identity mismatch. |
| Nginx Proxy Manager | `DEFERRED_SERVICE_CONTAINER_IDENTITY_MISMATCH` | Compose service `nginx-proxy-manager` and runtime container `npm` cannot satisfy the normalizer's exact service/container/Compose identity rule. |
| Portainer | `DEFERRED_DOCKER_SOCKET_ACCESS` | Docker socket access is outside the standard normalization contract. |
| Portainer Agent | `DEFERRED_DOCKER_SOCKET_ACCESS` | Docker socket access is outside the standard normalization contract. |
| SmokePing | `DEFERRED_NAMED_VOLUME_UNSUPPORTED` | The inspector/executor applies bind `source_kind` checks to every manifest mount, so the named `/config` volume cannot be represented safely. |
| WUD | `DEFERRED_DOCKER_SOCKET_ACCESS` | Docker socket access is outside the standard normalization contract. |

The final audit also proved that none of these thirteen services has an installed Stage 6 normalization manifest or normalization state that could be mistaken for a completed one-shot transaction.

## SmokePing reconciliation

SmokePing was the final closure blocker and required a separate authority reconciliation rather than an image normalization.

At review time:

- the running container declared `linuxserver/smokeping:latest`;
- the running image ID was `sha256:434c548231f753ab58190e1ccd429f4292b4f2271cbe286e38db2de4c5d5d0f4`;
- the local RepoDigest for that running content was `linuxserver/smokeping@sha256:3b0e0d469d711ba694ba102c145b4168361346844453057bb1afa574ab8d4e94`;
- Compose instead declared `linuxserver/smokeping:latest@sha256:a0d1e57744a2217a0fe83b7828cffe2cbce16f44e59c858bead8ff41e7b63581`;
- the `a0d1...` digest was not present locally and did not represent the running same-content target;
- `/data` is a bind mount while `/config` is the named Docker volume `availability_smokeping-config`.

Because the standard inspector/executor cannot safely represent the named volume, SmokePing was formally deferred. The stale/different Compose digest was then reconciled back to the actual deferred runtime declaration:

```yaml
image: linuxserver/smokeping:latest
```

The final availability Compose SHA after reconciliation is:

```text
0dcc0d504a034e0e7a3ad7f25bdc5d6eba38df452c4f65183b9bb8f3e6f30c9d
```

No SmokePing image was pulled, the container was not recreated, its restart count remained `0`, its image ID remained unchanged and `/smokeping/` returned HTTP `200` after reconciliation.

## Other immutable/local workloads

The seven normalization contracts are not the complete set of immutable runtimes. Final coverage also showed existing immutable references for AutoKuma, Dashy, Homepage, the maintenance page and Prometheus. These were already immutable/proven through earlier work and therefore are not counted among the seven one-shot normalization contracts closed here.

Local-build workloads such as BirdNET exporter, CrowdSec exporter, Engineering Portfolio, Projects site and the Jenkins controller remain in their separate local-build/provenance class rather than being counted as external registry-image normalizations.

## Protected control plane

Jenkins and Jenkins DinD remained protected through the normalization and closure work.

Final proof:

```text
jenkins running=true restart=0
jenkins-docker running=true restart=1
```

No Stage 6 closure action recreated either protected component.

## Normalizer constraints confirmed during rollout

Stage 6 production use established several constraints that should remain explicit in future framework work:

1. `service.name`, `service.container` and `service.compose.service` must be identical for the standard normalizer.
2. Privileged runtimes are rejected.
3. Explicit device access is rejected.
4. Docker socket access is rejected, including read-only socket access.
5. Bind sources are restricted to `file` or `directory` and file binds require a SHA-256 invariant.
6. Volatile file binds cannot satisfy stable SHA-based zero-drift checks.
7. The currently reviewed health strategies are HTTP-based (`http` and `container-http`); successful logs alone are not a health contract.
8. Named Docker volumes are not safely supported by the current inspector/executor mount-validation loop.
9. The target immutable image must already be local before arming; deployment-time pulls are not allowed.
10. Normalization is one-shot. A consumed marker is authoritative evidence that the transaction must not be rerun.
11. Pre-normalization inspection is not a reusable post-normalization steady-state contract.
12. Compose declarations alone do not prove runtime immutability; closure checks use `docker inspect .Config.Image`.

## Closure interpretation

Stage 6 closure does **not** mean every service is eligible for the generic normalizer. It means every running TestServer external registry image has been reviewed and placed into an explicit final Stage 6 class:

- immutable and already controlled;
- completed/consumed same-content normalization; or
- formally deferred with a specific framework or runtime reason.

No tagged external service remains unreviewed.

Future work on the deferred classes should be treated as framework extension work, not as unfinished Stage 6 execution. Examples include explicit support for named volumes, alternative non-HTTP health strategies, safe Docker-socket contracts, privileged/device-backed workloads and identity aliasing where Compose service and runtime container names intentionally differ.
