# Sprint #25 — revisão independente

2026-10-13 UTC. Revisão do PR #18 e da [issue #25](https://github.com/hmono/Luka-Tennis-Player/issues/25), com reproduções adversariais em arquivos temporários e adapters simulados.

**Código: GO no head `1f7d8dfa1a64043f94809402670e8990a160cfe0`. Ativação: NO-GO.** Os três problemas P1 encontrados nesta revisão foram corrigidos e as correções foram verificadas independentemente. Não há P0 ou P1 conhecido aberto no código revisado. A recomendação de código não autoriza merge, alteração de flags, reativação de workflow ou envio real.

## Escopo e independência

- Diff completo `833eafa6702bc5be14349a4efcead924c18fa55f` (`origin/main`) até o head; diff da sprint desde `dc5032a816c257202241ce650248771dd9b0dae2`.
- Entrada inicial da revisão: `69418e730d18c269dd3ee678a79b54cf2316d1db`. Depois foram incorporados para verificação os fixes root `df45ab6`, `7535619` e `1f7d8df`. Os cherry-picks do worktree de revisão têm SHAs diferentes; o diff de conteúdo contra `1f7d8df` estava vazio antes deste relatório.
- Leitura dos contratos A/B/C, arquitetura, workflow, units systemd, fonte ITF, domínio/CH, journal, checkpoint Git, migração, entrega, runtime, watchdog, receptor, frontend e caminhos legados. Os documentos H2 foram tratados como histórico, conforme a issue #25 e os avisos de substituição do runbook.
- Falhas reproduzidas usando SQLite real temporário, callbacks sem rede e factories simuladas. Nenhum WhatsApp, implantação, alteração de secrets/configuração externa, merge ou remoção de histórico produtivo foi realizado. As consultas GitHub foram somente de leitura.
- As conclusões abaixo resultam da leitura de código, execução local e inspeção direta dos metadados/logs de CI; não presumem que os relatos A/B/C provam comportamento em produção.

## Achados P1 corrigidos

### S25-REV-01 — forwarding parava definitivamente após erro transitório de SQLite

No head inicial, `OpsInbox.forward()` podia lançar uma exceção nas operações de banco anteriores/posteriores ao callback. A função interna `forward_loop()` não a capturava. O daemon morria, mas o servidor HTTP permanecia ativo; `Restart=on-failure` não recuperava esse serviço ainda vivo.

Reprodução independente: inserir um evento, abrir outra conexão SQLite com `BEGIN EXCLUSIVE`, iniciar o loop de produção com HTTP simulado e manter o lock além do timeout real de 30 segundos. Resultado inicial: `OperationalError: database is locked`; após liberar o lock e inserir outro evento, dois eventos pendentes e zero requests de forwarding. A recuperação exigia reiniciar o processo.

**Correção `7535619`, verificada:** o loop captura a falha, incrementa `forwarding_failures` e continua. Repeti o lock com o timeout original de 30 segundos; somente o intervalo entre iterações foi reduzido para o teste. O worker permaneceu vivo, encaminhou `first` e `second` automaticamente após o unlock e terminou com:

```json
{"persisted_events": 2, "pending_forwarding": 0, "forwarding_failures": 1}
```

### S25-REV-02 — resposta negativa era marcada como forwarding concluído

O closure de produção ignorava o conteúdo retornado por `_request()` e retornava `True`. Uma resposta JSON `{"accepted": false}` retirava o evento da fila permanentemente. Isso podia perder silenciosamente um alerta operacional mesmo com HTTP acessível.

**Correção `7535619`, verificada:** `forward_sender()` exige HTTPS e `accepted is True`. Na reprodução independente, `{"accepted": false}`, `{}`, `{"accepted": 1}` e `"ok"` mantiveram o evento pendente. Somente `{"accepted": true}` o marcou encaminhado. O destino precisa implementar esse contrato de persistência/deduplicação; um webhook genérico que devolve texto ou HTTP 2xx vazio ainda precisa de adapter qualificado antes da ativação.

### S25-REV-03 — segunda indisponibilidade de configuração ficava silenciosa

`event_id="provider-configuration"` era uma identidade global. Depois do primeiro alerta aceito, a sequência configuração inválida → válida → inválida produzia contagens de alertas `1 → 1 → 1`. O resultado mantinha `error_code=null`, e a CLI encerrava com sucesso; o watchdog de execução também não identificava essa segunda interrupção da entrega.

**Correção `1f7d8df`, verificada:** o ledger registra episódios de configuração e recuperação com identidades próprias; a CLI retorna 1 quando a configuração está indisponível. Em uma prova adicional, intercalei falhas/retries operacionais com recuperação da configuração e uma segunda indisponibilidade. As observações planejadas foram exatamente:

```text
PROVIDER_CONFIGURATION_UNAVAILABLE
PROVIDER_CONFIGURED
PROVIDER_CONFIGURATION_UNAVAILABLE
```

As três intenções chegaram a `provider_accepted`, com respectivamente 3, 2 e 1 tentativas. Retentar o alerta antigo não alterou a saúde observada nem criou episódios falsos. A prova isolada da CLI confirmou exit code 1 com fonte válida e configuração indisponível.

## Correções adicionais verificadas

- **Clock regressivo — achado root, fix `df45ab6`:** antes, `append_cycle()` gravava um evento inválido e só depois validava o arquivo, tornando o erro permanente. Verifiquei que um timestamp anterior agora é rejeitado preservando os bytes anteriores e que o próximo timestamp válido permite continuar. Não atribuo a descoberta deste defeito à revisão independente.
- **Digest pendente durante erro da fonte — fix anterior `b704722`:** forcei rejeição 429, depois identidade inválida. O retry de digest ficou retido; a recuperação válida enviou o digest. O status semanal continuou sendo um evento distinto.
- **Backlog operacional versus esporte — fix anterior `69418e7`:** usei 12 intenções operacionais indisponíveis durante coleta/429/recuperação. O orçamento operacional não impediu as tentativas esportivas autorizadas. O teste também falha se o loader do calendário for chamado.
- **Runbook histórico:** `7535619` acrescentou avisos claros no estado operacional e no gate H2, apontando para Sprint #25 e retirando os passos humanos anteriores da operação vigente.

## P2 residual — atribuição das duas janelas de segunda-feira

`assess_runs()` usa a última janela com grace vencida e limita elegibilidade pela janela seguinte. Segunda-feira possui slots 12:00 e 12:17 UTC, mais próximos que o grace de 90 minutos.

Reprodução: o slot 12:00 falta; uma recuperação `collect-and-deliver` criada às 13:31 termina com sucesso às 13:35. Às 13:40 o monitor ainda reporta `MISSED_RUN` para 12:00, pois esse dispatch está depois de 12:17. Às 13:50 reporta apenas `SCHEDULER_DELAY` da janela 12:17. O ciclo de recuperação executou e pode satisfazer o resumo semanal, mas a atribuição da recuperação permanece imprecisa durante esse intervalo.

Não reproduzi bloqueio permanente, duplicação esportiva ou esgotamento permanente da recuperação por esse caso. Classifico como P2 não bloqueante. Uma evolução pode associar um dispatch ao slot que o originou ou consolidar os polls próximos. O relatório de telemetria deve continuar declarando que a atribuição é inferida, sem prometer pontualidade exata do Actions.

## Contratos confirmados e limites

| Área | Conclusão da revisão |
| --- | --- |
| Autonomia normal | A CLI/workflow novos não carregam calendário, `valid_until`, PlayerZone, backfill manual ou gate de duas publicações. Os caminhos antigos são explícitos e não fazem parte do ciclo normal. |
| Fonte/edição | Título e heading completos, perfil ITF fixo e S/D com datas explícitas iguais precedem a persistência. Avanço estrito da data produz edição; repetição é `NO_NEW_EDITION_OBSERVED`. Coleta recente não transforma edição antiga em ATP atual. |
| Dados | Pontos desconhecidos continuam `null`; snapshots/revisões preservam histórico; CH considera baseline e versões vigentes. A migração reconhece aceite/ambiguidade de qualquer revisão da edição. |
| Persistência/concorrência | Journal protege snapshot/outbox; lock local e grupo Actions serializam escritores cooperativos; push divergente impede o efeito externo. Reserva remota precede request. Teste com dois clones Git reais passou. |
| Esporte | Aceite é do provider, nunca comprovação no dispositivo. Timeout/2xx ambíguo/crash após reserva terminam em `delivery_unknown` com perda possível. Próximas edições continuam. 429 definitivamente rejeitado recebe retry persistido e limitado. |
| Resumo | Identidade é segunda-feira 09:00 São Paulo, independente das edições. Uma execução posterior recupera o período; períodos antigos podem ser suprimidos com histórico preservado. Não existe garantia de pontualidade durante indisponibilidade externa. |
| Operações | Intenções persistem com retries independentes. Inbox e destino precisam deduplicar o mesmo `event_id`. Aceite durável no receptor/encaminhamento não demonstra que uma pessoa viu a notificação. |
| Supervisão | Watchdog externo pode detectar ausência/falha e solicitar até duas recuperações por slot com intervalo de 30 minutos. Não habilita workflows desativados. O host e o canal externos ainda precisam existir. |
| Credenciais | Cliente GitHub App renova installation tokens automaticamente; um PAT estático sem renovação externa não satisfaz esse caminho de ativação. Revogação, perda de chave, disco ou host continuam falhas de infraestrutura, não resolvidas por inventar sucesso. |

O sistema continua dependente de uma única fonte qualificada (ITF) e de CallMeBot no canal esportivo. Nenhum alternativo foi qualificado, e nenhuma integração Cloud API foi implantada. Logo não há failover automático de fonte nem prova independente de `SOURCE_LAG`. A política explícita de perda possível resolve a quarentena manual de ambiguidade; não transforma CallMeBot em exactly-once. Retentativas de coleta ocorrem nos ciclos agendados e recuperações limitadas, sem SLA de recuperação imediata.

## Validação

- Python local no head inicial: **279 testes passaram** em 107,428 s.
- Python local no código final: **283 testes passaram** em 201,171 s, via `python3 -m unittest discover -s tests/ranking_alerts -p 'test_*.py' -q`.
- Frontend local: **81 testes passaram**; `npm run build` passou com compilação, tipos e exportação estática. O primeiro uso de `NODE_PATH` não resolveu JSX no Vite; uma symlink temporária para as dependências instaladas corrigiu apenas o ambiente de teste. Symlink e arquivo de tipos gerado foram removidos após a verificação.
- `git diff --check` passou. As reproduções de falha usaram somente diretórios temporários e HTTP/factories simulados.
- Inspecionei diretamente metadados e log do head exato `1f7d8dfa1a64043f94809402670e8990a160cfe0`: [release checks](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38425392690), [CI](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38425392692) e [dry-run ITF](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38425392561), todos `success`, evento `push`.

O dry-run real declarou:

```json
{"collection":"NO_NEW_EDITION_OBSERVED","error_code":null,"last_valid_date":"2026-10-05","provider_requests":0,"writes":false}
```

Isso comprova a consulta repetida da edição de 05/10 sem gravação/envio; não comprova duas novas publicações, entrega WhatsApp, infraestrutura externa ou recuperação de um runner real interrompido. Os testes de oito períodos do ledger exercitam oito status e dois digests; a simulação integrada que inclui catch-up inicial e oito fronteiras semanais gera nove status, sem duplicar a identidade do período.

## Decisões separadas

**GO para o código revisado**, sujeito ao processo de aprovação de merge já estabelecido. Os P1 reproduzidos estão fechados por correções verificadas; não é necessário editar calendário ou reconciliar mensagens ambíguas a cada edição.

**NO-GO para ativação neste estado de implantação.** Não foram provisionados/verificados o host externo com systemd/volume/monitoramento, GitHub App/permissões, HTTPS do inbox e destino operacional com acknowledgment/deduplicação. É necessária a autorização inicial de implantação, coerência das flags e verificação prática dos canais e da supervisão externa antes de ativar. São requisitos de configuração/liberação inicial, não um passo humano semanal. Não autorizo nem executei merge, reativação do legado ou envio real por meio deste relatório.
