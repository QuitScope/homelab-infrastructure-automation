output "vm_id" {
  value = proxmox_virtual_environment_vm.lab.vm_id
}

output "vm_name" {
  value = proxmox_virtual_environment_vm.lab.name
}

output "mac_address" {
  description = "Pass to scripts/vm-ip.sh to find the DHCP address (no guest agent, so Proxmox cannot report it)."
  value       = var.mac_address
}
