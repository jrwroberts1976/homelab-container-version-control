# Stage 6 generic Jenkins service-update pipeline

## Goal

Use one Jenkins approval pipeline for every Stage 6 eligible registry-image service. Adding a service/update must require reviewed data in a service manifest, not a new service-specific Jenkinsfile.

## Pipeline

`Jenkinsfile.stage6-service-update` accepts one parameter:

- `STAGE6_MANIFEST`: a reviewed manifest filename under `config/services`.

The filename must match the pipeline allow-list and cannot contain a path separator or traversal sequence. The pipeline resolves it only beneath the fixed `config/services` directory, runs the Stage 6 schema/cross-field validator, and then derives the service, update ID, authority revision, Compose SHA, rollback identity, candidate identity, platform and health contract from the manifest.

No image reference, digest, Compose path or service name is accepted as an independent Jenkins execution argument.

## Preserved security ordering

The generic pipeline keeps the proven Stage 6 sequence:

1. checkout reviewed source;
2. validate the selected manifest and generic framework source;
3. run the first read-only inspection with only the inspector credential;
4. prove the installed manifest and inspector match reviewed source;
5. archive the full critical state;
6. require explicit human approval;
7. run a second read-only inspection;
8. require exact zero drift;
9. only then bind the executor credential;
10. arm the exact manifest-derived update ID;
11. deploy the exact manifest candidate through the root-owned generic helper;
12. use only the reviewed rollback path on an eligible deployment failure;
13. disarm after a proven terminal result;
14. archive the evidence.

The executor credential remains unavailable before the zero-drift gate.

## Health is manifest-driven

The pipeline does not assume one service health mechanism.

- `docker-health` manifests compare the inspection/execution result with the manifest expected health state.
- `http` manifests compare with the Stage 6 `http-<status>` result derived from the manifest expected HTTP status.

This allows the same pipeline to handle different eligible service health contracts without service-specific code.

## Source guard

`scripts/validate-stage6-generic-jenkins-pipeline.py` rejects service/image hard-coding, unsafe manifest/service selectors, missing approval/zero-drift gates, premature executor credentials, direct Docker/sudo/shell authority, raw executor-key use and weakened execution-result assertions.

Run the full source review with:

```bash
bash scripts/validate-stage6-generic-jenkins-service-update.sh
```

## Existing service-specific Jenkinsfiles

Existing Dashy-specific Stage 6 Jenkinsfiles remain historical pilot/smoke evidence. They are not the template for onboarding additional services. New eligible services should use the generic pipeline plus a reviewed manifest.
