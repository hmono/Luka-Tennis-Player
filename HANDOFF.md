# Handoff — branch `claude/ronaldo-abud-research-n9u96v`

**Sessão:** 2026-08-18 / 2026-08-19
**Pedido de origem:** "Pesquise Dr. Ronaldo Abud" — que evoluiu para preparar a consulta médica do Luka sobre cãibras recorrentes
**Status:** entregue; dois PRs abertos em draft, aguardando revisão

> **Consolidação:** o PR #3 (branch `claude/ronaldo-abud-prep-de514q`, de outra sessão) saiu deste branch em `8331607` e trouxe a rev. 3 do documento de consulta. Como os dois lados tocaram arquivos disjuntos, foi mergeado aqui sem conflito e o #3 foi fechado. O PR #1 carrega tudo.

---

## O que foi entregue

| # | Arquivo | PR | O que é |
| :--- | :--- | :--- | :--- |
| 1 | `docs/data-sources/ronaldo_abud_dossier.md` | #1 | Pesquisa sobre o médico |
| 2 | `docs/data-sources/consulta_dr_abud_2026-08-19.md` | #1 | Preparação da consulta (rev. 2) |
| 3 | `scripts/md2pdf.py` | #1 | Pipeline Markdown → PDF A4 |
| 4 | `.gitignore` | #2 | Faltava no repo |

**PRs:** [#1](https://github.com/hmono/Luka-Tennis-Player/pull/1) (dossiê + consulta + pipeline) · [#2](https://github.com/hmono/Luka-Tennis-Player/pull/2) (`.gitignore`, sai de `main`, independente)

Nenhum arquivo em `data/`, `app/`, `lib/` ou `components/` foi tocado. Os documentos são referência humana e não são importados pelo app.

---

## Decisões tomadas, e por quê

Registradas aqui porque o raciocínio não é óbvio pelo diff.

### O dossiê é curto de propósito

O rastro digital público do Dr. Abud é mínimo. **Um** fato se sustenta com corroboração: é docente da pós-graduação em Cardiologia do Esporte e do Exercício (programa Cardioesporte, do Prof. Dr. Nabil Ghorayeb), na disciplina *"Oxidação, inflamação e radicais livres no exercício físico"*.

Não foram encontrados: CRM/RQE, consultório, Doctoralia, LinkedIn, Lattes, produção indexada. Não inflei a biografia com o que não pude confirmar.

**Limitação de método que trava a confiança:** o proxy de egresso do ambiente de pesquisa bloqueou acesso direto a **todas** as fontes primárias (`medicineposgraduacao.com.br`, `cardioesporte.com.br`, `cardiofitness.com.br`, `pubmed`). O conteúdo veio de snippets de mecanismo de busca. Por isso o documento adota escala `[V]`/`[C]`/`[?]`/`[X]` e **nenhuma afirmação atinge `[V]`**. A seção 7 do dossiê deixa a rota de verificação pronta para quem retomar de uma rede sem bloqueio.

### O documento de consulta mudou de eixo duas vezes

**rev. 1** tratava o **teste de sódio no suor** como a lacuna decisiva.

**rev. 2** — primeiro bloco de respostas do atleta: cãibra na panturrilha, a partir do 2º set, nos momentos tensos, **nunca em treino**, há 12 meses, sal moderado. "Nunca em treino" enfraqueceu a depleção de eletrólitos, e o teste de suor caiu para "descarte formal".

**rev. 3** — segundo bloco de respostas, trazido pelo branch `claude/ronaldo-abud-prep-de514q` (PR #3, consolidado aqui). Três achados materiais:

> A cãibra é **específica do saque**, sempre. **Trava entre os pontos**, não durante. E o atleta **toma Gatorade em jogo e nada em treino**.

**O terceiro é o discriminador mais forte do dossiê.** Ele repõe sódio exatamente na condição em que tem cãibra, e não repõe naquela em que nunca tem. Sob depleção, o cenário de risco seria o treino. Isso não apenas enfraquece o eixo eletrolítico — praticamente o inverte.

Consequências, todas já aplicadas no documento:
- Teste de sódio no suor **rebaixado de novo**, para "opcional, baixo rendimento"
- **Hipótese unificadora:** volume e intensidade de saque em jogo não são replicados no treino. Amarra os três discriminadores sem invocar eletrólito, e é testável — basta contar saques em treino versus em partida
- **CK 1.024 reposicionada** como predisposição de fundo, não gatilho — com a **creatina** somada como confundidor da leitura
- **Componente de tensão derrubado** pelo próprio atleta; a contradição com o relato da rev. 2 ficou **registrada na seção 5**, não apagada
- Síndrome compartimental crônica **muito enfraquecida** — trava no repouso, não no esforço
- Perguntas reescritas: **23 itens em blocos A–F**, lideradas pelo gesto do saque
- **Magnésio já está em uso** e as cãibras continuam — teste empírico em curso, e falhando

### O que não fiz, deliberadamente

- **Não integrei ao app.** Não há vínculo confirmado entre o Dr. Abud e o Luka que justifique tratá-lo como equipe de suporte em `data/player.json`.
- **Não atualizei `docs/data-sources/README.md`.** A tabela de lá mapeia documento → JSON correspondente; estes documentos não têm JSON, e uma linha nova criaria correspondência falsa.
- **Não versionei o PDF gerado.** O `.md` é a fonte de verdade; o PDF se regera com `scripts/md2pdf.py`.
- **Não incluí dados de contato de agregadores** (ZoomInfo/RocketReach) que apareceram nas buscas — procedência não curada, e é dado pessoal sem valor para o projeto.
- **Não rodei `docs/data-sources/MIGRATE.sh`.** Os `.md` de `data/` continuam onde estavam; fora de escopo.

---

## Pipeline de PDF

```bash
pip install markdown
python scripts/md2pdf.py docs/data-sources/consulta_dr_abud_2026-08-19.md
```

Gera A4 pronto para impressão, com as caixinhas `- [ ]` marcáveis. Descobre o Chromium sozinho (`$CHROME_BIN` → PATH → bundle Playwright em `/opt/pw-browsers/`).

Verificado na rev. 3: **13 páginas** para o documento de consulta, 6 para o dossiê. As **23 perguntas** ocupam as **páginas 7–8**; o **resumo de uma página** está na **página 10**. Para levar impresso o mínimo útil: páginas 7, 8 e 10.

---

## O que ficou em aberto

### 1. A seção 9 do documento de consulta está em branco

É o registro pós-consulta: diagnóstico de trabalho, exames pedidos com prazo, o que muda no treino, conduta aguda em quadra. Preencher **logo após o atendimento**, antes que a memória degrade.

Ela termina com um checklist de propagação para o resto do repo:
- `luka_tennis_findings.md` Seção 09 — fenótipo e novos marcadores
- `data/nutrition.json` — sódio/hora em jogo **e** introdução de reposição em treino
- `data/physiology.json` — se entrar novo marcador de monitoramento
- `data/physical.json` — se entrar trabalho específico de panturrilha
- `data/tactical.json` / rotina de treino — se mudar o volume de saque

### 2. Itens de fenótipo não levantados

Listados no fim da seção 5. Os de maior retorno, todos baratos:

- **Piso e calçado** — jogo e treino são no mesmo piso, com o mesmo tênis? Saibro e piso rápido impõem cargas de panturrilha muito diferentes. É a maior lacuna restante, e um confundidor não controlado da hipótese do saque.
- **Contagem de saques** em treino versus em partida, com intensidade — testa a hipótese unificadora a custo zero.
- **Duração e horário** de treino versus partida — controla a ressalva metodológica do discriminador do Gatorade.
- **Reconciliar as respostas A e F** — trava ao subir para sacar, ou na pausa depois do game em que sacou?

### 3. A origem do nome

**Nada no registro público conecta o Dr. Abud ao Luka, ao tênis ou a Campinas.** Sem saber de onde veio a indicação, não dá para dizer se o dossiê descreve um contato relevante ou uma pista falsa. É o passo 6 da seção 7 do dossiê.

### 4. Verificação do médico numa rede sem bloqueio

Consulta CRM, Lattes/CNPq, PubMed, e a página do corpo docente do programa — elevariam a identificação de `[C]` para `[V]`.

---

## Notas operacionais

- **Sem CI nestes branches.** `.github/workflows/deploy.yml` só dispara em push para `main`; `get_status` retorna `pending` com `total_count: 0`, que é ausência de checks, não falha.
- **Verificação executada:** `npm test` (77 testes, 4 arquivos, todos passando) e `npm run build` (export estático sem alteração de rotas).
- **`package-lock.json`** foi alterado pelo `npm install` durante a verificação e revertido antes do commit — não faz parte do diff.
- **Artefatos de build** (`node_modules/`, `.next/`, `out/`, `next-env.d.ts`) foram removidos após a verificação. O PR #2 evita que reapareçam como não rastreados.
