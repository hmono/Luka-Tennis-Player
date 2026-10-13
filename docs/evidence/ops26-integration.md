# OPS-04 — integração isolada e gate de preparação

Data: 13/10/2026 UTC. Base preservada: `944e4174444a32ba7182db62f644e5a433dcee67`.
Branch de integração: `ops26/integration`, worktree `/home/ono/ops26/integration`.

**HOST_NO_GO, SINK_NO_GO, STAGING_NO_GO, ACTIVATION_NO_GO.** A sprint entrega
código, testes e documentação revisáveis. Não entrega infraestrutura instalada
ou homologada. Não existe autorização de instalação/ativação nesta execução.

## Execução e ownership

Três agentes novos GPT-6.1 Sol/high foram iniciados simultaneamente. Cada um
escreveu somente no worktree e arquivos designados. Os agentes de implementação
entregaram patches dos arquivos compartilhados; somente o coordenador os aplicou.
Testes locais foram serializados e executados em `nice -n15` após o preflight
preliminar. Não se reaproveitou um implementador como revisor independente.

| Frente | Commit original local | Commit incorporado | Resultado |
| --- | --- | --- | --- |
| A / #27 | `71a1acc` | `c0b74e2` | HOST_NO_GO; relatório quantitativo read-only |
| B / #28 | `d7003b9` | `d25614c` | 24 testes da proposta passaram; auditoria App/watchdog |
| C / #29 | `9174d0a` | `27a2864` | 17 testes da proposta passaram; SINK_NO_GO |

Os commits incorporados preservam as entregas dos agentes, incluindo as propostas
de patch. O commit seguinte aplica o código e harmoniza os contratos; portanto
os commits de testes isolados não representam, sozinhos, um runtime integrado.

## Avaliação independente do coordenador

Foram lidos os relatórios e os dois patches de código antes de aplicar as mudanças.
O coordenador repetiu observações read-only às **19:34:28 UTC**: disco raiz 94%,
cerca de 3,2 GiB livres; MemAvailable 5.831 MiB; CPU PSI some avg300 8,10%;
I/O PSI full avg300 9,93%; `fpa-app.service` active/running, NRestarts=0,
MemoryCurrent 100.204.544 bytes e MemoryPeak 114.733.056. Units ATP `not-found`.
Isso confirma que a disponibilidade de RAM não remove os bloqueios de disco/I/O.

A frente A examinou 260 amostras sysstat já existentes e observou load5 máximo
3,68 em 2 vCPUs, await máximo 695,96 ms e apenas 3,14 GiB livres ao fim de sua
janela. O orçamento proposto é 384 MiB RAM, 0,2 CPU e 512 MiB disco. Após a
reserva de disco sobrariam 2,64 GiB, contra mínimo proposto de 5 GiB **mais**+crescimento FP&A desconhecido. Déficit mínimo de 2,36 GiB + crescimento.
Esses limites são critérios conservadores da sprint, não SLA de hardware.

O parecer foi acatado: sem preparação de instalação em caminhos de sistema,
sem package manager, limpeza, criação de usuários, reload ou start de serviços.
A alternativa proposta é um host persistente existente separado, com preflight
e autorização próprios; não foi escolhido/provisionado um host alternativo.

## Alterações integradas e justificativa

- GitHub App: escopo explícito de repositório e Actions read/write condicionado
  à recuperação; validação de expiração/chave e assinatura RSA; renovação única
  em GET 401; POST nunca repetido silenciosamente; cooldown 403/429 persistido.
- Watchdog: observação/reserva serializadas, espera de lock finita, falhas de
  estado sanitizadas, ack booleano estrito. Modo desligado/dry-run não emite
  token de instalação App nem cria estado. Recuperação continua limitada a duas
  reservas por slot e jamais habilita um workflow desabilitado.
- Inbox: WAL/FULL, fechamento explícito de conexões e commit anterior ao ack;
  quatro workers, backlog oito, timeout de socket, overload503, storage503,
  conflict409 e validação de framing/JSON/autenticação.
- Integração dos dois saltos: uma função compartilhada valida HTTPS, ausência
  de userinfo/fragmento e hostname; bearer obrigatório; resposta precisa conter
  `accepted: true` booleano e `event_id` correspondente. O contrato ampliado
  está nos exemplos e runbook; nenhum sink real preexistente foi presumido.
- Templates systemd: inbox usa principal próprio, sem acesso à chave App;
  watchdog/inbox limitados a 128/256 MiB, CPUQuota=10% cada, TasksMax=32,
  Nice=15, IOWeight=10, capabilities vazias, dispositivos privados e proteções
  de kernel/cgroups. **Somente templates no repositório**, não limites aplicados
  na VM. IOWeight é prioridade relativa, não quota de bytes/IOPS/disco.
- [Runbook](../ATP_OPS26_RUNBOOK.md): preparação desligada, dependências uma vez,
  backup consistente SQLite, rollback sem retroceder estado, retenção sem perda
  das identidades, supervisão fora do host e gates distintos.
- Teste integrado de perda de ack em ambos os saltos: reinício de watchdog,
  inbox e sink SQLite sintético conserva um evento e resolve o replay sem duplicar.

Nenhum arquivo de workflow, dado esportivo, ledger de produção ou frontend foi
alterado. O checkout primário sujo foi preservado integralmente.

## Validação realizada

- `systemd-analyze verify` nos três templates: exit0 antes e depois do hardening.
  É verificação estática, não ensaio de permissões reais, quotas ou isolamento.
- Dry-run real anônimo às **19:42:57 UTC**, ambiente limpo, flags `false`:
  `workflow_state=disabled_manually`, `released=false`, `recoveries=0`,
  `alerts_accepted=0`, incidente `WORKFLOW_DISABLED`; exit1 esperado. Diretório
  de estado inexistente antes/depois. Somente leitura de metadados GitHub.
- A API autenticada existente de manutenção também confirmou workflow
  `disabled_manually` e nenhuma variável `ATP_*` de repositório. Essa observação
  não comprova valores de environments/organização nem credenciais App futuras.
- Regressão Python integrada: **312 testes passaram**, 133,748 s unittest /
  134,63 s elapsed, CPU agregada 5%, pico RSS 35.440 KiB, nice15. Comando:
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/ranking_alerts -q`.
  Métricas são do processo de teste e não certificam consumo futuro do serviço.
- No código integrado `25c8a94`, a [regressão remota](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38457571977)
  passou: **312 Python, 81 frontend e build Next/export**, concluída às
  19:47:53 UTC. O [CI do PR](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38457571955)
  também passou. O [PR #32](https://github.com/hmono/Luka-Tennis-Player/pull/32)
  permanece draft, sem merge. Nenhum dependency install/build ocorreu na ONO.
- Revisão independente iniciada após integração e checks, em novo agente
  **GPT-6 Astra/max**, worktree exclusivo `ops26/independent-review`.

O CI remoto usa os workflows existentes `CI` e `ATP Ranking Release Checks`
no PR de staging. Eles executam testes/build, sem deploy. O workflow de deploy
é restrito a push em main; o workflow ATP desabilitado não é habilitado ou
despachado. Não se executa `collect-and-deliver` ou provider real nesta sprint.

## Riscos e bloqueios restantes

Zero risco externo foi considerado resolvido apenas por mocks. Permanecem:
capacidade da ONO, picos/saúde FP&A incompletamente conhecidos, GitHub App/chave,
TLS/DNS/renovação, destino operacional idempotente e visível ao operador,
monitor externo do host/watchdog/inbox, backup/restore e controle de crescimento.
Os dados SQLite crescem sem retenção automática segura; não apagar pendências
ou IDs para esconder esse bloqueio. FIFO do forwarding pode atrasar eventos
novos quando os primeiros 100 falham permanentemente (P2 registrado por C).
O watchdog também seleciona somente oito pendências ordenadas por ID; falhas
permanentes no começo podem atrasar as demais. Ambos requerem política de
progresso/capacidade antes da operação contínua.

Falhas transitórias simuladas têm recuperação automática; revogação de chave,
falha de disco/host, alteração do contrato do sink e manutenção de capacidade
ainda exigem responsáveis operacionais. Não há passo humano por edição/semana,
mas tampouco se declara operação perpétua sem manutenção de infraestrutura.

A revisão OPS-05 registra a classificação consolidada e as reproduções. P0/P1
de código devem ser corrigidos antes de aprovação técnica; bloqueios externos
mantêm staging/ativação fechados. Nenhum merge em main foi autorizado/executado.

## Correções exigidas pela revisão independente

O revisor reproduziu dois P1 com fixtures novas sobre `25c8a94`: histórico
retido de 500 runs tornava a observação permanentemente indisponível; um novo
episódio disabled após recuperação/restart perdia seu alerta por ID constante.
O coordenador corrigiu ambos em `3cb3e8d`: filtro `created` de dois dias com
overflow recente ainda fechado; identidade de episódio/generation persistida,
preservada durante indisponibilidade contínua e renovada após state active.
O parâmetro de intervalo é documentado na [API oficial de workflow runs](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-workflow).
As duas reproduções passaram localmente após a correção (2,182 s), assim como
os 25 testes focados do scheduler (29,484 s, nice15).

Um terceiro P1 foi reproduzido pelo revisor com HTTP loopback: o timeout de
inatividade permitia corpo com bytes lentos manter a única thread de forwarding
ocupada sem fim. `3cb3e8d` move a requisição a um filho Python transitório com
deadline total no pai e kill/wait, incluindo DNS/connect/headers/body. Não usa
threads abandonadas, secrets em argv ou arquivos temporários; erros/status e
headers de cooldown são reduzidos a campos sanitizados. Novo arquivo de runtime:
`scripts/ranking_alerts/http_transport.py`. O custo extra de processo deve ser
medido em staging; as cotas propostas não equivalem a essa homologação.
O JSON passa a usar UTF-8 para evitar que escape ASCII multiplique payload
Unicode válido além do limite do próximo inbox (P2 encontrado pelo revisor).

A reverificação independente de `3cb3e8d` (cherry-pick `bf53221` do revisor)
passou em **seis testes adversariais, 20,176 s, nice15**: dois P1 originais,
fronteira de 500/501 runs recentes, episódio estável durante falha de API/restart
e perda de ack, deadlines reais em cabeçalho/corpo HTTP lentos com filho
recolhido e próxima requisição funcionando, mais 2.000 caracteres `é` enviados
a um inbox loopback com limite de 8 KiB. Credenciais e endpoints são sintéticos.
O revisor confirmou **nenhum P0/P1 de código conhecido aberto**; Unicode P2
também corrigido. Starvation/crescimento/idade da fila e provisionamento externo
continuam como riscos/bloqueios, sem alterar os gates NO_GO.

Uma sétima regressão independente passou (0,290 s): HTTP429 real em loopback
preserva status e headers de cooldown ao atravessar o worker, sem propagar
corpo/URL/token/header privado; HTTP302 não segue `Location`. As sete regressões
e o [relatório final independente](ops26-independent-review.md) foram integrados
no commit `52daaab`. Parecer final: **TECHNICAL_GO** para o código corrigido
`3cb3e8d`, mantendo **STAGING_NO_GO / ACTIVATION_NO_GO**.

O dry-run real anônimo foi repetido com o novo transporte às **20:03:10 UTC**:
`disabled_manually`, `released=false`, zero alertas/recuperações, exit1 esperado
e nenhum diretório de estado criado. Nenhuma credencial App foi emitida.
Os resultados da regressão final no head do PR são registrados em
[checks do PR #32](https://github.com/hmono/Luka-Tennis-Player/pull/32/checks)
e nas issues [#30](https://github.com/hmono/Luka-Tennis-Player/issues/30) e
[#31](https://github.com/hmono/Luka-Tennis-Player/issues/31), sem confundir o
SHA do código revisado com commits posteriores de testes/documentação.
