# ATP Ranking — integração H2 / issue #23

Data: 13/10/2026 UTC. PR draft [#18](https://github.com/hmono/Luka-Tennis-Player/pull/18),
branch `fix/atp-ranking-freshness-202610`, início `147b1e4`.
As três frentes Sol/high terminaram antes da integração. Seus estados foram
confirmados como concluídos e suas execuções interrompidas/encerradas; nenhum
agente inicial continuou escrevendo durante a integração ou a revisão final.
Os worktrees e commits foram preservados para auditoria.

## Evidência e decisão arquitetural

| Frente | Commit original → integrado | Conclusão |
|---|---|---|
| A / #20 | `ae34a16` → `b816d91` | [12/10 INCONCLUSIVA em S/D](evidence/atp-2026-10-12-publication.md). ATP inacessível, ITF anterior de 05/10 não prova não publicação |
| B / #21 | `6edd802` → `60f20a0` | [Onze segundas inconclusivas](evidence/atp-publication-calendar-2026-h2.md). Nenhuma extensão futura contínua comprovada, inclusive mínimo 02/11 |
| C / #22 | `35b8b6c` → `4679602` | [QA independente](evidence/atp-actions-operational-audit-202610.md): dois P1 no código e um P1 operacional legado; 222 testes da base passaram apesar dos defeitos |

Não se altera `valid_until: 2026-10-26`, o weekday, cutoff nem `exceptions: []`.
O JSON recebe somente metadados de evidência H2, mantém o vínculo ao documento
anterior e explicita `inherited_not_recertified`. A revisão de abril foi
identificada, mas sua íntegra e o conjunto de alterações posteriores não foram
verificados suficientemente para estender vigência. O horizonte herdado não é
certificado retroativamente por testes ou pela falta de uma exceção conhecida.

12/10 continua sendo expectativa operacional, não publicação demonstrada.
Não se adiciona `no_edition`, `moved`, snapshot, rank, pontos ou fallback.
`America/Sao_Paulo` permanece; para 12/10 o SLA interno é 15/10 12h local.
Em 27/10 00h local (03h UTC) o calendário expira, inclusive para dados de 26/10.

PENDING pode registrar catch-up de uma edição anterior observada, válida e
ainda não persistida, e recuperar incidente daquela própria edição. Isso
preserva a data real, não declara a edição esperada publicada nem autoriza
envio esportivo. O docstring foi alinhado a esse comportamento preexistente.
Os novos testes verificam `points=None` em ambas as disciplinas e não criam
fatos esportivos produtivos. Todos os cenários com 12/10 ou datas posteriores
nos testes são sintéticos, sem valor de evidência de publicação.

## Correções reproduzidas

### H2-QA-01 — entrega indevida de backlog

A reprodução independente usou histórico 28/09, catch-up 05/10 e coleta FRESH
sintética de 12/10; a base enviou dois digests mock. A integração:

- Publica `sporting_edition_date` somente quando a coleta termina FRESH sem erro.
- Passa essa edição pelo ambiente do step e por `deliver --edition-date`.
- Exige edição explícita para entrega esportiva na CLI; verifica FRESH no relógio
  real da entrega, calendário válido e correspondência à maior data persistida.
- Filtra o lote por essa edição. O helper de baixo nível também exclui outras
  datas; seus guards de operação permanecem na CLI/workflow.
- Revalida antes da reserva e após o checkpoint durável: uma virada local de
  semana/expiração durante o push não autoriza request de edição antiga.
- Mantém intenções antigas intactas, imprime `sporting_edition_held` e retorna
  falha de revisão enquanto existirem pendências antigas elegíveis. A edição
  atual pode ser enviada uma vez; a antiga exige decisão explícita do operador.

A mudança não marca silenciosamente backlog como enviado/cancelado, não apaga
outbox e não implementa replay/reconciliação automática. O teste integrado
espera somente o digest atual, item antigo idêntico e zero requests no rerun.
Ausência da opção, data inválida, data antiga, falta do snapshot correspondente
e calendário expirado bloqueiam antes de construir o provider.

### H2-QA-04 — recuperação ocultava entrega incerta

A base retornava sucesso após `provider_failed(transport_timeout)` seguido de
`recovered`, embora ninguém tivesse reconciliado a entrega. Agora
`unresolved_deliveries` examina a última transição do provider por incidente
independentemente dos eventos de recuperação da fonte. Tentativas em voo,
falhas não retryable e timeouts/5xx legados continuam visíveis, sem replay.
Aceite confirmado, incidente nunca enviado e rejeição explícita 429 recuperada
não viram incerteza de entrega. O ledger e os nonces anteriores são preservados.

Testes cobrem timeout, 503, interrupção em voo, recuperação append-only e
rerun da CLI sem construir provider. Recuperação esportiva não equivale a
aceite nem a entrega no dispositivo; `provider_accepted` conserva seu alcance.

## Risco externo não removido

**H2-QA-02, P1 operacional, permanece pendente:** o workflow ativo de `main`
`833eafa` é legado e não consulta a flag. Steps de entrega em schedules anteriores
tiveram sucesso, o que não prova request real. A ausência da flag protege a
branch deste PR, não desativa o legado. As proteções estão implementadas no PR;
não foram implantadas em `main` e nenhum workflow foi desativado nesta sprint.
Esse risco precisa de tratamento autorizado separado e impede declarar todos
os P1 operacionais encerrados. Não se solicita nem executa merge para contorná-lo.

H2-QA-03 permanece P2: atraso do primeiro cron de quinta pode ser atribuído ao
segundo slot. A estimativa não é prova de pontualidade; não altera o relógio de
freshness. Concurrency pode substituir uma execução pendente, e runs descartadas
não aparecem na telemetria. H2-QA-05 foi esclarecido pela política de catch-up;
seu efeito indevido de entrega foi corrigido em H2-QA-01.

## Validação e trilha final

Repros originais foram executadas pelo coordenador com mocks/temporários antes
da correção. Após a mudança, 88 testes dirigidos de integração, incidentes,
freshness, workflow, entrega e durabilidade passaram. A suíte completa passou
com **231 testes Python**, frontend com **80 testes** e build aprovado. O teste
legado que exigia FIFO de edições antigas foi ajustado ao contrato novo,
verificando preservação integral do backlog e falha apenas na edição atual.
CI e dispatch ITF dry-run serão registrados no SHA publicado, sem usar
envio real. O relatório final e os links por head estão na
[issue #24](https://github.com/hmono/Luka-Tennis-Player/issues/24) e no
[gate H2](ATP_RANKING_FINAL_GATE_202610.md); a revisão independente ocorre após
a integração. Os resultados da base não são apresentados como aprovação do head
novo. Arquivos reais de dados/outbox/receipts permanecem byte a byte preservados.
