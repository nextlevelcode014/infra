# 0011. gluetun no `latest`, pela lista de servidores

- **Status:** Aceita
- **Data:** 2026-10-19

## Contexto

O gluetun publica tag de major (`v3`), então pela 0010 ele não podia ficar em
`latest`, e o PR que aplicou a 0005 nas stacks do Pi o pôs na `v3` (a versão
v3.41.3, de julho). O `latest` dele é a branch principal, reconstruída a cada
mudança.

O ensaio no pi-lab mostrou que a versão publicada mal conecta. A lista de
servidores da ProtonVPN (endereço e chave de cada um) vem **dentro da
imagem**, e os servidores mudam: a lista de julho já não responde. Medido no
pi-lab, mesma chave, três reinícios de cada:

| Imagem | Servidores tentados até ficar healthy | Tempo |
|---|---|---|
| `v3` (v3.41.3) | 21, 22, 30 | 51 s, 61 s, ainda unhealthy aos 81 s |
| `latest` | 1, 1, 1 | ~10 s |

O `docker compose up --wait` desiste no primeiro `unhealthy`, então o
playbook do gluetun falhava, e a VPN ficava um minuto fora a cada reinício.

O gluetun sabe atualizar a lista sozinho (`UPDATER_PERIOD`), mas para a
ProtonVPN isso exige e-mail e senha de uma conta Proton dentro do container,
e a de servidores pagos exige a conta paga.

## Decisão

`gluetun_image` (o gluetun do Pi e o do exit node) fica em
`qmcgaw/gluetun:latest`. A imagem nova já traz a lista atual, e o
`pi-atualizar.yml` a renova junto com o resto.

É uma exceção à condição 1 da 0010 (sem tag de major publicada): para um
cliente de VPN, a versão publicada é a que não conecta. A condição 2 (volta
barata) vale: o gluetun não guarda estado, e o registro de versões do
`pi-atualizar.yml` guarda o digest de antes para voltar.

## Alternativas descartadas

- **`v3` com `UPDATER_PERIOD`:** põe a senha de uma conta Proton no Pi, num
  container. Uma conta grátis descartável só traz servidores grátis.
- **Digest de um build recente da branch principal:** reproduzível, mas a
  lista envelhece do mesmo jeito; só adia o problema e vira bump à mão.
- **Só o gluetun do Pi no `latest`, o exit node na `v3`:** o exit node
  conecta hoje porque o servidor é fixo (`exit_node_server_hostnames`), mas
  quebra no dia em que a ProtonVPN trocar a chave dele; e as duas stacks
  deixariam de compartilhar a variável (0005).

## Consequências

- Um `pi-atualizar.yml` pode trazer um gluetun da branch principal com
  mudança que quebra; o resumo do fim mostra o que mudou, e o log tem o
  digest de antes.
- Se um dia a lista também envelhecer no `latest` (o projeto parar de
  publicar), o caminho é o `UPDATER_PERIOD`, reavaliando a conta Proton.
- A tabela de imagens em `latest` da 0010 passa a ter o gluetun, por esta.
