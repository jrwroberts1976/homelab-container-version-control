# K3s Stage 1 Compliance Monitoring

## Scope

This extension applies the project’s Git-controlled desired-state and runtime-compliance model to the single-node K3s platform on `k3s-node-01`.

The authoritative Kubernetes source is [jrwroberts1976/kubernetes-homelab](https://github.com/jrwroberts1976/kubernetes-homelab). This repository records the cross-estate governance milestone and its relationship to the Docker programme.

## Completed controls

| Control | Verified result |
|---|---|
| K3s installation | `v1.36.2+k3s1` pinned; official ARM64 checksum matched |
| Kubeconfig access | root-owned mode `0600`; persistent next-start setting |
| whoami | immutable declared digest equals running digest; 2/2 Ready |
| Homelab Defender | approved tag-plus-digest equals running digest; 1/1 Ready |
| MetalLB | chart `0.16.1`; address configuration matches Git |
| kube-state-metrics | chart `8.1.3`; reconciled service address `192.168.2.211` |
| Active inventory | 16 active container instances |
| Policy | 3 digest-pinned; 13 explicit version tags; 0 floating |
| Drift | 0 pinned-digest mismatches |
| Ownership | Helm, K3s-packaged or kubectl; 0 unknown |
| Readiness | all active instances ready |

## Automation

The Kubernetes repository contains:

- `scripts/inventory-k3s-images.sh` — read-only workload, pod and runtime-digest correlation;
- `scripts/export-k3s-image-metrics.sh` — atomic Prometheus textfile generation;
- `systemd/k3s-image-compliance.service` — hardened root oneshot;
- `systemd/k3s-image-compliance.timer` — persistent five-minute schedule.

The exporter writes `/home/james/node-exporter/textfile/k3s_image_compliance.prom`. Node exporter `1.12.1` exposes it on `k3s-node-01:9100`.

## Central monitoring

Prometheus `3.13.1` runs on `ids-01` and scrapes `192.168.2.195:9100` under the `linux-hosts` job.

Final validation showed:

- target health `up`;
- `k3s_image_inventory_success 1`;
- 3 `compliant-digest` instances;
- 13 `compliant-version-tag` instances;
- aggregate digest drift `0`;
- no unready series;
- inventory age within the seven-minute freshness gate;
- `node_textfile_scrape_error 0`.

## Alerting decision

Grafana on `ids-01` is the notification control plane. Prometheus has no Alertmanager configuration. The existing `jrwroberts1976/grafana-alerting` repository contains email contact points, notification policies and API-managed rule definitions.

The local alerting checkout has unrelated modified and untracked files, so no K3s alert was added directly to that working tree. The next controlled change will create separate Grafana rules for:

1. missing or failed inventory;
2. stale inventory timestamp;
3. pinned digest drift;
4. unready workload containers;
5. noncompliant image policy.

## Boundary

This milestone adds read-only assessment and observability. It does not introduce automated Kubernetes mutation, automatic image updates, admission enforcement or GitOps reconciliation.
