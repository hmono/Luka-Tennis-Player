# Homologação — ATP Ranking, Sprint #17 / PR #18

13/10/2026 UTC. Repositório `hmono/Luka-Tennis-Player`, branch
`fix/atp-ranking-freshness-202610`, base desta homologação `c7b1ddd`.
O PR permanece draft; merge e entrega continuam bloqueados.

## Decisão

**NO-GO para merge e ativação nesta homologação.** As correções de confiabilidade
foram implementadas e testadas, mas a documentação oficial disponível não
comprova todas as edições e exceções até 31/12/2026. O calendário mantém o bloqueio
em 26/10. Também permanece pendente a conferência de duas publicações novas
consecutivas completas, conforme os gates da sprint. CI e dry-run finais
passaram; sucesso técnico não remove esses gates.

## Arquitetura e decisões

1. A ITF continua sendo a única fonte qualificada. Identidade, disciplinas e data
   passam pelo gate FRESH/PENDING_PUBLICATION/STALE/SOURCE_ERROR. Erros não criam
   snapshots; pontos ausentes continuam `null`.
2. SOURCE_ERROR usa um ledger independente, append-only, com chave
   `ranking_source_error:<identity|http|timeout|schema|unavailable>:<edição>`.
   STALE preserva a chave legada `ranking_stale:<edição>`. Recuperação acrescenta
   evento, cancela intenções pendentes e não repete alerta da mesma classe/edição.
3. Cada envio segue reserva não retryable + nonce único → persistência local →
   commit/push → provider → resultado local → commit/push. Falha de checkpoint
   interrompe o lote. Timeout, transporte, 408/5xx e resposta ambígua exigem
   revisão; só rejeição 429 admite retry limitado. HTTP 2xx isolado não é aceite;
   aceite explícito é `provider_accepted`, sem prova de entrega no dispositivo.
4. Um journal local recupera a transação de rankings, outbox e recuperação de
   incidentes. Antes de replay, compara estado anterior/planejado para não
   sobrescrever progresso concorrente. O checkpoint publica o bundle completo,
   sem pull/rebase. Falha de coleta continua sendo falha no Actions, mesmo quando
   o ledger é publicado e os incidentes são processados.
5. O grupo `repository-data-writer-main`, checkout atualizado da branch e lock
   local serializam escritores. Nonces distintos e push fast-forward protegem
   clones concorrentes. Entrega CLI exige checkpoint durável e caminhos canônicos;
   workflow escritor exige main e a flag explicitamente habilitada.
6. Somente coleta FRESH bem-sucedida libera mensagens esportivas no workflow.
   Demais resultados usam `--incidents-only`. Tentativas em quarentena aparecem
   como falha operacional em reruns, sem envio automático.
7. Outbox substituída é preservada com `superseded_by`; receipts anteriores não
   são reescritos. Correções comparam com o último conteúdo aceito da mesma
   edição, inclusive quando o rank volta ao valor da semana anterior. Revisão
   A→B→A, cujo hash já existe, e revisão após envio incerto ficam bloqueadas para
   reconciliação, preservando o histórico.
8. Cron terça–sexta 09h BRT mais quinta 12h05 BRT, com telemetria do atraso.
   O cutoff quinta 12h é SLA interno, não garantia ATP. `America/Sao_Paulo`
   permanece. Não se inferem edições de calendários de torneios.

Sem idempotência comprovada do provider não se promete exactly-once. A proteção
prioriza evitar replay: uma interrupção depois da reserva pode deixar uma
mensagem não enviada ou sem confirmação. O registro permanece para revisão.

## Orquestração e resultados

| Frente | Modelo solicitado e usado | Resultado |
|---|---|---|
| Agente 1 — SOURCE_ERROR | GPT-6.1 Sol / high | 188 testes isolados; cinco classes, dedup, recuperação, compatibilidade v1 e claim antes do provider. Commit original `725982e`, integrado como `80ccb92` |
| Agente 2 — calendário | GPT-6.1 Sol / high | 51 testes dirigidos; fontes ATP/ITF registradas, validade mantida em 26/10 por falta de evidência. Original `08dac00`, integrado como `794e71c` |
| Agente 3 — QA independente | GPT-6.1 Sol / high | Leitura e testes, sem editar código. 168 testes na base; quatro P1 reproduzidos; revisão integrada com 222 testes e verificação das correções |
| Revisão arquitetural | GPT-6 Astra / xhigh | Exigiu paths canônicos, recuperação dentro da transação, nonce por claim e preservação de tentativas incertas |
| Revisão adversarial final | GPT-6 Astra / max | Leu o código e reproduziu defeitos independentemente; gate esportivo, quarentena e correções sucessivas corrigidos pelo coordenador |

As três frentes iniciais usaram worktrees separados. A integração ocorreu depois
de suas entregas. A sessão principal coordenou implementação, testes e publicação;
a revisão Astra foi executada por ferramenta, sem alegar troca do modelo da sessão.

## Achados e fechamento

| Severidade | Local / evidência | Correção e validação |
|---|---|---|
| P1 | `providers.py`: aceite seguido de timeout produzia 2 requests | Sem replay de resultado incerto; teste agora verifica 1 request |
| P1 | `update_rankings.deliver` / `incidents.deliver_incidents`: falha de gravação após aceite deixava evento reenviável | Reserva persistida/publicada antes do send; crash e falha de write resultam em 0 reenvios |
| P1 | `update_rankings.yml`: recovery write failure podia publicar outbox sem snapshot | Checkpoint do bundle inteiro, mesmo após coleta falhar; entrega depende do push bem-sucedido |
| P1 | `collect`: segundo write falho perdia intenção permanentemente | Journal recupera 1 snapshot + 1 intenção; terceiro write recupera também ledger |
| P1 | `update_rankings.yml`: coleta bloqueada ainda permitia digest antigo | Output FRESH explícito; SOURCE_ERROR, STALE, PENDING e calendário inválido passam por `--incidents-only` |
| P1 | `main deliver`: quarentena podia aparecer como sucesso sem trabalho | Diagnóstico e exit 1 até reconciliação; não instancia provider quando só há quarentena |
| P1 | `plan_collection`: correção que voltava ao valor da semana anterior não gerava aviso | Compara último conteúdo aceito da mesma edição; teste legado corrigido após reprodução independente |
| P1/P2 | `plan_collection`: duas correções pendentes eram ambas elegíveis | Preserva ambas; marca a anterior `superseded_by`, deixando só a mais recente enviável |
| P2 | `plan_collection`: A→B→A retornava unchanged e mantinha B como vigente | SOURCE_ERROR explícito e bloqueio esportivo; reconciliação manual necessária |
| P2 | `dry_run`: conflito de revisão perdia assessment | Mantém SOURCE_ERROR e preview de incidente, como collect |
| P2 | Preview de correção omitia prefixo “Correção” | Usa exatamente o formatter da entrega, com teste de igualdade da mensagem |
| P2 | Cron anterior detectava corte só na sexta (21h depois) | Execução extra quinta 12h05 BRT e teste de telemetria |

Testes adicionais usam apenas mocks, temporários e repositórios Git locais:
falha antes/depois do checkpoint, dois clones com outbox antiga, rejeição de
paths não canônicos, conflito no replay, bloqueio de escritor local,
compatibilidade e prefixo append-only. Nenhum teste envia WhatsApp.

## Commits e arquivos

- `80ccb92`: SOURCE_ERROR e claims de incidentes.
- `794e71c`: calendário, documentação oficial e casos de expiração/exceções.
- `84ac512`: durabilidade Git, journal, proteção de receipts, outbox preservada,
  provider, locks e cron.
- `7eed1d5`: gate esportivo, visibilidade de quarentena, correções sucessivas e
  paridade do dry-run.
- `816eed2`: preview de correção com o mesmo formatter da entrega.
- Commit documental de fechamento: este relatório e `RANKING_UPDATE_STATE.md`.

Arquivos de produção: `.github/workflows/update_rankings.yml`, `.gitignore`,
`config/atp_publication_calendar.json`, `scripts/update_rankings.py` e módulos
`ranking_alerts/{backfill,collection_transaction,domain,durability,freshness,
incidents,providers,telemetry}.py`. Testes: `test_delivery_state`, `test_durability`,
`test_freshness`, `test_incidents`, `test_providers`, `test_sprint_integration`,
`test_telemetry`, `test_update_rankings`, `test_workflow_rankings`.
Evidência documental: `docs/evidence/atp-publication-calendar-2026-10-13.md`.
Nenhum arquivo frontend nem dado esportivo foi alterado nesta homologação.

## Validação e workflows

- Python final: **222 testes aprovados**.
- Frontend: **80 testes aprovados**, cinco arquivos.
- `npm run build`: compilação, tipos e exportação estática aprovados.
- `git diff --check`: aprovado.
- CI e dry-run GitHub Actions aprovados no código final `816eed2`:

| Execução | Resultado / link |
|---|---|
| CI, pull_request | [Aprovado](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38395032288) |
| Release checks, pull_request | [Python + frontend + build aprovados](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38395032352) |
| CI, push | [Aprovado](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38395023704) |
| Release checks, push | [Aprovado](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38395024121) |
| ITF ao vivo, workflow_dispatch dry-run | [Aprovado, envio ignorado](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38395023002) |

Captura ao vivo em 13/10 às 12:08:16 UTC: identidade B0UF correta, APIs de
simples/duplas HTTP 200 e data explícita 05/10 em ambas; ranks 2250/1417.
Resultado `PENDING_PUBLICATION`, edição esperada 12/10, cutoff 15/10 15:00 UTC,
`snapshot=unchanged outbox=none`, sem recuperação a efetuar. Isso confirma o
funcionamento do gate, não a publicação de 12/10 nem a entrega no WhatsApp.
As quatro etapas de coleta persistente, checkpoint inicial, entrega e checkpoint
final ficaram `skipped`. O [extrato sanitizado](evidence/atp-homologation-dry-run-20261013.txt)
preserva os resultados dessa execução. O commit documental posterior não altera
o código homologado.

SHA-256 dos arquivos produtivos, iguais ao início desta homologação:

| Arquivo | SHA-256 |
|---|---|
| `data/rankings.json` | `f310ca9400d51ede71a58f9d36336d42d1bef0535fba3993cd44b9642d11ebd1` |
| `automation/state/ranking_alerts.json` | `8d8922a121b7a2466d1f544a97358d37f692662d82c9ba34e66060d4060b015a` |

Nenhum ledger real criado, WhatsApp real enviado, secret lido/exposto, flag
ativada ou histórico removido. A variável de liberação não estava configurada
nas consultas somente leitura. O PR permanece draft, sem merge em main.

## Pendências para liberação

1. Obter cronograma/comunicação ATP vigente com edições e exceções de
   27/10–31/12, incluindo alterações posteriores à revisão de março. Fontes,
   limitações de acesso e páginas estão na
   [revisão documental](evidence/atp-publication-calendar-2026-10-13.md).
   Em 27/10 às 03:00 UTC o calendário bloqueia avaliações, inclusive coleta
   da edição de 26/10; não esperar até o cutoff de 29/10 para resolver.
2. Conferir manualmente simples/duplas em duas publicações novas consecutivas,
   sem converter ausência em zero nem recorrer a fonte não qualificada.
3. Aprovação explícita para merge e, separadamente, ativação. Validar configuração
   do provider sem expor credenciais. Esta homologação não autoriza mensagem real.
4. Se houver tentativa incerta em operação futura, verificar o resultado com o
   operador/provider e documentar a reconciliação. Não apagar claim/receipt nem
   reativar retry automaticamente. A→B→A também requer revisão explícita.
