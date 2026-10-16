#!/usr/bin/env bash
# Runs Terraform in a container, so nothing has to be installed locally.
# Usage: scripts/tf.sh init | plan | apply | destroy | output ...
#        TF_DIR=terraform/vault scripts/vault-admin.sh scripts/tf.sh apply   (Vault configuration)
set -euo pipefail
source "$(dirname "$0")/_docker.sh"
[ -f "$REPO_ROOT/.env" ] || { echo "Missing .env, copy .env.example first." >&2; exit 1; }
tty=(); [ -t 0 ] && tty=(-t)
# VAULT_TOKEN is only set by scripts/vault-admin.sh; "-e NAME" passes it through only when it exists.
exec docker run --rm -i "${tty[@]}" \
  -v "$REPO:/work" -v "$SSH_DIR:/ssh:ro" -w "/work/${TF_DIR:-terraform}" \
  --env-file "$REPO/.env" -e TF_VAR_ssh_public_key_path=/ssh/id_ed25519.pub -e VAULT_TOKEN \
  hashicorp/terraform:1.16.6 "$@"
