#!/usr/bin/env bash
# Finds the DHCP address of a VM by MAC. The template has no guest agent, so Proxmox cannot report it.
# Pings the subnet from the Proxmox host to fill its ARP table, then looks up the MAC.
# Usage: scripts/vm-ip.sh [MAC]   (default: Terraform output mac_address)
set -euo pipefail
mac="${1:-$("$(dirname "$0")/tf.sh" output -raw mac_address)}"
pve="${PVE_HOST:-192.168.178.47}"
net="${LAB_SUBNET_PREFIX:-192.168.178}"
ssh -o BatchMode=yes "root@$pve" \
  "for i in \$(seq 1 254); do ping -c1 -W1 $net.\$i >/dev/null 2>&1 & done; wait; ip -4 neigh | grep -i '$mac' | awk '{print \$1}' | head -n1"
