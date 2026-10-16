# homelab-infrastructure-automation

[Deutsche Version](README.md)

Infrastructure as Code for my Proxmox homelab: Terraform creates VMs, Ansible configures them
idempotently, GitHub Actions checks every push. New VMs ship their auth logs to Splunk via Cribl
on their own and therefore show up in the [SOC portal](https://github.com/QuitScope/homelab-soc-portal)
without any extra step.

![Architecture](docs/img/architecture.en.png)

![lab-iac-01 in the SOC portal](docs/img/soc-portal-hosts.png)

## What's inside

| Area | Content |
|---|---|
| `terraform/` | bpg/proxmox provider, one VM as a linked clone of template 900, 1 vCPU / 1 GB, cloud-init with DHCP and SSH key, fixed MAC |
| `ansible/roles/base` | Hostname, updates + unattended-upgrades, admin user `ops` (key only, sudo), SSH hardening, ufw (deny incoming, SSH rate-limited), fail2ban |
| `ansible/roles/docker` | Docker Engine + Compose plugin from the official Docker repository |
| `ansible/roles/rsyslog_cribl` | `auth,authpriv.* @<VM-IP>:9514`, hooks the VM into the SIEM pipeline |
| `ansible/roles/soc_portal` | Deploys the SOC portal on siem-docker: git checkout via deploy key, `.env` from HashiCorp Vault, `docker compose` (playbook `soc-portal.yml`) |
| `ansible/roles/ara` | [ARA Records Ansible](https://ara.recordsansible.org/) on siem-docker: web dashboard that records every playbook run with tasks, `changed`/`ok` and duration (playbook `ara.yml`) |
| `ansible/roles/vault` + `terraform/vault` | HashiCorp Vault on siem-docker: deploy and unseal with Ansible, configuration (KV v2, audit log, policies, AppRoles) with Terraform |
| `scripts/` | `tf.sh` and `ansible.sh` run both tools in containers, `vm-ip.sh` finds the DHCP address |
| `.github/workflows/ci.yml` | `terraform fmt`/`validate`, `yamllint`, `ansible-lint` (production profile), `--syntax-check` |

## Quick start

Requirements: Docker, Bash (Git Bash on Windows), SSH key `~/.ssh/id_ed25519` with root access to the
Proxmox host. Terraform and Ansible do not need to be installed, both run as containers.

```bash
cp .env.example .env          # add the API token, see docs/operations.en.md
scripts/tf.sh init
scripts/tf.sh apply
export LAB_VM_IP=$(scripts/vm-ip.sh)
scripts/ansible.sh ansible-playbook playbooks/site.yml
```

Clean up: `scripts/tf.sh destroy`.

Deploy the SOC portal (needs `.vault_pass`, see [docs/operations.en.md](docs/operations.en.md#deploying-the-soc-portal)):

```bash
scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml
```

Every run through `scripts/ansible.sh` is recorded in the ARA dashboard at http://<VM-IP>:8091
(see [docs/operations.en.md](docs/operations.en.md#ara-dashboard)).

![ARA: recorded playbook runs](docs/img/ara-playbooks.png)

## Addresses

The docs use placeholders instead of fixed IPs: `<VM-IP>` is the VM `siem-docker` running Splunk, Cribl, the
portal, ARA and Vault, `<LAB-VM-IP>` the test VM created by Terraform, and `<PROXMOX-IP>` the Proxmox host. The
real addresses are in the inventory (`ansible/inventory/hosts.yml`), the role defaults and `.env`.

## Documentation

- [docs/architecture.en.md](docs/architecture.en.md): layout, data flow, design decisions
- [docs/operations.en.md](docs/operations.en.md): token setup, operations, updates, recovery, secrets
- [docs/test-protocol.en.md](docs/test-protocol.en.md): real runs with their results

## Secrets

Secrets are managed centrally in HashiCorp Vault. Terraform fetches the Proxmox API token at runtime through
its own AppRole, as an ephemeral resource so the token never ends up in the state. Ansible reads the portal
configuration through `community.hashi_vault`. Each AppRole can only reach its own secret, and every access is
recorded in the audit log. Vault's own unseal key and root token are protected with Ansible Vault; its
password is kept locally in `.vault_pass`. Details: [docs/operations.en.md](docs/operations.en.md#hashicorp-vault).
