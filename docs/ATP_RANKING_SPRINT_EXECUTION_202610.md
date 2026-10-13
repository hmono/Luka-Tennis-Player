# Execução local — Sprint ATP Ranking #17

12/10/2026, branch `fix/atp-ranking-freshness-202610`, sem merge/push/envio.
O planejamento de abertura permanece em `ATP_RANKING_SPRINT_202610.md` como
registro histórico. Este documento descreve a implementação posterior.

| Issue | Implementação |
|---|---|
| #10 RANK-01 | Captura ITF instrumentada e classificação de falhas; identidade completa e disciplinas com datas explícitas iguais |
| #11 RANK-02 | Calendário versionado, exceções, clock injetável, quatro estados, cutoff BRT, regressão/futuro fail-closed |
| #12 RANK-03 | Recoleta terça–sexta, telemetria do cron/idade e resumo Actions, dry-run default e envio bloqueado |
| #13 RANK-04 | Ledger STALE append-only, deduplicação por edição, aceite/retry/recuperação, persistência antes/depois do provider |
| #14 RANK-05 | Resposta CallMeBot validada, erro/ambiguidade não aceitos, receipt distingue aceite, retry permanente bloqueado |
| #15 RANK-06 | Backfill isolado verificado de 05/10, idempotente, sem evento retroativo; conflitos de revisão/CH exigem revisão |
| #16 RANK-07 | Regressão integrada, fixtures frontend independentes do histórico produtivo, CI de release e gates operacionais |

Commits por issue (somente locais):

| Issue | Commits |
|---|---|
| #10 | `d54cb32`, `9cac7ff` |
| #11 | `589dde6`, `9fa8c5d`, `58b08e0` |
| #12 | `eac2975` |
| #13 | `4656ef1` |
| #14 | `9d89426`, `e554689`, `d73d461` |
| #15 | `638712d`, `d6bd00a` |
| #16 | Commit de fechamento desta execução: `test(rankings): add sprint release checks and verified execution evidence (#16)` |

## Evidências locais

- Suíte Python completa: 168 testes aprovados.
- Suíte frontend: 80 testes aprovados em 5 arquivos.
- `npm run build`: compilação, tipos e exportação estática aprovados.
- Dry-run real após integração, concluído 12/10 às 21:04:51 UTC, exit 0:
  `PENDING_PUBLICATION`, esperada 12/10, observada 05/10, cutoff 15/10 às
  15:00 UTC; `snapshot=unchanged outbox=none message=none`.
- Perfil/DOM corretos; ambas APIs HTTP 200. Nenhum envio ou provider real foi
  chamado; testes de entrega usam mocks somente em memória.
- Snapshot 28/09 preservado integralmente. Snapshot 05/10 acrescentado com
  proveniência verificada. SHA-256 atual dos rankings:
  `f310ca9400d51ede71a58f9d36336d42d1bef0535fba3993cd44b9642d11ebd1`.
- Outbox/receipts sem alteração desde a abertura, SHA-256:
  `8d8922a121b7a2466d1f544a97358d37f692662d82c9ba34e66060d4060b015a`.
- Nenhum ledger real criado: dry-runs não persistem incidentes simulados.
- O checkout original com alterações existentes foi preservado.

## Limites do aceite

O código e testes estão prontos para revisão; a sprint não é declarada encerrada.
Faltam CI/dispatch no GitHub e observação de duas edições consecutivas novas,
com conferência manual oficial. A edição 12/10 não foi confirmada pela ITF na
captura; não foi inventada nem confundida com a data da execução.

A causa exata da falha transitória original de identidade não pôde ser
reproduzida. Capturas posteriores passaram com verificação mais estrita;
telemetria e testes agora distinguem falhas de navegação/carregamento/bloqueio
de atleta incorreto. ATP direto respondeu 403 no diagnóstico, impedindo
comparação independente nessa consulta; a fonte qualificada continua ITF.

O calendário exige extensão revisada antes de 27/10. A estimativa de atraso do
cron usa o slot elegível anterior à criação da run porque GitHub não fornece
timestamp nominal da ocorrência. O risco at-least-once do CallMeBot permanece.
Envio e merge em main não foram liberados.
