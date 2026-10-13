# ATP Ranking — gate final H2 / issue #24

13/10/2026 UTC · [Epic #19](https://github.com/hmono/Luka-Tennis-Player/issues/19)
· [PR draft #18](https://github.com/hmono/Luka-Tennis-Player/pull/18).

## Decisões separadas

**Merge do código com envio desligado: NO-GO / homologação pendente.**
A evidência ainda não qualifica o calendário futuro, duas novas edições
consecutivas não foram verificadas e existe risco P1 operacional no workflow
legado ativo de `main`. As correções do PR não estão implantadas. Não se concede
GO fictício pela aprovação de testes; nenhum merge é executado.

**Ativação do WhatsApp: NO-GO.** Além das pendências acima, continuam exigidos
aprovação separada de ativação e procedimento de conferência de recebimento.
Nenhuma variável foi habilitada nem envio real executado nesta sprint.
Sucesso de um step ou `provider_accepted` não prova entrega ao dispositivo.

## Matriz documental e operacional

| Gate | Estado nesta revisão |
|---|---|
| 12/10 classificada com evidência ou registrada inconclusiva | Atendido como **INCONCLUSIVA** em simples/duplas, sem inferência de não publicação; [A](evidence/atp-2026-10-12-publication.md) |
| Extensão proporcional à evidência | Nenhuma extensão aprovada. `valid_until: 26/10` herdado, não recertificado; [B](evidence/atp-publication-calendar-2026-h2.md) |
| Duas novas edições oficiais consecutivas, S/D B0UF | **Pendente externo**. 28/09 e 05/10 preexistentes não são novas edições pós-sprint; 12/10 inconclusiva; demais candidatas ainda futuras |
| P1 no código | H2-QA-01/H2-QA-04 e H2-REV-01/H2-REV-02 reproduzidos e corrigidos; reverificação descrita no [relatório independente](evidence/atp-h2-independent-review-20261013.md) |
| P1 operacional legado em main | **Aberto**, H2-QA-02; flag ausente não desativa workflow antigo. Tratamento separado autorizado necessário |
| Testes, build, CI e dry-run no mesmo head final | Resultado exclusivamente no [registro por SHA final](https://github.com/hmono/Luka-Tennis-Player/issues/24#issuecomment-6146425191), após o último commit; candidatos anteriores não bastam |
| Revisão independente Astra/max | [Relatório e reproduções](evidence/atp-h2-independent-review-20261013.md); sem GO documental/operacional antecipado |
| Auditoria e dados | Relatórios base preservados; snapshots, outbox e receipts reais não modificados |

A [integração #23](ATP_RANKING_H2_INTEGRATION_20261013.md) registra a reconciliação
de A/B/C, decisões, correções e limites. O [QA da base](evidence/atp-actions-operational-audit-202610.md)
permanece como evidência histórica dos defeitos, sem ser reescrito para aparentar
aprovação de uma versão que não auditou.

## Pendências externas verificáveis

1. ATP: lista datada ou comunicação explícita que resolva a edição 12/10 em
   cada disciplina; falha de acesso/ausência na ITF não basta para `no_edition`.
2. ATP: cronograma vigente, revisões e exceções da janela futura; conferir
   íntegra de abril e alterações posteriores antes de qualquer extensão. Sem
   isso, em **27/10 03:00 UTC** o código continuará fail-closed.
3. Observação: duas novas edições efetivamente publicadas, ambas disciplinas,
   identidade B0UF/800625103, data explícita, deltas e unicidade de intenção.
   Reavaliar após publicações disponíveis; não agendar nem simular publicação.
4. Operação: resolver o workflow legado que permanece ativo em `main`, com
   decisão específica do responsável. Nada foi alterado em `main`, workflows
   ativos, flags ou secrets por esta execução.

## Procedimento e recuperação

Antes de qualquer liberação futura, conferir o head aprovado, validade local
do calendário, fonte qualificada e gates de edição. O cron do PR só passa a
operar após merge na default branch; dispatch desta homologação usa `dry-run`
e não equivale a observação do novo schedule.

Em falha operacional, manter envio desligado e preservar o bundle completo,
journal disponível, intenções, receipts e nonces. Não reativar retry de timeout,
transporte, 408/5xx ou resposta ambígua automaticamente; recuperar a fonte não
reconcilia entrega incerta. Para backlog de edição antiga, obter decisão explícita
de reconciliação; o código o mantém visível sem envio automático.

Rollback de código é decisão posterior, nunca rollback de dados/receipts.
Não voltar ao workflow legado sem trava de envio. Ausência de idempotência
comprovada do provider impede promessa de exactly-once. Reenvio real ou teste
de recebimento continua fora da autorização desta sprint.

## Registro de validação imutável por head

Os resultados finais com SHA completo e URLs de Actions serão publicados como
relatório de execução no [relatório final da issue #24](https://github.com/hmono/Luka-Tennis-Player/issues/24#issuecomment-6146425191)
e no [PR #18](https://github.com/hmono/Luka-Tennis-Player/pull/18) após o último
commit. Isso permite executar todos os checks no próprio head final sem criar
um novo commit somente para gravar seus links. Enquanto esse registro não
estiver presente e aprovado, o gate técnico permanece pendente.
