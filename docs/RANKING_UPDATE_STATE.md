# Estado — atualização semanal de rankings

> **Registro histórico H2, substituído pela Sprint #25.** O runtime vigente do
> PR usa [operação publication-driven](ATP_RANKING_AUTONOMY_SPRINT25.md), sem
> calendário obrigatório, aprovação por edição ou reconciliação humana recorrente.
> Os gates descritos abaixo documentam a decisão anterior; não devem ser
> reinstalados na operação autônoma. Ativação inicial continua não autorizada.

Atualizado: 13/10/2026 UTC, sprint H2 / epic #19, PR #18 draft,
`fix/atp-ranking-freshness-202610`. Integração em
[`ATP_RANKING_H2_INTEGRATION_20261013.md`](ATP_RANKING_H2_INTEGRATION_20261013.md)
e decisões separadas em [`ATP_RANKING_FINAL_GATE_202610.md`](ATP_RANKING_FINAL_GATE_202610.md).
Merge e ativação não liberados. A [homologação #17](ATP_RANKING_HOMOLOGATION_20261013.md)
permanece como registro histórico.

12/10 é INCONCLUSIVA em simples/duplas; nenhuma extensão de calendário foi
comprovada. O limite herdado 26/10 não foi recertificado. Duas novas publicações
consecutivas continuam pendentes. O workflow legado ativo em `main` não consulta
a flag de entrega: as proteções abaixo descrevem a branch do PR e só seriam
implantadas após merge autorizado. A ausência da flag não desativa o legado.

## Decisão

Fonte produtiva: ITF player profile API (`RANKING_SOURCE=itf`). Go registrado
em `docs/spikes/2026-09-24-itf-ranking-source.md`. Caminho ATP PDF e runner
macOS removidos.

## Histórico e fonte

A edição 05/10 foi confirmada ao vivo: simples 2250, duplas 1417; pontos não
publicados continuam `null`. Backfill acrescentou somente o snapshot, sem
evento retroativo. Snapshot anterior e outbox/receipts preservados.
Evidência: `docs/evidence/atp-2026-10-05-itf.json`.

Perfil/título/DOM e crosswalk ATP B0UF ↔ ITF 800625103 são validados;
simples e duplas exigem datas explícitas iguais. Não há fallback automático.

## Operação

- Agenda implementada: terça–sexta 12:00 UTC (09h BRT) e quinta 15:05 UTC
  (12h05 BRT, após cutoff), runner `ubuntu-latest`;
  resumo com atraso >60 min e idade da fonte.
- Manual default `dry-run`; schedule também usa dry-run enquanto a variável
  `ATP_RANKING_DELIVERY_ENABLED` não for explicitamente `true`. A mesma variável
  no ambiente é exigida pelo CLI deliver antes de construir o provider.
  Nenhuma variável do repositório foi alterada nesta sessão.
- A coleta FRESH fornece a edição explícita para `deliver --edition-date`.
  A CLI revalida calendário/edição antes do envio e após o checkpoint; backlog
  de outras edições fica intacto para reconciliação, com falha operacional
  visível. Recuperação da fonte não encerra revisão de entrega incerta.
- Freshness: FRESH/PENDING_PUBLICATION/STALE/SOURCE_ERROR, cutoff quinta 12h BRT,
  clock injetável e calendário `config/atp_publication_calendar.json` com
  exceções referenciadas. Validade termina pelo relógio em 26/10: revisar e
  estender antes de 27/10, inclusive para coletar a edição de 26/10 na terça.
  ATP não publica em todas as segundas do ano; não existe rollover automático.
- STALE e SOURCE_ERROR: ledger append-only separado `automation/state/ranking_incidents.json`,
  criado somente quando há incidente real, deduplicado por edição esperada,
  SOURCE_ERROR por categoria (identity/http/timeout/schema/unavailable) e edição;
  intenção e reserva UUID persistidas e publicadas antes do provider; recuperação cancela intenção ainda
  não enviada e preserva auditoria. O ledger é commitado/pushed antes e depois
  do provider, mantendo `repository-data-writer-main`.
- Mensagem: digest semanal em toda nova publicação (rank, delta, career high); `Correção` em revisão já entregue.
- CallMeBot exige confirmação explícita de fila; 200+erro, 204 e respostas
  ambíguas não confirmam aceite. Falhas permanentes/ambíguas continuam auditáveis
  sem retry automático. Somente rejeição HTTP 429 admite retry limitado;
  timeout, transport, 408 e 5xx ficam bloqueados para revisão.
  A CLI usa uma tentativa HTTP por intenção em cada execução: 429 permanece
  retryable para outro run, que revalida edição/calendário e publica nova reserva;
  não há sleep/retry interno que atravesse a validade sem rechecagem.
- `sent` legado continua legível; novos receipts registram
  `delivery_status=provider_accepted`, sem afirmar entrega ao dispositivo.
  Reserva não retryable é publicada antes do request e permanece em caso de
  crash/resultado incerto. A próxima execução sinaliza revisão necessária, sem
  repetir o envio. Pode haver mensagem não enviada/sem confirmação: sem
  idempotência do provider não se promete exactly-once.
- Coleta usa journal local para recuperar conjuntamente snapshots, outbox e
  recuperação de incidentes. Checkpoint valida/publica o bundle; não faz rebase.
  Writers CLI/backfill usam lock local; Actions compartilham concurrency group
  e checkout atualizado da branch. Entrega produtiva exige main, caminhos
  canônicos e `--durable-git`; somente coleta FRESH permite mensagens esportivas.
  Nos outros estados, o workflow usa `--incidents-only` e mantém falhas visíveis.
- Intenções substituídas ficam na outbox com `superseded_by`. Correções comparam
  com o último receipt aceito da mesma edição. Retorno A→B→A ou revisão com
  tentativa incerta exige reconciliação explícita, sem alterar o histórico.
- Backfill sem `--apply` é read-only; com `--apply` não enfileira mensagens.
  Conflitos de revisão ou de career highs posteriores exigem reconciliação
  revisada, preservando hashes e receipts existentes.
- Rollback: desabilitar schedule/flag, manter dispatch dry-run e preservar
  snapshots, outbox, receipts e ledger. Não apagar evidências.

## Gates pendentes

Regressão CI configurada em `.github/workflows/ranking_checks.yml`: Python,
frontend e build em PR/push da branch. Evidências da revisão final, CI e dry-run
estão no relatório de homologação acima.

- Conferência manual de edição nova oficialmente publicada nas duas disciplinas
  e observação de duas publicações consecutivas quando disponíveis.
- Obter cronograma/alterações oficiais suficientes para 27/10–31/12; extensão
  bloqueada conforme [revisão documental](evidence/atp-publication-calendar-2026-10-13.md).
- Revisar secrets de produção sem expô-los e autorizar merge/ativação separadamente.
- Falha original de identidade: não reproduzida nas novas capturas, com perfil
  correto confirmado ao vivo. Causa transitória exata não comprovada;
  instrumentação distingue navegação, bloqueio, redirecionamento, estrutura,
  parcialidade e divergência de atleta, sem relaxar identidade.

H2-REV-02: career highs usam baseline manual e última versão de cada edição; a revisão atual substitui os fatos anteriores da mesma data. Snapshots e CHs derivados antigos continuam na auditoria, mas não voltam ao cálculo nem ao frontend como prova independente. Nenhum dado real foi migrado.
