# Especificação corretiva — fonte de rankings ATP

Status: proposta para aprovação  
Data: 2026-09-04  
Escopo: aquisição de rankings; domínio, outbox e CallMeBot permanecem válidos

## 1. Contexto e evidência

O coletor atual em `scripts/ranking_alerts/atp_source.py` usa Playwright para
consultar páginas oficiais da ATP. O teste real no ambiente do monitor produziu:

- HTTP 403/Cloudflare no perfil e ranking breakdown do atleta;
- HTTP 403 no endpoint de tabela de rankings com `ajax=true`;
- HTTP 403 no relatório PDF oficial;
- término do `dry-run` com `atp_source_timeout`;
- hashes de `data/rankings.json` e
  `automation/state/ranking_alerts.json` inalterados.

Conclusão: a lógica fail-closed funcionou, mas a fonte ATP web não é operacional
em runners cloud. Alterar user-agent, usar navegador stealth, cookies, CAPTCHA,
proxy rotativo ou técnicas equivalentes de evasão não faz parte da solução.

Esta especificação corrige e prevalece sobre as seções 2, 4.1, 5, 6, 7, 11,
14, 15 e 16 de `docs/ATP_RANKING_WHATSAPP_CALLMEBOT_SPEC.md` quando houver
conflito relacionado à fonte de rankings.

## 2. Objetivo

Obter semanalmente uma observação completa e auditável de Luka Bojicic Ono,
ATP ID `B0UF`, contendo para singles e doubles individual:

- data oficial da publicação do ranking;
- posição atual ou estado explicitamente não classificado;
- pontos oficiais;
- identidade inequívoca do atleta.

A fonte deve funcionar em ambiente equivalente ao GitHub Actions. A coleta deve
continuar sem efeitos persistentes quando qualquer campo obrigatório estiver
ausente, ambíguo ou incoerente.

## 3. Não objetivos

- Burlar ou contornar controles anti-bot da ATP.
- Inferir pontos a partir de resultados de torneios.
- Usar cache de mecanismo de busca como fonte operacional.
- Tratar ausência do atleta em uma resposta truncada como `rank: null`.
- Promover um fornecedor antes de validar cobertura real do atleta.
- Alterar a semântica at-least-once do CallMeBot ou introduzir banco/fila.

## 4. Decisão arquitetural

Promover o protocolo `RankingSource`, hoje definido junto ao adaptador ATP, para
uma porta neutra:

```text
RankingSource
  -> RawRankingObservation
  -> validação de contrato e identidade
  -> enriquecimento local de career high
  -> RankingObservation
  -> domínio, storage e outbox existentes
```

Contrato:

```python
class RankingSource(Protocol):
    name: str

    def fetch(self) -> RawRankingObservation: ...
```

`RawRankingObservation` contém somente dados fornecidos pelo source. Career high
não é obrigatório no contrato externo e será enriquecido localmente.

O source deve ser selecionado explicitamente por `RANKING_SOURCE`. Não haverá
fallback automático: trocar silenciosamente de fonte impediria distinguir
indisponibilidade, atraso e divergência de dados.

### 4.1 Proveniência

O snapshot deve registrar o fornecedor real, por exemplo `api-tennis`. Dados
obtidos de terceiros não podem ser rotulados como `atptour`.

A proveniência não participa da decisão de mudança esportiva. Uma troca de
provider na mesma data, com os mesmos ranks e pontos, não cria alerta nem
`ranking_correction`. O hash de conteúdo esportivo deve ser separado do registro
de proveniência ou a regra de revisão deve ignorar mudança apenas de source.

## 5. Qualificação obrigatória de provider

Nenhum provider alternativo será habilitado em produção antes de um spike
documentado com decisão `go` ou `no-go`.

API-Tennis é candidata, não decisão definitiva. O spike deve comprovar:

1. mapeamento inequívoco entre o atleta do provider e ATP ID `B0UF`;
2. singles e doubles individual, não equipe, dupla ou resultado de torneio;
3. posição e pontos em ambas as disciplinas;
4. data oficial da publicação, sem usar `date.today()` ou data do request;
5. cobertura além da posição 2.000 em singles e doubles;
6. semântica documentada para atleta ausente e não classificado;
7. duas publicações ATP consecutivas comparadas manualmente;
8. funcionamento em runner equivalente ao GitHub Actions;
9. autenticação, custo, termos, quotas, timeout e rate limit conhecidos;
10. payload estável o suficiente para fixture e validação fail-closed.

Falha em qualquer item obrigatório resulta em `no-go`.

Sportradar não atende ao requisito atual: o feed documentado de doubles
individual é limitado ao top 500. Só pode ser reconsiderado se o requisito de
cobertura for explicitamente reduzido.

## 6. Career high

O fornecedor não precisa fornecer career high. Criar baseline versionado e
manualmente verificado para singles e doubles:

```json
{
  "schema_version": 1,
  "player": { "atp_id": "B0UF", "name": "Luka Bojicic Ono" },
  "verified_at": "YYYY-MM-DDTHH:MM:SSZ",
  "disciplines": {
    "singles": {
      "rank": 0,
      "ranking_date": "YYYY-MM-DD",
      "reference": "manual-verification-reference"
    },
    "doubles": {
      "rank": 0,
      "ranking_date": "YYYY-MM-DD",
      "reference": "manual-verification-reference"
    }
  }
}
```

Os zeros são placeholders inválidos e devem ser substituídos por valores
verificados antes da ativação.

Para cada disciplina:

- o high é o menor rank entre baseline, histórico e observação atual;
- a data do baseline é preservada enquanto ele for o melhor resultado;
- um rank estritamente menor usa a primeira `ranking_date` observada;
- empates posteriores preservam a primeira data;
- baseline ausente, placeholder ou inconsistente causa falha antes de escrita;
- o primeiro snapshot continua sem gerar alerta.

Os valores `1827` para singles e `1784` para doubles existentes no histórico do
projeto não devem ser promovidos automaticamente a baseline sem nova verificação.

## 7. Erros e segurança

Erros públicos e persistidos devem usar códigos sanitizados:

- `ranking_source_blocked`;
- `ranking_source_authentication`;
- `ranking_source_rate_limited`;
- `ranking_source_timeout`;
- `ranking_source_schema_changed`;
- `ranking_source_identity_mismatch`;
- `ranking_source_incomplete`;
- `ranking_source_coverage_truncated`;
- `career_high_baseline_invalid`.

HTTP 403/challenge conhecido deve ser detectado após `domcontentloaded` e
retornar `ranking_source_blocked`, sem aguardar timeout genérico.

API keys, telefone, URLs assinadas, query strings autenticadas, bodies completos
e headers de autenticação não podem aparecer em logs, exceções ou commits.

## 8. Fluxo operacional

O fluxo de outbox existente é preservado:

```text
source.fetch
  -> validar observação completa
  -> enriquecer career high
  -> collect
  -> persistir snapshot + pending outbox
  -> commit/push da intenção
  -> deliver via CallMeBot
  -> persistir receipt/tentativa
  -> commit/push do estado
```

Invariantes adicionais:

- singles e doubles devem pertencer à mesma publicação;
- source ausente ou não configurado falha antes da rede;
- indisponibilidade não aciona fallback ou dry-run;
- erro de coleta não modifica rankings nem outbox;
- repetição da mesma observação é no-op;
- mudança somente de provenance é no-op esportivo;
- `dry-run` consulta e valida, mas não grava nem envia.

## 9. Configuração e secrets

Após aprovação de um provider:

```text
RANKING_SOURCE=<provider-approved-name>
RANKING_SOURCE_API_KEY=<repository secret>
CALLMEBOT_PHONE=<repository secret>
CALLMEBOT_API_KEY=<repository secret>
```

O nome concreto do secret da fonte pode ser especializado quando o provider for
aprovado, por exemplo `API_TENNIS_API_KEY`. Ele deve existir somente nos passos
de coleta/check-config, nunca em testes, build, Git ou entrega CallMeBot.

Enquanto o spike estiver pendente ou resultar em `no-go`, o schedule deve ficar
desabilitado. `workflow_dispatch` com fixture/dry-run local permanece permitido.

## 10. Plano de arquivos

| Arquivo | Mudança prevista |
| --- | --- |
| `scripts/ranking_alerts/source.py` | Porta neutra, DTO bruto e erros sanitizados. |
| `scripts/ranking_alerts/api_tennis_source.py` | Adaptador somente após gate aprovado. |
| `scripts/ranking_alerts/career_high.py` | Validação do baseline e enriquecimento. |
| `scripts/ranking_alerts/atp_source.py` | Manter como diagnóstico, sem source produtivo/fallback. |
| `scripts/ranking_alerts/domain.py` | Proveniência flexível e hash esportivo independente do provider. |
| `scripts/update_rankings.py` | Seleção explícita do source e enriquecimento antes de collect. |
| `data/ranking_career_high_baseline.json` | Baseline auditável, após verificação. |
| `tests/ranking_alerts/` | Contrato, baseline, cobertura, falhas e troca de provider. |
| `.github/workflows/update_rankings.yml` | Config/secret do source; schedule condicionado ao go. |
| `requirements-automation.txt` | Remover Playwright se nenhum coletor ativo o utilizar. |
| `docs/spikes/` | Evidências sanitizadas e decisão de provider. |

## 11. Testes obrigatórios

- provider válido normaliza singles, doubles, posição, pontos e data;
- atleta/ID divergente falha;
- singles ou doubles ausente falha;
- doubles de equipe em vez de individual falha;
- data ausente, local ou ambígua falha;
- pontos ausentes ou não numéricos falham;
- resposta truncada não vira `rank: null`;
- baseline ausente, placeholder ou inconsistente falha;
- novo high, empate e preservação da primeira data;
- troca apenas de provider não gera snapshot corretivo nem alerta;
- 401/403/429/5xx/timeout são categorizados e redigidos;
- erro deixa ambos os JSONs byte a byte inalterados;
- duas execuções idênticas são idempotentes;
- testes atuais de domínio, storage, providers e workflow permanecem verdes;
- nenhum teste chama ATP, provider de dados ou CallMeBot reais.

## 12. Critérios de aceite

1. O relatório do spike contém evidências de todos os gates e decisão `go`.
2. O provider aprovado entrega o atleta além do top 2.000 nas duas disciplinas.
3. Ranking, pontos e data são comparados com duas publicações verificadas.
4. Career high é produzido deterministicamente pelo baseline/histórico local.
5. Toda falha de coleta preserva rankings e outbox byte a byte.
6. Uma mudança esportiva cria no máximo uma intenção agregada pendente.
7. Reexecução idêntica não cria snapshot, revisão ou outbox duplicada.
8. Troca somente de provider/proveniência não envia alerta.
9. Outbox continua persistida antes do envio e entregue em FIFO.
10. Logs, fixtures e commits não contêm secrets ou payloads desnecessários.
11. Suites Python, Vitest e build passam.
12. Um dry-run real no ambiente do workflow conclui com sucesso.
13. O schedule só é habilitado após aprovação explícita do spike e dry-run.

## 13. Sequência de entrega

### Fase A — qualificação, sem produção

1. Obter chave trial do provider candidato.
2. Executar probe sanitizado no ambiente alvo.
3. Verificar manualmente duas publicações.
4. Registrar `go/no-go` em `docs/spikes/`.

### Fase B — implementação, somente após `go`

1. Extrair `RankingSource` neutro.
2. Implementar adapter e fixtures do provider aprovado.
3. Implementar baseline/enriquecimento de career high.
4. Corrigir idempotência para ignorar troca apenas de provenance.
5. Atualizar CLI, workflow, documentação e testes.
6. Executar suites e dry-run real.
7. Habilitar schedule após aprovação explícita.

## 14. Rollback

Em erro pós-ativação:

1. desabilitar o schedule;
2. preservar snapshots e outbox para auditoria;
3. não marcar pendências como `sent` sem receipt;
4. reverter somente a seleção/configuração do source;
5. reativar após fixture, teste de regressão e novo dry-run real.

Não remover histórico válido nem force-pushar estado operacional.

## 15. Spec 1 — PDFs alfabéticos oficiais em runner próprio

Decisão de 2026-09-04: implementar uma fonte candidata `atp-pdf`, sem
promovê-la a produção. Os endpoints fixos são os relatórios alfabéticos de
singles e doubles publicados pela ATP. O adaptador faz downloads HTTPS comuns,
limitados e em memória; não contorna Cloudflare e não persiste os PDFs.

O pipeline de qualificação é deliberadamente separado do pipeline de produção:

```text
workflow_dispatch
  -> runner dedicado [self-hosted, macOS, atp-ranking]
  -> testes sem rede
  -> probe ATP PDF somente leitura
  -> evidência sanitizada
  -> revisão humana go/no-go
```

O workflow não recebe secrets, não grava `data/rankings.json`, não altera a
outbox e não chama CallMeBot. O schedule, a coleta persistente e a entrega só
podem retornar em mudança posterior e explicitamente aprovada.

### Gates ainda pendentes

- confirmar no Mac o layout textual real de ambos os PDFs;
- confirmar que a linha do atleta contém rank e pontos individuais corretos;
- resolver identidade inequívoca: se o PDF não expuser ATP ID, criar crosswalk
  local versionado com nome do relatório, nacionalidade e referência auditável;
- comprovar que o documento está completo antes de interpretar ausência como
  atleta não classificado;
- comparar duas publicações consecutivas com verificação manual;
- substituir o baseline inválido de career high por valores e referências
  verificadas.

Enquanto esses gates estiverem pendentes, o resultado operacional é `no-go`.
Uma execução bem-sucedida do parser é apenas evidência candidata e nunca altera
automaticamente essa decisão.

### Evidência permitida

Pode ser registrada somente informação sanitizada: status/código, hashes e
tamanhos dos documentos, data de ranking, presença das duas disciplinas e
decisão. Não commitar PDF oficial, texto integral extraído, headers, cookies ou
conteúdo de resposta de bloqueio.
