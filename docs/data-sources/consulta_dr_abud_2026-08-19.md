# Consulta Dr. Ronaldo Abud — Preparação

**Atleta:** Luka Bojičić Ono (21a · 180 cm · 75 kg · Campinas)
**Domínio:** Cãibras recorrentes de esforço (EAMC)
**Consulta:** 2026-08-19, 15h00 — Dr. Ronaldo Abud, médico do esporte e do exercício
**Objetivo declarado:** resolver as cãibras recorrentes
**Versão dos dados:** 2026-08
**Última atualização:** 2026-08-18
**Agente responsável:** Research
**Status:** Pré-consulta — seção 8 a preencher após o atendimento

---

## Notation Key

- **[E]** = Empiricamente estabelecido (peer-reviewed)
- **[I]** = Inferência baseada em evidências
- **[L]** = Laboratorial (painel 23/06/2026, lab Orosimbo Maia)
- **[R]** = Do próprio repositório (`luka_tennis_findings.md`, `data/*.json`)
- **[?]** = A levantar / não medido

> **Enquadramento:** este documento prepara a conversa com o médico. Não é diagnóstico nem conduta. Quem examina, decide e prescreve é o Dr. Abud, em conjunto com o Dr. Tales Saia.

---

## 1. Estado do caso — o que já se sabe

O painel de 23/06/2026 (solicitante Dr. Tales Saia) já fez metade do trabalho. Ver `luka_tennis_findings.md`, Seção 09.

### Já excluído como causa

| Hipótese afastada | Marcador | Valor |
| :--- | :--- | :--- |
| Disfunção tireoidiana | TSH | 2,05 uUI/mL [L] |
| Anemia / deficiência de ferro | Hb · Ht · Ferritina · B12 | 15,3 · 45,9 · 116 · 699 [L] |
| Hipocalemia | Potássio | 4,6 mmol/L [L] |
| Hipocalcemia | Cálcio total | 10,0 mg/dL [L] |
| Disfunção renal | Creatinina · eGFR | 0,96 · >90 [L] |
| Alteração glicêmica | Glicemia jejum | 84 mg/dL [L] |

### O achado que sobrou — e que é o eixo da consulta

| Marcador | Valor | Referência | Leitura |
| :--- | :--- | :--- | :--- |
| **CK (creatinoquinase)** | **1.024 U/L** | <190 | **~5,4×**, repetida e confirmada [L] |
| AST / ALT | 46 / 42 U/L | <50 / <50 | Topo; acompanham a CK → origem **muscular**, não hepática [L] |
| Ureia | 43 mg/dL | 19–44 | Topo → hidratação subótima, modulador de cãibra [L] |

> **Síntese:** o painel afasta distúrbio metabólico de repouso. Resta a **CK elevada**, que sustenta o eixo de dano muscular e sub-recuperação. [L/I]

---

## 2. As duas teorias da cãibra de esforço

Entender isto é o que permite acompanhar o raciocínio do médico amanhã. As duas levam a **condutas diferentes**.

### Teoria 1 — Depleção de eletrólitos / desidratação

Perda de sódio pelo suor contrai o compartimento de líquido intersticial, deformando mecanicamente as terminações nervosas e tornando-as hiperexcitáveis. [E]

Base do fenótipo **"salty sweater"** — atleta com alta concentração de sódio no suor. Contexto clássico: calor, sudorese alta, jogo prolongado. Tênis é cenário típico. [E]

### Teoria 2 — Controle neuromuscular alterado *(dominante na literatura atual)*

A fadiga muscular aumenta a atividade excitatória do fuso muscular (aferente Ia) e **reduz** a inibição do órgão tendinoso de Golgi (aferente Ib). O motoneurônio alfa fica hiperexcitável e a cãibra é uma descarga sustentada. [E]

Evidências que a sustentam: a cãibra atinge o **músculo específico sobrecarregado**, não o corpo todo; ocorre também em clima fresco; o **alongamento alivia**, porque recarrega o órgão de Golgi. [E]

> **Consenso atual:** as duas operam, em **fenótipos diferentes** de atleta. Distinguir o fenótipo do Luka é o objetivo prático da consulta. [E/I]

---

## 3. Onde o Luka provavelmente se encaixa

A CK 5,4× elevada aponta com força para o **eixo neuromuscular / dano + sub-recuperação**, não para depleção eletrolítica. [L/I]

E há um mecanismo concreto no próprio repositório. A Seção 07 mostra que o nível ITF, onde ele compete, é o **mais punitivo metabolicamente** dos três: [R]

| Variável | ATP Tour | Challenger | **ITF M25/M15** |
| :--- | :--- | :--- | :--- |
| Pontos por set | 45–50 | 47–53 | **50–58** |
| Bolas por ponto (média) | 3,9–4,2 | 4,3–4,7 | **4,5–5,0** |
| Quebras por set | 1,2–1,5 | 1,5–2,0 | **2,0–2,8** |
| Demanda glicolítica | Menor | Média | **Maior** |

Mais pontos por set, ralis mais longos, mais quebras — com protocolo de recuperação frequentemente relaxado por ser "só ITF". A **Prioridade de Desenvolvimento 05** já registrava isso antes das cãibras entrarem em pauta: *"Recovery protocols should not be relaxed at ITF level."* [R]

---

## 4. A lacuna decisiva — teste de sódio no suor

Nunca foi feito. É a medida que **define o fenótipo salty sweater**. [?]

O protocolo intra-jogo atual (`data/nutrition.json`) prevê **500–700 mg de sódio/hora**. [R]

Ordem de grandeza da perda em cenário de salty sweater sob calor:

| Parâmetro | Faixa típica |
| :--- | :--- | 
| Taxa de sudorese em tênis sob calor | 1,0 – 2,0 L/h [E] |
| Concentração de Na⁺ no suor (salty sweater) | 1.200 – 1.800 mg/L [E] |
| **Perda horária resultante** | **1.800 – 3.600 mg/h** [I] |

> Se o Luka for esse fenótipo, o protocolo repõe cerca de **um terço** da perda — e nenhum ajuste de carga de treino corrigiria isso. Daí a prioridade do teste. [I]

### Demais lacunas do painel [R]

Sódio sérico · Magnésio · 25-OH-vitamina D · Cálcio iônico + albumina · **repetir CK em repouso (48–72h sem treino)**

---

## 5. Lição de casa — levantar ANTES da consulta

O médico vai perguntar. "Não sei" desperdiça o atendimento.

### Fenótipo da cãibra
- [ ] Qual músculo, especificamente? (panturrilha · posterior de coxa · adutor · abdome)
- [ ] Em que momento? (3º set · minuto 90 · já no aquecimento)
- [ ] Só em jogo, ou também em treino?
- [ ] Só no calor, ou também em dia fresco?
- [ ] Desde quando? Está piorando?

### Rastreio de salty sweater (grosseiro, mas informativo)
- [ ] Fica **crosta branca de sal** no boné, camiseta, viseira?
- [ ] Suor arde no olho / gosto salgado marcante?

### Taxa de sudorese — medir num treino
- [ ] Pesar **sem roupa** antes e depois da sessão
- [ ] Anotar o volume ingerido durante
- [ ] Calcular: `(kg perdidos + litros ingeridos) ÷ horas` = **L/h**

> É o número que ninguém tem e todo médico do esporte quer.

### A realidade, não o protocolo
- [ ] O que ele **de fato** bebe e come em jogo — não o que está no plano

### Contexto
- [ ] Suplementos em uso hoje
- [ ] Histórico familiar de cãibra ou doença muscular
- [ ] Sono e carga nas semanas em que as cãibras apareceram

---

## 6. Perguntas para o Dr. Abud

### Sobre a CK — o achado central
- [ ] **1.** CK de 1.024 confirmada, tenista de 21 anos em treino: é carga esperada, ou sinaliza dano além do adaptativo?
- [ ] **2.** Podemos repetir a CK **em repouso real** (48–72h sem treino) para conhecer a linha de base verdadeira?
- [ ] **3.** Há risco de rabdomiólise? Que sinais justificariam pronto-socorro?

### Sobre o fenótipo — maior retorno da consulta
- [ ] **4.** Faz sentido o **teste de sódio no suor**? Onde se faz? Muda a conduta?
- [ ] **5.** Se ele for salty sweater, **quanto sódio por hora em números**, versus os 500–700 mg/h atuais?

### Sobre as lacunas do painel
- [ ] **6.** Vale medir **magnésio, sódio sérico, vitamina D, cálcio iônico com albumina**?
- [ ] **7.** Em cãibra recorrente de atleta jovem, investigaria **traço falciforme** ou **miopatia metabólica**? Ou o painel já afasta?
- [ ] **8.** Se as cãibras forem localizadas em perna com o esforço, entra **síndrome compartimental crônica de esforço** no diferencial?

### Sobre carga e recuperação
- [ ] **9.** Sabendo que o ITF tem mais pontos e ralis mais longos por set que Challenger e ATP, isso é causa plausível de sub-recuperação crônica?
- [ ] **10.** O que mudaria na semana: volume, densidade, ou dias entre competições?

### Sobre a especialidade dele — e o timing
- [ ] **11.** Se indicar antioxidante: **em que momento do dia e em que fase do bloco?** (dose alta na janela pós-treino pode atenuar a adaptação ao treino)
- [ ] **12.** Que marcador acompanharia para saber se a conduta funciona — CK seriada, marcador inflamatório, ou clínico?

### Fechamento — não sair sem isto
- [ ] **13.** Qual o **plano de reavaliação**: que exame, em quanto tempo, o que define sucesso?
- [ ] **14.** Pode conversar com o **Dr. Tales Saia** (solicitante do painel) e com os treinadores **Ricardo Siggia** e **Alexandre Bonatto**?

---

## 7. Como interpretar as respostas

### O primeiro fork — para onde ele aponta a causa

| Se ele disser | Eixo que segue | Conduta esperada | Como ler |
| :--- | :--- | :--- | :--- |
| "A CK explica: dano e sub-recuperação" | **Neuromuscular** | Ajuste de carga, recuperação, alongamento, condicionamento | Coerente com os dados. Solução é de **treino**, não de suplemento — e é mais lenta. |
| "Vamos testar o suor / repor mais sódio" | **Eletrolítico** | Teste de Na⁺ no suor, reposição individualizada | Coerente. Exigir o **teste**, não só aumento empírico de sal. |
| "São os dois, em proporções diferentes" | **Consenso atual** | Ataca as duas frentes | **Melhor resposta.** Indica domínio da literatura de EAMC. |
| "É falta de magnésio/potássio" *sem pedir exame* | — | Suplemento genérico | ⚠️ Potássio **já medido e normal** (4,6). Magnésio nunca medido. Pedir o exame. |

### Sinais de consulta bem conduzida
- Pede a **CK em repouso** antes de concluir qualquer coisa
- Pergunta **qual músculo e em que minuto** — pensa em fenótipo, não em receita
- Menciona o **teste de sódio no suor** por conta própria
- Pergunta da **carga de treino e do calendário**, não só de dieta e suplemento
- Quer **falar com os treinadores**

### Sinais para desconfiar
- Prescreve suplemento **sem** pedir nenhum exame novo
- Atribui a magnésio **sem medir** magnésio
- Ignora a CK de 1.024 — único achado alterado do painel
- Promete resolução rápida (EAMC com CK elevada raramente resolve em semanas)

### Leitura específica da resposta sobre a CK

| Resposta | Como interpretar |
| :--- | :--- |
| "Normal para atleta em carga" | Aceitável **se** pedir repetição em repouso. Sem isso, não se sabe se 1.024 é piso ou pico. |
| "Preocupante, vamos investigar" | Esperar pesquisa de miopatia metabólica e possivelmente traço falciforme. Investigar é conduta correta, não sinal de gravidade. |
| "Irrelevante para a cãibra" | Pedir o raciocínio. É o único marcador alterado; descartá-lo exige justificativa. |

### Se propuser antioxidante — ouvir o *quando*, não só o *quê*

| Resposta | Leitura |
| :--- | :--- |
| "Tome sempre, logo após o treino" | Perguntar sobre efeito na adaptação — é exatamente a janela em que os ROS sinalizam o ganho do treino [E] |
| "Depende da fase: em bloco de base evitamos, em competição usamos" | Resposta sofisticada. Domina o tema. |

> Contexto: a disciplina que o Dr. Abud ministra é *"Oxidação, inflamação e radicais livres no exercício físico"* — ver `docs/data-sources/ronaldo_abud_dossier.md`. É provável que a suplementação antioxidante entre na conversa.

### Critério de saída

Sair da consulta com **três coisas escritas**:

1. **Diagnóstico de trabalho** — qual eixo
2. **Exames pedidos**, com prazo
3. **O que muda amanhã** no treino e na hidratação

Faltando qualquer uma, perguntar antes de sair.

---

## 8. Registro pós-consulta

*A preencher em 2026-08-19, logo após o atendimento — antes que a memória degrade.*

### Diagnóstico de trabalho
>

### Exames solicitados
| Exame | Prazo | Onde |
| :--- | :--- | :--- |
|  |  |  |

### Conduta — o que muda imediatamente
| Área | Mudança |
| :--- | :--- |
| Hidratação / sódio |  |
| Nutrição |  |
| Carga de treino |  |
| Suplementação (e **timing**) |  |

### Respostas às perguntas-chave
| # | Pergunta | Resposta |
| :--- | :--- | :--- |
| 1 | CK 1.024 — carga ou dano? |  |
| 4 | Teste de sódio no suor? |  |
| 9 | Carga ITF como causa? |  |
| 13 | Plano de reavaliação |  |

### Reavaliação
- **Data:**
- **Critério de sucesso:**

### Propagação para o repositório
- [ ] Atualizar `luka_tennis_findings.md` Seção 09 com os novos marcadores
- [ ] Ajustar `data/nutrition.json` se o sódio/hora mudar
- [ ] Registrar em `data/physiology.json` se entrar novo marcador de monitoramento

---

## Fontes

- `luka_tennis_findings.md` — Seção 09 (marcadores laboratoriais, coleta 23/06/2026) e Seção 07 (demanda metabólica por nível)
- `data/nutrition.json` — protocolo intra-jogo de sódio e hidratação
- `data/player.json` — biometria do atleta
- `docs/data-sources/ronaldo_abud_dossier.md` — perfil e domínio técnico do médico
- Literatura de EAMC: teoria da depleção de eletrólitos vs. teoria do controle neuromuscular alterado
