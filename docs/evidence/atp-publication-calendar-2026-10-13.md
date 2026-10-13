# Calendário ATP — revisão documental de 13/10/2026

Escopo: homologação da Sprint #17 / PR #18, base `c7b1ddd`. Pesquisa somente
leitura, sem consulta ao provider de mensagens e sem alteração de snapshots.
Não foram encontrados arquivos `AGENTS.md` no worktree nem nos diretórios pais.

## Decisão e bloqueio

**Não estender a validade até 31/12/2026.** O calendário de produção continua
limitado a 28/09–26/10/2026, versão `2026-10-13`, com `exceptions: []`. A revisão
fica registrada em `review.extension_status` como
`blocked_missing_official_edition_schedule`; esse metadado é informativo e não
altera o contrato do carregador. A trava efetiva continua sendo `valid_until`.

As fontes consultadas não confirmam todas as datas de edição de novembro e
dezembro nem a totalidade das exceções de 2026. Isso é evidência faltante, não
prova de que não haverá rankings nesses meses. Tampouco confirma ou cancela as
edições esperadas na janela já existente da sprint.

## Fontes e alcance da evidência

| Fonte oficial e localização | Evidência verificável | Limite |
|---|---|---|
| [ATP 2026, capítulo IX, revisão 31/03](https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook-chapter-9_pif-atp-rankings_31mar26.pdf), §9.01 C/E, p. impressa 267 | Aproximadamente 45 execuções anuais; resultados ITF entram na segunda segunda-feira após a semana do torneio | Frequência aproximada e inclusão de pontos não especificam todas as datas de publicação |
| [ATP 2026, capítulo I](https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook-chapter-1_atp-circuit-regulations19dec25.pdf), §1.06, p. 11; [Rulebook ITF](https://www.itftennis.com/media/15604/atp-2026-rulebook.pdf), §1.08 B, pp. 12–13 | Versão online prevalece; alterações comunicadas por PlayerZone/Tour Weekly têm efeito após publicação | A disponibilidade pública consultada não permite atestar ausência de novas alterações |
| [ATP, alterações de janeiro](https://www.atptour.com/-/media/files/rulebook/2026/26rulebook-changes_jan15_2026v1.pdf), §9.03 A, referência à p. 268 | Ranking de encerramento anual publicado na segunda-feira após Nitto ATP Finals | Ranking anual não comprova ausência de outras edições em dezembro |
| [ITF, ATP/WTA Ranking Points](https://www.itftennis.com/media/3625/player-rankings-atp-wta-points.pdf), atualização 30/06/2020, PDF p. 3, seção “Rankings Dates and Inclusion” | Regra geral de segunda-feira; exceções históricas nas semanas intermediárias de Slams, Indian Wells e Miami; atraso de inclusão de resultados ITF | Documento antigo, insuficiente para aplicar automaticamente essas exceções ou excluir outras em 2026 |
| [ATP, Rulebook](https://www.atptour.com/corporate/rulebook), seção “RULEBOOK BY SECTIONS” | Índice 2026 e alterações de abril | Índice acessível por pesquisa; acesso direto retornou 403, sem verificação integral das alterações |
| [ATP, brochura 2026](https://www.atptour.com/-/media/files/partnerships/2026-atp-partnerships-brochure.pdf), seção “2026 CALENDAR”, nota de versão 20/02/2025; página não confirmada | Calendário de eventos sujeito a mudanças | Datas de torneios não equivalem a datas de edição; não foi usado para gerar exceções nem fundamentar a validade |

O capítulo IX e outros trechos ATP foram lidos no conteúdo indexado da pesquisa
web. A abertura direta do capítulo IX retornou 403. O PDF integral ITF chegou
a ser identificado pelo navegador como PDF de 210 páginas (páginas em pares),
mas as tentativas seguintes de abertura expiraram; download HTTPS local
retornou HTML, não um PDF utilizável. Nenhuma proteção foi contornada. As
páginas citadas acima são as páginas impressas, salvo indicação “PDF”.

## Regra esportiva, expectativa e SLA interno

A segunda-feira configurada é uma expectativa operacional versionada, não
garantia universal ATP. O corte `days_after_edition: 3`, `time: 12:00`, em
`America/Sao_Paulo` é o SLA interno da sprint. Para uma edição prevista na
segunda-feira, o corte ocorre na quinta-feira às 12h locais (15h UTC nas datas
testadas). Nenhuma fonte consultada atribui esse horário à ATP ou à ITF.

Uma exceção `moved` substitui a data esperada por uma data documentalmente
confirmada; o SLA interno passa a contar dessa substituição. `no_edition`
retira apenas a expectativa daquela edição. Ambas exigem referência HTTPS.
Uma URL sintaticamente válida não prova autenticidade: a revisão documental
humana deve preceder a inclusão em produção.

Ausência de dados, erro da fonte ou pontos ITF ainda não incorporados não
autorizam `no_edition`, rank zero, pontos zero ou snapshot novo. Rankings ao
vivo também não são confirmação de edição oficial. Nenhuma exceção real foi
adicionada nesta revisão.

A validade usa a data local da avaliação, não só a data do ranking. O último
instante aceito é 26/10/2026 23:59:59 em São Paulo (27/10 02:59:59 UTC); a partir
de 27/10 03:00:00 UTC ocorre `CalendarError` / `ranking_calendar_invalid`.
Consequentemente, a rotina de terça-feira 27/10 fica bloqueada mesmo que a fonte
traga 26/10. O SLA teórico dessa edição seria 29/10 12h locais, mas avaliações
desse dia exigem primeiro uma extensão revisada. A documentação operacional
principal deve continuar expondo essa pendência como gate de homologação.

## Verificação e evidência ainda necessária

Testes locais cobrem o instante do corte e fusos equivalentes, domingo/segunda
em São Paulo, início/fim da validade, futuras edições, datas movidas e seu corte,
semana sem edição, colisões/duplicações e exceções inválidas. O cenário até
31/12 é **fixture sintética**, inclusive suas semanas sem edição; demonstra
somente o mecanismo e sua expiração em 2027, sem fundamentar a extensão real.

Comando executado nesta revisão:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.ranking_alerts.test_freshness tests.ranking_alerts.test_telemetry \
  tests.ranking_alerts.test_update_rankings tests.ranking_alerts.test_sprint_integration
```

Resultado: **51 testes aprovados**, sem acesso externo nos testes e sem envio.

Para remover o bloqueio, obter comunicação ATP vigente ou cronograma oficial
de edições que cubra 27/10–31/12 e permita revisar explicitamente semanas
intermediárias, eventuais adiamentos/cancelamentos e publicações após o ranking
anual. Conferir também alterações posteriores à revisão 31/03 e a comunicação
de abril listada no índice. Registrar URL, versão, seção/página e efeito de cada
exceção antes de mudar `valid_until`; renovar novamente para 2027, sem rollover.
