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
