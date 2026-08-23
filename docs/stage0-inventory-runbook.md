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
| `drift` | `no`, `yes-reference`, `yes-image`, `not-assessed-local-build` or `not-locally-resolvable` |

## Interpretation limits

- The collector deliberately does not pull images. A remote registry may have moved a floating tag even when the local result says `drift=no`.
- `yes-reference` means the current Compose reference differs from the reference used to create the container; this can produce an unintended downgrade on recreation.
- `yes-image` means the reference is unchanged but resolves locally to a different image ID, commonly after a mutable tag moved.
- `not-assessed-local-build` means the service uses `build:` and requires source/build provenance checks.
- `not-locally-resolvable` means the desired reference could not be resolved from the host's local image store.
- Compose interpolation can fail when its required environment file is unavailable. In that case the collector falls back to the container's creation-time image reference and records `compose:runtime-creation`.
- A version tag without a digest is classified as `version-tagged`; it is more controlled than a floating channel, but it is not immutable.

## Acceptance checks

Before Stage 0 is complete:

1. Every running container on both hosts appears exactly once.
2. Every critical service has a readable Compose source.
3. Every `unmanaged`, `floating`, `yes-reference`, `yes-image`, `not-assessed-local-build` and `not-locally-resolvable` row is reviewed.
4. Known exceptions are recorded in `policy/exceptions.yml`.
5. Secret delivery methods are inventoried separately without collecting values.

## Local-build provenance

Run this after the image inventory identifies `not-assessed-local-build` services:

```bash
sudo bash scripts/local-build-provenance.sh TestServer \\
  | sudo tee /var/tmp/local-build-provenance-testserver.tsv

column -t -s $'\\t' \\
  /var/tmp/local-build-provenance-testserver.tsv
```

The collector processes running Compose services with a `build:` declaration. It records the resolved build context and Dockerfile, Dockerfile SHA-256, build-argument names, source Git root and commit, scoped dirty state, running image ID and OCI provenance labels. It never reports build-argument values or container environment values.

Assessment values:

| Assessment | Meaning |
|---|---|
| `revision-match` | The image embeds an OCI revision matching the current source commit |
| `revision-mismatch` | The embedded image revision differs from the current source commit |
| `unverified-no-revision-label` | Source is clean, but the image does not embed a revision |
| `source-dirty` | Files under the build context differ from the recorded Git commit |
| `no-git-source` | The resolved build context is not inside a Git worktree |

A clean source tree without an embedded revision is useful evidence, but does not prove which commit produced the running image. Stage 1 should add OCI revision/source labels and deterministic build metadata before automated local-image deployment.
