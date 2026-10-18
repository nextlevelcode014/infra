# Proxmox — host

O Proxmox roda num notebook (Lenovo IdeaPad 3 15ALC6) ligado na tomada 24/7.
`playbooks/proxmox.yml` aplica o role `proxmox_host`, que configura a máquina
física. Os containers são do `lxc.yml`; criá-los é do `../terraform/`.

```bash
ansible-playbook playbooks/proxmox.yml --ask-vault-pass
```

## Bateria

Bateria parada em 100% e quente se desgasta rápido e pode inchar. O
`ideapad_laptop` expõe o modo de carga em
`/sys/class/power_supply/BAT0/charge_types`:

- `Fast`: carga rápida (era o padrão aqui, o pior para quem fica na tomada);
- `Standard`: carga normal até 100%;
- `Long_Life`: "conservation mode", o firmware para perto de 60%.

O role escolhe `Long_Life` (`proxmox_battery_charge_type`) na hora e grava uma
regra do udev que reaplica o modo no boot. No IdeaPad não dá para escolher a
porcentagem: o limite é o do firmware.

Confira:

```bash
ssh root@<proxmox_host> 'cat /sys/class/power_supply/BAT0/charge_types /sys/class/power_supply/BAT0/status'
```

O IP é o Tailscale do `pve`, o mesmo do `inventory/static.ini`. Deve
mostrar `[Long_Life]` entre colchetes. O status continua `Full` enquanto a
bateria estiver acima do limite: na tomada ela não descarrega até 60%, só
para de carregar, e a carga baixa com o tempo. A prova de que o modo está
ativo é o driver:

```bash
ssh root@<proxmox_host> 'cat /sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode'
```

Tem que responder `1`. Depois de um reboot, repita:
o modo tem que continuar `[Long_Life]`.

Estado em 2026-10-03, antes da mudança: 1019 ciclos e 82% da capacidade
original (31,1 de 38 Wh).

## Rede dos LXCs

Os LXCs não ficam na LAN do roteador: moram na `vmbr1`, uma bridge só do
Proxmox, sem porta física, e saem para a internet por NAT pela `vmbr0`
(ADR 0009, na raiz). Trocar o Proxmox de rede muda só o DHCP da `vmbr0`; o IP
dos LXCs, o Terraform e o inventário continuam iguais.

```
LAN qualquer (DHCP) ─► vmbr0  Proxmox  vmbr1 10.50.0.1/24 ─► LXCs 10.50.0.200-299
                                       NAT de 10.50.0.0/24 para fora pela vmbr0
```

O role `proxmox_host` grava a `vmbr1` em `/etc/network/interfaces.d/vmbr1`
(com a regra de NAT no `post-up`), liga o `net.ipv4.ip_forward` e sobe só a
`vmbr1` com `ifup`. A `vmbr0` fica no `/etc/network/interfaces`, onde o
instalador do Proxmox a pôs, e o Ansible não toca nela: um erro ali corta o
acesso ao host. A faixa está no `defaults` do role e no `../terraform/local.tf`;
mudar num é mudar no outro.

Da sua máquina não há rota até `10.50.0.0/24`. O Ansible salta pelo Proxmox
(`ansible_ssh_common_args` em `inventory/group_vars/lxc/vars.yml`), e o seu SSH
faz o mesmo pelo `~/.ssh/config`. Num Proxmox novo, a ordem é: este playbook,
depois o `terraform apply`, depois o `lxc.yml`.

1. **Reautenticar no Tailscale SSH do Proxmox.** O root dele usa `check` na
   ACL, que pede login no navegador. Sem isso, o Ansible e o salto ficam
   parados esperando, sem mensagem. Não dá para automatizar porque é o login
   da sua conta Tailscale:

   ```bash
   ssh root@<proxmox_host> true
   ```

   Confira: o comando volta sem erro depois do login. Vale por algumas horas;
   repita quando um playbook parecer travado na conexão.

2. **Conferir que o `interfaces` lê o `interfaces.d`** (o Proxmox já vem
   assim; o role recusa seguir sem a linha):

   ```bash
   ssh root@<proxmox_host> grep -n 'interfaces.d' /etc/network/interfaces
   ```

   Confira: mostra `source /etc/network/interfaces.d/*`.

3. **Aplicar:**

   ```bash
   ansible-playbook playbooks/proxmox.yml --ask-vault-pass
   ```

   Confira:

   ```bash
   ssh root@<proxmox_host> 'ip -br addr show vmbr1; sysctl net.ipv4.ip_forward; iptables -t nat -S POSTROUTING | grep 10.50.0.0'
   ```

   Mostra a `vmbr1` com `10.50.0.1/24`, `net.ipv4.ip_forward = 1` e a regra
   `MASQUERADE` saindo pela `vmbr0`.

4. **SSH da sua máquina para os LXCs.** O `~/.ssh/config` é da sua máquina,
   fora do repo. Acrescente:

   ```
   Host 10.50.0.*
       User root
       ProxyJump root@<proxmox_host>
   ```

   Confira, com os LXCs já criados: `ssh root@10.50.0.203 hostname` responde
   `pi-lab`, e `ssh root@10.50.0.203 curl -sI https://deb.debian.org | head -1`
   mostra `HTTP/... 200` (a saída pelo NAT funciona).

Porta de um LXC no navegador: túnel pelo mesmo salto (`docs/pi.md`, "pi-lab").
