#!/usr/bin/env bash
set -e

ROOT="homelab-ansible"

# --- pastas ---
mkdir -p "$ROOT"/{inventory,group_vars,host_vars}

# roles criadas com ansible-galaxy (já geram a estrutura interna completa)
ansible-galaxy role init "$ROOT/roles/common"
ansible-galaxy role init "$ROOT/roles/docker"

# --- ansible.cfg ---
cat > "$ROOT/ansible.cfg" <<'EOF'
[defaults]
inventory       = inventory/
roles_path      = roles
remote_user     = ansible
host_key_checking = False

[privilege_escalation]
become      = True
become_method = sudo
EOF

# --- requirements.yml ---
cat > "$ROOT/requirements.yml" <<'EOF'
collections:
  - name: community.general
  - name: community.docker
EOF

# --- inventário estático ---
cat > "$ROOT/inventory/static.ini" <<'EOF'
[raspberry]
rpi5.local ansible_user=pi

[proxmox_hosts]
pve.local ansible_user=root
EOF

# --- inventário dinâmico do Proxmox ---
cat > "$ROOT/inventory/proxmox.proxmox.yml" <<'EOF'
plugin: community.general.proxmox
url: https://pve.local:8006
user: ansible@pve
token_id: ansible-token
token_secret: "{{ lookup('env', 'PROXMOX_TOKEN') }}"
validate_certs: false
want_facts: true
EOF

# --- variáveis globais ---
cat > "$ROOT/group_vars/all.yml" <<'EOF'
---
timezone: America/Fortaleza
ntp_server: pool.ntp.org
EOF

# --- site.yml ---
cat > "$ROOT/site.yml" <<'EOF'
---
- import_playbook: playbooks/common.yml
- import_playbook: playbooks/docker.yml
EOF

mkdir -p "$ROOT/playbooks"

cat > "$ROOT/playbooks/common.yml" <<'EOF'
---
- name: Configuração base de todas as máquinas
  hosts: all
  roles:
    - common
EOF

cat > "$ROOT/playbooks/docker.yml" <<'EOF'
---
- name: Instalar Docker
  hosts: raspberry
  roles:
    - docker
EOF

echo "Estrutura criada em ./$ROOT"
