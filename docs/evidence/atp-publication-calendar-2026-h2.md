# Calendário de publicação ATP — H2-02 / issue #21

Revisão: **13/10/2026**, corte documental nessa data. Repositório
`hmono/Luka-Tennis-Player`, PR draft #18, base `147b1e4`; worktree
`/home/ono/luka-h2-21-calendar`, branch `review/h2-21-calendar`.
Esta pesquisa cobre todas as segundas-feiras de 19/10 a 28/12 e as avaliações
até 31/12/2026. Não modifica configuração, código ou dados operacionais.

## Decisão para integração

**NO-GO para estender `valid_until` com a evidência obtida nesta revisão.**
Não foi comprovada nenhuma janela contínua futura no intervalo solicitado,
nem a extensão mínima até 02/11. O maior intervalo futuro documentalmente
qualificado por esta pesquisa é **nenhum**. Isso não afirma que não haverá
edições: afirma que falta prova suficiente de datas e exceções.

Proposta ao integrador: preservar `valid_until: "2026-10-26"`,
`exceptions: []` e `review.extension_status:
"blocked_missing_official_edition_schedule"`; registrar este documento como
nova evidência, conforme o contrato existente. A validade herdada
28/09–26/10 é um limite operacional já configurado, **não uma janela oficial
recertificada por esta pesquisa**. As expectativas de 19/10 e 26/10 também
ficam inconclusivas sob o critério documental abaixo.

A trava segue efetiva em **27/10/2026 00h em America/Sao_Paulo**
(03h UTC). Portanto, a execução de terça-feira 27/10 permanece bloqueada,
inclusive se aparecer uma edição de 26/10. Não foi identificada uma extensão
segura que permita remover esse gate hoje. O prazo da issue de 20/10 é um
prazo de obtenção de evidência; não é evidência esportiva.

## Critério de qualificação

Uma data é **confirmada** quando fonte oficial identificável, vigente para
2026 e consultável legitimamente, confirma a publicação naquela data ou
fornece cronograma futuro explícito que a abrange. Uma **exceção comprovada**
exige comunicação oficial específica de não edição ou mudança de data.
**Inconclusiva** significa que regra geral, índice, relato histórico ou falha
de acesso não resolve a data. Ausência de resultado de busca não comprova
ausência de edição ou de alteração de regra.

Há duas provas diferentes: um cronograma pode confirmar uma **previsão
oficial futura**, mas somente uma lista datada/arquivo oficial ou comunicação
de edição permite confirmar uma **publicação já ocorrida**. Em 13/10 todas
as onze datas da matriz ainda são futuras. Não foi consultado nem produzido
snapshot de ranking para elas. A classificação não trata ATP Live Rankings
como uma edição publicada; a própria [FAQ ATP Live, sem versão datada,
seções de definição e finalidade, consultada em 13/10/2026](https://www.atptour.com/en/rankings/rankings-faq/live)
descreve esses valores como previsão para o ranking seguinte.

## Registro de fontes e versões

Todos os acessos abaixo ocorreram em **13/10/2026**. “Indexado” significa
texto devolvido pela pesquisa web na URL oficial, não download integral nem
certificação de que aquele arquivo é a última revisão disponível. As páginas
indicadas são impressas quando informadas; página não verificada é declarada.

| ID | URL oficial, versão e seção | Conteúdo relevante e limite verificável |
|---|---|---|
| R1 | [Capítulo IX ATP, revisão nominal 31/03/2026](https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook-chapter-9_pif-atp-rankings_31mar26.pdf), título indexado `2026 Rulebook_31Mar26_1405.indd`, §9.01 C/E, p. 267; §9.03 A, p. 268 | Texto indexado confirma frequência aproximada de 45 execuções/ano, regra de inclusão ITF na segunda segunda-feira após a semana do evento e publicação anual na segunda após Nitto ATP Finals. Não enumera as onze datas desta matriz. A inclusão de resultados não deve ser convertida em cronograma de edições. Abertura direta: 403. |
| R2 | [Alterações ATP de abril, arquivo `apr2026v1`](https://www.atptour.com/-/media/files/rulebook/2026/26rulebook-changes_apr2026v1.pdf), §9.03 A, referência p. 268; §9.03 F.1/F.5, p. 270; Exhibit X, p. 386; §3.16 B, pp. 54–55 | Trechos indexados preservam regra relativa do ranking anual; indicam alterações de proteção de entrada em 30/03 e de protocolo premier/finanças em 27/04. Nenhum trecho lido fornece calendário futuro de edições. PDF integral indisponível na abertura; não se certifica ausência de outros itens. |
| R3 | [Alterações ATP de março, arquivo `mar2026v1`](https://www.atptour.com/-/media/files/rulebook/2026/26rulebook-changes_mar2026v1.pdf), §9.03 A, p. 268; §9.03 F.1, p. 270 | Texto indexado permite rastrear revisões intermediárias, incluindo eficácia 25/02 e 30/03. Não é cronograma. |
| R4 | [Alterações ATP de janeiro, arquivo `jan15_2026v1`](https://www.atptour.com/-/media/files/rulebook/2026/26rulebook-changes_jan15_2026v1.pdf), §9.03 A, referência p. 268 | Evidência anterior do mesmo marco relativo anual; não autoriza encerrar publicações após esse marco. Texto indexado. |
| R5 | [ATP Rulebook, índice 2026](https://www.atptour.com/en/corporate/rulebook), seção `RULEBOOK BY SECTIONS`, sem data editorial exposta | Índice de busca anuncia capítulo IX e alterações de abril. A URL canônica retorna 403. Índice não comprova íntegra, vigência final nem cronograma; rastreamento do motor tem atraso. Não se presume ausência de revisões posteriores a abril. |
| R6 | [Rulebook ATP integral, revisão nominal 27/04/2026](https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook_27apr26.pdf), capítulo IX pretendido | Candidato posterior informado pela frente H2-01. A abertura nesta frente falhou; busca exata não entregou seu capítulo IX. Conteúdo e páginas dessa versão **não verificados nesta frente**; não serve como prova de calendário. |
| R7 | [ATP capítulo I, revisão nominal 19/12/2025](https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook-chapter-1_atp-circuit-regulations19dec25.pdf), §1.06, p. 11; §1.08 B, pp. 12–13; [cópia integral hospedada pela ITF](https://www.itftennis.com/media/15604/atp-2026-rulebook.pdf), mesmas seções | A versão online é oficial; PlayerZone/Tour Weekly são meios oficiais e alterações produzem efeito após sua publicação. Trechos indexados e primeira abertura ITF permitiram leitura parcial; reabertura ITF expirou. Cópia ITF não certifica revisão ATP mais recente. |
| R8 | [ITF, ATP/WTA Ranking Points](https://www.itftennis.com/media/3625/player-rankings-atp-wta-points.pdf), atualização 30/06/2020 identificada na revisão anterior; `Rankings Dates and Inclusion` e `Rankings history`, PDF p. 3 | Texto indexado indica regra geral de segunda-feira e exceções históricas. Idade e escopo impedem transferir automaticamente essas exceções para 2026. Histórico do ranking anual também não é lista de publicações posteriores. |
| R9 | [ATP Rankings FAQ](https://www.atptour.com/en/rankings/rankings-faq), sem revisão datada, seções de definição/fórmula e ressalva final | Conteúdo indexado é resumo e subordina-se ao Rulebook. Não fornece lista de datas desta janela. Abertura direta: 403. |
| R10 | [ATP Rankings & Media Reports](https://www.atptour.com/en/media/rankings-and-stats), seção `Files`, sem edição datada no índice | Índice oficial oferece rankings singles numérico/alfabético e relatórios. Texto indexado não identifica um cronograma futuro nem entrega histórico completo por edição. Abertura: 403. |
| R11 | [ATP Media Guide 2026 — Player Bios & Birthdays](https://www.atptour.com/-/media/files/media-guide/2026/2026-atp-media-guide-player-bios-birthdays.pdf), ficha Jesper de Jong, p. 39; revisão interna não verificada | Registro oficial indexado de ranking máximo em **29/12/2025**, distinto do ranking anual 2025 na mesma ficha. É evidência histórica de ranking datado em dezembro; não é cronograma 2026 nem prova de todas as edições de 2025. |
| R12 | [ITF WTT Points Tables 2026](https://www.itftennis.com/media/15605/wtt-points-tables-2026.pdf), `Ranking Calculations`, página não verificada | Texto indexado sobre segunda-feira trata **ranking ITF WTT**. Não se aplica ao calendário ATP. |

R2 e R3 ampliam a revisão anterior, que não havia identificado/lido o conteúdo
de abril. A revisão 31/03 não deve ser apresentada como a última versão ATP
certificada. Pesquisa de alterações posteriores, inclusive maio–13/10,
retornou o índice de abril, mas isso não permite uma declaração de completude.
R6 permanece uma lacuna concreta de comparação da íntegra.

## Matriz completa de 19/10 a 31/12

A coluna de referências usa o registro acima: cada ID contém URL, versão,
seção/página, modo de leitura e data de acesso. R1 e R8 permitem registrar a
expectativa geral; R2/R5/R6/R7 explicitam o limite de vigência. Nenhum deles
qualifica uma exceção individual nesta janela. Todos os cortes abaixo são
**SLA interno** às 12h de São Paulo, não horário de publicação prometido pela
ATP. Foram calculados somando três dias à data candidata, sem afirmar que
ela será publicada.

| Segunda candidata | Classe em 13/10/2026 | Prova de previsão específica / prova de publicação ocorrida | Regra/versão consultada | Corte interno teórico |
|---|---|---|---|---|
| 19/10/2026 | **Inconclusiva** | Não obtida / futura | R1, R2, R5–R8 | 22/10/2026 12h |
| 26/10/2026 | **Inconclusiva** | Não obtida / futura | R1, R2, R5–R8 | 29/10/2026 12h |
| 02/11/2026 | **Inconclusiva** | Não obtida / futura; alvo mínimo condicionado | R1, R2, R5–R8 | 05/11/2026 12h |
| 09/11/2026 | **Inconclusiva** | Não obtida / futura | R1, R2, R5–R8 | 12/11/2026 12h |
| 16/11/2026 | **Inconclusiva** | Não obtida / futura | R1, R2, R5–R8 | 19/11/2026 12h |
| 23/11/2026 | **Inconclusiva** | Não obtida / futura; marco anual relativo não convertido em data | R1 §9.03 A, R2, R5–R8 | 26/11/2026 12h |
| 30/11/2026 | **Inconclusiva** | Não obtida / futura | R1, R2, R5–R8 | 03/12/2026 12h |
| 07/12/2026 | **Inconclusiva** | Não obtida / futura | R1, R2, R5–R8, R11 | 10/12/2026 12h |
| 14/12/2026 | **Inconclusiva** | Não obtida / futura | R1, R2, R5–R8, R11 | 17/12/2026 12h |
| 21/12/2026 | **Inconclusiva** | Não obtida / futura | R1, R2, R5–R8, R11 | 24/12/2026 12h |
| 28/12/2026 | **Inconclusiva** | Não obtida / futura | R1, R2, R5–R8, R11 | 31/12/2026 12h |
| 29–31/12/2026, avaliações após a última segunda do escopo | **Inconclusiva** | Dependem de qualificar 28/12 e quaisquer mudanças; não são edições adicionais presumidas | Mesmas referências da linha 28/12 | O corte teórico cairia em 31/12 |

Contagem: **0 datas confirmadas, 0 exceções comprovadas, 11 segundas
inconclusivas**. `exceptions: []` significa nenhuma exceção autorizada para
inclusão; não comprova que onze edições ocorrerão sem exceções.

Não foram inferidas datas a partir de torneios, calendários Tour/Challenger,
semanas de ITF, feriados ou fim de temporada. Em particular, o marco relativo
de §9.03 A não fundamenta `no_edition` em 30/11 ou em dezembro. R11 oferece
um contraexemplo histórico à hipótese de que ranking anual significa
necessariamente o último ranking datado do ano, sem extrapolação para 2026.

## Histórico oficial e canais não disponíveis

O seletor/arquivo de edições ATP foi procurado por data. A página singles
retornou 403; consultas oficiais datadas `rankDate=2026-10-12` e
`rankDate=2025-12-29` não ficaram acessíveis nesta ferramenta. Não foi obtida
uma relação oficial completa de edições. Há comprovação retrospectiva
limitada em notícias ATP datadas: [Movers de 13/04/2026](https://www.atptour.com/en/news/sinner-pif-atp-rankings-13-april-2026),
[20/04/2026](https://www.atptour.com/en/news/jodar-pif-atp-rankings-20-april-2026)
e [31/08/2026](https://www.atptour.com/en/news/buse-pif-atp-rankings-31-august-2026),
cada uma na seção/subtítulo que identifica a segunda-feira de referência,
consultadas via texto indexado em 13/10. Essas referências confirmam os
respectivos relatos históricos, sem comprovar continuidade, datas futuras
ou listas integrais usadas pelo coletor.

PlayerZone/Tour Weekly: não houve acesso autenticado legitimamente fornecido
à frente de pesquisa, nem foi encontrado comunicado público datado que
qualifique esta janela. Não foram usadas credenciais, fontes privadas,
proxies ou mecanismos de evasão. As falhas 403/timeout foram tratadas como
limitação, sem contornar anti-bot. O [anexo de consultas](h2-21-research-log-2026-10-13.md)
registra consultas e resultados em paráfrase sanitizada, sem cookies/tokens,
respostas HTML ou dados de atletas do projeto.

## Informação necessária e extensão condicionada

Para liberar a janela mínima, obter de ATP um cronograma de edições ou
comunicado de ranking que cubra explicitamente **19/10, 26/10 e 02/11**, com
versão/data de emissão, lista de mudanças/não edições e confirmação de que
é a comunicação vigente até a data de revisão. Também comparar o capítulo
IX da íntegra 27/04 e possíveis revisões posteriores com R1/R2. O responsável
com acesso legítimo pode fornecer exportação sanitizada de PlayerZone/Tour
Weekly contendo título, data, seção, emissor e trecho de calendário; uma URL
de login ou declaração de acesso sem conteúdo não basta. Não se enviou
pedido à ATP, mensagem externa ou comentário GitHub nesta tarefa.

Caso se obtenha essa prova, `valid_until: "2026-11-02"` seria uma extensão
**condicionada**, suficiente para cobrir a avaliação de 27/10 e a data 02/11.
Ela expiraria em 03/11 00h BRT: não cobre a execução de terça-feira 03/11 nem
o corte interno teórico de 05/11 para a edição de 02/11. Para cobrir esse ciclo
completo, revisar explicitamente uma validade até **05/11**, compatível com a
fonte e o contrato do calendário. Esses valores não estão aprovados por esta
pesquisa nem foram escritos no JSON.

Para o ideal 31/12, qualificar todas as onze linhas e suas avaliações,
inclusive edições depois do ranking anual e possíveis datas movidas. Só
adicionar `no_edition`/`moved` com prova oficial específica, URL precisa,
versão/seção e data de consulta; adicionar `moved` exige data substituta
expressa e recalcular o SLA interno. Se a fonte cobrir somente uma parte,
limitar `valid_until` a essa janela, sem extrapolar para dezembro ou 2027.

## Verificação desta entrega

As onze segundas e seus onze cortes de três dias foram conferidos com
`datetime` da biblioteca padrão Python. Não se executaram coletores ou testes
que escrevessem dados; não há mudança de implementação a validar. A revisão
de diff deve confirmar apenas este relatório e seu anexo textual, dentro do
ownership H2-02. Configuração e documento de 13/10 anterior permanecem como
fontes de comparação, sem edição por esta frente.
