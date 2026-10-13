# Sprint #25 — autonomia orientada à publicação

Base: `dc5032a`, PR #18, issue #25. As instruções da issue #25 substituem os
gates de calendário e conferência manual das sprints anteriores. Os documentos
H2 permanecem como histórico, não como requisitos de operação da versão nova.

## Contratos da arquitetura

`scripts/autonomous_rankings.py run` executa sob o lock comum do bundle:
coleta ITF validada → journal de snapshot/outbox → provenance de ciclo → planos
de digest/status/incidente → checkpoint remoto → reserva → checkpoint remoto →
request → receipt/disposição → checkpoint remoto. A flag de liberação e a branch
`main` são exigidas pela CLI e pelo workflow. `--dry-run` não escreve estado nem
constrói provider. O calendário histórico continua disponível para testes e
comandos legados explícitos; não é carregado pelo runtime autônomo.

| Máquina | Estados e transições |
|---|---|
| Coleta | Resposta validada com data maior → `FRESH`; data igual → `NO_NEW_EDITION_OBSERVED`; identidade/schema/data futura/regressão/falha HTTP → `SOURCE_ERROR`. A próxima consulta válida recupera automaticamente o episódio |
| Publicação | Identidade ATP B0UF/ITF800625103 + S/D com mesma data; data declarada da fonte difere da hora da consulta. Nova edição é avanço estrito da data observada. Repetição não prova ausência de publicação ATP |
| Snapshot | Novo conteúdo → snapshot imutável; revisão → novo snapshot com predecessor explícito, inclusive A→B→A. CH usa baseline e versões vigentes; pontos desconhecidos permanecem `null` |
| Sporting notification | `planned` → `reserved` → `provider_accepted`, `retry_wait`, `rejected` ou `delivery_unknown`; nenhuma dessas transições prova entrega ao dispositivo |
| Ambiguidade | Reserva interrompida/timeout/resultado sem confirmação → terminal `delivery_unknown`, risco `possible_loss`; não repetir. Novas edições continuam operando, sem reconciliação manual |
| Rejeição recuperável | 429 explicitamente rejeitado → backoff persistido → nova reserva em ciclo posterior; orçamento finito. Fatos substituídos não podem ser enviados em retry |
| Operacional | Intenção persistida → receptor independente com identidade idempotente → aceite durável. Retentativas persistem com backoff enquanto indisponível; o receptor deduplica |
| Scheduler | Slots diários e resumo nominal segunda 09h São Paulo; watchdog em host externo consulta runs, detecta ausência/falha/duração/atraso e solicita recuperação limitada por slot após liberação inicial |

O resumo semanal é independente da existência de nova edição. Identifica última
data confirmada, hora da checagem e estado da fonte. Intenções antigas são
suprimidas com transição auditável quando substituídas por edição/período mais
recente, conservando registros. Receipts e reservas legadas cercam a edição na
migração: não geram replay, e a recuperação da fonte não representa entrega.

## Persistência e concorrência

Snapshots, outbox e incidents existentes mantêm seus schemas e registros.
`ranking_delivery.json` acrescenta histórico append-only de decisões de envio;
`ranking_runtime.json` acrescenta ciclos e proveniência sanitizada. O checkpoint
valida e publica o bundle completo. O lock local, o grupo de concorrência Actions
e push Git sem rebase protegem escritores cooperativos; push divergente bloqueia
o efeito externo. Um próximo checkout recupera a partir do estado remoto.

O journal existente protege a escrita snapshot/outbox. Interrupção entre coleta
e planejamento de entrega é recuperada por replanejamento idempotente dos
snapshots. Uma reserva já publicada sem receipt usa a política de perda possível,
nunca é tratada como entrega confirmada. Rollback não deve retroceder o bundle.

## Limites externos e implantação inicial

CallMeBot permanece o único provider esportivo configurado; não tem contrato de
exactly-once nem comprovação no dispositivo. A política evita duplicação por
replay ambíguo e admite perda possível, comunicada no canal independente. A
Cloud API foi avaliada na frente B, sem ativação, uso de credenciais ou envio real.

A referência de watchdog/systemd e receptor idempotente necessita provisionamento
inicial fora do GitHub: host persistente, HTTPS, credenciais de acesso e destino
operacional. Código no PR não constitui infraestrutura implantada. O workflow
desabilitado não é reativado nesta sprint. Um cron Actions não pode provar a
própria ausência; a supervisão externa é requisito de ativação.

Indisponibilidade externa permanente, revogação de credenciais, falha do host
externo ou perda do disco não são resolvidas por inventar dados. A implementação
reporta status desconhecido e preserva intenção/auditoria quando os canais estão
disponíveis. Não se promete disponibilidade indefinida ou ausência de manutenção
de infraestrutura/credenciais por toda a vida do serviço; não existe passo humano
por edição, semana ou resultado ambíguo no ciclo implementado.

## Gates desta sprint

Merge e ativação têm decisões separadas no relatório final, vinculadas ao head
testado e à revisão independente. Merge não é executado. Ativação permanece
**NO-GO** até autorização inicial, provisionamento/verificação do watchdog e
canal independente, liberação de produção e implantação autorizada. Nenhum envio
real, secret alterado, configuração externa modificada ou histórico removido.

Resultados A/B/C, regressões e revisão independente ficam em `docs/evidence/`;
SHAs e runs remotos são registrados na issue #25 e no PR #18 após a integração.
