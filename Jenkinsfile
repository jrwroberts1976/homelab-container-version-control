pipeline {
  agent any

  options {
    skipDefaultCheckout(true)
    disableConcurrentBuilds()
    timestamps()
  }

  parameters {
    string(
      name: 'CONTAINER',
      defaultValue: 'dozzle',
      description: 'TestServer container to validate through the Stage 4 read-only runner'
    )
  }

  environment {
    STAGE4_HOST = '172.18.0.1'
    STAGE4_KNOWN_HOSTS = '/var/jenkins_home/.ssh/stage4-testserver-known_hosts'
    STAGE4_SCHEMA_BLOB = '7420557838813710378b468034db33f1fc9c0b25'
    STAGE4_WRAPPER_SHA256 = '091626e74ae811ff3a76b236ff57056b34efd38d421cc76bfe566097c9b967c7'
    STAGE4_HOSTKEY_FINGERPRINT = 'SHA256:PEDpP7QlmSztJSIYHzZ+YuIT7XurmpeWp85wRnlfZuk'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Stage 4 preflight') {
      steps {
        script {
          if (!(params.CONTAINER ==~ /^[A-Za-z0-9][A-Za-z0-9_.-]*$/)) {
            error('Invalid Stage 4 container name')
          }
        }

        sh '''
          set -eu

          test -f config/deployment-plan.schema.json
          test -f ops/testserver/homelab-stage4-validation-ssh
          test -s "$STAGE4_KNOWN_HOSTS"

          ACTUAL_SCHEMA_BLOB="$(
            git hash-object config/deployment-plan.schema.json
          )"

          if [ "$ACTUAL_SCHEMA_BLOB" != "$STAGE4_SCHEMA_BLOB" ]; then
            echo "ERROR: deployment-plan schema is not the reviewed Stage 4 blob" >&2
            exit 2
          fi

          ACTUAL_WRAPPER_SHA256="$(
            sha256sum ops/testserver/homelab-stage4-validation-ssh |
            awk '{print $1}'
          )"

          if [ "$ACTUAL_WRAPPER_SHA256" != "$STAGE4_WRAPPER_SHA256" ]; then
            echo "ERROR: Stage 4 wrapper does not match reviewed source" >&2
            exit 2
          fi

          if ! ssh-keygen \
            -lf "$STAGE4_KNOWN_HOSTS" \
            -E sha256 |
            grep -F "$STAGE4_HOSTKEY_FINGERPRINT" \
            >/dev/null
          then
            echo "ERROR: pinned TestServer SSH host key does not match" >&2
            exit 2
          fi

          if grep -nE \
            'docker (pull|run|rm|restart|exec|tag|push|build)|docker compose (up|down|pull|push|build)|git (commit|push|reset|checkout|switch|merge|rebase)' \
            ops/testserver/homelab-stage4-validation-ssh
          then
            echo "ERROR: Stage 4 wrapper contains a mutation primitive" >&2
            exit 2
          fi

          echo "PASS: Stage 4 reviewed inputs and SSH identity are pinned"
        '''
      }
    }

    stage('Generate deployment plan') {
      steps {
        withCredentials([
          sshUserPrivateKey(
            credentialsId: 'homelab-stage4-testserver-validator',
            keyFileVariable: 'STAGE4_SSH_KEY',
            usernameVariable: 'STAGE4_SSH_USER'
          )
        ]) {
          sh '''
            set -eu
            set +x

            install -d -m 0700 artifacts
            rm -f artifacts/deployment-plan.json

            ssh \
              -i "$STAGE4_SSH_KEY" \
              -o IdentitiesOnly=yes \
              -o BatchMode=yes \
              -o ConnectTimeout=10 \
              -o StrictHostKeyChecking=yes \
              -o UserKnownHostsFile="$STAGE4_KNOWN_HOSTS" \
              "$STAGE4_SSH_USER@$STAGE4_HOST" \
              "plan $CONTAINER" \
              > artifacts/deployment-plan.json

            test -s artifacts/deployment-plan.json

            echo "PASS: Stage 4 deployment-plan artifact received"
          '''
        }
      }
    }

    stage('Assert read-only contract') {
      steps {
        script {
          String rawPlan = readFile(
            file: 'artifacts/deployment-plan.json'
          )

          def plan = new groovy.json.JsonSlurperClassic()
            .parseText(rawPlan)

          if (plan.schema_version != 1) {
            error('Stage 4 artifact schema_version is not 1')
          }

          if (plan.mode != 'read-only') {
            error('Stage 4 artifact mode is not read-only')
          }

          if (plan.artifact != 'deployment-plan') {
            error('Unexpected Stage 4 artifact type')
          }

          if (plan.service == null) {
            error('Stage 4 service object missing')
          }

          if (plan.service.container != params.CONTAINER) {
            error('Stage 4 artifact container does not match request')
          }

          if (plan.service.host != 'TestServer') {
            error('Stage 4 artifact came from an unexpected host')
          }

          if (plan.deployment == null) {
            error('Stage 4 deployment object missing')
          }

          if (plan.deployment.allowed != false) {
            error('Stage 4 artifact unexpectedly permits deployment')
          }

          if (plan.deployment.performed != false) {
            error('Stage 4 artifact reports deployment was performed')
          }

          if (plan.gates == null) {
            error('Stage 4 gate results missing')
          }

          [
            'ownership',
            'comparison',
            'architecture',
            'security',
            'secret_readiness',
            'local_build_provenance'
          ].each { gateName ->
            if (plan.gates[gateName] == null) {
              error("Stage 4 gate missing: ${gateName}")
            }

            if (plan.gates[gateName].result == null) {
              error("Stage 4 gate result missing: ${gateName}")
            }
          }

          if (plan.decision == null) {
            error('Stage 4 decision object missing')
          }

          def allowedDecisions = [
            'no-change',
            'ready-for-review',
            'rebuild-required',
            'blocked'
          ]

          if (!allowedDecisions.contains(plan.decision.result)) {
            error('Unsupported Stage 4 decision result')
          }

          def actionByDecision = [
            'no-change'        : 'none',
            'ready-for-review' : 'deploy-registry-image',
            'rebuild-required' : 'rebuild-local-image',
            'blocked'          : 'manual-review'
          ]

          if (
            plan.decision.proposed_action
              != actionByDecision[plan.decision.result]
          ) {
            error(
              'Stage 4 decision and proposed action are inconsistent'
            )
          }

          if (plan.decision.result == 'blocked') {
            error(
              'Stage 4 validation is blocked; manual review required'
            )
          }

          echo(
            "Stage 4 result: " +
            "${plan.service.container} -> " +
            "${plan.decision.result} / " +
            "${plan.decision.proposed_action}"
          )

          echo(
            'PASS: Jenkins independently confirmed ' +
            'deployment.allowed=false and deployment.performed=false'
          )
        }
      }
    }

    stage('Stop before deployment') {
      steps {
        echo(
          'Stage 4 complete: validation artifact produced. ' +
          'No deployment authority exists in this pipeline.'
        )
      }
    }
  }

  post {
    always {
      archiveArtifacts(
        artifacts: 'artifacts/deployment-plan.json',
        allowEmptyArchive: true,
        fingerprint: true
      )
    }
  }
}
