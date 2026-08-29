#!/bin/bash
set -u
set -o pipefail

ROOT="$(
    cd "$(dirname "$0")/.." &&
    pwd
)"

TRANSITION="$ROOT/ops/testserver/homelab-stage6-normalization-transition"

fail() {
    echo "FAIL: $1"
    exit 2
}

[ -f "$TRANSITION" ] ||
    fail "normalization transition source missing"

bash -n "$TRANSITION" ||
    fail "normalization transition shell syntax invalid"

for REQUIRED in \
    'normalization transition requires root' \
    'normalization transition is not running from reviewed installed path' \
    'normalization pre-approval inspection failed' \
    'pre-approval inspection artifact failed approval gate' \
    'zero_drift_baseline_sha256' \
    'post_approval_reinspection_required' \
    'normalization is already armed' \
    'normalization ID is already consumed' \
    'stage6-image-normalization-approval' \
    'human_approval_present:true' \
    'normalization_authority:true' \
    'normalization_authority:false' \
    'container_mutation_performed:false' \
    'normalization_performed:false' \
    'deployment_pull_allowed == false' \
    'one_shot_required == true'
do
    grep -Fq "$REQUIRED" "$TRANSITION" ||
        fail "required transition safety gate missing: $REQUIRED"
done

echo "PASS: approval and zero-drift gates present"

if grep -Eiq \
    '^[[:space:]]*docker([[:space:]]|$)|[;&|][[:space:]]*docker([[:space:]]|$)' \
    "$TRANSITION"
then
    fail "transition helper contains direct Docker command access"
fi

if grep -Eiq \
    'docker[[:space:]]+compose|compose[[:space:]]+(up|down|pull|build|restart|stop|start|rm)' \
    "$TRANSITION"
then
    fail "transition helper contains Compose mutation surface"
fi

if grep -Eiq \
    '(^|[[:space:]])(ssh|scp|rsync)([[:space:]]|$)' \
    "$TRANSITION"
then
    fail "transition helper contains remote execution surface"
fi

if grep -Eiq \
    '(^|[[:space:]])git([[:space:]]|$)' \
    "$TRANSITION"
then
    fail "transition helper contains Git command surface"
fi

if grep -Eiq \
    'executor|homelab-stage6-normalization-execute' \
    "$TRANSITION"
then
    fail "transition helper prematurely depends on executor"
fi

echo "PASS: no Docker, Compose, SSH, Git or executor surface"

for COMMAND in \
    'install \' \
    'mktemp \' \
    'chown root:root "$tmp"' \
    'chmod 0600 "$tmp"' \
    'mv -f \' \
    'rm -f -- "$APPROVAL_FILE"'
do
    grep -Fq "$COMMAND" "$TRANSITION" ||
        fail "reviewed approval-state mutation missing: $COMMAND"
done

echo "PASS: filesystem mutation limited to approval-state lifecycle"

grep -Fq \
    'STATE_ROOT="/var/lib/homelab-stage6/image-normalization-state"' \
    "$TRANSITION" ||
    fail "fixed normalization state root missing"

grep -Fq \
    'APPROVAL_FILE="${SERVICE_STATE_DIR}/approval.json"' \
    "$TRANSITION" ||
    fail "fixed approval file missing"

grep -Fq \
    'CONSUMED_FILE="${SERVICE_STATE_DIR}/${NORMALIZATION_ID}.consumed"' \
    "$TRANSITION" ||
    fail "one-shot consumed identity missing"

echo "PASS: fixed one-shot state paths present"

for FIELD in \
    'runtime.container_id' \
    'runtime.restart_count' \
    'runtime.networks' \
    'runtime.published_ports' \
    'runtime.mounts' \
    'health.resolved_url' \
    'protected_containers'
do
    grep -Fq "$FIELD" "$TRANSITION" ||
        fail "zero-drift baseline field missing: $FIELD"
done

echo "PASS: zero-drift baseline covers runtime and protected state"

echo "PASS: normalization transition source regression"
