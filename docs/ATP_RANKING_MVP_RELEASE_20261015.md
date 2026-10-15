# ATP Ranking — MVP de operação automática (15/10/2026)

**Status:** sprint de simplificação APROVADA; **produção NÃO ativada**.
**Issue:** [#42 — MVP ATP](https://github.com/hmono/Luka-Tennis-Player/issues/42).
**Base:** `main@944e4174444a32ba7182db62f644e5a433dcee67`.
**Atleta:** Luka Bojicic Ono · ATP `B0UF` · ITF `800625103`.
**Arquitetura escolhida:** ITF → GitHub Actions → CallMeBot/WhatsApp, com snapshots e receipts no GitHub.

## 1. Resultado de produto

Entregar um WhatsApp semanal, sem ação humana recorrente, mostrando a data da última edição de **simples e duplas** validada. Ao observar uma nova edição válida, enviar **um digest por edição** com posições, variação e career high quando verificáveis. Pontos que a ITF não fornece permanecem `null`; não inferir ausência de edição ATP a partir da repetição da data ITF.

**Sem nova infraestrutura.** Não usar VM ONO, watchdog externo, inbox próprio, Cloudflare Workers/D1, GitHub App ou cron duplicado. Cloudflare Pages continua apenas como site, sem mudança de infraestrutura neste MVP.

## 2. O que já está pronto

A versão em `main`, oriunda do PR #18, já contém coleta ITF, validação por atleta/modalidade/data, snapshots imutáveis, deltas, career high, Git checkpoint, outbox e receipts, política conservadora de envios ambíguos, resumo semanal e testes automatizados. **Reaproveitar, não reimplementar.**

Situação antes da sprint: `.github/workflows/update_rankings.yml` está confirmado como `disabled_manually` na última verificação humana; **verificar novamente antes de qualquer liberação**. A flag `ATP_RANKING_DELIVERY_ENABLED` não estava habilitada. O runtime possui intenções operacionais separadas do digest esportivo, hoje acopladas a um sink externo ainda não provisionado.

## 3. Backlog — somente três pacotes

| Código | Prioridade | Entrega | Aceite |
| --- | --- | --- | --- |
| MVP-01 | P0 | Pré-flight sem escrita: fonte ITF, identidade, S/D, presença dos secrets CallMeBot, GitHub Actions e estado de dados/receipts; `--dry-run` real em runner isolado | Estado documentado, nenhuma gravação/mensagem, blockers explícitos |
| MVP-02 | P0 | Ajuste pequeno no workflow/runtime: sem sink obrigatório; incidentes por logs/Actions summary e status, sem backlog operacional ilimitado; polling Seg–Sex 09h BRT | Dados esportivos/ledger conservados, testes verdes e retry/replay seguros |
| MVP-03 | P0 | PR draft + revisão focada, CI, checklist de merge/ativação, validação de WhatsApp autorizada posteriormente e rollback | GO/NO-GO separados para code, merge e live delivery |

**Estimativa ativa:** cerca de 6–8 horas, excluídos tempos de espera por publicações, GitHub Actions e validação do primeiro envio. **Sem subagentes ou nova sprint de arquitetura obrigatórios.**

## 4. Contrato técnico mínimo

### Publicação, periodicidade e mensagens
- **Agendamento proposto:** `0 12 * * 1-5` (09h BRT durante o regime atual de UTC-3); GitHub cron é best effort e pode atrasar ou ser omitido.
- **Resumo semanal:** um status por período semanal, mesmo quando a ITF não atualizar, com data do ranking observado e timestamp da consulta; uma falha de fonte não vira atualização fictícia.
- **Nova edição:** até um digest por data válida; revisões, dados antigos e estado legado não podem reabrir um envio já aceito ou ambíguo.
- Caso ocorram status semanal e digest da edição na mesma semana, podem existir duas mensagens **identificadas**, não duplicações de uma mesma intenção.

### Segurança e estado
- Conservar `data/rankings.json`, `automation/state/ranking_alerts.json`, journal, `ranking_delivery.json`, `ranking_runtime.json`, snapshots, CH, nonces, outbox e receipts; sem migração destrutiva.
- `dry-run` nunca grava ou contata CallMeBot. `SOURCE_ERROR`, identidade incompatível e datas inconsistentes não autorizam digest novo.
- Resposta CallMeBot `provider_accepted` não equivale a recebimento no dispositivo. Timeout/reserva incerta → `delivery_unknown / possible_loss`, sem replay automático.
- Ausência de sink externo não deve impedir a **entrega esportiva**. No MVP, falhas e diagnósticos operacionais devem aparecer em GitHub Actions (exit code, annotations ou `GITHUB_STEP_SUMMARY`) com informações sanitizadas. Não criar fila infinita `retry_wait` para um receptor que não existe. Preservar eventos já persistidos, sem apagar histórico.
- Se uma falha impedir coleta ou envio, o workflow não poderá relatar sucesso esportivo falso; reportar estado distinguindo `NO_NEW_EDITION_OBSERVED`, `SOURCE_ERROR`, `provider_accepted`, `delivery_unknown` e `delivery_disabled`.
- Flag de liberação obrigatória `ATP_RANKING_DELIVERY_ENABLED=true` **e** execução em `main`. Não inserir tokens em logs. A versão do workflow com flag falsa deve permanecer não produtiva.

### Testes de aceitação
1. ITF sem edição nova, edição com ranks iguais, ranks diferentes, duas modalidades consistentes/inconsistentes e erros de fonte.
2. Resumo semanal uma vez por período; digest uma vez por edição; suppress de backlog antigo.
3. CallMeBot HTTP 429 (retry apenas se rejeição clara), timeout ambíguo/receipt incerto (sem replay), secrets ausentes e configuração inválida.
4. Checkpoint Git rejeitado, dois writers, histórico legado e correção de career high.
5. Sink externo ausente: zero envio operacional remoto, zero crescimento ilimitado de pendências novas, visibilidade em Actions, sem interferir com alertas esportivos válidos.
6. Dry-run ITF live, Python CI + frontend/build conforme workflows do repo, diff revisado por escopo. Testes reais de WhatsApp **somente após aprovação de ativação**.

## 5. Release em três gates

| Gate | Aprovação | Proibido antes |
| --- | --- | --- |
| **CODE_GO** | Regressão, dry-run live, revisão do diff, dados preservados | Merge e envio real |
| **MERGE_GO** | Autorização para merge; avaliar deploy automático Cloudflare Pages por push em `main` | Ativar workflow/flag e WhatsApp |
| **ACTIVATION_GO** | Autorização separada para configurar a flag, `gh workflow enable`, primeira entrega controlada ao destinatário e conferência do recibo/resultado | Envio real sem consentimento |

Após ativação, verificar primeiros runs pelo GitHub; não exigir validação humana por edição. Para interromper: desabilitar workflow e flag, **sem reverter o ledger**. Não criar retry manual automático de mensagens antigas/ambíguas.

## 6. Riscos aceitos e fora de escopo

| Risco | Tratamento MVP |
| --- | --- |
| GitHub não dispara ou atrasa um cron | Aceitar best-effort; não anunciar garantia de execução em todas as semanas |
| CallMeBot aceita mas não entrega ao aparelho | Distinguir `provider_accepted` de entrega final; primeiro teste controlado |
| Timeout CallMeBot com efeito externo incerto | Priorizar evitar duplicidade; admitir perda possível auditada |
| ITF indisponível ou atrasada | Alertar pelo Actions quando executar; preservar última edição com data, sem inventar dados |
| GitHub Actions/CallMeBot indisponíveis prolongadamente | Sem resiliência multi-cloud no MVP; reavaliar apenas após incidente concreto |

**Explicitamente fora:** Cloudflare Workers/D1 [PR #34](https://github.com/hmono/Luka-Tennis-Player/pull/34), watchdog/inbox Linux [PR #32](https://github.com/hmono/Luka-Tennis-Player/pull/32), sprints de infraestrutura [#26](https://github.com/hmono/Luka-Tennis-Player/issues/26), [#33](https://github.com/hmono/Luka-Tennis-Player/issues/33), [#35](https://github.com/hmono/Luka-Tennis-Player/issues/35). Permanecem **suspensas e preservadas** como referências, sem merge ou mudanças no host.

## 7. Definição de concluído

**Produto:** a automação está habilitada após autorização, consulta ITF sozinha, envia resumo semanal e digest para novas edições, registra estado e não exige ação humana semanal.

**Esta sprint de planejamento não ativa produto**: primeiro entregar PR de código mínimo + checks e obter `CODE_GO`; depois autorizações distintas para merge e envio real.

**Princípio:** não introduzir infraestrutura para resolver falhas que ainda não ocorreram. Só reconsiderar watchdog/fornecedor após evidência objetiva de problemas recorrentes.