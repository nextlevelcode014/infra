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
       IdentityFile ~/.ssh/id_ed25519.pub
       IdentitiesOnly yes
   ```

   A chave é a que o Terraform põe nos LXCs (`terraform/local.tf`). A
   privada fica no agente do Bitwarden, não em disco: com a `.pub` no
   `IdentityFile`, o ssh pede ao agente a privada que forma par com ela. Sem o
   `IdentitiesOnly`, o agente oferece todas as chaves dele antes, e o sshd
   do LXC corta com `Too many authentication failures`.

   Confira, com os LXCs já criados: `ssh root@10.50.0.203 hostname` responde
   `pi-lab`, e `ssh root@10.50.0.203 'wget -S -O /dev/null https://deb.debian.org 2>&1 | grep HTTP/'`
   mostra `HTTP/1.1 200 OK` (a saída pelo NAT funciona).

Porta de um LXC no navegador: túnel pelo mesmo salto (`docs/pi.md`, "pi-lab").

## ACL do lab

O repo `lab` cria VMs com o usuário `lab@pve`, que só tem permissão nos VMIDs
900–999, por uma ACL em cada `/vms/<id>` (o `docs/proxmox.md` do lab). O
Proxmox apaga as ACLs de `/vms/<id>` **sempre** que a VM é destruída, com ou
sem purge: sem o timer, cada `terraform destroy` no lab deixa aquele VMID
recusando o próximo create com `403 Permission check failed (/vms/<id>,
VM.Config.Options)`, até alguém repor a ACL como root (ADR 0017).

O role `proxmox_host` instala o `lab-acl.timer`, que a cada minuto repõe o
`PVEVMAdmin` do `lab@pve` no VMID da faixa que estiver sem ele. A faixa e o
papel estão no `defaults` do role e no `docs/proxmox.md` do lab; mudar num é
mudar no outro.

1. **Aplicar** (é o mesmo playbook do host):

   ```bash
   ansible-playbook playbooks/proxmox.yml --ask-vault-pass
   ```

2. **Conferir que o timer roda e que nada falta:**

   ```bash
   ssh root@<proxmox_host> 'systemctl list-timers lab-acl.timer; journalctl -u lab-acl.service -n 20 --no-pager'
   ssh root@<proxmox_host> "pveum acl list | grep -c 'lab@pve'"
   ```

   O timer aparece com a próxima execução em menos de um minuto; o journal
   mostra `ACL reposta: /vms/<id>` só na primeira execução para os VMIDs que
   estavam sem ACL, e nada nas seguintes (se toda execução repuser a faixa
   inteira, o script não está lendo a saída do `pveum acl list`). A contagem
   é `104` (100 VMIDs + pool + 2 storages + bridge).

Um destroy seguido de create **no mesmo VMID** em menos de um minuto (um
`-/+` que não troca o VMID) ainda pode levar o 403: espere o timer e rode o
`apply` de novo.

## Rede do lab

As VMs do repo `lab` moram na `vmbr2`, outra bridge só do Proxmox, e só saem
para a internet (ADR 0021):

```
vmbr2 10.60.0.1/24 ─► VMs do lab 10.60.0.100-199 (VMID 900-999)
  NAT para fora pela vmbr0; nada para a vmbr1, a LAN, a tailnet ou o host
```

O role `proxmox_host` grava a `vmbr2` em `/etc/network/interfaces.d/vmbr2` e
o `/usr/local/sbin/lab-isolamento`, que sobe e desce com ela: NAT e as
chains `LAB-FORWARD` e `LAB-INPUT` no topo do `FORWARD` e do `INPUT`. A
faixa está no `defaults` do role e no `modules/proxmox-vm` do lab; mudar num
é mudar no outro.

1. **Aplicar** (é o mesmo playbook do host):

   ```bash
   ansible-playbook playbooks/proxmox.yml --ask-vault-pass
   ```

   Confira:

   ```bash
   ssh root@<proxmox_host> 'ip -br addr show vmbr2; iptables -S LAB-FORWARD; iptables -S LAB-INPUT; iptables -S FORWARD | head -2; iptables -t nat -S POSTROUTING | grep 10.60.0.0'
   ```

   Mostra a `vmbr2` com `10.60.0.1/24`, as duas chains com as regras de
   `DROP`, o `-j LAB-FORWARD` como primeira regra do `FORWARD` e o
   `MASQUERADE` saindo pela `vmbr0`.

2. **Trocar a permissão de rede do `lab@pve`** da `vmbr0` para a `vmbr2`. É
   ACL do Proxmox, como root, e mora no `docs/proxmox.md` do lab (seção 2):
   lá estão os dois comandos e como conferir.

3. **Conferir o isolamento** de dentro de uma VM do lab já criada na `vmbr2`
   (o `README` do experimento diz o IP):

   ```bash
   ssh -J root@<proxmox_host> lab@10.60.0.101 \
     'curl -sS -o /dev/null -w "%{http_code}\n" https://deb.debian.org;
      for alvo in 10.50.0.200:443 10.60.0.1:8006 10.60.0.1:22; do
        timeout 3 bash -c "</dev/tcp/${alvo%:*}/${alvo#*:}" 2>/dev/null && echo "ABERTO $alvo" || echo "fechado $alvo";
      done'
   ```

   Tem que mostrar `200` (a internet funciona) e `fechado` nos três: o Caddy
   na `vmbr1`, a API e o SSH do host.
