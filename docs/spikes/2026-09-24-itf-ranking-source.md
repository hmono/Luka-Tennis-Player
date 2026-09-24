# Spike — fonte ITF para rankings ATP

Status: **go** (aprovado em 2026-09-24)  
Escopo: substitui a Fase A da `docs/ATP_RANKING_SOURCE_RECOVERY_SPEC.md`

## Evidência

Probe read-only em `ubuntu-latest`, Playwright + Chromium, mesmo método de
acesso de `scripts/update_career.py`. Endpoint
`/tennis/api/PlayerApi/GetPlayerOverview?circuitCode=MT&matchTypeCode={S|D}&playerId=800625103`.

| Campo | Singles | Doubles |
|---|---|---|
| Nome | `ATP Singles Ranking` | `ATP Doubles Ranking` |
| Rank | 2205 | 1460 |
| Data oficial | 21 September 2026 | 21 September 2026 |
| Career high | 1827 (01 December 2025) | 1407 (22 June 2026) |
| Pontos | ausente | ausente |

Runs: 36003388449 e 36003657264 (GitHub Actions, 2026-09-24).
Payloads: 406 bytes (S) e 241 bytes (D). Cópia sanitizada em
`tests/ranking_alerts/test_itf_source.py`.

O texto renderizado do DOM exibiu valores intermediários (2200/378/1823)
durante a animação de contagem. Somente a API é fonte; o DOM nunca é lido.

## Gates (spec §5)

| # | Gate | Resultado |
|---|---|---|
| 1 | Identidade ↔ ATP `B0UF` | Crosswalk versionado `ITF_PLAYER_ID = 800625103` em `itf_source.py`; título da página validado a cada coleta |
| 2 | Singles e doubles individual | OK |
| 3 | Posição e pontos | Rank OK; pontos não publicados → `points: null` (decisão D1) |
| 4 | Data oficial | OK, publicação de segunda-feira |
| 5 | Cobertura >2000 | OK (2205) |
| 6 | Não classificado | Resposta bem formada sem entrada ATP → `unranked`; resposta malformada → falha |
| 7 | Duas publicações | Pendente; primeira coleta agendada sem alerta (decisão D4a) |
| 8 | Runner GitHub | OK |
| 9 | Auth/custo/quota | Nenhum; mesmo risco de ToS já aceito para `career.json` |
| 10 | Payload estável | OK |

## Decisões (2026-09-24)

- D1: `points` passa a ser opcional em todo o domínio; nunca inferido, nunca 0.
- D2: acesso via Playwright com UA de navegador, exceção explícita para ITF,
  já praticada por `update_career.py`. A cláusula da spec permanece para ATP.
- D3: baseline de career high preenchido com os valores ITF acima.
- D4: schedule ativado imediatamente; primeiro snapshot não gera alerta.
- D5: caminho ATP PDF e runner macOS removidos.
