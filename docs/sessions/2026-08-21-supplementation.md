# Sessão 2026-08-20/21 — Suplementação prescrita

**Tema:** função bioquímica e mecanismo de ação do protocolo de suplementação
prescrito em 2026-08-20 para Luka Bojičić Ono.
**Branch:** `claude/vitaminas-funcao-bioquimica-anp3qs`
**PR:** [#4](https://github.com/hmono/Luka-Tennis-Player/pull/4) — aberto, draft
**Status:** encerrada. Retomar lendo este arquivo.

---

## Entregue

| Commit | Conteúdo |
| :--- | :--- |
| `982a272` | `docs/data-sources/supplementation.md` (v1.0.0) — prescrição tabulada, função bioquímica dos 11 itens, pontos críticos, fontes; índice atualizado em `docs/data-sources/README.md` |
| `7b4d2c3` | Camada "Mecanismo de ação" (v1.1.0) — subseção por item com química do passo catalítico, regulação e consequência fisiológica; mecanismo da interferência redox em 5 passos; fontes reorganizadas em 3 blocos |

Arquivo final: 357 linhas. Head do PR: `7b4d2c3`, `mergeable_state: clean`,
sem CI (mudança só em `docs/` não dispara workflow), sem review threads.

---

## Decisões tomadas

| Decisão | Razão |
| :--- | :--- |
| Documento em `docs/data-sources/`, não em `data/` | `data/README.md` proíbe `.md` no diretório de dados |
| Sem JSON correspondente | Material de referência humana; nenhum componente do app o consome |
| Framework Olav Bu removido do enquadramento | Instrução explícita do usuário em 2026-08-20 |
| Ponto crítico antioxidante mantido | Sustenta-se na literatura primária (Ristow 2009, Paulsen 2014, Morrison 2015), independe de framework |
| Duas camadas (função + mecanismo) | Decisões práticas do protocolo — forma do sal, horário da dose, redundância, plausibilidade ergogênica — só se resolvem no nível do mecanismo |

---

## Pendências (não executadas — aguardavam aprovação)

1. **Seção transversal em `supplementation.md`** — "Ação sobre radicais" e "Ação
   sobre cãibras", com matriz por item nos dois eixos e a ponte RyR1/SERCA
   (oxidação de cisteínas do RyR1 → vazamento de Ca²⁺; oxidação da SERCA →
   recaptação lenta). Conteúdo já elaborado na conversa de 2026-08-21, não
   commitado. Inclui o enquadramento de que a EAMC é desequilíbrio Ia/Ib
   (Schwellnus), não evento eletrolítico, e que o selênio é o único item com
   mecanismo simultâneo e não redundante nos dois eixos (GPx4 + SelenoN/RyR1).

2. **Campo de registro de cãibra em `physiology_log.md`** — hoje inexistente.
   `grep -ri 'cãibra|cramp'` no repo retorna zero: existe protocolo de
   eletrólitos (`nutrition.md:66`, 500–700 mg Na/h) mas nenhum evento logado.
   Sem esse dado, a discussão sobre cãibra permanece teórica.

---

## Próximos passos sugeridos

- Marcar o PR #4 como *ready for review* ou merge, conforme decisão do usuário.
- Se as pendências forem retomadas, abrir sessão nova (regra de higiene de
  sessão do `CLAUDE.md`) e partir deste arquivo.
- Exames que o documento indica como pré-requisito para revisar doses:
  25(OH)D, cálcio, PTH, e verificação de certificação de lote antidoping.
