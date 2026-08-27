# Stage 6 Dashy executor ping smoke

## Purpose

Prove that Jenkins can bind and use the restricted Stage 6 executor SSH credential before the full Dashy human-approval job is allowed to run.

## Scope

The smoke test is intentionally non-mutating. It:

1. checks out reviewed source;
2. verifies the Stage 6 executor forced-command wrapper has not changed since the reviewed Stage 6 human-approval pipeline baseline;
3. verifies the pinned TestServer host key;
4. binds only `homelab-stage6-testserver-executor`;
5. requires username `homelab-stage6-executor`;
6. sends exactly one SSH command: `ping`;
7. requires the exact response `pong`;
8. archives the ping and validation evidence.

## Explicit exclusions

The pipeline does not:

- bind the inspector credential;
- run `inspect dashy`;
- run `arm dashy`;
- run `deploy dashy`;
- run `rollback dashy`;
- run `disarm dashy`;
- run Docker or sudo locally in Jenkins;
- invoke Stage 6 helper paths directly;
- create or consume Stage 6 transaction state;
- mutate Dashy, Jenkins, Jenkins-DinD, or any other container.

The full `stage6-dashy-human-approval` job must remain at zero builds until this ping-only smoke has passed and post-smoke host safety state is independently verified.
