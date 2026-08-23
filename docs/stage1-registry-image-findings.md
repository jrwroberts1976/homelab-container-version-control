# Stage 1 Registry-Image Policy Findings

Assessment date: **23 August 2026**

## Scope

The Stage 1 policy assessment was validated against all 61 in-scope containers:

- TestServer: 30 containers;
- ids-01: 31 containers.

The assessment is read-only and uses the Stage 0 inventory as its input. It does not contact registries, pull images, modify Compose or restart containers.

## Initial assessment

| Host | Digest compliant | Version-tag compliant | Exception required | Local-build unverified | Drift | Unmanaged |
|---|---:|---:|---:|---:|---:|---:|
| TestServer | 1 | 23 | 1 | 5 | 0 | 0 |
| ids-01 | 0 | 11 | 20 | 0 | 0 | 0 |

### TestServer

The single floating registry reference was `linuxserver/smokeping`.

The five local builds were deliberately classified separately:

- `projects-jrwroberts-co-uk`;
- `crowdsec-exporter`;
- `birdnet-exporter`;
- `engineering-portfolio`;
- `jenkins`.

### ids-01

All 20 floating references belonged to the coordinated `greenbone-community-edition` Compose project. No unrelated floating reference, drift or unmanaged container was found.

## Greenbone policy decision

Exception `EX-2026-001` was approved on 23 August 2026, with review due 30 September 2026.

The project-wide exception recognises Greenbone Community Edition's coordinated rolling-release model. Independently pinning its service and feed-data containers could break the vendor-supported stack lifecycle.

Compensating controls include:

- review the current vendor `compose.yaml`;
- treat the complete project as one elevated change;
- record all pre-change and candidate digests;
- require backup and Compose validation;
- verify login, scanner readiness, container health and feed state;
- retain exact rollback images;
- prohibit direct runtime deployment by WUD or similar tools.

## SmokePing remediation

The TestServer declaration was changed from:

```yaml
image: linuxserver/smokeping
```

to the exact verified running artifact:

```yaml
image: linuxserver/smokeping:latest@sha256:a0d1e57744a2217a0fe83b7828cffe2cbce16f44e59c858bead8ff41e7b63581
```

Host validation proved:

- candidate Compose was valid;
- desired and running repo digests matched;
- the existing container ID, image ID, creation timestamp and running state were unchanged.

No image was pulled and no container was recreated or restarted.

## Digest comparison regression

The first post-merge inventory incorrectly reported SmokePing as `yes-reference` because its container creation reference did not include the digest.

The collector was corrected to canonicalise a desired `repository:tag@digest` reference to `repository@digest` and compare it with the running image's repo digests.

Regression validation passed:

| Classification | Count |
|---|---:|
| `compliant-digest` | 2 |
| `compliant-version-tag` | 23 |
| `local-build-unverified` | 5 |
| Drift | 0 |
| Unmanaged | 0 |
| Unapproved floating reference | 0 |

## Registry-image policy outcome

The registry-image portion of Stage 1 is operationally reconciled:

- zero registry-image drift;
- zero unmanaged containers;
- zero unapproved floating references;
- Greenbone covered by a time-bounded, reviewed exception;
- SmokePing fixed to its verified runtime digest;
- downgrade and rollback policies recorded in Git.

## Remaining Stage 1 workload

The remaining policy work is local-build provenance.

Each local build needs:

- authoritative source root and Dockerfile;
- clean source revision;
- OCI `org.opencontainers.image.revision` label;
- build timestamp;
- reproducible build-argument names;
- retained previous image ID;
- documented handling where source is dirty or not associated with Git.

`birdnet-exporter` is the first pilot because it is Compose-managed, source-controlled, stateless and already has a verified Prometheus health path.
