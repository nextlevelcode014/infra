# Reconstruir o Raspberry Pi do zero

Para um Pi novo ou reformatado. `playbooks/pi-completo.yml` aplica a base, traz
os dados do Borg e sobe todos os serviços, nessa ordem: os dados voltam
**antes** de cada serviço subir pela primeira vez.

## O que precisa existir fora do Pi

Sem isto, a reconstrução trava. Confira agora, não no dia do problema.

O `vault.yml`, a senha dele e a passphrase do LUKS valem para a infra toda:
onde guardar e como copiar está em `docs/fora-da-infra.md`, na raiz do repo.
O que é só do Pi:

| O quê | Onde deve estar |
|---|---|
| Clone deste repo (`infra`) | no seu computador. Se o Forgejo estiver fora, é o único |
| Backups Borg (`arr-*`, `adguard-*`, `fmd-*`) | BorgBase (senha e chave estão no vault) |
| Senha de criptografia do backup do Nextcloud AIO | no KeePass, como em `docs/fora-da-infra.md`. O AIO pede para restaurar |
| Backup do Nextcloud | hoje no celular (Termux), ver #44 |

## 1. Sistema e acesso

1. Instalar Ubuntu Server 26.04 (ARM64) pelo Raspberry Pi Imager, com o usuário
   `ubuntu` e a `p3` reservada **antes do primeiro boot**: `docs/pi.md`,
   "Instalar o Ubuntu".
2. **Tailscale no host.** Antes, remova o nó antigo `nextlevelcode` no console,
   para o nome ficar livre:

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --ssh --hostname=nextlevelcode
   ```

   Confira: `ssh ubuntu@nextlevelcode.<tailnet>.ts.net true`.

   O Pi novo ganha **outro IP Tailscale**. Anote: ele substitui o
   o `ts_ip` do Pi no nameserver do console (DNS do AdGuard) e em toda regra de
   ACL que use o IP em vez de nome ou tag.

3. **LUKS** na partição reservada, como em `docs/pi.md` ("Uma vez, num Pi
   zerado", passo 2), e o UUID novo em `pi_luks_uuid` (`inventory/pi.yml`).
   Deixe o volume aberto e montado em `/mnt/secure`: nesta primeira vez é à
   mão, porque o `secure-unlock` só passa a existir depois que o Ansible roda
   (passo 2 abaixo). Daí em diante, a cada boot:

   ```bash
   ssh -t ubuntu@nextlevelcode.<tailnet>.ts.net secure-unlock
   ```

4. **Roteador:** se o Pi trocou de placa, o MAC mudou. Atualize a reserva do
   DHCP no OpenWrt para o MAC novo (`docs/adguard.md`, "Instalação", passo 6).

## 2. Config, dados e serviços

```bash
ansible-playbook playbooks/pi-completo.yml --ask-vault-pass --limit rpi \
  -e pi_restaurar_tudo=RESTAURAR_PI
```

| Etapa | O que acontece |
|---|---|
| `pi.yml` | Docker com data-root no LUKS, redes, disk-guard, `secure-unlock` |
| restores | Arr, AdGuard e FMD (com o estado do nó do Funnel) voltam do Borg |
| serviços | gluetun, Arr, SearXNG, AdGuard, FMD, Immich, exit-node, Nextcloud |
| `pi-recuperacao.yml` | Forgejo e Vaultwarden em standby, **sem** restore |
| `caddy-pi.yml` | Caddy reserva do `*.lab`, só no IP Tailscale; atende quando o `*.lab` da Cloudflare aponta para o Pi |

Sem o `-e pi_restaurar_tudo=RESTAURAR_PI`, nada é restaurado e os serviços
sobem vazios.

## 3. O que ainda é manual

- **Nextcloud:** na primeira tela do AIO
  (`https://nextlevelcode.<tailnet>.ts.net:8080`), escolha restaurar de um
  backup, informe o repositório (hoje o celular) e a senha de criptografia do
  backup. O domínio (`nextcloud.lab.nextlevelcode.pro`) volta com o backup.
  Depois, ajuste o Talk como em `docs/nextcloud.md` ("Instalação", passo 3).
- **Immich:** sem restore automatizado ainda (#29); o backup no repositório
  compartilhado depende do #31. Até lá, a cópia é a do omarchy.
- **exit node:** a identidade do nó não está no backup. Ele entra como um nó
  novo: remova o `vpn-exit` antigo no console antes, para o nome ficar livre.
- **Nós antigos no console:** remova o que sobrou do Pi anterior.
- **Tailscale DNS:** nameserver do AdGuard para o IP Tailscale novo do Pi.

## 4. Conferir

```bash
ssh ubuntu@nextlevelcode.<tailnet>.ts.net 'docker ps --format "{{.Names}} {{.Status}}" | sort'
dig +short @<ip-tailscale-novo> doubleclick.net
for h in jellyfin immich nextcloud searxng adguard fmd; do
  curl -s -o /dev/null -w "$h: %{http_code}\n" https://$h.lab.nextlevelcode.pro/
done
```

E, por serviço, as conferências do runbook de cada um (`docs/*.md`). Anote a
duração da reconstrução.

## Ensaio no pi-lab

O pi-lab ensaia a reconstrução com os archives reais. Lá ele **não**
restaura a stack Arr (`pi_completo_restaurar_arr: false`), porque o
`arr-stack.yml` subiria em seguida a config de produção, qBittorrent incluído.
O restore do Arr se ensaia sozinho (`docs/arr-stack-restore.md`).

```bash
ansible-playbook playbooks/pi-completo.yml --ask-vault-pass --limit pi_staging \
  -e pi_restaurar_tudo=RESTAURAR_PI
```

Ele restaura os archives reais. No fim, limpe o pi-lab:

```bash
ansible-playbook playbooks/pi-lab-limpar.yml --ask-vault-pass
```

Derruba todas as stacks, apaga os dados restaurados e tira a chave e a senha
do Borg do pi-lab. A base (Docker, redes, imagens) fica, para o próximo ensaio.
