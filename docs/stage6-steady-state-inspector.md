# Stage 6 steady-state inspector

## Purpose

The existing Stage 6 inspector is a transition inspector. Before human approval it proves that a workload is still running the reviewed rollback image and that the reviewed candidate is locally available. After a successful deployment that contract is intentionally consumed and must not be reused as a steady-state desired-state assertion.

This component introduces a separate read-only steady-state inspection contract.

## Separation of concerns

A transition manifest records a reviewed change from rollback identity to candidate identity. It remains historical execution and rollback evidence after consumption.

A steady-state manifest records only the current desired state. For registry-image services the configured runtime image must be an exact immutable `repository@sha256:...` reference. There is no rollback or candidate concept in the steady-state manifest.

## Initial backend scope

Phase 2A is intentionally narrow:

- host: TestServer;
- runtime: Docker Compose;
- image class: registry image;
- architecture: linux/arm64 or linux/amd64 in the schema, with the first manifest on linux/arm64;
- risk class: low or medium;
- devices: forbidden;
- Docker socket: forbidden by default, with the already-reviewed exact read-only socket exception allowed only for medium-risk services;
- health: Docker health or a fixed local HTTP endpoint;
- mutation: none.

The first manifest is Homepage 2.1.2.

## Homepage desired state

The steady-state Homepage manifest records:

- docker-env authority revision `788b302c67fc21618d471ab7951ebf379d2a5593`;
- dashboards Compose SHA-256 `9a1295c5c7848c578a9b339411b02b2320cb7bd4b78764fce1d6b661fe97287f`;
- desired version `2.1.2`;
- exact configured/immutable image `ghcr.io/gethomepage/homepage@sha256:da9dca9ec258c628146bed1445da0853f2b88f0b10bafd97c091de807c363d60`;
- local image ID `sha256:3a2b25796deabbf5c77ed9efcca2e1cb270b64f00c70ca87cf797640e26705fe`;
- exact network, mount, restart, user and Docker-socket shape;
- Docker health `healthy`;
- Jenkins and Jenkins-DinD presence as protected control-plane evidence.

The old v2.0.0 rollback identity remains only in the consumed transition manifest and is not copied into the steady-state desired-state contract.

## Inspector behaviour

`homelab-stage6-steady-inspect SERVICE` accepts one reviewed service name only. All paths, image identities, authority values and runtime expectations come from a root-owned manifest under `/etc/homelab-stage6/steady-state`.

The inspector verifies:

1. root-owned, non-writable installed inspector, validator and service manifest;
2. exact clean docker-env authority revision;
3. authority and live Compose SHA-256 identity;
4. read-only Compose rendering with the exact desired immutable image override;
5. exact local desired image ID, platform and RepoDigest;
6. running container image/configured-image identity;
7. exact networks, published ports and bind-mount shape;
8. bind source type/hash rules;
9. user, privileged, read-only-rootfs, restart and device rules;
10. exact Docker-socket policy;
11. health contract;
12. protected control-plane container presence.

Success emits `service-steady-state-inspection` JSON with:

- `mode=read-only`;
- `mutation_allowed=false`;
- `deployment.allowed=false`;
- `deployment.performed=false`;
- `result=steady-state-verified`.

## Explicitly absent

The inspector contains no image pull, image build, container lifecycle mutation, Compose lifecycle mutation, Git mutation, sudo, arbitrary shell execution, Stage 6 arm, deploy, rollback or disarm capability.

## Next steps

1. validate this source from an exact clean TestServer checkout;
2. review and merge the source-only PR;
3. install the exact merged validator, inspector and Homepage manifest as root-owned files on TestServer;
4. run the first live read-only Homepage steady-state inspection;
5. only after that proof, update the estate catalogue and connect `homelab-update --action inspect` to the steady-state backend;
6. then resolve Prometheus authority roll-forward and onboard the same steady-state model.
