# VPS (Hetzner)

A VPS fica fora de casa e serve duas coisas:

- o **Caddy público** (`*.nextlevelcode.pro`, hoje o `forge` e o `status`) e os **sites
  privados** que moram nela (`uptime.lab`, só da tailnet), pelo
  `playbooks/caddy-vps.yml`;
- o **Anubis** na frente do `forge` (`playbooks/anubis.yml`, ver `docs/anubis.md`);
- o **Uptime Kuma** (`playbooks/uptime-kuma.yml`, ver `docs/uptime-kuma.md`).

Segredos vêm do vault: o token da Cloudflare **próprio da VPS**
(`vault_caddy_vps_cloudflare_token`, separado do do Proxmox) e o acesso ao Borg. O Docker roda com `sudo`: o
usuário `hetzner` não fica no grupo `docker`.

## VPS nova (ou reinstalada)

O que vem antes de o Ansible conseguir entrar, mais o DNS público:

1. **Criar a VPS** (Ubuntu 26.04) com o usuário `hetzner` e sudo sem senha:

   ```bash
   echo 'hetzner ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/hetzner
   sudo chmod 440 /etc/sudoers.d/hetzner
   ```

2. **Tailscale no host.** Remova antes o nó `hetzner` antigo no console, para
   o nome ficar livre. É por aqui que o Ansible entra (Tailscale SSH):

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --ssh --hostname=hetzner
   tailscale ip -4
   ```

   Confira, do seu computador: `ssh hetzner@hetzner.<tailnet>.ts.net true`.
   A tag da VPS e a policy do Tailscale SSH precisam permitir o usuário
   `hetzner`.

3. **Cloudflare** (zona `nextlevelcode.pro`, DNS only):

   | Nome | Tipo | Valor |
   |---|---|---|
   | `*` | A | IP público novo da VPS |
   | `uptime.lab` | A | IP Tailscale novo (o do passo 2) |

   O curinga `*.lab` fica como está (Caddy do Proxmox; só aponta para a VPS
   na contingência, `docs/pi-recuperacao.md`).

4. **Aplicar:**

   ```bash
   ansible-playbook playbooks/anubis.yml --ask-vault-pass
   ansible-playbook playbooks/caddy-vps.yml --ask-vault-pass
   ansible-playbook playbooks/uptime-kuma.yml --ask-vault-pass
   ```

   O Anubis vem antes: o Caddy aponta o `forge` para ele, e sem ele o `forge`
   dá 502.

   Confira: `forge.nextlevelcode.pro` e `uptime.lab.nextlevelcode.pro`
   respondem.

5. **Dados do Uptime Kuma** (monitores, avisos, histórico), se quiser recuperar
   em vez de configurar de novo: com o container parado, `borg extract` do
   archive `uptime-kuma-*` mais recente para `/opt/uptime-kuma/data`, e subir.
