"""Generates the architecture and sequence diagrams (DE/EN). Usage: python docs/diagrams/generate.py docs/diagrams

PNG export: render each HTML file headless at scale 2 and screenshot the <svg> element (e.g. Playwright locator('svg').screenshot()).
"""
import html, pathlib, sys

OUT = pathlib.Path(sys.argv[1])

PAPER, INK, MUTED, SOFT, ACCENT, LINK = "#f5f5f5", "#2d3142", "#4f5d75", "#5a6580", "#bf4520", "#2e5aa8"
SANS, MONO = "'Geist', sans-serif", "'Geist Mono', monospace"
CW = 5.6  # approx. width per char of 8px mono labels with letter-spacing

TREAT = {
    "focal":   ("rgba(191,69,32,0.08)", ACCENT, "rgba(191,69,32,0.50)", ACCENT),
    "backend": ("#ffffff", INK, "rgba(45,49,66,0.40)", INK),
    "store":   ("rgba(45,49,66,0.05)", MUTED, "rgba(79,93,117,0.50)", MUTED),
    "input":   ("rgba(79,93,117,0.10)", SOFT, "rgba(90,101,128,0.40)", SOFT),
}


def node(x, y, w, h, kind, tag, name, sub):
    fill, stroke, tagstroke, tagtext = TREAT[kind]
    tw = len(tag) * 5 + 12
    cx = x + w / 2
    return f'''
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1"/>
  <rect x="{x+8}" y="{y+8}" width="{tw}" height="12" rx="2" fill="transparent" stroke="{tagstroke}" stroke-width="0.8"/>
  <text x="{x+8+tw/2}" y="{y+17}" fill="{tagtext}" font-size="7" font-family="{MONO}" text-anchor="middle" letter-spacing="0.08em">{tag}</text>
  <text x="{cx}" y="{y+h/2+6}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">{name}</text>
  <text x="{cx}" y="{y+h/2+22}" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">{sub}</text>'''


def label(cx, top, text, color):
    w = round(len(text) * CW + 12)
    w += w % 2
    return f'''
  <rect x="{cx-w/2}" y="{top}" width="{w}" height="12" rx="2" fill="{PAPER}"/>
  <text x="{cx}" y="{top+9}" fill="{color}" font-size="8" font-family="{MONO}" text-anchor="middle" letter-spacing="0.08em">{html.escape(text)}</text>'''


def zone(x, y, w, h, text):
    lw = round(len(text) * 5.2 + 12)
    return f'''
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="rgba(45,49,66,0.02)" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>
  <rect x="{x+12}" y="{y+4}" width="{lw}" height="12" rx="2" fill="{PAPER}"/>
  <text x="{x+12+lw/2}" y="{y+13}" fill="{SOFT}" font-size="7" font-family="{MONO}" text-anchor="middle" letter-spacing="0.14em">{text}</text>'''


def legend(y, items):
    out = [f'''
  <line x1="40" y1="{y}" x2="1240" y2="{y}" stroke="rgba(45,49,66,0.10)" stroke-width="0.8"/>
  <text x="40" y="{y+16}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.18em">{items[0]}</text>''']
    x = 40
    for kind, text in items[1:]:
        if kind in TREAT:
            fill, stroke, _, _ = TREAT[kind]
            out.append(f'<rect x="{x}" y="{y+32}" width="14" height="10" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
        else:
            color, marker, dash, width = {
                "accent": (ACCENT, "arrow-accent", "", 1.4),
                "link": (LINK, "arrow-link", "", 1.2),
                "dashed": (MUTED, "arrow", ' stroke-dasharray="4,3"', 1),
                "muted": (MUTED, "arrow", "", 1.2),
                "async": (MUTED, "arrow-open", ' stroke-dasharray="4,3"', 1),
            }[kind]
            out.append(f'<line x1="{x}" y1="{y+37}" x2="{x+22}" y2="{y+37}" stroke="{color}" stroke-width="{width}"{dash} marker-end="url(#{marker})"/>')
        out.append(f'<text x="{x+30}" y="{y+40}" fill="{MUTED}" font-size="8.5" font-family="{SANS}">{text}</text>')
        x += 30 + round(len(text) * 4.6) + 32
    return "\n  ".join(out)


DEFS = f'''<defs>
    <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.9" fill="rgba(45,49,66,0.10)"/></pattern>
    <marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{MUTED}"/></marker>
    <marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{ACCENT}"/></marker>
    <marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{LINK}"/></marker>
    <marker id="arrow-open" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polyline points="0 0, 8 3, 0 6" fill="none" stroke="{MUTED}" stroke-width="1.2"/></marker>
  </defs>
  <rect width="100%" height="100%" fill="{PAPER}"/>
  <rect width="100%" height="100%" fill="url(#dots)" opacity="0.55"/>'''


def page(lang, slug, eyebrow, h1, title, desc, body, height=720):
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --color-paper: {PAPER};
      --color-ink: {INK};
      --color-muted: {MUTED};
      --font-sans: 'Geist', system-ui, sans-serif;
      --font-serif: 'Instrument Serif', serif;
      --font-mono: 'Geist Mono', ui-monospace, monospace;
    }}
    body {{ font-family: var(--font-sans); background: var(--color-paper); color: var(--color-ink);
           min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 3rem 2rem; }}
    .frame {{ max-width: 1280px; width: 100%; }}
    .eyebrow {{ font-family: var(--font-mono); font-size: 0.66rem; font-weight: 500; letter-spacing: 0.18em;
               text-transform: uppercase; color: var(--color-muted); margin-bottom: 0.5rem; }}
    h1 {{ font-family: var(--font-serif); font-size: clamp(1.5rem, 2.4vw + 0.75rem, 2rem); font-weight: 400;
         letter-spacing: -0.02em; line-height: 1.15; margin-bottom: 1.5rem; }}
    .diagram-container {{ overflow-x: auto; }}
    svg {{ width: 100%; min-width: 1280px; display: block; }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{h1}</h1>
    <div class="diagram-container">
    <svg viewBox="0 0 1280 {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{slug}-title {slug}-desc">
  <title id="{slug}-title">{title}</title>
  <desc id="{slug}-desc">{desc}</desc>
  {DEFS}
{body}
    </svg>
    </div>
  </div>
</body>
</html>
'''


# ---------------------------------------------------------------- architecture
def architecture(t):
    D = -64  # vertical offset; the drawing uses a fit-height 1280x520 frame
    s = []
    s.append(zone(40, 128 + D, 208, 288, t["zone_pc"]))
    s.append(zone(292, 128 + D, 376, 288, "PROXMOX VE · PVE"))
    s.append(zone(716, 288 + D, 524, 128, t["zone_siem"]))
    # arrows (before nodes)
    s.append(f'<line x1="224" y1="{192+D}" x2="324" y2="{192+D}" stroke="{LINK}" stroke-width="1.2" marker-end="url(#arrow-link)"/>')
    s.append(f'<path d="M 396,{224+D} V {332+D} Q 396,{340+D} 404,{340+D} H 500" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    s.append(f'<line x1="572" y1="{224+D}" x2="572" y2="{320+D}" stroke="{MUTED}" stroke-width="1" stroke-dasharray="4,3" marker-end="url(#arrow)"/>')
    s.append(f'<line x1="224" y1="{364+D}" x2="500" y2="{364+D}" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    s.append(f'<line x1="644" y1="{352+D}" x2="740" y2="{352+D}" stroke="{ACCENT}" stroke-width="1.4" marker-end="url(#arrow-accent)"/>')
    s.append(f'<line x1="868" y1="{352+D}" x2="912" y2="{352+D}" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    s.append(f'<line x1="1040" y1="{352+D}" x2="1084" y2="{352+D}" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    s.append(f'<path d="M 144,{384+D} V {440+D} Q 144,{448+D} 152,{448+D} H 1140 Q 1148,{448+D} 1148,{440+D} V {384+D}" fill="none" stroke="{MUTED}" stroke-width="1.2" marker-end="url(#arrow)"/>')
    # labels
    s.append(label(274, 172 + D, "API TOKEN", LINK))
    s.append(label(428, 272 + D, "CLONE", MUTED))
    s.append(label(612, 266 + D, t["base_disk"], MUTED))
    s.append(label(262, 344 + D, "SSH", MUTED))
    s.append(label(692, 332 + D, "UDP 9514", ACCENT))
    s.append(label(890, 332 + D, "HEC", MUTED))
    s.append(label(1062, 332 + D, "REST", MUTED))
    s.append(label(640, 456 + D, t["deploy"], MUTED))
    # nodes
    s.append(node(64, 160 + D, 160, 64, "input", "IAC", "Terraform", "scripts/tf.sh"))
    s.append(node(64, 320 + D, 160, 64, "input", "CFG", "Ansible", "scripts/ansible.sh"))
    s.append(node(324, 160 + D, 144, 64, "backend", "API", "Proxmox API", ":8006"))
    s.append(node(500, 160 + D, 144, 64, "store", "TPL", "Template 900", "Ubuntu 22.04"))
    s.append(node(500, 320 + D, 144, 64, "focal", "VM", "lab-iac-01", "VM 220 · 1 vCPU/1 GB"))
    s.append(node(740, 320 + D, 128, 64, "backend", "PIPE", "Cribl Stream", "syslog :9514"))
    s.append(node(912, 320 + D, 128, 64, "store", "SIEM", "Splunk", "homelab_auth"))
    s.append(node(1084, 320 + D, 128, 64, "backend", "WEB", t["portal"], ":8090"))
    s.append(legend(432, t["legend_arch"]))
    return "\n  ".join(s)


# ---------------------------------------------------------------- sequence
def actor(x, name, sub):
    return f'''
  <rect x="{x-88}" y="64" width="176" height="56" rx="6" fill="{PAPER}"/>
  <rect x="{x-88}" y="64" width="176" height="56" rx="6" fill="#ffffff" stroke="{INK}" stroke-width="1"/>
  <text x="{x}" y="88" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}" text-anchor="middle">{name}</text>
  <text x="{x}" y="104" fill="{MUTED}" font-size="9" font-family="{MONO}" text-anchor="middle">{sub}</text>'''


TEXT = {
    "de": {
        "zone_pc": "ADMIN-PC · DOCKER", "zone_siem": "VM 210 · SIEM-DOCKER", "base_disk": "BASIS-DISK",
        "deploy": "DEPLOY · VAULT", "portal": "SOC-Portal",
        "legend_arch": ["LEGENDE", ("focal", "Neue VM (Fokus)"), ("input", "Werkzeug"), ("backend", "Dienst"),
                        ("store", "Daten / Vorlage"), ("accent", "Log-Pfad"), ("link", "HTTPS-API"),
                        ("muted", "Steuerung"), ("dashed", "Linked Clone")],
        "arch_eyebrow": "Architektur · homelab-infrastructure-automation",
        "arch_h1": "Von terraform apply bis ins SOC-Portal",
        "arch_title": "Homelab-IaC: Provisionierung und Log-Pfad",
        "arch_desc": "Terraform klont über die Proxmox-API die VM lab-iac-01 aus Template 900, Ansible konfiguriert sie per SSH, und ihre Auth-Logs laufen über Cribl und Splunk ins SOC-Portal, das Ansible ebenfalls deployt.",
        "actors": [("Admin-PC", "tf.sh · ansible.sh"), ("Proxmox VE", "API · pve"), ("lab-iac-01", "VM 220"),
                   ("Cribl → Splunk", "UDP 9514 · HEC"), ("SOC-Portal", ":8090")],
        "msgs": [(0, 1, "call", "APPLY · CLONE"), (1, 2, "async", "CLOUD-INIT"), (1, 0, "return", "ID=220 · 4 S"),
                 (0, 1, "call", "VM-IP.SH"), (1, 0, "return", "<LAB-VM-IP>"),
                 (0, 2, "call", "PLAYBOOK RUN 1"), (2, 0, "return", "CHANGED=18"),
                 (0, 2, "call", "PLAYBOOK RUN 2"), (2, 0, "headline", "CHANGED=0"),
                 (2, 3, "async", "AUTH-LOG"), (4, 3, "call", "REST-SUCHE"), (3, 4, "headline", "LAB-IAC-01")],
        "legend_seq": ["LEGENDE", ("muted", "Aufruf"), ("dashed", "Antwort"), ("async", "Asynchron"), ("accent", "Nachweis")],
        "seq_eyebrow": "Ablauf · homelab-infrastructure-automation",
        "seq_h1": "Eine neue VM in fünf Minuten: geklont, konfiguriert, überwacht",
        "seq_title": "Homelab-IaC: Ablauf einer neuen VM",
        "seq_desc": "Terraform klont VM 220, vm-ip.sh findet ihre Adresse, der zweite Ansible-Lauf meldet changed=0, und nach einem Test-Login zeigt das SOC-Portal den Host lab-iac-01.",
    },
    "en": {
        "zone_pc": "ADMIN PC · DOCKER", "zone_siem": "VM 210 · SIEM-DOCKER", "base_disk": "BASE DISK",
        "deploy": "DEPLOY · VAULT", "portal": "SOC portal",
        "legend_arch": ["LEGEND", ("focal", "New VM (focus)"), ("input", "Tool"), ("backend", "Service"),
                        ("store", "Data / template"), ("accent", "Log path"), ("link", "HTTPS API"),
                        ("muted", "Control"), ("dashed", "Linked clone")],
        "arch_eyebrow": "Architecture · homelab-infrastructure-automation",
        "arch_h1": "From terraform apply to the SOC portal",
        "arch_title": "Homelab IaC: provisioning and log path",
        "arch_desc": "Terraform clones VM lab-iac-01 from template 900 through the Proxmox API, Ansible configures it over SSH, and its auth logs flow through Cribl and Splunk into the SOC portal, which Ansible also deploys.",
        "actors": [("Admin PC", "tf.sh · ansible.sh"), ("Proxmox VE", "API · pve"), ("lab-iac-01", "VM 220"),
                   ("Cribl → Splunk", "UDP 9514 · HEC"), ("SOC portal", ":8090")],
        "msgs": [(0, 1, "call", "APPLY · CLONE"), (1, 2, "async", "CLOUD-INIT"), (1, 0, "return", "ID=220 · 4 S"),
                 (0, 1, "call", "VM-IP.SH"), (1, 0, "return", "<LAB-VM-IP>"),
                 (0, 2, "call", "PLAYBOOK RUN 1"), (2, 0, "return", "CHANGED=18"),
                 (0, 2, "call", "PLAYBOOK RUN 2"), (2, 0, "headline", "CHANGED=0"),
                 (2, 3, "async", "AUTH LOG"), (4, 3, "call", "REST SEARCH"), (3, 4, "headline", "LAB-IAC-01")],
        "legend_seq": ["LEGEND", ("muted", "Call"), ("dashed", "Return"), ("async", "Async"), ("accent", "Proof")],
        "seq_eyebrow": "Sequence · homelab-infrastructure-automation",
        "seq_h1": "A new VM in five minutes: cloned, configured, monitored",
        "seq_title": "Homelab IaC: lifecycle of a new VM",
        "seq_desc": "Terraform clones VM 220, vm-ip.sh finds its address, the second Ansible run reports changed=0, and after a test login the SOC portal lists host lab-iac-01.",
    },
}


def sequence_body(t):
    xs = [160, 400, 640, 880, 1120]
    s = []
    for x in xs:
        s.append(f'<line x1="{x}" y1="120" x2="{x}" y2="584" stroke="rgba(45,49,66,0.20)" stroke-width="1" stroke-dasharray="3,3"/>')
    bars = [(0, 152, 460), (1, 152, 240), (1, 260, 312), (2, 332, 456), (3, 512, 564), (4, 512, 564)]
    for i, top, bot in bars:
        s.append(f'<rect x="{xs[i]-4}" y="{top}" width="8" height="{bot-top}" fill="rgba(45,49,66,0.06)" stroke="{MUTED}" stroke-width="0.8"/>')

    def active(i, y):
        return any(b == i and top <= y <= bot for b, top, bot in bars)

    for n, (a, b, kind, text) in enumerate(t["msgs"]):
        y = 160 + 36 * n
        right = xs[b] > xs[a]
        x1 = xs[a] + ((4 if right else -4) if active(a, y) else 0)
        x2 = xs[b] + ((-4 if right else 4) if active(b, y) else 0)
        color, marker, dash, width = {
            "call": (MUTED, "arrow", "", 1.2),
            "return": (MUTED, "arrow", ' stroke-dasharray="4,3"', 1),
            "async": (MUTED, "arrow-open", ' stroke-dasharray="4,3"', 1),
            "headline": (ACCENT, "arrow-accent", "", 1.4),
        }[kind]
        s.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="{width}"{dash} marker-end="url(#{marker})"/>')
        s.append(label((x1 + x2) / 2, y - 20, text, color))
    for x, (name, sub) in zip(xs, t["actors"]):
        s.append(actor(x, name, sub))
    s.append(legend(604, t["legend_seq"]))
    return "\n  ".join(s)


OUT.mkdir(parents=True, exist_ok=True)
for lang, t in TEXT.items():
    suffix = "" if lang == "de" else ".en"
    slug = "architecture" + ("" if lang == "de" else "-en")
    (OUT / f"architecture{suffix}.html").write_text(
        page(lang, slug, t["arch_eyebrow"], t["arch_h1"], t["arch_title"], t["arch_desc"], architecture(t), 520),
        encoding="utf-8", newline="\n")
    slug = "sequence" + ("" if lang == "de" else "-en")
    (OUT / f"sequence{suffix}.html").write_text(
        page(lang, slug, t["seq_eyebrow"], t["seq_h1"], t["seq_title"], t["seq_desc"], sequence_body(t)),
        encoding="utf-8", newline="\n")
print("ok")
