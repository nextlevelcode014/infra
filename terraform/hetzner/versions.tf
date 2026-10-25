terraform {
  # State no HCP Terraform, execução local (ADR 0019): o plan roda daqui,
  # pela Tailscale. O state também é o inventário do Ansible.
  cloud {
    organization = "NextLevelCode"
    workspaces {
      name = "infra-hetzner"
    }
  }

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.52"
    }
  }
}
