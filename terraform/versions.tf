terraform {
  # State no HCP Terraform, execução local (ADR 0019): o plan roda daqui,
  # pela Tailscale. O state também é o inventário do Ansible.
  cloud {
    organization = "NextLevelCode"
    workspaces {
      name = "infra-proxmox"
    }
  }

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.114"
    }
    ansible = {
      source  = "ansible/ansible"
      version = "1.3.0"
    }
  }
}
