#!/usr/bin/env bash
# Runs an Ansible command in a container. LAB_VM_IP is passed through to the inventory.
# Usage: LAB_VM_IP=1.2.3.4 scripts/ansible.sh ansible-playbook playbooks/site.yml
set -euo pipefail
source "$(dirname "$0")/_docker.sh"
docker build -q -t homelab-ansible "$REPO/ansible" >/dev/null
tty=(); [ -t 0 ] && tty=(-t)
# HashiCorp Vault address and the "ansible" AppRole from .env, for community.hashi_vault lookups.
vault_env=()
if [ -f "$REPO_ROOT/.env" ]; then
  while IFS= read -r line; do vault_env+=(-e "${line%$'\r'}"); done \
    < <(grep -E '^(VAULT_ADDR|ANSIBLE_HASHI_VAULT_ROLE_ID|ANSIBLE_HASHI_VAULT_SECRET_ID)=' "$REPO_ROOT/.env" || true)
  vault_env+=(-e ANSIBLE_HASHI_VAULT_AUTH_METHOD=approle)
fi
# Bind-mounted Windows files show up as 0777 and ssh refuses such keys, so copy them with proper modes.
# ANSIBLE_CONFIG is set explicitly because Ansible ignores ansible.cfg in world-writable directories.
exec docker run --rm -i "${tty[@]}" \
  -v "$REPO:/work" -v "$SSH_DIR:/ssh:ro" -w /work/ansible \
  -e LAB_VM_IP="${LAB_VM_IP:-}" -e ANSIBLE_CONFIG=/work/ansible/ansible.cfg \
  -e ARA_API_SERVER="${ARA_API_SERVER-http://192.168.178.91:8091}" "${vault_env[@]}" \
  homelab-ansible sh -c '
    install -d -m700 /root/.ssh && install -m600 /ssh/id_ed25519 /ssh/id_ed25519.pub /root/.ssh/
    # Vault password file (git-ignored). Ansible would try to execute it with the 0777 mount mode.
    if [ -f /work/.vault_pass ]; then
      install -m600 /work/.vault_pass /root/.vault_pass && export ANSIBLE_VAULT_PASSWORD_FILE=/root/.vault_pass
    fi
    # Record every run in ARA; ARA_API_SERVER= (empty) turns recording off.
    if [ -n "$ARA_API_SERVER" ]; then
      export ARA_API_CLIENT=http ANSIBLE_CALLBACK_PLUGINS="$(python3 -m ara.setup.callback_plugins)"
    fi
    exec "$@"' -- "$@"
