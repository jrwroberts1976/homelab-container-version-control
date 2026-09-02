# Jenkins job control

This directory stores reproducible Jenkins job definitions that are part of the container-version-control operating model.

## TestServer controller

Current reviewed controller facts on TestServer (2 September 2026):

- container: `jenkins`
- container port: `8080/tcp`
- host binding: `8096/tcp`
- local controller endpoint: `http://127.0.0.1:8096/`
- Jenkins security: enabled
- security realm: `hudson.security.HudsonPrivateSecurityRealm`
- authorization strategy: `hudson.security.FullControlOnceLoggedInAuthorizationStrategy`

The Jenkins container currently does not expose `java` on its shell `PATH`, so job provisioning should not assume that the Jenkins CLI can be executed from inside the controller container. Use an authenticated controller API/web flow or other reviewed host-side provisioning mechanism.

Do not store Jenkins usernames, passwords, API tokens, private SSH keys or other credentials in this repository.

## Stage 6 VERIFY_CLOSED

Git-owned job definition:

```text
jenkins/jobs/stage6-verify-closed.xml
```

Expected Jenkins job name:

```text
stage6-verify-closed
```

The job is a Pipeline-from-SCM definition using:

```text
repository: https://github.com/jrwroberts1976/homelab-container-version-control.git
branch:     */main
scriptPath: Jenkinsfile.stage6-verify-closed
parameter:  STAGE6_SERVICE
```

The default qualification target is `dozzle`.

This job is intentionally separate from `stage6-generic-service-update`. Its contract is read-only verification of an already-closed service. It must not acquire a candidate, bind the deployment executor, arm an update, run Compose lifecycle commands, recreate/restart the target, or clear consumed deployment evidence.

Expected successful result:

```text
SUCCESS_VERIFIED_CLOSED
```

Before provisioning or replacing the live job, compare the reviewed XML with the active Jenkins job configuration and preserve the existing credential store. The job definition contains no credentials; the Pipeline binds the reviewed inspector credential by Jenkins credential ID at runtime.
