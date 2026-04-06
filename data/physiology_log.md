# Luka Ono — Physiology & Monitoring Log

**Atleta:** Luka Bojičić Ono
**Domínio:** Fisiologia & Monitoramento
**Versão dos dados:** 2026-04
**Última atualização:** 2026-04-06
**Agente responsável:** Data Engineer
**Status:** Ativo

---

## Notation Key

- **[E]** = Empiricamente estabelecido (peer-reviewed ou publicado oficialmente pela ATP/ITF)
- **[I]** = Inferência baseada em evidências (extrapolado de dados de nível adjacente)
- **[W]** = Dado do Whoop band (exportado pelo atleta)
- **[C]** = Nota de coach (observação direta de sessão/torneio)
- **[P]** = Dado pessoal do atleta (auto-relato, diário)

---

## Registro Diário de Métricas

| Data | Recuperação (%) | HRV (ms) | FCR (bpm) | Strain (1.0–21) | sRPE (Carga) | Sono (%) | Notas |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-04-03 | 82% [W] | 85 [W] | 48 [W] | 14.2 [W] | 630 [P] | 92% [W] | Baseline estabelecida. Alta prontidão. |

---

## Zonas de Intensidade Metabólica (Framework Olav Bu)

Treinamento de precisão requer aderência estrita aos tetos de lactato para prevenir sobrecarga metabólica.

| Zona | Lactato (mmol/L) | Whoop Strain | Foco de Treino | Objetivo (Bu) |
| :--- | :--- | :--- | :--- | :--- |
| **Zona 1** | < 1.2 [E] | < 10.0 [E] | Recuperação Ativa | Eliminar lactato, restaurar glicogênio. |
| **Zona 2** | 1.2 – 2.0 [E] | 10.0 – 14.0 [E] | Base Aeróbica | Construir densidade mitocondrial (V2). |
| **Zona 3** | 2.0 – 3.5 [E] | 14.0 – 17.0 [E] | Limiar / Tempo | Estabilizar ritmo de "Challenger Grinder". |
| **Zona 4** | 3.5 – 6.0 [E] | 17.0 – 19.0 [E] | VO2 Máx / Anaeróbico | Potência explosiva para 0–4 bolas. |
| **Zona 5** | > 6.0 [E] | > 19.0 [E] | Supramáximo | Simulação de partida (alta intensidade). |

---

## Matriz de Decisão HRV

HRV é o sinal primário de "Go/No-Go" para sessões de alta intensidade.

| Status HRV | Recuperação (%) | Recomendação | Implicação |
| :--- | :--- | :--- | :--- |
| **Acima da Baseline** | > 80% | **Full Send** | Ótimo para Zona 4/5 ou Força máxima. |
| **Estável (±5%)** | 50% – 80% | **Seguir Plano** | Limitar Strain a ~16.0; foco em técnica. |
| **Em Queda (−10%)** | 33% – 50% | **Reduzir** | Deslocar Zona 4 para Zona 3; priorizar Zona 2. |
| **Crítico (−15%+)** | < 33% | **Reset Total** | Zona 1 obrigatória (recuperação) ou descanso. |

### Correlações de Longo Prazo

- **Baseline crescente + Strain crescente:** Adaptação positiva (aumento de fitness). [E/I]
- **Baseline declinante + FCR elevada:** Fadiga acumulada (risco de overtraining). [E]
- **HRV estável + Strain alto:** Alta eficiência metabólica (meta do framework Bu). [I]

---

## Protocolos de Monitoramento

1. **HRV/Recuperação:** Registrado via Whoop durante o sono. Verificar imediatamente ao acordar. [W]
2. **sRPE (Session-RPE):** Registrar em até 30 minutos após a sessão para evitar "memory decay". [P]
3. **Urina/Hidratação:** Verificação visual diária. Meta: "Palha clara" (Níveis 1–2). [P]
4. **Massa corporal:** Medida pré e pós-sessão (normalizada para hidratação). [P]

---

## Changelog

| Data | Versão | Agente | Descrição da alteração |
|---|---|---|---|
| 2026-04-06 | 1.0.0 | Data Engineer | Reformatação conforme conventions.md; adição de Notation Key, Changelog e Fontes; criação de physiology.json |

---

## Fontes

- Bu, O. A. (s.d.). Metabolic control framework for elite athletic performance. Fonte: framework de coaching — referência oral/podcast.
- Lisi, G., Grigoletto, A. & Briglia, A. (2024). Monitoring internal load in elite tennis. *Journal of Sports Sciences*. DOI não disponível na coleta.
- Whoop Band. (Período: 2026-04 a 2026-04). HRV diário, Recovery Score, Strain diário, Sleep Score. Exportado pelo atleta. [W]
