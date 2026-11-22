# Luka Bojicic Ono — revisão técnica da temporada 2026

> **Status:** evidência histórica/provisória; não homologado como base oficial ITF/ATP.  
> **Data de corte:** 2026-11-18 (partidas disputadas até essa data).  
> **Versão registrada:** 2026-11-19.  
> **Escopo:** simples ITF M15/M25 e qualifying de ATP Challenger; duplas apresentadas separadamente.  
> **Origem:** análise da conversa de 18–19/11/2026 e planilha `luka_bojicic_ono_jogos_oficiais_2026.xlsx`, reconvertida em snapshots CSV.  
> **Natureza da alteração:** documentação e evidências, **sem mudança** no `data/career.json`, no app, nos alertas de ranking ou no deploy.

## Resumo executivo

A hipótese técnica mais sustentada pela amostra observada é que **a baixa eficiência no segundo saque e a dificuldade de consolidar a vantagem após vencer o primeiro set** prejudicam a conversão de competitividade em vitórias. A quadra dura apresenta retrospecto melhor, mas com **n=7**, insuficiente para comprovar preferência técnica intrínseca sem controlar a força dos adversários.

Prioridades propostas: (1) segundo saque + primeiro golpe depois do saque (`serve+1`), (2) estudo de pontos críticos e transição do 1º para o 2º set, (3) sequência controlada de torneios em quadra dura, (4) progressão do qualifying à chave principal de M15/M25.

## 1. Retrospecto observado

| Indicador | Saibro | Dura | Total |
|:--|--:|--:|--:|
| Simples disputados | 27 | 7 | 34 |
| Vitórias | 7 | 4 | 11 |
| Derrotas | 20 | 3 | 23 |
| Aproveitamento | 25,9% | 57,1% | 32,4% |
| Games vencidos* | 192 | 63 | 255 |
| Games perdidos* | 285 | 60 | 345 |
| Games vencidos / games totais* | 40,3% | 51,2% | 42,5% |

\* Cálculo em **32 partidas concluídas**; as duas partidas encerradas por retirada do adversário estão fora desse denominador. Match tie-breaks ([10–x]) não foram convertidos em games.

- **Chave principal de simples:** 0 vitórias em 5 partidas registradas.
- **Duplas:** 21 partidas jogadas, 8 W / 13 L (38,1%); 3 W.O. excluídos da contagem de partidas.
- **Global simples + duplas:** 55 partidas efetivamente disputadas, 19 W / 36 L (34,5%).
- **Diferença entre superfícies:** +31,2 pontos percentuais de aproveitamento em quadra dura e +10,9 pp de games conquistados. Há viés potencial de seleção de torneio/adversário.

Fontes do inventário: [snapshot de simples](evidence/luka-2026-singles-snapshot.csv), [snapshot de duplas](evidence/luka-2026-doubles-snapshot.csv) e [W.O. não disputados](evidence/luka-2026-walkovers-snapshot.csv). A base inclui torneios de qualificação. O placar é sempre da perspectiva de Luka/dupla.

## 2. Segundo saque e primeiros golpes

### 2.1. Estimativa de fonte secundária (não homologada)

Na análise anterior foi reportada amostra móvel de **15 partidas em saibro, janela de 52 semanas até 10/11/2026**, atribuída ao Tennis Pythia; não equivale à temporada civil integral e **não foi acompanhada de exportação dos pontos**.

| Métrica | Valor reportado |
|:--|--:|
| Primeiros saques dentro | 67,8% |
| Pontos ganhos com o primeiro saque | 55,4% |
| Pontos ganhos com o segundo saque | **31,5%** |
| Duplas faltas / pontos de serviço | **8,1%** |

Em uma **subamostra selecionada de seis derrotas** (não aleatória), foram reportados 253/361 primeiros saques dentro (70,1%), 26/108 pontos ganhos com segundo saque (24,1%), 32 duplas faltas e 330/724 pontos totais ganhos (45,6%). **Não extrapolar** esses valores como média anual.

Exemplos reportados no estudo anterior (provisórios até conferência dos scorecards originais):

| Confronto | 1º dentro | 2º: pontos ganhos | Duplas faltas | Total de pontos ganhos |
|:--|--:|--:|--:|--:|
| Tsz Fu/Tao Wong, Brasília | 78% | 7% | 7 | 51,0% |
| Gabriel Ribeiro Pinho, Leme | 77% | 22% | 5 | 50,3% |
| Augusto Land, Santa Cruz do Sul | 68% | 35% | 6 | 49,6% |
| Guilherme Barbieri Renner | 67% | 33% | 5 | 45,2% |
| Eduardo Heineberg | 67% | 29% | 5 | 37,8% |
| Eduardo Ribeiro, Challenger Brasília | 53% | 11% | 4 | 28,4% |

**Inferência:** a principal hipótese de trabalho é vulnerabilidade do segundo saque e do `serve+1` diante de devoluções agressivas. Não atribuir causalidade sem dados de ponto a ponto, tipo/direção de serviço, rally, contexto de placar e qualidade do adversário.

**Simulação, não previsão:** com 67,8% de primeiros saques dentro e 55,4% dos pontos ganhos no primeiro, elevar a conversão no segundo de 31,5% para 45% produziria:
- `P(serviço) atual = 0.678 * 0.554 + 0.322 * 0.315 = 47,7%`
- `P(serviço) cenário = 0.678 * 0.554 + 0.322 * 0.450 = 52,1%`
- Ganho teórico de **4,4 pp** de pontos vencidos ao sacar, mantendo as outras premissas constantes.

Não implica aumento proporcional de partidas vencidas.

## 3. Consolidação de vantagem e pontos decisivos

- **Venceu o 1º set em 13 partidas; converteu 9 em vitória (69,2%).**
- **Quatro derrotas após ganhar o 1º set**, todas decididas em match tie-break:
  - Tsz Fu/Tao Wong (08/06, dura): `6-2, 3-6, [8-10]`
  - Gabriel Ribeiro Pinho (07/09, saibro): `6-4, 4-6, [8-10]`
  - Gabriel Schenekenberg (25/10, saibro): `6-1, 2-6, [6-10]`
  - Augusto Land (09/11, saibro): `6-2, 2-6, [8-10]`
- **Match tie-breaks em simples:** 6 disputados, 2 W / 4 L.
- Em partidas específicas, o estudo anterior reportou vitória em mais de 50% dos pontos totais e derrota no jogo (Wong 51,0%; Pinho 50,3%). A hipótese é distribuição desfavorável dos pontos, **não evidência isolada de fragilidade psicológica**.

Perguntas para análise posterior: perda de velocidade/precisão após o 1º set? Queda de 1º serviço? Aumento de duplas faltas em `30-30`, `deuce`, break points ou match tie-break? Mudança de posicionamento na devolução? Efeito de qualidade do adversário? Sem registro ponto a ponto e vídeo não é possível discriminar tais mecanismos.

## 4. Distância até o nível Challenger

Duas derrotas por `0-6, 0-6` em qualifying Challenger (Eduardo Ribeiro em Brasília e João Eduardo Schiessl em São Paulo) indicam distância competitiva relevante naqueles confrontos, mas o tamanho amostral é **n=2**. No estudo anterior foram reportados para Schiessl 41% de pontos ganhos com primeiro saque, 7% com segundo, 5 duplas faltas, 6 winners e 29 erros não forçados. **Esses indicadores de shot-level não foram reextraídos do site oficial neste registro e permanecem pendentes de auditoria.**

Implicação operacional: priorizar partidas que aumentem probabilidade de entrada e progressão em chaves principais M15/M25; Challenger como aferição seletiva, não como principal gerador esperado de vitórias.

## 5. Comparação por ranking: provisória

A planilha anterior registra ranking ATP do adversário quando encontrado e `SR` nos demais. **SR significa ausência de posição numérica verificada na base consultada, e NÃO comprova que o adversário era pior ranqueado ou não ranqueado na data.** Sem reconstruir o ranking semanal de Luka e do adversário, não é correto tratar os percentuais como oficiais.

Indicadores preliminares do estudo anterior:
- Derrotas contra adversário numericamente pior ranqueado entre confrontos com ranking conhecido: **1/14 = 7,1%** (Tsz Fu/Tao Wong; identidade e posições históricas a reconfirmar).
- Derrotas contra pior ranqueado **ou adversário marcado SR**: **10/23 = 43,5%**; **não usar como estatística de inferioridade real**.
- Vitórias contra adversários numericamente melhor ranqueados: **2/11 = 18,2%**; uma foi por retirada adversária (Tomás Meneo), e ambas requerem conferência da posição de Luka naquela semana.
- Identidades dos adversários do M25 Villa María de 03–05/05 estão em divergência entre a planilha anterior e o histórico do projeto; **não reconciliadas**. Conservar o snapshot original, sem substituição especulativa.

## 6. Plano de desenvolvimento — hipóteses a testar

| Prioridade | Intervenção | KPI | Meta proposta, sujeita ao treinador |
|:--|:--|:--|:--|
| P1 | Segundo saque + `serve+1`, inclusive sob pressão | % pontos ganhos no 2º serviço, hold rate | 40–45% de pontos de 2º serviço (partindo do reporte de 31,5%) |
| P1 | Reduzir duplas faltas mantendo profundidade/variação | Duplas faltas / pontos de serviço | <5%, contra reporte de 8,1% |
| P1 | Analisar transição entre sets e match tie-breaks | % conversão após ganhar 1º set; pontos em 30-30/deuce/BP | Linha de base por 8–10 jogos; não estabelecer causalidade sem vídeo |
| P2 | Sequência de M15 em quadra dura, com adversários comparáveis | % games e partidas vencidos; força do adversário | Acrescentar 8–10 jogos para reduzir incerteza |
| P1 | Melhorar transição qualificatório → chave principal | Chaves principais alcançadas e partidas vencidas | Superar 0/5 de vitórias em simples, com nível do adversário controlado |

## 7. Requisitos para auditoria point-by-point ITF/ATP

O snapshot **não contém feed oficial de todos os pontos**. Para transformar as hipóteses em conclusões auditáveis:

1. Vincular partida a identificadores oficiais estáveis ITF/ATP; conciliar data, torneio, superfície, adversário, retirada e placar.
2. Guardar URL oficial, data de coleta, origem da evidência e permissões de uso. Se não houver point-by-point disponível para determinado torneio, registrar indisponibilidade (nunca imputar).
3. Estrutura mínima de ponto: `match_id, set, game, point_index, server, receiver, score_before, first_serve_in, serve_number, point_winner, double_fault, break_point, tiebreak, source_url, captured_at, source_status`. Winners/UE/rally length somente com fonte que os publica.
4. Calcular intervalos por nível, superfície, fase de torneio e faixas de ranking; controlar qualidade do oponente e tamanho de amostra.
5. Revisar manualmente os 4 jogos de reversão após vencer o primeiro set e os 2 qualifying Challengers com vídeo/scorecard disponível.
6. Publicar indicadores novos no `data/*.json` **apenas após homologação** de schema, fontes, qualidade e pipeline. Este commit não executa tal promoção.

## 8. Proveniência, limites e qualidade

- **Base tabular de resultados**: planilha criada em 18/11/2026 com fontes secundárias por linha; links incluídos nos CSVs. Fonte principal declarada de simples: [TennisDatabaseAPI — histórico 2026](https://tennisdatabaseapi.com/players/pl_g9qkxeg3/2026); duplas: [TennisExplorer — 2026](https://www.tennisexplorer.com/player/bojicic-ono/?annual=2026).
- **Estatísticas de saque e pontos individuais**: números transcritos da análise conversacional anterior, com referência a Tennis Pythia, TennisLive/TennisTemple e supostos scorecards; não se anexou dump oficial PBP, nem se conseguiu reproduzir integralmente a extração nesta persistência. Indicadores técnicos = **provisórios**.
- **Rankings**: números do snapshot não são auditoria semanal oficial. Revisar links, ranking de Luka, ranking de cada adversário e apelidos/identidades; não presumir superioridade/inferioridade dos `SR`.
- **Superfície e calendário**: validar denominações e datas na ITF; a planilha anterior apresenta divergências de torneio/identidade (especialmente Villa María).
- **Amostras**: 7 jogos em dura, 2 jogos Challenger com dados específicos, e 6 derrotas com estatísticas detalhadas não têm força para inferências causais.
- **Preservação**: snapshots são evidências derivadas, **não fonte canônica** consumida pelo aplicativo. A fonte operacional atual segue `data/career.json` e automações existentes.

**Regra de uso:** manter separação entre resultado verificado na planilha, estatística secundária reportada, hipótese interpretativa e recomendação de treinamento. Até auditoria, não exibir métricas de PBP ou ranking como oficiais em dashboards públicos.

## Próximo passo de retomada

Reconciliar os três adversários de Villa María, normalizar Tsz Fu/Tao Wong, construir o ranking semanal por partida e coletar as páginas oficiais ITF/ATP com identificação de pontos. Após validação cruzada, atualizar esta revisão com carimbo de homologação e somente então propor integração ao frontend.
