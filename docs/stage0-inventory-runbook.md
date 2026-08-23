# Stage 0 Inventory Runbook

This collector is read-only. It does not pull images, restart containers, alter Compose files or expose environment-variable values.

## Requirements

- Docker Engine and Docker Compose v2
- Bash
- jq
- permission to inspect Docker containers and images
- read access to the Compose files referenced by Docker's Compose labels

## Run on TestServer

```bash
git clone https://github.com/jrwroberts1976/homelab-container-version-control.git
cd homelab-container-version-control
git switch stage0/container-inventory-collector

sudo bash scripts/inventory-images.sh TestServer \
  | sudo tee /var/tmp/container-inventory-testserver.tsv
```

## Run on ids-01

```bash
git clone https://github.com/jrwroberts1976/homelab-container-version-control.git
cd homelab-container-version-control
git switch stage0/container-inventory-collector

sudo bash scripts/inventory-images.sh ids-01 \
  | sudo tee /var/tmp/container-inventory-ids-01.tsv
```

If the repository already exists, use `git fetch origin` followed by
`git switch stage0/container-inventory-collector`.

## Quick summary

Run this after creating either TSV:

```bash
awk -F '\t' '
  NR == 1 { next }
  {
    total++
    management[$10]++
    policy[$11]++
    drift[$12]++
  }
  END {
    print "Containers:", total

    print ""
    print "Management:"
    for (key in management) {
      print " ", key, management[key]
    }

    print ""
    print "Version policy:"
    for (key in policy) {
      print " ", key, policy[key]
    }

    print ""
    print "Drift:"
    for (key in drift) {
      print " ", key, drift[key]
    }
  }
' /var/tmp/container-inventory-ids-01.tsv
```

Change the filename to inspect the TestServer result.

## Column meanings

| Column | Meaning |
|---|---|
| `desired_image` | Image resolved from the current Compose configuration when possible; otherwise the image reference used when the container was created |
| `creation_image` | Image reference stored in the container configuration |
| `running_image_id` | Immutable Docker image ID used by the container |
| `running_repo_digests` | Registry digests known for the running image |
| `management` | Whether the container is Compose-managed and whether the current Compose declaration could be resolved |
| `version_policy` | `floating`, `version-tagged` or `digest-pinned` |
| `drift` | Whether the locally resolved desired reference points at a different image ID from the running container |

## Interpretation limits

- The collector deliberately does not pull images. A remote registry may have moved a floating tag even when the local result says `drift=no`.
- `not-locally-resolvable` means the desired reference could not be resolved from the host's local image store.
- Compose interpolation can fail when its required environment file is unavailable. In that case the collector falls back to the container's creation-time image reference and records `compose:runtime-creation`.
- A version tag without a digest is classified as `version-tagged`; it is more controlled than a floating channel, but it is not immutable.

## Acceptance checks

Before Stage 0 is complete:

1. Every running container on both hosts appears exactly once.
2. Every critical service has a readable Compose source.
3. Every `unmanaged`, `floating`, `drift=yes` and `unknown` row is reviewed.
4. Known exceptions are recorded in `policy/exceptions.yml`.
5. Secret delivery methods are inventoried separately without collecting values.
