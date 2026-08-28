# Stage 6 executor activation boundary

Status: generic manifest-driven activation contract under review

Date: 2026-08-28

## Purpose

Define one reusable host-side executor transport for every reviewed Stage 6 registry-image service without adding service-specific wrapper branches or sudo rules.

The executor still becomes reachable from Jenkins only after human approval and post-approval zero-drift inspection. Making the transport generic does not weaken that ordering.

## Dedicated executor identity

The TestServer identity remains `homelab-stage6-executor`.

Required account properties:

- dedicated local account and primary group only;
- locked password;
- no Docker group membership;
- no supplementary administrative groups;
- no interactive password login;
- no general sudo authority;
- no ownership or write access to Stage 6 manifests, helpers, authority checkout, state root, sudoers or authorized-key policy files.

The preferred home is `/var/lib/homelab-stage6-executor`. SSH policy material remains root-owned, using the proven root:root `0755` home, root:homelab-stage6-executor `0750` `.ssh`, and root:homelab-stage6-executor `0640` `authorized_keys` model.

## SSH boundary

The authorized-key template remains:

```text
restrict,from="172.30.255.250",command="/usr/local/sbin/homelab-stage6-executor-ssh" ssh-ed25519 __PUBLIC_KEY__ homelab-stage6-testserver-executor
```

The private key must never be committed to Git.

The forced-command wrapper accepts only:

```text
ping
arm <service>
deploy <service>
rollback <service>
disarm <service>
```

`<service>` must match:

```text
^[a-z0-9][a-z0-9-]*$
```

The wrapper derives both action and service from `SSH_ORIGINAL_COMMAND`, validates the service before sudo, and routes only:

```text
arm/disarm       -> /usr/local/libexec/homelab-stage6-transition
deploy/rollback  -> /usr/local/libexec/homelab-stage6-execute
```

Extra arguments, paths, image names, digests, shell syntax and malformed service identifiers fail closed.

The root-owned transition and execution helpers independently require exactly two arguments, repeat the service-name validation, load `/etc/homelab-stage6/services/<service>.json`, validate it, and require the manifest service/container identity to match the requested service.

## Sudo boundary

The executor sudoers fragment is constant regardless of how many services are onboarded:

```text
homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-transition ^arm [a-z0-9][a-z0-9-]*$
homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-transition ^disarm [a-z0-9][a-z0-9-]*$
homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-execute ^deploy [a-z0-9][a-z0-9-]*$
homelab-stage6-executor ALL=(root) NOPASSWD: /usr/local/libexec/homelab-stage6-execute ^rollback [a-z0-9][a-z0-9-]*$
```

These are anchored sudoers argument regular expressions, not shell wildcards. The sudo surface therefore remains limited to four fixed Stage 6 actions and one constrained service identifier.

The fragment must be root:root `0440` and pass `visudo -cf` before activation.

There is no caller-supplied image argument, digest argument, path argument, Docker command, Compose command, Git command, shell, editor, file-copy utility or `NOPASSWD: ALL` authority.

## Manifest is the service allow-list

A valid service identifier does not by itself make a service deployable.

For every action, the root-owned helper requires a reviewed manifest at:

```text
/etc/homelab-stage6/services/<service>.json
```

The manifest pins the only acceptable service/container identity, Compose authority, candidate and rollback immutable references, runtime shape, bind-mount hashes, health contract and protected containers.

As a result, adding an eligible service requires a reviewed manifest and evidence, but does not require new SSH wrapper code or sudo rules.

## Jenkins ordering remains mandatory

For any reviewed `<service>`, Jenkins must preserve:

1. bind only the read-only inspector credential;
2. run pre-approval `inspect <service>`;
3. present exact current/candidate/rollback/Git/runtime identities;
4. require explicit human approval;
5. repeat `inspect <service>`;
6. compare the critical identities and complete container baseline;
7. fail closed on any drift;
8. only then bind the executor credential;
9. invoke `arm <service>`;
10. invoke `deploy <service>`;
11. verify the execution result and runtime invariants;
12. invoke `rollback <service>` only when reviewed rollback preconditions are satisfied;
13. invoke `disarm <service>` after a proven terminal state.

The executor credential must never be present before approval and zero-drift proof complete.

## Source guard

`scripts/validate-stage6-executor-activation.py` and `scripts/validate-stage6-execution-boundary.py` prove that:

- wrappers do not hard-code Dashy, Prometheus or any other service;
- only the four reviewed actions exist;
- the service identifier is validated before sudo dispatch;
- sudoers contains only the four anchored action/service regex rules;
- the underlying root helpers retain their own exact argument counts, service validation and manifest gates;
- no shell, Docker, Compose, Git or arbitrary command authority is introduced;
- the source-restricted forced-command authorized-key contract remains unchanged.

## Live activation requirements

Before installing this refactor on TestServer:

1. run all Stage 6 source guards;
2. verify the host sudo version supports argument regular expressions;
3. stage both sudoers fragments and validate them with `visudo -cf` before replacing live files;
4. install wrappers and sudoers with reviewed root ownership/modes;
5. prove `ping` works for both identities;
6. prove malformed and unknown services fail;
7. prove inspector access remains read-only;
8. prove no state, arm marker, consumed marker or container mutation occurs during transport validation.

Installing this transport refactor alone does not arm or deploy any service.
