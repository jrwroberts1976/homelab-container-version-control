# Stage 6 `STAGE6_MANIFEST` parameter reference

## Purpose

The generic Jenkins job `stage6-generic-service-update` accepts one operator-supplied value: `STAGE6_MANIFEST`.

The value is the **reviewed manifest filename only**. Do not include `config/services/` and do not enter only the version number.

The reviewed preparation/update workflow should create the versioned manifest automatically under `config/services/`. The operator should then copy/select the generated filename in Jenkins.

## Naming convention

Use:

```text
<service>-<version>.json
```

For services with a host-specific manifest, use:

```text
<service>-<host>-<version>.json
```

Examples currently present in `config/services`:

| Service | Host | `STAGE6_MANIFEST` pattern | Current/example value |
|---|---|---|---|
| Alloy | TestServer | `alloy-X.Y.Z.json` | `alloy-1.19.2.json` |
| Dashy | TestServer | `dashy-X.Y.Z.json` | `dashy-4.6.0.json` |
| Dozzle | TestServer | `dozzle-X.Y.Z.json` | `dozzle-10.8.0.json` |
| Homepage | TestServer | `homepage-X.Y.Z.json` | `homepage-2.1.2.json` |
| Prometheus | TestServer | `prometheus-X.Y.Z.json` | `prometheus-3.13.2.json` |
| Prometheus | ids-01 | `prometheus-ids01-X.Y.Z.json` | `prometheus-ids01-3.13.2.json` |
| Loki | ids-01 | `loki-ids01-X.Y.Z.json` | `loki-ids01-3.7.7.json` |

## Jenkins entry example

For an Alloy update to version `1.19.2`, enter exactly:

```text
alloy-1.19.2.json
```

Do not enter:

```text
1.19.2.json
```

and do not enter:

```text
config/services/alloy-1.19.2.json
```

## Automation requirement

The normal Stage 6 preparation flow should be responsible for:

1. discovering/selecting the target service and approved version;
2. resolving and verifying the immutable candidate image identity;
3. generating the reviewed versioned manifest under `config/services`;
4. validating the manifest against the Stage 6 schema and cross-field security invariants;
5. making the resulting manifest filename available to the operator/Jenkins front end.

The operator should not need to manually construct image digests, Compose paths, authority revisions, health checks, or rollback identities. Those values belong in the generated reviewed manifest.

The long-term Jenkins/front-end experience should therefore reduce to selecting a generated manifest such as `alloy-1.20.0.json`, rather than manually assembling update metadata.
