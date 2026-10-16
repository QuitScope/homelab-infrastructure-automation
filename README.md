# homelab-infrastructure-automation

[English version](README.en.md)

Meine Proxmox-VMs habe ich lange in der Weboberfläche zusammengeklickt und danach per SSH von Hand
eingerichtet. Spätestens beim dritten Mal wusste ich nicht mehr genau, welche Pakete, Firewall-Regeln und
rsyslog-Zeilen auf welcher Maschine gelandet sind. Mit diesem Repo baue ich das Homelab jetzt reproduzierbar:
Terraform legt die VMs an, Ansible richtet sie ein, und GitHub Actions prüft jeden Push.

Mein Lieblingseffekt dabei: Jede neue VM schickt ihre Auth-Logs automatisch an mein
[Homelab-SIEM](https://github.com/QuitScope/homelab-siem) und taucht ohne weiteren Handgriff im
[SOC-Portal](https://github.com/QuitScope/homelab-soc-portal) auf.

![Architektur](docs/img/architecture.png)

![lab-iac-01 im SOC-Portal](docs/img/soc-portal-hosts.png)

## Was drin ist

| Bereich | Inhalt |
|---|---|
| `terraform/` | eine VM als Linked Clone aus meinem Ubuntu-Template, 1 vCPU / 1 GB, cloud-init mit DHCP und SSH-Key |
| `ansible/roles/base` | Admin-User mit Key, SSH-Härtung, ufw, fail2ban, automatische Sicherheitsupdates |
| `ansible/roles/docker` | Docker Engine und Compose-Plugin aus dem offiziellen Repo |
| `ansible/roles/rsyslog_cribl` | schickt `auth,authpriv` an Cribl auf `<VM-IP>:9514` |
| `ansible/roles/soc_portal` | rollt das SOC-Portal auf siem-docker aus, die `.env` kommt aus HashiCorp Vault |
| `ansible/roles/ara` | ARA als Dashboard, das jeden Ansible-Lauf aufzeichnet |
| `ansible/roles/vault` + `terraform/vault` | HashiCorp Vault: Betrieb per Ansible, Konfiguration per Terraform |
| `scripts/` | Wrapper, die Terraform und Ansible in Containern starten, und `vm-ip.sh` |
| `.github/workflows/ci.yml` | `terraform fmt`/`validate`, `yamllint`, `ansible-lint`, `--syntax-check` |

## Warum so und nicht anders

- **Terraform und Ansible im Container:** Mein Arbeitsrechner läuft unter Windows, Ansible gibt es dort nicht
  nativ. Statt WSL einzurichten, laufen beide Werkzeuge über `scripts/tf.sh` und `scripts/ansible.sh` in Docker,
  mit denselben Versionen wie in der CI.
- **Kleine Linked Clones:** Der Proxmox-Host hat vier Kerne und kaum noch freien RAM. Eine Test-VM bekommt
  deshalb 1 vCPU und 1 GB und teilt sich die Basis-Disk mit dem Template. Nach dem kompletten Ansible-Lauf
  belegt sie rund 3 GB statt 32 GB.
- **Monitoring ab dem ersten Boot:** Die Rolle `rsyslog_cribl` gehört zum Standard-Playbook. Eine VM, die nicht
  im SIEM auftaucht, gilt für mich als nicht fertig eingerichtet.
- **ARA statt AWX:** AWX bräuchte Kubernetes und mehrere GB RAM, die der Host nicht hat. ARA ist ein einzelner
  Container und zeigt trotzdem jeden Lauf mit allen Tasks, `changed`/`ok` und Dauer.
- **HashiCorp Vault für Secrets:** Ich wollte Zugangsdaten nicht in `.env`-Dateien auf mehreren Rechnern
  verteilen. Vault läuft als Container auf siem-docker, Terraform und Ansible holen sich ihre Secrets dort zur
  Laufzeit ab, jedes Werkzeug mit eigener AppRole und nur mit Zugriff auf das, was es braucht.

Die ausführliche Begründung zu jeder Entscheidung steht in [docs/architecture.md](docs/architecture.md).

## Schnellstart

Voraussetzungen: Docker, Bash (unter Windows Git Bash) und ein SSH-Key `~/.ssh/id_ed25519` mit Root-Zugriff auf
den Proxmox-Host. Terraform und Ansible müssen nicht installiert sein.

```bash
cp .env.example .env          # Proxmox-Endpunkt und Vault-Adresse, siehe docs/operations.md
scripts/tf.sh init
scripts/tf.sh apply
export LAB_VM_IP=$(scripts/vm-ip.sh)
scripts/ansible.sh ansible-playbook playbooks/site.yml
```

Ein zweiter Lauf des Playbooks muss `changed=0` zeigen, sonst ist eine Rolle nicht idempotent. Aufräumen geht
mit `scripts/tf.sh destroy`.

Das SOC-Portal, ARA und Vault auf siem-docker werden über eigene Playbooks ausgerollt, zum Beispiel
`scripts/ansible.sh ansible-playbook playbooks/soc-portal.yml`. Dafür braucht `.env` die AppRole-Zugangsdaten
für Vault, siehe [docs/operations.md](docs/operations.md#hashicorp-vault). Jeder Lauf über `scripts/ansible.sh`
landet automatisch in ARA unter `http://<VM-IP>:8091`.

![ARA: aufgezeichnete Playbook-Läufe](docs/img/ara-playbooks.png)

## Was schiefging und was ich daraus gelernt habe

- **Der API-Token durfte nichts.** Der erste `terraform apply` endete mit `403 Permission check failed`. Der
  Token war mit Privilege Separation angelegt und erbt dann die Rechte des Benutzers nicht. Die Rolle hängt jetzt
  direkt am Token, das ist ohnehin sauberer, weil ich ihn so unabhängig vom Benutzer widerrufen kann.
- **Mein Playbook war nicht idempotent.** Der zweite Lauf zeigte `changed=1` bei fail2ban. Ursache: Das Template
  hat kein rsyslog, beim ersten Lauf gab es noch keine `/var/log/auth.log`, und fail2ban stürzte ab. Der
  sshd-Jail liest jetzt aus journald. Ohne den Test auf `changed=0` wäre mir das nie aufgefallen.
- **Feste MAC heißt nicht feste IP.** Nach `destroy` und `apply` vergab die FritzBox trotz gleicher MAC eine neue
  Adresse. `vm-ip.sh` sucht sie deshalb jedes Mal über die ARP-Tabelle des Proxmox-Hosts, weil das Template keinen
  Guest-Agent hat, der sie melden könnte.
- **Windows-Dateien im Linux-Container:** Eingebundene Windows-Ordner erscheinen im Container mit Modus `0777`.
  SSH verweigert dann den Key, Ansible ignoriert `ansible.cfg` in so einem Verzeichnis und hätte die
  Vault-Passwortdatei sogar als Skript ausgeführt. Der Wrapper kopiert diese Dateien deshalb mit sauberen Rechten
  in den Container.
- **ARA brauchte mehr Speicher als gedacht.** Mit 256 MB lag der Container direkt nach dem Start bei 188 MB.
  Das Limit steht jetzt auf 384 MB.
- **Der Token landete fast im State.** Die erste Version las den Proxmox-Token als Datenquelle aus Vault, damit
  stand er im Terraform-State. Der Provider hat das selbst als veraltet markiert. Mit einer ephemeral resource
  wird der Wert nur noch zur Laufzeit gelesen.

Alle Läufe mit den tatsächlichen Ausgaben stehen im [Testprotokoll](docs/test-protocol.md).

## Adressen

Die Doku nutzt Platzhalter statt fester IPs: `<VM-IP>` ist die VM `siem-docker` mit Splunk, Cribl, Portal,
ARA und Vault, `<LAB-VM-IP>` die per Terraform erzeugte Test-VM und `<PROXMOX-IP>` der Proxmox-Host. Die echten
Adressen stehen im Inventory (`ansible/inventory/hosts.yml`), in den Rollen-Defaults und in `.env`.

## Doku

- [docs/architecture.md](docs/architecture.md): Aufbau, Datenfluss, Entscheidungen
- [docs/operations.md](docs/operations.md): Einrichtung, Betrieb, Updates, Wiederherstellung, Secrets
- [docs/test-protocol.md](docs/test-protocol.md): echte Läufe mit Ergebnissen

## Secrets

Secrets werden zentral in HashiCorp Vault verwaltet. Terraform holt sich den Proxmox-API-Token zur Laufzeit
über eine eigene AppRole, Ansible die Portal-Konfiguration über `community.hashi_vault`. Jede AppRole kommt nur
an ihr eigenes Secret heran, und jeder Zugriff wird im Audit-Log festgehalten. Unseal-Key und Root-Token von
Vault selbst sichert Ansible Vault, das Passwort dafür liegt lokal in `.vault_pass`. Details stehen in
[docs/operations.md](docs/operations.md#hashicorp-vault).
