# 0017. Um timer no Proxmox repõe a ACL do lab depois de cada destroy

- **Status:** Aceita
- **Data:** 2026-10-24

## Contexto

O repo `lab` cria VMs no Proxmox com o usuário `lab@pve`, isolado da
produção por permissão: `PVEVMAdmin` só no pool `lab` e numa ACL em cada
`/vms/<id>` da faixa 900–999. A ACL por VMID é necessária porque, no
create, o Proxmox confere `/vms/<id>` antes de a VM estar no pool (`403
Permission check failed (/vms/900, VM.Config.Options)`).

O destroy de uma VM apaga as ACLs de `/vms/<id>`, com ou sem purge: o state
do exercício 02 do roadmap tinha `purge_on_destroy = false` nas duas VMs, e
as ACLs da 990 e da 991 sumiram mesmo assim (o `purge` só limpa jobs de
backup, replicação e HA). Cada `terraform destroy` no lab, então, inutiliza
aquele VMID até alguém repor a ACL como root, e o lab destrói o tempo todo.

## Decisão

O role `proxmox_host` instala o `lab-acl.timer`, que a cada minuto repõe o
`PVEVMAdmin` do `lab@pve` em cada `/vms/<id>` da faixa 900–999 que estiver
sem ele. O script só grava o que falta.

## Alternativas descartadas

- **Repor à mão depois de cada destroy:** é um SSH como root por destroy, e o
  lab foi feito para destruir à vontade. O passo seria esquecido, e o 403 só
  aparece no próximo `apply`, longe da causa.
- **ACL em `/vms` com propagação:** um papel só, que o destroy não apaga,
  mas valeria para toda VM e container do host, incluindo os LXCs de
  produção (200–299). É exatamente a separação que o `lab@pve` existe para
  manter.
- **`purge_on_destroy = false` no Terraform do lab:** foi a primeira
  tentativa e não protege a ACL (ver Contexto).

## Consequências

- O infra passa a configurar uma coisa do lab no host. A faixa e o papel
  ficam no `defaults` do `proxmox_host` e no `docs/proxmox.md` do lab: mudar
  num é mudar no outro.
- Entre o destroy e a próxima execução do timer (até ~1 min) o VMID ainda
  recusa o create: um `-/+` que mantém o VMID pode falhar uma vez, e rodar o
  `apply` de novo resolve.
- Um VMID da faixa 900–999 sempre tem a ACL do `lab@pve`, exista a VM ou
  não. Nada de produção pode morar nessa faixa, que já era a regra.
