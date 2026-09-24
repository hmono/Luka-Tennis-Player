# Estado — atualização semanal de rankings

Atualizado: 2026-09-24 (sessão fable)

## Decisão

Fonte produtiva: ITF player profile API (`RANKING_SOURCE=itf`). Go registrado
em `docs/spikes/2026-09-24-itf-ranking-source.md`. Caminho ATP PDF e runner
macOS removidos.

## Pendências

| Item | Responsável | Prazo |
|---|---|---|
| Revisar e mesclar o PR da branch `claude/loving-planck-xg0ery` | ono | antes de terça 09:00 UTC (29/09) para a primeira coleta agendada |
| Confirmar secrets `CALLMEBOT_PHONE` e `CALLMEBOT_API_KEY` no repositório | ono | antes de terça 29/09: todo snapshot gera digest, o passo `deliver` falha sem os secrets |
| Gate 7 (duas publicações): conferir manualmente o snapshot de 28/09 contra a ATP | ono | após a run de 29/09 |

## Operação

- Agenda: terça 09:00 UTC (`update_rankings.yml`), runner `ubuntu-latest`.
- Manual: `workflow_dispatch` com `mode=dry-run` valida a fonte sem gravar.
- Mensagem: digest semanal em toda nova publicação (rank, delta, career high); `Correção` em revisão já entregue.
- Rollback: desabilitar o schedule; snapshots e outbox permanecem para auditoria.
