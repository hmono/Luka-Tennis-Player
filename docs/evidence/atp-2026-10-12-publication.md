# ATP 12/10/2026 — auditoria de publicação, Sprint H2 / H2-01

Repositório `hmono/Luka-Tennis-Player`; [issue #20](https://github.com/hmono/Luka-Tennis-Player/issues/20),
[PR draft #18](https://github.com/hmono/Luka-Tennis-Player/pull/18).
Pesquisa em **13/10/2026 UTC**, base `147b1e4`, worktree isolado
`luka-h2-20-publication`, branch `review/h2-20-publication`.
As datas posteriores a 13/10 são somente pendências operacionais, nunca
publicações observadas.

## Resultado por disciplina

| Disciplina | Edição alvo | Classificação | Presença/rank/pontos de B0UF nessa edição | Fundamento |
|---|---|---|---|---|
| Simples ATP | 12/10/2026 | **INCONCLUSIVA** | Desconhecidos | Página ATP datada indisponível; HTTP direto 403; história indexada não fornece linha verificável de 12/10; nenhuma captura histórica qualificada obtida |
| Duplas ATP, ranking individual | 12/10/2026 | **INCONCLUSIVA** | Desconhecidos | Mesma limitação ATP; consulta histórica CDX de duplas falhou com 503; ITF anterior informa outra edição |

Não foi obtida prova suficiente nem de publicação nem de não publicação oficial
em 12/10. O grau de certeza é alto quanto à **insuficiência da evidência desta
consulta**; a ocorrência da publicação permanece desconhecida. Uma falha de
acesso não constitui prova negativa. Não atribuir `unranked`, rank zero ou pontos
zero a Luka nessa data.

**Decisão operacional:** esta pesquisa não autoriza `no_edition`, data movida,
snapshot de 12/10, preenchimento de pontos nem remoção do gate de homologação.
Preservar o calendário existente com `exceptions: []` até confirmação oficial.
A documentação anterior registra cutoff interno de 15/10 às 12h BRT
(15h UTC); esse horário não é garantia de publicação ATP/ITF e não transforma
ausência de confirmação em ausência de edição.

## Fontes consultadas e proveniência

As consultas web abaixo ocorreram em 13/10/2026 UTC; a ferramenta não informou
hora exata de cada abertura/busca. O [anexo HTTP sanitizado](h2-20-http-queries-20261013.txt)
preserva horários exatos das consultas diretas, URLs, tipo de conteúdo e status.
Não foram guardados cookies, headers de autenticação, corpos de bloqueio ou
HTML integral. Não houve tentativa de contornar proteção de acesso.

| Fonte / localização | Data de edição ou alcance observado | Status e evidência | Limite |
|---|---|---|---|
| [ATP simples, requisição de 12/10](https://www.atptour.com/en/rankings/singles?rankDate=2026-10-12&rankRange=0-5000) | 12/10 apenas no parâmetro solicitado | Web: inacessível. HTTPS direto: **403**, 13/10 12:48:57.402199 UTC | O parâmetro não demonstra existência de edição, seleção efetiva da data nem presença de B0UF |
| [ATP duplas, requisição de 12/10](https://www.atptour.com/en/rankings/doubles?rankDate=2026-10-12&rankRange=0-5000) | 12/10 apenas no parâmetro solicitado | Web: inacessível. HTTPS direto: **403**, 13/10 12:48:57.403959 UTC | Não foi vista a lista nem uma linha individual de Luka |
| [ATP simples sem data](https://www.atptour.com/en/rankings/singles) e [duplas sem data](https://www.atptour.com/en/rankings/doubles) | Data atual não verificável | Web: 403; HTTPS direto também 403 | Impossível conferir seletor de edições ou eventual aviso de adiamento/cancelamento |
| [ATP B0UF — Rankings History](https://www.atptour.com/en/players/luka-bojicic-ono/b0uf/rankings-history), blocos Singles/Doubles e Date/Rank | Nenhuma data preenchida na abertura web | Nome do atleta visível; campos de data/rank são placeholders. HTTPS direto: **403** | A identidade da página é corroborável, mas dados dinâmicos não renderizados não confirmam uma edição |
| [Variante oficial ATP da história B0UF](https://www.atptour.com/en/players/luka-bojicic%20ono/b0uf/rankings-history), tabelas de história | Resposta de pesquisa mostrou linhas até **01/12/2025**; não uma linha de outubro de 2026 | A ferramenta marcou o resultado como rastreado meses antes. Ao abrir, voltaram placeholders | Indexação antiga e abertura dinâmica diferem; os valores históricos não foram usados como ranking vigente. Zeros de tabelas antigas não foram convertidos em fato esportivo para 2026 |
| [Perfil ITF 800625103](https://www.itftennis.com/en/players/luka-bojicic-ono/800625103/bra/mt/s/overview/), título/cabeçalho | Sem edição de ranking no texto extraído | Web abriu a página, exibindo nome, Brasil e seção Men's Singles Overview | Corrobora o identificador ITF pelo perfil nominal, não uma edição ATP de 12/10 |
| [API ITF simples](https://www.itftennis.com/tennis/api/PlayerApi/GetPlayerOverview?circuitCode=MT&matchTypeCode=S&playerId=800625103) e [API ITF duplas](https://www.itftennis.com/tennis/api/PlayerApi/GetPlayerOverview?circuitCode=MT&matchTypeCode=D&playerId=800625103) | Nenhuma edição lida nesta tentativa direta | HTTPS direto às 12:48:57 UTC: **200, text/html, 212 bytes** em ambas | Não era JSON válido de rankings; HTTP 200 isolado não é coleta bem-sucedida. Não interpretar como rank ausente ou zero |
| [FAQ ATP Live Rankings](https://www.atptour.com/en/rankings/rankings-faq/live), seções sobre rankings oficiais e reset | Explicação geral, sem certificação de 12/10 | Conteúdo oficial indexado distingue ranking oficial de projeções durante a semana | Explica categorias, não atesta a edição alvo |
| [ATP Tennis Explained](https://www.atptour.com/en/news/atp-tour), seção How To Climb The Pepperstone ATP Rankings | Explicação geral, texto originalmente publicado em 2023 | Conteúdo indexado explica janela móvel e Race do ano civil | Regra geral de segunda-feira não substitui prova de publicação de uma data específica |

Extrato curto da história ATP aberta via web: `Luka Bojicic Ono`,
`{{formatDate(playerItem.RankDate)}}`, `{{playerItem.SglRollRank}}`,
`{{playerItem.DblRollRank}}`. Localização na extração: nome e blocos
Date/Rank de simples e duplas; não se trata de tabela preenchida.

### Arquivos históricos

O índice público [Wayback CDX de simples](https://web.archive.org/cdx/search/cdx?url=www.atptour.com/en/rankings/singles*&from=20261012&to=20261013&output=json&filter=statuscode:200&filter=mimetype:text/html&collapse=urlkey)
retornou HTTP 200 e `[]` em 13/10 às 12:49:39.670468 UTC. A consulta abrangeu
somente URLs com caminho `/en/rankings/singles*`, capturas de 12–13/10/2026,
status 200 e MIME HTML. **Isso demonstra somente ausência de entradas nessa
consulta do índice, não ausência de publicação ATP.** Não abrange outros
caminhos, PDFs, respostas JSON, páginas sem captura ou atrasos do índice.

A [consulta equivalente de duplas](https://web.archive.org/cdx/search/cdx?url=www.atptour.com/en/rankings/doubles*&from=20261012&to=20261013&output=json&filter=statuscode:200&filter=mimetype:text/html&collapse=urlkey)
retornou HTTP **503** às 12:49:39.672756 UTC. Nenhum conteúdo arquivado foi
obtido para ser qualificado como cópia de uma edição oficial.

Buscas restritas aos domínios ATP/ITF por variantes `12 October 2026`,
`October 12, 2026`, `2026-10-12`, `2026/10/12`, simples/duplas e nome/ID de
Luka não produziram documento oficial que certifique a publicação alvo.
Resultados contendo 12/10 como **drop date** em breakdowns de outros atletas,
rankings ITF World Tennis/juniores/cadeira de rodas, tabelas WTA ou calendário
de torneios não constituem evidência de edição ATP. Resultados de terceiros
não foram promovidos a comprovação oficial, mesmo quando rotulados como ATP.
Ausência em busca também não é prova negativa.

## Identidade, republicação ITF e edições anteriores

A página ATP com ID `b0uf` exibe o nome Luka Bojicic Ono; a página ITF com ID
`800625103` exibe o mesmo nome e Brasil. Isso corrobora nominalmente os dois
perfis. O vínculo ATP/ITF já qualificado pelo projeto foi lido em
`scripts/ranking_alerts/itf_source.py` e na evidência existente; nenhuma nova
ligação explícita entre os dois sistemas foi obtida nesta pesquisa. Identidade
compatível, por si só, não prova data ou rank.

A [captura ITF preexistente](atp-2026-10-05-itf.json), realizada em 12/10
20:53:23–20:53:28 UTC, registra **05/10/2026** separadamente em simples e duplas,
HTTP 200, ranks 2250 e 1417, respectivamente, com pontos `null`. A
[homologação anterior](../ATP_RANKING_HOMOLOGATION_20261013.md) e seu
[extrato de dry-run](atp-homologation-dry-run-20261013.txt) registram nova consulta
em 13/10 12:08:16 UTC ainda com 05/10 em ambas. São evidências locais de
republicação ITF; não foram modificadas nem apresentadas como observações novas
desta auditoria.

Esses registros demonstram o alcance da ITF naquele instante. Não distinguem
entre ATP ainda sem edição de 12/10, atraso de propagação ITF, cache ou outro
problema da fonte. Também não justificam trocar a data 05/10 pela data de
acesso 12/10 ou 13/10.

As listas ATP de **28/09** foram solicitadas por HTTPS diretamente nesta
pesquisa e retornaram 403 em ambas as disciplinas; as de **05/10** foram
solicitadas via web e ficaram inacessíveis. Não se verificou uma lista ATP
completa dessas datas. A republicação ITF de 05/10 já estava documentada antes
da H2. **28/09 e 05/10 não contam como duas novas publicações consecutivas
pós-sprint**; o gate permanece pendente.

## Critério e ações para concluir

- **PUBLICADA:** obter lista ATP oficial ou cópia arquivada qualificável com
  data de edição explícita 12/10/2026, disciplina definida e conteúdo efetivo.
  Verificar B0UF individualmente, incluindo rank/pontos quando publicados e
  eventual ausência somente em lista cuja cobertura completa possa ser provada.
- **NÃO PUBLICADA COM PROVA:** obter comunicação oficial ATP ou histórico de
  edições suficientemente completo e verificável que explicitamente documente
  cancelamento, adiamento ou ausência da edição de 12/10, com alcance separado
  por disciplina. Bloqueio HTTP, ITF defasada e falta de captura não atendem ao
  critério.
- **INCONCLUSIVA:** classificação atual; manter a expectativa operacional e
  os gates existentes enquanto faltarem os documentos acima.

Para encerrar a pendência, consultar as páginas ATP em uma sessão pública
normal, caso estejam acessíveis ao revisor, e preservar extrato curto/screenshot
da data selecionada, disciplina, identificação B0UF e linha relevante; conferir
também que a interface não está no modo Live ou Race. Se o acesso continuar
indisponível, obter confirmação/documento ATP pelo processo oficial do operador,
sem assumir ausência de edição. Esta auditoria não enviou solicitação a terceiros.

**Ranking oficial ATP** é a lista histórica de classificação; **Live Rankings**
projeta mudanças durante a semana; **Race** usa o ano civil e pode classificar
equipes nas duplas; **ITF** pode republicar o rank ATP com sua data explicitada.
Nenhuma categoria substitui automaticamente a outra. A regra de incorporação
de resultados ITF não é o prazo de propagação da lista ATP no site ITF.
O [relatório de calendário](atp-publication-calendar-2026-10-13.md) mantém
separadas essas regras e limitações; calendários de torneios não foram usados
para inferir publicação ou exceção.

Alterações deste trabalho restritas a este relatório e ao anexo textual
sanitizado. Nenhum código, calendário JSON, dado esportivo, snapshot,
outbox/receipt, flag ou secret foi alterado; nenhum WhatsApp foi enviado.
