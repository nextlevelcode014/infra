# lxc_flags

Aplica no container o que o Proxmox não deixa um token de API mexer.

## Por que existe

Não é configuração de software — é provisionamento, e provisionamento é do
Terraform. O problema é que o Proxmox reserva **duas** coisas ao `root@pam`:

| Coisa | Mensagem de erro com token |
|---|---|
| Feature flags (`keyctl`) | `changing feature flags (except nesting) is only allowed for root@pam` |
| Device passthrough (`/dev/net/tun`) | `configuring device passthrough is only allowed for root@pam` |

Para feature flags a checagem é literal:

```perl
# PVE::LXC::check_ct_modify_config_perm
return 1 if $authuser eq 'root@pam';
```

O `$authuser` de um token é `terraform@pve!provider`, então ele **nunca** é
igual a `root@pam` — não importa a role que o token tenha. `nesting` é a única
exceção para container unprivileged, e por isso ficou no Terraform; `keyctl` e
o passthrough precisam vir pra cá.

As saídas possíveis eram:
- autenticar o provider do Terraform com `username`/`password` de `root@pam`
- manter o token e aplicar isso fora do Terraform ← **escolhida**

Escolhemos a segunda para não colocar a senha de admin do Proxmox no estado
do Terraform. O custo é que este role existe.

## O que faz

1. Confere que `{{ lxc_tun_device }}` existe no host.
2. Lê `pct config` e descobre o que falta (`keyctl=1`, `dev0`).
3. Para o container **só se** precisar mexer — nem feature nem passthrough são
   hot-plug, só valem no próximo boot.
4. Aplica as duas coisas e sobe o container.

É idempotente: se já está tudo aplicado, nada é parado nem reiniciado.

## Variáveis

| Var | Default | Para que serve |
|---|---|---|
| `lxc_vmid` | — (obrigatório) | vem do inventário do Terraform |
| `lxc_features` | `nesting=1,keyctl=1` | string inteira, porque `pct set` substitui tudo |
| `lxc_tun_device` | `/dev/net/tun` | device do host exposto como `dev0` |

## Uso

O VMID vem como host var do inventário do Terraform (`inventory.tf` publica
`lxc_vmid`). Chamado com loop sobre o grupo `lxc`:

```yaml
- hosts: proxmox
  tasks:
    - ansible.builtin.include_role:
        name: lxc_flags
      vars:
        lxc_vmid: "{{ hostvars[item].lxc_vmid }}"
      loop: "{{ groups['lxc'] }}"
```
