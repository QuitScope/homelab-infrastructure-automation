resource "proxmox_virtual_environment_vm" "lab" {
  name        = var.vm_name
  node_name   = var.node_name
  vm_id       = var.vm_id
  description = "Managed by Terraform (homelab-infrastructure-automation). Configured by Ansible."
  tags        = ["iac", "lab", "terraform"]

  # Linked clone: shares the template's base disk, only changed blocks use space on local-lvm.
  clone {
    vm_id = var.template_id
    full  = false
  }

  # The template has no running qemu-guest-agent; waiting for it would block apply.
  agent {
    enabled = false
  }

  # No guest agent means a clean ACPI shutdown cannot be confirmed, so destroy stops the VM hard.
  stop_on_destroy = true
  on_boot         = false

  cpu {
    cores = var.cores
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = var.memory_mb
  }

  network_device {
    bridge      = "vmbr0"
    mac_address = var.mac_address
  }

  operating_system {
    type = "l26"
  }

  initialization {
    datastore_id = "local-lvm"

    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }

    user_account {
      username = "root"
      keys     = [trimspace(file(pathexpand(var.ssh_public_key_path)))]
    }
  }
}
