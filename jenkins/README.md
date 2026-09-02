# Jenkins job control

This directory documents reproducible Jenkins job control that is part of the container-version-control operating model.

## TestServer controller

Current reviewed controller facts on TestServer (2 September 2026):

- container: `jenkins`
- container port: `8080/tcp`
- host binding: `8096/tcp`
- local controller endpoint: `http://127.0.0.1:8096/`
- Jenkins security: enabled
- security realm: `hudson.security.HudsonPrivateSecurityRealm`
- authorization strategy: `hudson.security.FullControlOnceLoggedInAuthorizationStrategy`

The Jenkins Java runtime is `/opt/java/openjdk/bin/java`; it is not available on the shell `PATH` by default.

Do not store Jenkins usernames, passwords, API tokens, private SSH keys or other credentials in this repository.

## Stage 6 generic job

Stage 6 reuses the existing Jenkins job:

```text
stage6-generic-service-update
```

Pipeline-from-SCM definition:

```text
repository: https://github.com/jrwroberts1976/homelab-container-version-control.git
branch:     */main
scriptPath: Jenkinsfile.stage6-service-update
```

`VERIFY_CLOSED` is an action of this existing generic Stage 6 job, not a separate Jenkins job. The generic pipeline must route actions fail-closed:

```text
UPDATE        -> existing reviewed update/deployment path
VERIFY_CLOSED -> reviewed catalogue/steady-state read-only verification path
```

The `VERIFY_CLOSED` path must not acquire a candidate, bind the deployment executor, arm an update, run Compose lifecycle commands, recreate/restart the target, or clear consumed deployment evidence.

Expected successful verification result:

```text
SUCCESS_VERIFIED_CLOSED
```

The standalone `Jenkinsfile.stage6-verify-closed` currently captures the reviewed non-mutating verification contract and is implementation/reference material while that action is folded into `Jenkinsfile.stage6-service-update`.
