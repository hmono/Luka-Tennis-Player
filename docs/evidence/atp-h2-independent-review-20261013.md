# ATP H2 — revisão independente / issue #24

13/10/2026 UTC · [issue #24](https://github.com/hmono/Luka-Tennis-Player/issues/24)
· [PR draft #18](https://github.com/hmono/Luka-Tennis-Player/pull/18).
Worktree: `/home/ono/luka-h2-final-review`; branch `review/h2-final-astra`.

Revisão iniciada em `0915682d964e2fc36ecb60adc26c803d41193982`, com leitura
do diff completo contra `origin/main` (`833eafa`), das mudanças desde
`147b1e4`, das issues #19–24 e dos relatórios A/B/C, integração e gate.
A revisão encontrou dois P1 adicionais; suas reproduções usam somente
observações sintéticas, arquivos temporários e providers/HTTP simulados.
Datas futuras nos testes não comprovam publicação ATP.

**Revisão de implementação concluída em
`24a5ce9e8c4e1209a20ebc9efc6f0764af62a696`.** H2-REV-01 e H2-REV-02 foram
corrigidos pelo coordenador e reverificados independentemente. Não reproduzi
P0/P1 remanescente no código candidato dentro do escopo auditado. Isso não
encerra o P1 operacional legado nem os gates externos de homologação.

## Decisões separadas

- **Merge com entrega desligada: NO-GO de homologação.** Faltam calendário
  oficialmente qualificado, duas novas edições consecutivas verificadas e
  encerramento do P1 operacional legado. Os P1 de código encontrados foram
  corrigidos; CI, build e dry-run ainda devem ser vinculados ao head final
  após este relatório, conforme o registro previsto na issue #24.
- **Ativação da flag/WhatsApp: NO-GO.** Além desses gates, exige autorização
  posterior específica. Aceite do provider não prova recebimento no dispositivo.
- **Teste de recebimento real: não autorizado nem executado.** Requer decisão
  posterior separada, preservando toda a trilha de tentativa e receipt.

## Achados e reproduções

### H2-REV-01 — P1: retry 429 atravessava a validade da autorização esportiva

Em `0915682`, `scripts/update_rankings.py:297` reavaliava a edição depois do
checkpoint, mas `scripts/ranking_alerts/providers.py:182` podia fazer até
quatro requests dentro de `send()`. O sleep após 429 não revalidava o relógio.

Reprodução independente: `/tmp/h2_final_retry_rollover_repro.py`. A CLI usa
`CallMeBotProvider` real, com opener e sleep simulados e relógio compartilhado;
nenhuma conexão externa é aberta. O primeiro request recebe 429 com
`Retry-After: 120`; o segundo receberia confirmação de fila.

| Edição sintética | Primeiro request | Segundo request indevido em `0915682` | Resultado incorreto |
|---|---|---|---|
| 12/10 | 19/10 02:59:59 UTC, FRESH | 19/10 03:01:59 UTC, PENDING_PUBLICATION | exit 0, sent, attempts 2 |
| 26/10 | 27/10 02:59:59 UTC, FRESH | 27/10 03:01:59 UTC, calendário expirado | exit 0, sent, attempts 2 |

Correção do coordenador: `427ec4c` configura `from_env(max_attempts=1)` na
CLI. O 429 fica persistido como rejeição explícita retryable; a próxima
execução passa novamente pelos gates e pela reserva durável. O helper mantém
seu default, mas ele não rege o caminho operacional da CLI.

**Reverificação independente aprovada:**
`/tmp/h2_final_retry_rollover_recheck.py` respeita os argumentos da factory,
executa ambos os casos e repete a CLI 120 segundos depois. Há apenas um request
429 no período FRESH, estado pending/attempts 1, exit 1; o rerun retorna
`ranking_delivery_edition_not_fresh` ou `ranking_calendar_invalid`, sem novo
request e com os bytes do estado intactos. Os testes adicionados também
conferem retry em outro run ainda FRESH, nonce novo e posterior deduplicação.
A troca é explícita: 429 espera outro run; não há orçamento global de tentativas.

### H2-REV-02 — P1: versão substituída contaminava o career high vigente

Reproduzido em `427ec4c`, em lógica herdada pelo candidato, também presente
antes da H2. Não é o risco externo do workflow legado.

`/tmp/h2_final_ch_revision_repro.py` usa o coletor real com observações Raw ITF
sintéticas: edição 12/10, singles 1700; a mesma edição depois é corrigida para
1900. O baseline verificado é 1827. O coletor retorna FRESH e uma intenção
elegível contendo `Singles: #1.900 | CH #1.700 (2026-10-12)`. A intenção da
versão 1700 está superseded, mas seu rank continua alimentando o high.

Causa no candidato reproduzido: `scripts/update_rankings.py:438` inclui
revisões da própria edição no enriquecimento; `career_high.py:190` acumula os
ranks de todas as versões; `lib/career.ts:33` também usa todas as versões para
os highs exibidos. Histórico imutável não equivale a fatos esportivos vigentes.
A correção deve preservar snapshots/receipts e impedir que um fato substituído
seja usado para o high da revisão ou de edições seguintes. Um bloqueio somente
transitório da coleta não basta se a próxima edição recuperar o incidente e
voltar a derivar o high inválido.

Correção do coordenador: `24a5ce9` introduz `effective_snapshots`, seleciona
somente a última versão de cada edição anterior e substitui a própria edição
pela observação atual no enriquecimento. Todas as versões continuam validadas
e preservadas. O delta de novo high deixa de consumir versões substituídas e
ecos derivados na janela observada. O frontend calcula o high com baseline
manual mais ranks vigentes; conferi que as três páginas consumidoras usam
`getCareerHighs`, enquanto os accessors de auditoria conservam os dados brutos.

**Reverificação independente aprovada:** a reprodução original agora retorna
CH 1827. Em `/tmp/h2_final_ch_revision_recheck.py`, expandi o cenário para ambas
as disciplinas e para revisão a ranks piores ou unranked: CHs voltam a
1827/1407; a edição seguinte 1800/1350 anuncia corretamente os novos highs.
O snapshot antigo fica idêntico, a intenção antiga é superseded, a repetição
preserva os bytes e há uma única intenção elegível da nova edição. A regressão
integrada adicionada pelo coordenador também verifica correção após aceite e
preservação do receipt antigo. Nenhum dado produtivo foi migrado.

### Correções H2-QA-01 e H2-QA-04 confirmadas

Para H2-QA-01, o workflow transmite `sporting_edition_date` somente no resultado
FRESH; a CLI exige data explícita, validade temporal e maior data persistida.
O helper filtra por edição e a CLI revalida antes e depois do checkpoint.
Repeti a reprodução C apontando imports para este worktree: catch-up PENDING
05/10 seguido de FRESH sintético 12/10 envia somente o digest de 12/10; 05/10
continua pending e o resultado é `ranking_delivery_review_required`.
A suíte integrada verifica preservação do item antigo e ausência de replay.

Para H2-QA-04, `unresolved_deliveries` lê a última transição do provider
independentemente de `recovered`. Repeti timeout → recovery: antes e depois
há exit 1 e `delivery_review_required=1`. O ledger preserva created,
provider_in_flight, provider_failed e recovered, com o mesmo nonce da tentativa.
Os testes cobrem ainda 503, interrupção em voo, formato legado, aceite e 429
explicitamente rejeitado. Recuperação da fonte não reconcilia entrega incerta.

### H2-QA-02 — P1 operacional externo continua aberto

Consulta independente à API confirmou `main` em
`833eafa6702bc5be14349a4efcead924c18fa55f` e `update_rankings.yml` active.
Li o workflow remoto desse SHA: cron `0 9 * * 2`, dispatch default
collect-and-deliver, writers sem consulta a `ATP_RANKING_DELIVERY_ENABLED`.
A flag do PR não desliga essa versão já implantada. Nada foi alterado em main,
workflow ativo, variáveis ou secrets por esta revisão.

O [run legado de 06/10](https://github.com/hmono/Luka-Tennis-Player/actions/runs/37489325767)
com steps success não prova request ou recebimento real. O risco é a execução
futura do código legado com uma intenção pendente. Exige tratamento autorizado
separado; não pode ser declarado resolvido por código ainda em PR draft.

### H2-QA-03 — P2 de telemetria permanece

`telemetry.py:28` infere o último slot a partir de created_at. Reproduzi quinta
15/10, criação 15:06 UTC e início 15:07 UTC: informa 2 minutos contra o slot
15:05, mesmo se o evento real tivesse sido o cron das 12h atrasado 187 minutos.
O workflow não passa `github.event.schedule`, que ajudaria a distinguir as
expressões. A métrica permanece estimativa; não comprova pontualidade nem
identifica runs descartadas. O cálculo de freshness usa relógio independente.

## Semântica ATP e suficiência documental

| Gate | Evidência independente e conclusão |
|---|---|
| Edição 12/10 em simples e duplas de B0UF | As aberturas das listas ATP datadas ficaram indisponíveis nesta revisão. Não obtive lista ou aviso oficial que resolva a data. A/HTTP preservam a limitação: **INCONCLUSIVA**, sem `no_edition` nem snapshot inventado |
| ITF 05/10 | Evidência preservada identifica S/D 2250/1417, data 05/10 e pontos null. HTTP 200 com HTML em consulta direta não equivale ao JSON obtido pelo navegador qualificado; ambos podem coexistir |
| Calendário futuro | Aberturas independentes do capítulo IX 31/03, mudanças de abril e íntegra 27/04 retornaram 403. Não recertifiquei vigência integral nem obtive cronograma futuro. As onze segundas 19/10–28/12 continuam inconclusivas |
| Configuração integrada | `exceptions: []`, segunda-feira, cutoff de três dias às 12h America/Sao_Paulo e `valid_until: 26/10` preservados. Metadados explicitam horizonte herdado não recertificado. Nenhuma extensão autorizada |
| Expiração | A validade aplica-se ao dia local de avaliação. Em 27/10 03h UTC bloqueia inclusive uma observação datada 26/10; o cutoff teórico 29/10 não amplia a validade |
| Duas novas edições consecutivas | **Não comprovadas.** 28/09 e 05/10 são registros anteriores à H2; testes com 12/10, 19/10, 26/10 ou dezembro são sintéticos |

Referências verificadas quanto ao acesso:
[ATP simples 12/10](https://www.atptour.com/en/rankings/singles?rankDate=2026-10-12&rankRange=0-5000),
[ATP duplas 12/10](https://www.atptour.com/en/rankings/doubles?rankDate=2026-10-12&rankRange=0-5000),
[capítulo IX](https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook-chapter-9_pif-atp-rankings_31mar26.pdf),
[mudanças de abril](https://www.atptour.com/-/media/files/rulebook/2026/26rulebook-changes_apr2026v1.pdf),
[íntegra 27/04](https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook_27apr26.pdf).
Falha de acesso não prova ausência de publicação. Os relatórios
[A](atp-2026-10-12-publication.md) e [B](atp-publication-calendar-2026-h2.md)
são coerentes ao não extrapolar suas fontes. Uma URL HTTPS aceita pelo parser
não qualifica sozinha uma exceção; a revisão documental continua obrigatória.

PENDING pode persistir uma edição anterior observada que ainda não foi salva,
sem trocar a data pela esperada ou pela data da captura. A reprodução confirmou
que esse catch-up não autoriza digest. Dados ausentes, live rankings, Race,
inclusão de pontos de torneios e calendário de torneios não são intercambiáveis
com a publicação oficial de uma edição.

## Persistência, concorrência e compatibilidade

As reservas não retryable com nonce precedem o provider; o push sem rebase
precede o efeito externo. Falhas no resultado mantêm claim/receipt recuperável,
sem replay automático de timeout, transporte, 408/5xx ou resposta ambígua.
O journal valida estado anterior/planejado antes de recuperar rankings,
outbox e recovery do ledger. Falha de persistência não autoriza entrega.

Repeti a corrida C com dois clones temporários, barrier e remote Git bare local:
**1 chamada mock, 1 `ranking_checkpoint_failed`, remote sent/attempts 1**.
Isso verifica a rejeição do segundo claim divergente. Não prova exactly-once
externo nem disponibilidade: uma reserva durável sem request pode exigir revisão
manual, e outro escritor Git pode bloquear um push válido sem conflito esportivo.

O [GitHub documenta](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
schedule na default branch, UTC por padrão e possível atraso/descarte. O cron
do PR draft ainda não é schedule implantado. O
[grupo de concorrência](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
sem queue max mantém uma execução ativa e uma pendente, substituindo pendentes;
`cancel-in-progress: false` não garante todas as execuções. Lock local e
concurrency não serializam escritores externos que não os respeitem.

Receipts legados continuam legíveis sem inventar `delivered_to_device`.
Intenções substituídas e tentativas incertas permanecem na auditoria.
O diff integral inclui backfill de 05/10 realizado na sprint anterior; o diff
H2 desde `147b1e4` não altera dados esportivos ou receipts reais.

| Arquivo produtivo | SHA-256, igual à base H2 |
|---|---|
| `data/rankings.json` | `f310ca9400d51ede71a58f9d36336d42d1bef0535fba3993cd44b9642d11ebd1` |
| `automation/state/ranking_alerts.json` | `8d8922a121b7a2466d1f544a97358d37f692662d82c9ba34e66060d4060b015a` |

Nenhum ledger produtivo foi criado. Apenas este relatório é escrito no
repositório pelo revisor; reproduções e seus estados são temporários.

## Testes e limites do aceite

- Executei 231 testes Python em `0915682`, 233 em `427ec4c` e **237 em
  `24a5ce9`**, todos aprovados. O segundo conjunto ainda passou com H2-REV-02
  presente: contagem verde não substitui revisão de invariantes esportivos.
- Executei **81 testes frontend**, cinco arquivos, em cópia temporária de
  `git archive 24a5ce9`, com cache desabilitado. A revisão lê as novas
  regressões de retirada do high, unranked, próxima edição e eco legado.
  Não repeti o build nesta revisão; sua validação final cabe ao registro
  do coordenador, no mesmo head publicado.
- Testes de workflow examinam texto e condições; não executam o interpretador
  Actions. Reproduções locais usam clocks/mocks e Git local, sem provider real.
- Fixtures frontend do candidato inicial não cobriam retirada de high por
  revisão da mesma edição. A suíte de correções também não combinava retry 429
  interno com mudança do período FRESH. Essas lacunas permitiram os dois P1.
- O live dry-run valida acesso/parsing e ausência de writers. Não testa o
  caminho real de persistência/entrega nem prova publicação futura, cron
  implantado ou entrega ao dispositivo.

Verifiquei via API os resultados de `0915682`: [CI](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38402367838),
[release checks](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38402367787)
e [dispatch dry-run](https://github.com/hmono/Luka-Tennis-Player/actions/runs/38402370336)
estão success nesse SHA; os quatro writers estão skipped. São evidências desse
head anterior, não validação antecipada dos commits de correção/revisão.
O coordenador deve publicar Python/frontend/build, CI e dispatch do head final
na issue #24/PR, depois do último commit documental. Release checks tem filtro
de paths; commit somente de docs pode exigir workflow_dispatch explícito.

## Recuperação e critérios para reconsiderar os gates

Preservar o bundle, journals disponíveis, versões, intenções, nonces e receipts.
Resolver uma tentativa incerta com evidência operacional antes de qualquer
reenvio; recovery da fonte não é essa decisão. Backlog antigo requer
reconciliação explícita. Rollback de código não deve retroceder os dados nem
restaurar automaticamente o workflow legado sem trava.

As soluções dos P1 de código estão verificadas no head acima. Reconsiderar
merge após tratamento separado do legado, calendário documentalmente suficiente,
duas novas publicações consecutivas reconciliadas em S/D B0UF e checks no
head final. Ativação e recebimento real continuam decisões posteriores
independentes. Nenhuma ação externa de escrita, merge, push, mudança de flag,
consulta de valores de secrets ou envio real foi executada pelo revisor.
