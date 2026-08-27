# Stage 6 Dashy human-approval pipeline

Status: source-only design under review

Date: 2026-08-27

## Purpose

Generalise the proven Stage 5 human-approved one-shot deployment ordering onto the Stage 6 generic service framework, using Dashy `4.5.13 -> 4.6.0` as the first generic deployment pilot.

This change is deliberately source-only. It does not create a Jenkins job, create or modify any Jenkins credential, arm an update, create Stage 6 transaction state, recreate a container, pull an image, or perform a deployment.

The Jenkins Stage 6 executor credential boundary has now been independently proven by the canonicalized ping smoke before this follow-up source change.

## Reviewed identities

Service: `dashy`

Update ID:

`stage6-dashy-40e3b27369002d4bce12cdffd5136b05924e1a7ea4e0d971a890557045fb1d59`

Rollback:

- version: `4.5.13`
- immutable ref: `lissy93/dashy@sha256:8bef3c7bf607de54bbcd4bc3733c481b06c0053b9d12ea781e3bd29457b8b6a4`
- local ARM64 image ID: `sha256:417b161fc4c22a4dc6759110f6794c880c72a91e4b8c64e1d653605c2726b3ee`

Candidate:

- version: `4.6.0`
- immutable ref: `lissy93/dashy@sha256:40e3b27369002d4bce12cdffd5136b05924e1a7ea4e0d971a890557045fb1d59`
- local ARM64 image ID/config digest: `sha256:f7c93e5961154c8ee4a4bce7f4448d30b9ee46def5ed8eb3ebef3d111370de99`
- ARM64 platform manifest: `sha256:cb6a9839b13481e8f96104482fed6e30f7aba186fa636a43a14cb2cb31b72e92`
- OCI revision: `d707730b454a35c52187e824879386e1eb30f869`

Docker Compose authority:

- docker-env revision: `f659d556365e47288fc99aeb74a1a5a78c2f1852`
- Compose SHA-256: `54d18c2d78fb80d04649271d5422cb886777f9b8ed5d4ef41d50217462876010`

## Proven prerequisite

The Stage 6 Jenkins inspector smoke is complete.

Jenkins build #2 proved that the Jenkins-managed `homelab-stage6-testserver-inspector` credential can use the pinned TestServer host key, reach the forced-command inspector account, receive `pong`, run `inspect dashy`, and validate/archive the exact generic inspection artifact.

At completion:

- inspector credential: present;
- executor credential: absent;
- Stage 6 state root: absent;
- update armed: false;
- candidate consumed: false;
- Dashy unchanged and healthy;
- Jenkins unchanged;
- Jenkins-DinD unchanged.

## Proven executor credential boundary

The restricted executor credential is now proven through Jenkins.

Ping-smoke build #3:

- checked out merged source `37c2bfd4fb039818a33478f86861750f9788cc65`;
- accepted exactly one leading blank line added by Jenkins credential binding;
- canonicalized into a temporary mode-0600 key;
- required exact executor fingerprint `SHA256:A9VBS2vpB6+OvA62GhWXIMTgsNc2DdqOUX4eqLR58gY`;
- passed only the normalized key to SSH;
- received exact forced-command result `pong`;
- archived only safe key-validation metadata;
- left no normalized private-key file behind;
- performed no mutation.

The same narrow canonicalization and fingerprint gate is therefore required for every post-approval executor binding in the real Dashy pipeline.

## Pipeline ordering

`Jenkinsfile.stage6-dashy-human-approval` uses this exact high-level order:

1. checkout source;
2. prove Stage 6 helper/manifest sources have not drifted from the reviewed Stage 6 core commit and verify the pinned TestServer host key;
3. bind only the inspector credential;
4. run `inspect dashy`;
5. assert exact rollback/candidate/authority/runtime identities and `deployment.allowed=false`;
6. write the critical pre-approval snapshot;
7. require Jenkins human approval from `james`;
8. bind only the inspector credential again;
9. run a second `inspect dashy`;
10. compare the complete critical snapshot, including all-container state, and require zero drift;
11. only after approval and zero-drift proof, bind the executor credential, canonicalize at most one leading blank line, require the exact executor fingerprint, and run `ping`;
12. repeat the same fail-closed key canonicalization/fingerprint gate for each subsequent executor binding, then arm the exact reviewed update with `arm dashy`;
13. deploy with `deploy dashy`;
14. if deployment fails, attempt only the reviewed `rollback dashy` path;
15. after successful deployment or successful rollback, run `disarm dashy`;
16. archive all Stage 6 Dashy evidence and report the terminal pipeline result.

The executor credential is not visible to the pipeline before the human-approval and second-inspection/zero-drift gates have completed. After that boundary, each executor binding uses a fresh temporary normalized key and the raw Jenkins-bound key is never passed to SSH.

## SSH boundary

Every Jenkins SSH call uses:

- `-n` and `</dev/null` stdin isolation;
- `IdentitiesOnly=yes`;
- `BatchMode=yes`;
- `PasswordAuthentication=no`;
- `KbdInteractiveAuthentication=no`;
- `StrictHostKeyChecking=yes`;
- the pinned TestServer known-hosts file.

The inspector credential may send only `inspect dashy`.

Before every executor SSH call, the pipeline accepts only either a clean OpenSSH private-key envelope or exactly one leading blank line before the exact BEGIN marker, rejects carriage returns, requires exact BEGIN/END markers and final newline, requires local `ssh-keygen` parsing, and requires fingerprint `SHA256:A9VBS2vpB6+OvA62GhWXIMTgsNc2DdqOUX4eqLR58gY`. Only the temporary normalized key is passed to SSH and it is removed by trap.

The executor path used by this pipeline consists only of:

- `ping`;
- `arm dashy`;
- `deploy dashy`;
- `rollback dashy`;
- `disarm dashy`.

The Jenkinsfile contains no local Docker invocation, no local `sudo`, and no direct call to a Stage 6 host helper. All execution authority remains behind the already-installed forced-command executor SSH boundary.

## Host-side independent controls

The pipeline does not trust Jenkins alone to authorize deployment.

On TestServer, the Stage 6 transition/execution helpers independently enforce the service manifest, secure root-owned installed context, exact update ID, local immutable rollback/candidate identities, clean Git authority, exact Compose hash, runtime shape, bind-mount content, health, unrelated-container invariance, one-shot consumed marker, and fixed no-pull service-scoped Compose recreation.

`arm` runs a fresh generic pre-approval inspection before creating the enable marker.

`deploy` revalidates authority and local images and runs a fresh pre-deployment inspection before consuming the update ID and recreating only the reviewed service.

`rollback` is available only after the reviewed update ID has been consumed and only when the exact candidate is current.

`disarm` requires a terminal healthy candidate or rollback state and removes the enable marker while preserving the consumed marker.

## Failure semantics

A local executor credential failure is distinguished from a remote deployment failure.

If the deploy-stage username assertion fails (`97`) or executor-key normalization/fingerprint validation fails (`96`), the deploy SSH command has not been invoked. The candidate is therefore unconsumed. Jenkins fails closed and does **not** invoke rollback. Because the update may already be armed, that state is left for controlled recovery rather than guessing at a remote action.

If the deploy command is actually attempted and fails, Jenkins does not improvise a Docker recovery action. It invokes only the reviewed rollback command.

If the reviewed rollback also fails, the pipeline fails and deliberately leaves the update armed/consumed for controlled manual recovery. No automatic disarm occurs in that unresolved state.

If rollback succeeds, the pipeline disarms but records an overall failure because the candidate deployment itself failed.

If deployment succeeds, the pipeline disarms and reports success.

## Source guard

Run:

`bash scripts/validate-stage6-dashy-human-approval.sh`

The guard verifies:

- stage ordering;
- exactly one human approval restricted to `james`;
- inspector credential references occur only for the two inspection stages;
- the first executor credential reference occurs only after the zero-drift stage;
- all five executor bindings use the pinned normalizer and exact executor fingerprint;
- raw Jenkins-bound executor keys are never passed to SSH;
- the normalizer accepts at most one leading blank line and rejects broader repair;
- exactly seven SSH calls with stdin isolation and fail-closed SSH options;
- remote command surface is exactly two inspections plus executor ping/arm/deploy/rollback/disarm;
- CPS-safe JSON parsing;
- exact immutable Dashy/update/authority identities;
- rollback/disarm failure handling;
- no local Docker, local sudo, or direct host-helper bypass.

## Activation sequence after merge

Do not create the executor credential as part of this source PR.

After the source PR is validated and merged:

1. verify the merged source and Jenkins Pipeline-from-SCM job configuration before any live run;
2. verify the existing Jenkins executor credential metadata and the already-proven canonicalized ping-smoke evidence;
3. verify the private-key/public-key/authorized-key fingerprint chain without displaying secret material;
4. take a fresh container and Stage 6 state baseline;
5. run the full pipeline once and stop at the human approval gate;
6. inspect the first read-only artifact before granting human approval;
7. grant approval only if the exact reviewed state is still acceptable;
8. validate the second inspection, executor binding, arm/deploy/rollback/disarm artifacts, runtime identities, health and one-shot terminal state.

Until those activation steps are deliberately performed, this source change cannot deploy anything by itself.
