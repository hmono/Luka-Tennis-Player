# Sprint #25 — evidência de integração

Implementação integrada avaliada inicialmente: `69418e730d18c269dd3ee678a79b54cf2316d1db`.
A revisão independente foi concluída após as correções registradas abaixo.
Código final qualificado: `1f7d8dfa1a64043f94809402670e8990a160cfe0`.

## Três frentes e integração

| Frente | Modelo/esforço | Commits originais | Commits integrados |
|---|---|---|---|
| A — coleta | GPT-6.1 Sol/high | `87b62c3`, `b3facf8` | `7d5d0ba`, `f98dc60` |
| B — entrega | GPT-6.1 Sol/high | `b870167` | `1b6a663` |
| C — scheduler | GPT-6.1 Sol/high | `a1f0891` | `23d3307` |
| Integração | sessão coordenadora atual | runtime/provenance/CLI/frontend/QA | `d3cb8b5`, `763406f`, `3175dbc`, `602a31c`, `fe4f5b4`, `b704722`, `69418e7` |

As três frentes terminaram e seus worktrees ficaram limpos antes do cherry-pick.
O coordenador não pode trocar o modelo de sua sessão; os três implementadores
usaram os modelos pedidos, e o revisor independente foi iniciado em GPT-6
Astra/max somente após integração e validação local/remota. Nenhum implementador
substituiu a revisão adversarial independente.

## Checks por SHA

| Check | Resultado | Evidência |
|---|---|---|
| Python + frontend + build no push `69418e7` | success; 279 Python, 81 frontend, Next.js build | [Release checks 38423188051](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38423188051) |
| CI push no mesmo SHA | success; 279 Python e 81 frontend | [CI 38423188161](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38423188161) |
| Dry-run ITF no mesmo SHA | success; NO_NEW_EDITION_OBSERVED, última data 05/10, writes=false, provider_requests=0 | [Dry-run 38423188175](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38423188175) |
| CI e release no merge temporário do PR | success; não houve merge em main | [CI 38423195706](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38423195706), [Release 38423195551](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38423195551) |

Os dois últimos runs fazem checkout do merge sintético `cb828e1`, não são
reclassificados como checkout direto do head. Os três primeiros registram
`event=push` e `headSha=69418e7`. Logs foram conferidos pela API/CLI.
O dry-run é um workflow de validação separado; o workflow legado continuou
`disabled_manually`, sem enable, dispatch produtivo, escrita ou secrets de envio.

Local: primeira regressão integrada, 277 Python; após os dois últimos guards,
24 testes direcionados runtime/entrega passaram. Frontend: 81; build: aprovado.
YAML dos workflows parseado; units/timer systemd verificados pela frente C.
Testes de texto/YAML não substituem interpretação Actions, coberta pelos runs
de validação acima. Os fluxos de envio usam mocks, sem destinatário real.

## Matriz de critérios obrigatórios

| Critério | Evidência automática |
|---|---|
| 1 — oito semanas sem publicação | `test_eight_weeks_without_calendar_one_status_per_period`: 56 dias + reruns, sem diretório de calendário, status por período; A/B também simulam oito semanas |
| 2/3 — nova edição igual e com S/D alterados | runtime `test_delayed_editions_identical_and_changed_ranks`; A `test_eight_weeks_without_edition_then_delayed_equal_ranks` |
| 4 — publicação atrasada vários dias | mesmas simulações, data observada preservada, retries periódicos sem cutoff ATP |
| 5 — datas S/D distintas | A `test_inconsistent_disciplines_and_identity_recover_without_mutating_facts` e parser ITF |
| 6 — identidade/schema | ITF/domain/source e A; runtime conserva bytes esportivos durante SOURCE_ERROR |
| 7 — HTTP/timeout/rate limiting | source/ITF/provider legados; B 429 com backoff/limite, timeout/2xx ambíguo; código de erro sanitizado |
| 8 — concorrência/checkpoints | root `test_two_real_git_executors_send_only_winning_remote_claim`, dois clones/remote bare temporários; uma execução vence e outra recebe ranking_checkpoint_failed; reservas/interrupções cobertas por B/journal |
| 9 — scheduler ausente | C `test_missing_failure_delay_duration_and_main_filter`, watchdog fora de Actions e testes de dispatch limitado |
| 10 — provider falha e recupera | B retry429 e recuperação de ops; runtime retoma digest após identidade normalizada e 429, alerta funciona com provider não configurado |
| 11 — resultado ambíguo | B/root timeout/crash sem replay, disposition possible_loss e alerta independente, próxima edição prossegue |
| 12 — uma vez/semana | ledger status:Monday, fronteira Monday09SP, reruns e oito semanas de runtime |
| 13 — nenhum calendário anual editado | assess_observation default, calendário patched-to-fail em A; runtime isolado sem config após 26/10 |
| 14 — nenhum rank/ponto inferido | somente observação validada; testes null em S/D, schema/identity/date bloqueiam, CH usa fatos vigentes/baseline |

Proteções adicionais de integração: SOURCE_ERROR não libera digest pendente;
falha do provider não impede o canal independente; backlog operacional não
consome o orçamento esportivo; retry usa revisão atual e não fatos retirados;
correções A→B→A conservam snapshots e recalculam CH.

## Integridade e limitações

Diff da sprint em `data/` e `automation/`: vazio. Hashes, iguais à base:

- `data/rankings.json`: `f310ca9400d51ede71a58f9d36336d42d1bef0535fba3993cd44b9642d11ebd1`.
- `automation/state/ranking_alerts.json`: `8d8922a121b7a2466d1f544a97358d37f692662d82c9ba34e66060d4060b015a`.

Os testes provam lógica e recuperação com mocks/temporários, não entrega real,
pontualidade futura do cron, disponibilidade eterna da ITF ou infraestrutura
externa implantada. Fonte alternativa não qualificada e Cloud API não ativadas.
O live dry-run observa a última edição oferecida pela ITF, sem deduzir que ATP
não publicou outra edição. Watchdog/receptor/destino operacional precisam do
provisionamento inicial autorizado descrito na arquitetura e no relatório C.

## Correções após revisão e regressão atual

Código final avaliado: `1f7d8dfa1a64043f94809402670e8990a160cfe0`.

| Correção | Commit | Evidência |
|---|---|---|
| Relógio retrocedendo não pode gravar runtime inválido | `df45ab6` | validação antes da escrita; bytes preservados; próximo ciclo normal recupera. Reproduzido pelo coordenador e reverificado independentemente |
| P1 — thread de forwarding morria após erro SQLite | `7535619` | teste de lock real e retomada automática; revisor reproduziu timeout real de 30s antes/depois |
| P1 — destino operacional respondia accepted:false e era marcado como sucesso | `7535619` | ack explícito booleano true obrigatório; {}, false, 1 e resposta textual não confirmam; intenção permanece pendente |
| P1 — segundo episódio de configuração inválida não gerava alerta | `1f7d8df` | estados de configuração/recovery persistidos por criação de episódio; alertas deduplicam cada episódio, retries antigos não mudam saúde; CLI registra falha sem confundir coleta com entrega |
| P2 — runbooks anteriores ainda prescreviam intervenções humanas | `7535619` | banners de supersessão em RANKING_UPDATE_STATE e gate H2, com link ao runtime autônomo |

| Check após correções, push no SHA final de código | Resultado | Link |
|---|---|---|
| Release checks | **283 Python, 81 frontend, build aprovados** | [38425392690](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38425392690) |
| CI | success | [38425392692](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38425392692) |
| ITF live dry-run | success; 05/10 repetida, NO_NEW_EDITION_OBSERVED, zero writes/requests ao provider | [38425392561](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38425392561) |

Metadados destes três runs conferidos: `event=push`,
`headSha=1f7d8dfa1a64043f94809402670e8990a160cfe0`. Regressão local anterior às
últimas mudanças de configuração: 282 Python; os dois testes dirigidos de
configuração também passaram. A suíte remota completa acima inclui a última
regressão, sem somar contagens de candidatos para fabricar um total.

A decisão final e as reproduções independentes constam em
[sprint25-independent-review.md](sprint25-independent-review.md). Commits
posteriores somente documentais não alteram o código deste SHA avaliado.

## Gate final

Revisão independente GPT-6 Astra/max: três P1 reproduzidos, corrigidos e
reverificados; nenhum P0/P1 conhecido aberto. Relatório original `be0afef`,
integrado como `b8f5d7c`. Um P2 residual de atribuição dos slots 12:00/12:17
de segunda-feira não bloqueia a coleta/entrega nem a recuperação automática.

**GO técnico para merge com envio desligado. NO-GO para ativação.** Não houve
merge; PR permanece draft. `main` continua em `833eafa`; workflow legado
`disabled_manually`; flag/secrets inalterados; nenhum WhatsApp real.
O watchdog externo e o receptor/destino idempotente estão implementados, mas
não provisionados. Sem essa configuração inicial autorizada, a supervisão
independente e os alertas operacionais não operam em produção. Não se atribui
sucesso de implantação ou recebimento a testes com mocks.
