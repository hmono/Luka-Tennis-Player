# Abertura — Sprint ATP Ranking #17

Preparação: 12/10/2026 UTC. Execução planejada: 13–23/10/2026, 9 dias úteis,
39 h; observação passiva de publicações oficiais fora dessa estimativa.

Issue coordenadora: https://github.com/hmono/Luka-Tennis-Player/issues/17.
Branch: `fix/atp-ranking-freshness-202610`.
Base publicada examinada: `833eafa6702bc5be14349a4efcead924c18fa55f`.

## Diagnóstico de abertura

- A fonte ITF já foi qualificada e implementada. Pontos não publicados são
  `null`; não reconstruir a fonte nem imputar pontos.
- O histórico publicado contém a edição de 28/09/2026, simples 2237 e duplas
  1401. Isso é evidência histórica, não confirmação do ranking atual.
- A execução agendada de 06/10 teve conclusão técnica `success`, iniciou às
  15:39:17 UTC para cron previsto às 09:00 UTC: atraso de 6h39min17s.
  Evidência: https://github.com/hmono/Luka-Tennis-Player/actions/runs/37489325767.
- A coleta rejeita uma data anterior à última persistida, mas não compara a
  edição retornada com a edição esperada e seu cutoff. Repetir uma edição
  antiga pode continuar retornando `unchanged` com sucesso indefinidamente.
- Digest por nova edição, idempotência da mesma edição, correções, baseline de
  career high e persistência antes/depois do provider já existem. Preservá-los.
- O provider aceita qualquer HTTP 2xx sem validar o corpo. O receipt atual
  representa aceite do provider, não comprovação de entrega ao dispositivo.
- Ainda faltam estados de freshness, calendário com exceções, alerta STALE,
  recoletas e resumo operacional de idade da fonte/atraso do cron.

O checkout original em `/home/ono/Luka-Tennis-Player` contém alterações locais
e um protótipo anterior à versão publicada. Foi preservado integralmente;
o trabalho da sprint usa o worktree `/home/ono/luka-atp-ranking-sprint`.

## Frentes dos agentes

| Frente | Trabalho de abertura | Resultado |
|---|---|---|
| Escopo | Conferir fonte aprovada, domínio, UI e documentação | Freshness é a lacuna principal; documentação operacional de setembro precisa atualização |
| Diagnóstico | Conferir execução publicada e tentar coleta somente leitura | Não confundir sucesso do job ou HTTP 200 com edição oficial confirmada |
| Release | Ler RANK-02 a RANK-07 e executar regressão existente | 112 testes Python de ranking aprovados na base publicada |

## Backlog e sequência

| Ordem | Issue | Esforço | Entrega e dependências |
|---|---|---|---|
| 1 | [RANK-01 #10](https://github.com/hmono/Luka-Tennis-Player/issues/10) | 4 h | Telemetria UTC, data por disciplina, status/cache quando disponíveis; confrontar fontes sem fallback |
| 2 | [RANK-02 #11](https://github.com/hmono/Luka-Tennis-Player/issues/11) | 7 h | Calendário versionado, exceções, clock injetável; FRESH/PENDING_PUBLICATION/STALE/SOURCE_ERROR; depende de 01 |
| 3 | [RANK-03 #12](https://github.com/hmono/Luka-Tennis-Player/issues/12) | 4 h | Cron terça–sexta 12h UTC, resumo de atraso e idade; depende de 02 |
| 4 | [RANK-04 #13](https://github.com/hmono/Luka-Tennis-Player/issues/13) | 8 h | Um STALE por edição esperada após quinta 12h BRT; intenção e aceite persistidos, recuperação auditável; depende de 02–03 |
| Paralela | [RANK-05 #14](https://github.com/hmono/Luka-Tennis-Player/issues/14) | 5 h | Contrato de aceite CallMeBot, 200+erro/204/401/429/5xx/timeout e respostas ambíguas |
| Após 01 | [RANK-06 #15](https://github.com/hmono/Luka-Tennis-Player/issues/15) | 5 h | Verificar lacuna de 05/10 nas duas disciplinas; backfill somente com evidência completa, sem envio retroativo automático |
| Integração | [RANK-07 #16](https://github.com/hmono/Luka-Tennis-Player/issues/16) | 6 h | Testes, CI, dry-run real, edição oficial verificada e observação de dois ciclos quando disponíveis |

13–14/10: diagnóstico e modelo de freshness. 15–16/10: recoleta, STALE e
validação inicial. 19–20/10: provider, regressão e edição de 19/10 se publicada.
21–22/10: lacuna 05/10 e documentação. 23/10: revisão das evidências de aceite.

## Validação inicial

Comando seguro executado na base publicada:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/ranking_alerts
```

Resultado: 112/112 testes aprovados. Isso é baseline de regressão, não aceite
das funcionalidades ainda pendentes.

O primeiro `python3 scripts/update_rankings.py dry-run --source itf` falhou com
`error=ranking_source_incomplete` num ambiente sem Playwright/Chromium. Não
interpretar essa falha de dependência como prova de atraso da ITF.
Uma consulta HTTP direta retornou 200 para perfil e endpoints ITF, mas os
endpoints não forneceram JSON decodificável; não equivale à captura do navegador
qualificado. O perfil ATP retornou 403. Nenhuma edição nova foi confirmada por
essas consultas, e nenhum fallback foi habilitado.

Após instalar Playwright/Chromium em ambiente isolado em `/tmp`, o dry-run
canônico foi repetido em 12/10/2026; resultado conferido às 20:45:53 UTC:

```sh
PLAYWRIGHT_BROWSERS_PATH=/tmp/luka-atp-sprint-browsers \
  /tmp/luka-atp-sprint-venv/bin/python scripts/update_rankings.py dry-run --source itf
```

Resultado: exit 1, `error=ranking_source_identity_mismatch`. A validação de
identidade bloqueou a observação; a edição ITF atual continua não verificada.
Investigar a captura/identidade em RANK-01 antes de atribuir o incidente a lag
editorial ou cache. Não relaxar a validação para obter um resultado positivo.
Não houve envio, dispatch ou alteração de estado. SHA-256 antes/depois iguais:

| Arquivo | SHA-256 |
|---|---|
| `data/rankings.json` | `2cea540ff13f0a114560b1b14e3a091391458c7af5dee074d2e5dc87399dbcd6` |
| `automation/state/ranking_alerts.json` | `8d8922a121b7a2466d1f544a97358d37f692662d82c9ba34e66060d4060b015a` |

Revisar também `lib/__tests__/career.test.ts`: o teste de bootstrap importa os
dados reais e espera histórico vazio, embora a base já contenha um snapshot.
Essa incompatibilidade foi identificada por leitura; executar a suíte frontend
e substituir a dependência de dados produtivos por fixtures em RANK-07.

## Gates de implementação e publicação

- No início, executar apenas diagnóstico/dry-run, sem provocar envio.
- Falha, parcialidade ou datas contraditórias não alteram dados válidos.
- Preservar snapshots, outbox, receipts, secrets e trilha de auditoria.
- Preservar `repository-data-writer-main` e a ordem collect → persistir intenção
  → commit/push → provider → persistir receipt → commit/push.
- Se houver ledger de incidentes, incluí-lo no commit/push antes e depois do
  envio. Chave STALE deve incluir tipo e edição esperada, não só snapshot.
- Cutoff em `America/Sao_Paulo`; admitir exceções oficiais ao calendário.
- Só liberar novo envio após testes, CI, dry-run ao vivo e uma edição oficial
  completa verificada. Observar duas publicações consecutivas quando disponíveis.
- Rollback: desabilitar schedule, manter dispatch dry-run, preservar evidências;
  reativar após correção e validação.

Não foram habilitadas recoletas, novos envios ou alterações de dados na abertura.
Os itens #10–16 permanecem pendentes de implementação/aceite.
