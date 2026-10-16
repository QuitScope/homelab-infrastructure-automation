# Betrieb

*[English version](operations.en.md)*

## Einmalige Einrichtung

### Proxmox-Rolle, Benutzer und Token

Rolle und Benutzer lassen sich per SSH auf dem Host anlegen. Es wird kein Passwort gesetzt, der
Benutzer meldet sich nur über Tokens an:

```bash
pveum role add TerraformProv -privs "VM.Allocate VM.Clone VM.Audit VM.PowerMgmt VM.GuestAgent.Audit VM.Config.CDROM VM.Config.CPU VM.Config.Cloudinit VM.Config.Disk VM.Config.HWType VM.Config.Memory VM.Config.Network VM.Config.Options Datastore.AllocateSpace Datastore.Audit SDN.Use Sys.Audit"
pveum user add terraform@pve --comment "Terraform IaC"
```

Den Token legst du in der UI an, damit das Secret nur dort angezeigt wird: **Datacenter → Permissions →
API Tokens → Add**, User `terraform@pve`, Token ID `iac`. Danach bekommt der Token die Rolle direkt:

```bash
pveum acl modify / -token 'terraform@pve!iac' -role TerraformProv
```

> Ein Token mit *Privilege Separation* hat keine Rechte, solange keine ACL direkt auf den Token
> zeigt. Die Rechte des Users erbt er dann nicht. Die Folge ist `403 Permission check failed (/vms/900,
> VM.Clone)` (siehe Testprotokoll).

Danach das Secret einmalig in `.env` eintragen (Vorlage: `.env.example`), `scripts/vault-seed.sh` legt
es in HashiCorp Vault ab (siehe [HashiCorp Vault](#hashicorp-vault)):

```
PROXMOX_VE_API_TOKEN=terraform@pve!iac=<secret>
```

### Werkzeuge

```bash
scripts/tf.sh init        # lädt den bpg/proxmox-Provider gemäß .terraform.lock.hcl
scripts/ansible.sh true   # baut das Image homelab-ansible (ansible-core, Collections)
```

## Täglicher Betrieb

| Aufgabe | Befehl |
|---|---|
| Änderungen ansehen | `scripts/tf.sh plan` |
| VM anlegen/anpassen | `scripts/tf.sh apply` |
| IP der VM | `scripts/vm-ip.sh` (oder `scripts/vm-ip.sh <MAC>`) |
| VM konfigurieren | `LAB_VM_IP=<ip> scripts/ansible.sh ansible-playbook playbooks/site.yml` |
| Nur prüfen, nichts ändern | `... ansible-playbook playbooks/site.yml --check --diff` |
| Lints lokal wie in der CI | `scripts/ansible.sh sh -c 'cd /work && yamllint --strict . && cd ansible && ansible-lint'` |
| VM entfernen | `scripts/tf.sh destroy` |

Nach `destroy` und erneutem `apply` hat die VM neue Host-Keys. Die Ansible-Container starten jedes Mal
mit leerer `known_hosts`, dort ist das kein Problem. Für eigene SSH-Sitzungen zuerst
`ssh-keygen -R <ip>` ausführen. Die FritzBox vergibt trotz fester MAC nicht zwingend dieselbe IP,
deshalb die IP nach jedem `apply` neu mit `vm-ip.sh` ermitteln.

## SOC-Portal deployen

```bash
scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml                                 # Stand von main
scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml -e soc_portal_version=<commit> # fester Commit / Rollback
```

Die Rolle `soc_portal` checkt das Repo `QuitScope/homelab-soc-portal` nach `/opt/homelab-soc-portal` aus,
legt die `.env` aus HashiCorp Vault (`homelab/soc-portal`) ab und startet das Compose-Projekt
`homelab-soc-portal`. Neu gebaut wird nur, wenn sich der Checkout geändert hat. Die SQLite-Datenbank liegt
im Volume `homelab-soc-portal_portal-data` und überlebt jedes Redeployment.

Einmalige Voraussetzungen:

1. HashiCorp Vault läuft und `.env` enthält `VAULT_ADDR` und die AppRole `ansible`
   (`ANSIBLE_HASHI_VAULT_ROLE_ID`/`_SECRET_ID`); `scripts/ansible.sh` reicht sie an Ansible weiter.
2. Deploy-Key: Die Rolle erzeugt beim ersten Lauf `/root/.ssh/homelab-soc-portal-deploy` auf siem-docker.
   Der öffentliche Schlüssel muss einmal als read-only Deploy-Key im Portal-Repo hinterlegt werden:
   ```bash
   ssh root@192.168.178.91 cat /root/.ssh/homelab-soc-portal-deploy.pub > deploy.pub
   gh repo deploy-key add deploy.pub --repo QuitScope/homelab-soc-portal --title "siem-docker (Ansible, read-only)"
   ```

Portal-Konfiguration ändern:

Neue `.env` nach `homelab/soc-portal` (Feld `env`) schreiben, siehe [HashiCorp Vault](#hashicorp-vault), dann:

```bash
scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml     # erzeugt den Container mit neuer .env neu
```

Die Umstellung vom alten, per `git archive` kopierten Deployment passiert einmalig automatisch: Das alte
Verzeichnis wird nach `/opt/homelab-soc-portal.pre-ansible` verschoben. Nach einer Prüfung kann es gelöscht werden.

## ARA-Dashboard

[ARA Records Ansible](https://ara.recordsansible.org/) zeichnet jeden Playbook-Lauf auf: Hosts, Tasks,
`changed`/`ok`/`failed`, Diffs, Dauer und die verwendeten Playbook-Dateien. Weboberfläche und API:
http://192.168.178.91:8091 (nur im LAN).

```bash
scripts/ansible.sh ansible-playbook playbooks/ara.yml           # Server deployen/aktualisieren
ARA_API_SERVER= scripts/ansible.sh ansible-playbook ...         # einzelnen Lauf nicht aufzeichnen
```

- Server: Rolle `ara`, Compose-Projekt `ara` in `/opt/ara` auf siem-docker. Das Image ist per Digest
  gepinnt (ARA 1.8.0), weil upstream nur rollende Tags veröffentlicht. SQLite und die beim ersten Start
  erzeugte `settings.yaml` liegen im Volume `ara_ara-data`.
- Client: `scripts/ansible.sh` setzt das ARA-Callback-Plugin und `ARA_API_SERVER`. Ist der Server
  nicht erreichbar, läuft das Playbook trotzdem durch; ARA gibt dann nur `[WARNING]: Callback dispatch ... failed` aus (getestet, Exit-Code 0).
- Was nicht gespeichert wird: Ergebnisse von Tasks mit `no_log` (z. B. die Portal-`.env`) erscheinen
  nur als „censored“. `extra_vars` und Vault-Passwortdateien ignoriert ARA standardmäßig.
- Grenze: Das Dashboard hat keine Anmeldung und ist nur an die LAN-Adresse gebunden. Wer im LAN ist,
  kann Läufe lesen und schreiben. Nächster Schritt wäre `ARA_READ_LOGIN_REQUIRED`/`ARA_WRITE_LOGIN_REQUIRED`
  mit einem Benutzer, dessen Passwort im Vault liegt.
- Aufräumen: `ssh root@192.168.178.91 docker exec ara-ara-1 ara playbook prune --days 30 --confirm`.

## HashiCorp Vault

Vault (2.2.0, Raft-Storage) läuft auf siem-docker unter http://192.168.178.91:8200 (nur LAN, HTTP).
Er hält die Secrets, die Terraform und Ansible zur Laufzeit holen:

| Pfad (KV v2, Mount `homelab`) | Feld | Leser (AppRole → Policy) |
|---|---|---|
| `homelab/proxmox` | `api_token` | `terraform` → `terraform-proxmox` |
| `homelab/soc-portal` | `env` (komplette Portal-`.env`) | `ansible` → `ansible-soc-portal` |

Jede AppRole darf genau ihr Secret lesen, Tokens leben 15 Minuten. Terraform liest den Proxmox-Token als
ephemeral resource, er landet also nicht im State. Alle Zugriffe stehen im Audit-Log
(`/vault/logs/audit.log` im Container).

Aufbau in vier Schritten (einmalig, so auch passiert, siehe Testprotokoll):

```bash
scripts/ansible.sh ansible-playbook playbooks/vault.yml                       # 1. Server deployen
scripts/vault-init.sh                                                          # 2. init, Unseal-Key + Root-Token → Ansible Vault
scripts/ansible.sh ansible-playbook playbooks/vault.yml                       #    entsiegeln
TF_DIR=terraform/vault scripts/tf.sh init
TF_DIR=terraform/vault scripts/vault-admin.sh scripts/tf.sh apply              # 3. Mount, Audit, Policies, AppRoles
scripts/vault-admin.sh scripts/vault-seed.sh                                   # 4. Secrets + AppRole-IDs in .env
```

`vault-seed.sh` liest den Proxmox-Token aus `.env` und die Portal-`.env` von siem-docker und schreibt
beide per Pipe nach Vault. Danach kann `PROXMOX_VE_API_TOKEN` aus `.env` entfernt werden.

Betrieb:

| Aufgabe | Vorgehen |
|---|---|
| Nach Neustart von siem-docker oder Vault | Vault startet versiegelt: `scripts/ansible.sh ansible-playbook playbooks/vault.yml` entsiegelt ihn |
| Portal-Konfiguration ändern | Neue `.env` per `vault kv put` bzw. erneut `vault-seed.sh`, dann `playbooks/soc-portal.yml` |
| Proxmox-Token rotieren | Neuen Token anlegen (siehe oben), Wert in `homelab/proxmox` schreiben. `.env` bleibt unverändert |
| AppRole-Secret-ID rotieren | `TF_DIR=terraform/vault scripts/vault-admin.sh scripts/tf.sh apply -replace='vault_approle_auth_backend_role_secret_id.consumer["ansible"]'`, dann `vault-seed.sh` |
| Wer hat was gelesen? | `ssh root@192.168.178.91 docker exec vault-vault-1 cat /vault/logs/audit.log` (JSON, Werte als HMAC) |
| Backup | `docker exec vault-vault-1 vault operator raft snapshot save /vault/file/backup.snap` (mit Root-Token) |

Wichtig: Unseal-Key und Root-Token liegen nur in `playbooks/files/siem-docker/vault-init.json.vault`,
verschlüsselt mit dem Passwort aus `.vault_pass`. Geht `.vault_pass` verloren, lässt sich Vault nach dem
nächsten Neustart nicht mehr entsiegeln und die Daten sind weg. `.vault_pass` gehört deshalb zusätzlich in
einen Passwortmanager.

## Updates

| Was | Vorgehen |
|---|---|
| Pakete auf den VMs | Playbook erneut laufen lassen (Rolle `base` macht `apt upgrade safe`). Zusätzlich installieren `unattended-upgrades` täglich Sicherheitsupdates |
| Terraform-Provider | `version` in `terraform/versions.tf` anheben, `scripts/tf.sh init -upgrade`, `plan` prüfen, Lock-Datei committen |
| Terraform selbst | Image-Tag in `scripts/tf.sh` und `terraform_version` in `.github/workflows/ci.yml` gemeinsam ändern |
| Ansible / Lints / Collections | Versionen in `ansible/requirements.txt` und `ansible/requirements.yml` anheben; das Image wird beim nächsten `scripts/ansible.sh` neu gebaut, die CI nutzt dieselben Dateien |
| Template 900 | Neues Template bauen, `template_id` setzen, `apply` ersetzt die VM. Danach Playbook laufen lassen |

Jede Änderung geht über einen Push, die CI muss grün sein, bevor sie gegen das Lab läuft.

## Wiederherstellung

| Lage | Vorgehen |
|---|---|
| VM kaputt oder falsch konfiguriert | `scripts/tf.sh apply -replace=proxmox_virtual_environment_vm.lab`, danach Playbook. Die VM hat keine eigenen Daten, alles entsteht aus dem Repo neu (getestet, siehe Testprotokoll) |
| Konfigurationsdrift | Playbook erneut laufen lassen, es setzt den Soll-Zustand. `--check --diff` zeigt vorher, was abweicht |
| SSH-Härtung sperrt aus | Proxmox-Konsole (`qm terminal 220`, serielle Konsole) oder VM ersetzen. `sshd -t` validiert jede Änderung vor dem Schreiben, das macht diesen Fall unwahrscheinlich |
| Terraform-State verloren | `scripts/tf.sh import proxmox_virtual_environment_vm.lab pve/220`, dann `plan` |
| Token kompromittiert | In der UI löschen (oder `pveum user token remove terraform@pve iac`), neuen anlegen, ACL setzen, Wert in Vault `homelab/proxmox` ersetzen |
| Portal-Update fehlerhaft | Mit `-e soc_portal_version=<letzter guter Commit>` erneut deployen; die Datenbank im Volume bleibt unberührt |
| Vault versiegelt | `scripts/ansible.sh ansible-playbook playbooks/vault.yml` (getestet nach `docker restart`) |
| Vault-Daten verloren | Raft-Snapshot zurückspielen (`vault operator raft snapshot restore`) oder neu aufbauen: `terraform/vault` anwenden und `vault-seed.sh`, die Quellen der Secrets (Proxmox, Portal-`.env` auf siem-docker) bleiben erhalten |
| `.vault_pass` verloren | Unseal-Key nicht mehr lesbar. Solange Vault entsiegelt läuft: Snapshot ziehen, neu initialisieren. Sonst Vault neu aufbauen (Zeile darüber) |
| Template 900 weg | Linked Clones hängen an der Basis-Disk des Templates; Proxmox verhindert das Löschen, solange Clones existieren. Template aus Ubuntu-Cloud-Image neu bauen und `template_id` anpassen |

## Secrets

| Secret | Ablage |
|---|---|
| Proxmox-API-Token | HashiCorp Vault `homelab/proxmox`, zur Laufzeit von Terraform gelesen (ephemeral, nicht im State) |
| Portal-Konfiguration (Splunk-/Cribl-Zugang, Session-Secret, Admin-Hash) | HashiCorp Vault `homelab/soc-portal`, zur Laufzeit von Ansible gelesen |
| AppRole-Role-/Secret-IDs | `.env` (git-ignoriert); Secret-IDs zusätzlich im lokalen State von `terraform/vault` |
| Unseal-Key und Root-Token | `playbooks/files/siem-docker/vault-init.json.vault`, Ansible Vault AES256, im Repo |
| Ansible-Vault-Passwort | `.vault_pass` (git-ignoriert), im Container mit Modus 0600 |
| SSH-Key des Admin-PCs | bleibt in `~/.ssh`, nur lesend in den Container gemountet |
| Deploy-Key für das Portal-Repo | nur auf siem-docker, read-only und auf ein Repo beschränkt |

Ansible Vault sichert nur noch das Bootstrap-Material, das Vault selbst zum Start braucht. Alles andere
liegt in HashiCorp Vault.

Bewusste Grenzen und nächste Schritte:

- Vault spricht HTTP im LAN. Nächster Schritt: TLS-Listener mit eigener CA; die Clients brauchen dann
  `VAULT_CACERT`.
- Ein Unseal-Key-Share (1 von 1) statt z. B. 3 von 5, und kein Auto-Unseal.
- Der Root-Token wird für die Administration (`terraform/vault`, `vault-seed.sh`) genutzt. In Produktion
  würde man ihn nach dem Aufbau widerrufen und bei Bedarf mit `vault operator generate-root` neu erzeugen.
- CI: GitHub-OIDC (JWT-Auth) statt gespeicherter Secret-IDs, sobald Pipelines gegen das Lab laufen.
- SSH-Secrets-Engine für kurzlebige SSH-Zertifikate statt statischer Keys.
