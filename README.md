# homelab-infrastructure-automation

*[English version](README.en.md)*

Infrastructure as Code für mein Proxmox-Homelab: Terraform erzeugt VMs, Ansible konfiguriert sie
idempotent, GitHub Actions prüft jeden Push. Neue VMs schicken ihre Auth-Logs automatisch über
Cribl an Splunk und erscheinen dadurch ohne weiteren Schritt im
[SOC-Portal](https://github.com/QuitScope/homelab-soc-portal).

![Architektur](docs/img/architecture.png)

![lab-iac-01 im SOC-Portal](docs/img/soc-portal-hosts.png)

## Was drin ist

| Bereich | Inhalt |
|---|---|
| `terraform/` | bpg/proxmox-Provider, eine VM als Linked Clone aus Template 900, 1 vCPU / 1 GB, cloud-init mit DHCP und SSH-Key, feste MAC |
| `ansible/roles/base` | Hostname, Updates + unattended-upgrades, Admin-User `ops` (nur Key, sudo), SSH-Härtung, ufw (deny incoming, SSH rate-limited), fail2ban |
| `ansible/roles/docker` | Docker Engine + Compose-Plugin aus dem offiziellen Docker-Repo |
| `ansible/roles/rsyslog_cribl` | `auth,authpriv.* @192.168.178.91:9514`, Anbindung an die SIEM-Pipeline |
| `ansible/roles/soc_portal` | Deployt das SOC-Portal auf siem-docker: Git-Checkout per Deploy-Key, `.env` aus HashiCorp Vault, `docker compose` (Playbook `soc-portal.yml`) |
| `ansible/roles/ara` | [ARA Records Ansible](https://ara.recordsansible.org/) auf siem-docker: Web-Dashboard, das jeden Playbook-Lauf mit Tasks, `changed`/`ok` und Dauer aufzeichnet (Playbook `ara.yml`) |
| `ansible/roles/vault` + `terraform/vault` | HashiCorp Vault auf siem-docker: Deploy und Unseal per Ansible, Konfiguration (KV v2, Audit-Log, Policies, AppRoles) per Terraform |
| `scripts/` | `tf.sh` und `ansible.sh` führen beide Tools in Containern aus, `vm-ip.sh` findet die DHCP-Adresse |
| `.github/workflows/ci.yml` | `terraform fmt`/`validate`, `yamllint`, `ansible-lint` (Profil production), `--syntax-check` |

## Schnellstart

Voraussetzungen: Docker, Bash (unter Windows Git Bash), SSH-Key `~/.ssh/id_ed25519` mit Root-Zugriff
auf den Proxmox-Host. Terraform und Ansible müssen nicht installiert sein, beide laufen als Container.

```bash
cp .env.example .env          # API-Token eintragen, siehe docs/operations.md
scripts/tf.sh init
scripts/tf.sh apply
export LAB_VM_IP=$(scripts/vm-ip.sh)
scripts/ansible.sh ansible-playbook playbooks/site.yml
```

Aufräumen: `scripts/tf.sh destroy`.

SOC-Portal deployen (braucht `.vault_pass`, siehe [docs/operations.md](docs/operations.md#soc-portal-deployen)):

```bash
scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml
```

Jeder Lauf über `scripts/ansible.sh` landet automatisch im ARA-Dashboard unter http://192.168.178.91:8091
(siehe [docs/operations.md](docs/operations.md#ara-dashboard)).

![ARA: aufgezeichnete Playbook-Läufe](docs/img/ara-playbooks.png)

## Doku

- [docs/architecture.md](docs/architecture.md): Aufbau, Datenfluss, Designentscheidungen
- [docs/operations.md](docs/operations.md): Token anlegen, Betrieb, Updates, Wiederherstellung, Secrets
- [docs/test-protocol.md](docs/test-protocol.md): echte Läufe mit Ergebnissen

## Secrets

Im Repo liegt kein Secret im Klartext. Laufzeit-Secrets liegen in HashiCorp Vault: Terraform holt den
Proxmox-API-Token per AppRole als ephemeral resource (nicht im State), Ansible die Portal-Konfiguration per
`community.hashi_vault`. Jede AppRole darf nur ihr eigenes Secret lesen, jeder Zugriff steht im Audit-Log.
Ansible Vault schützt nur noch Unseal-Key und Root-Token von Vault; dessen Passwort steht in `.vault_pass`
(git-ignoriert). Details: [docs/operations.md](docs/operations.md#hashicorp-vault).
