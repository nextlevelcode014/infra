# 0003. Atualização do Pi sob demanda, só imagem

- **Status:** Aceita
- **Data:** 2026-10-03
- **Fonte:** #56 do antigo repo `ansible`

## Contexto

Antes, atualizar o Pi era `pull` e `up -d` à mão, stack por stack, então só
acontecia quando algo quebrava. Atualização de segurança do Ubuntu já entra
sozinha pelo unattended-upgrades, mas pacotes fora de segurança e as imagens
das stacks não.

## Decisão

`ansible/playbooks/pi-atualizar.yml`, rodado quando você quiser: `apt
dist-upgrade`, `pull` e `up -d` das stacks, recriação dos dependentes do
gluetun e `prune`. Ele só troca imagem e não reaplica config, e não reinicia:
avisa se o SO pedir reboot.

## Alternativas descartadas

- **Timer automático:** uma imagem que quebra apareceria num horário
  qualquer, sem ninguém olhando.
- **Reaplicar config junto:** uma quebra depois da atualização não diria se a
  culpa é da imagem nova ou da config nova.
- **Reboot automático:** o LUKS pede passphrase a cada boot; o Pi ficaria
  parado até alguém destravar.

## Consequências

- Separar imagem de config é regra: o playbook do serviço aplica config sem
  trocar imagem que já existe (`pull: missing`, ver 0006).
- Ficam de fora o Nextcloud AIO (atualiza pela própria interface) e os
  serviços em standby (ver 0004).
- A VPS ainda não tem equivalente: o `vps-atualizar.yml`, no mesmo molde,
  está planejado na #17.
