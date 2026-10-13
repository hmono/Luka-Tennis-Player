# Auditoria operacional independente — ATP H2 / issue #22

13/10/2026 UTC. Repositório `hmono/Luka-Tennis-Player`; PR draft [#18](https://github.com/hmono/Luka-Tennis-Player/pull/18); escopo [H2-03 #22](https://github.com/hmono/Luka-Tennis-Player/issues/22). Código auditado: `147b1e4`. Worktree isolado `/home/ono/luka-h2-22-qa`, branch `review/h2-22-qa`.

**Conclusão sobre a base auditada: NO-GO para merge/ativação.** A suíte existente passa, mas a repro de backlog comprova que uma coleta FRESH atual libera também digest de edição anterior. Esse P1 foi comunicado e aceito pelo coordenador para correção na integração. A recuperação da fonte também faz uma tentativa incerta deixar de aparecer como falha de revisão; esse segundo P1 do código foi aceito pelo coordenador. Existe ainda um P1 operacional pré-existente: o workflow legado em `main` permanece ativo e não consulta a flag do PR. As restrições da issue não autorizam alterar esse workflow; ele não foi executado nem interrompido nesta auditoria. Este relatório registra a base, não afirma que uma correção posterior foi homologada.

Nenhum P0 foi demonstrado. Isso não constitui prova de ausência de defeitos: não houve teste remoto de envio, verificação de entrega ao dispositivo, nem simulação de todas as falhas do runner/provider. O calendário expira em 26/10 e continuam necessários os gates documentais e as duas publicações novas consecutivas do [relatório anterior](../ATP_RANKING_HOMOLOGATION_20261013.md).

## Limites e preservação

Somente este relatório foi escrito/commitado no repositório. Código e testes versionados permaneceram inalterados. Repros usam `/tmp`, fontes fictícias, provider mock e, para concorrência, remote Git bare exclusivamente local. Não houve CallMeBot real, consulta de valores de secrets, alteração de flag, workflow remoto, merge, push remoto ou publicação GitHub. Consultas GitHub foram de issue/PR, conteúdo do workflow e metadata de runs/jobs, sem logs.

Os hashes foram comparados com os bytes de `147b1e4`, sem alterar os arquivos:

| Arquivo | SHA-256 | Resultado |
|---|---|---|
| `data/rankings.json` | `f310ca9400d51ede71a58f9d36336d42d1bef0535fba3993cd44b9642d11ebd1` | Igual à base |
| `automation/state/ranking_alerts.json` | `8d8922a121b7a2466d1f544a97358d37f692662d82c9ba34e66060d4060b015a` | Igual à base |

`automation/state/ranking_incidents.json` não existe no worktree; nenhum ledger produtivo foi criado. Os objetos em fixtures/repros são sintéticos; pontos ausentes permanecem `None`, sem conversão para zero.

## Semântica Actions verificada em fonte oficial

O GitHub executa schedule na default branch e exige que o arquivo exista nela. UTC é o padrão sem timezone explícito; atrasos/cargas elevadas podem ocasionar descarte. Repositórios públicos sem atividade por 60 dias podem ter schedule desativado. O payload permite identificar a expressão com `github.event.schedule`. Assim, os crons do PR draft ainda não estão ativos. [GitHub: eventos schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

O grupo compartilhado permite uma execução ativa e, por padrão, apenas uma pendente; uma nova execução substitui a pendente anterior. `cancel-in-progress: false` preserva a ativa, mas não garante que todas as pendentes serão executadas. A ordem efetiva depende do início da espera; não pode ser usada como prova de entrega ordenada. [GitHub: concorrência](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

| Agendamento no PR / base | Horário em São Paulo em outubro/2026 | Relação com cutoff |
|---|---|---|
| `0 12 * * 2-5` (`update_rankings.yml:7`) | Terça a sexta 09:00 | Quinta 09:00 ainda precede cutoff |
| `5 15 * * 4` (`update_rankings.yml:8`) | Quinta 12:05 | Cinco minutos após cutoff interno quinta 12:00 |
| Cron legado `main`, `0 9 * * 2` | Terça 06:00 | Não inclui checagem na quinta |

`config/atp_publication_calendar.json:14` fixa `America/Sao_Paulo`, três dias após segunda e 12:00 local; `freshness.py:85` converte cutoff para UTC. Para a edição 12/10, o corte é `2026-10-15T15:00:00Z`. Não é garantia de publicação ATP nem de início pontual do GitHub. O relógio da coleta, e não o slot nominal, decide freshness. Em `2026-10-27T02:59:59Z` ainda é 26/10 local; a partir de `03:00:00Z` a validade local expira, inclusive se a fonte retorna 26/10.

## Achados por severidade

### H2-QA-01 — P1, backlog antigo é enviado após liberação FRESH da edição atual

**Defeito demonstrado na base e aceito pelo coordenador para correção.** `scripts/update_rankings.py:170`/`:187` mantém intenções de edições anteriores; a substituição só trata revisões da mesma data. `scripts/update_rankings.py:271`/`:272` entrega qualquer `_sendable` sem conferir a edição recém-confirmada. `.github/workflows/update_rankings.yml:88` usa um boolean FRESH, sem vincular o lote à edição confirmada.

Repro independente A, abaixo, parte de histórico 28/09, outbox vazia e incidente SOURCE_ERROR sintético de 05/10:

1. Fonte retorna 05/10 em 13/10 12:00 UTC: `PENDING_PUBLICATION expected_date=2026-10-12 actual_date=2026-10-05`, `snapshot=created outbox=created`, `sporting_delivery_allowed=false`. Recupera o incidente 05/10. `--incidents-only` não envia digest nem modifica a pendência.
2. Fonte passa a 12/10 no mesmo dia: `FRESH`, nova intenção criada e output true.
3. `deliver` com provider mock retorna `provider_accepted=2`: `ATP Ranking — 2026-10-05` seguido de `ATP Ranking — 2026-10-12`. Os dois itens viram `sent`, embora só a última edição tenha sido liberada como atual.

Isso não depende exclusivamente de catch-up PENDING: também ocorre quando uma edição antiga foi FRESH, ficou pendente por indisponibilidade anterior ao provider e só houve nova entrega após a semana seguinte. A flag de liberação e o checkpoint protegem autorização/durabilidade, mas não filtram antiguidade. A repro usa checkpoint mock para isolar a seleção; a corrida Git separada valida o checkpoint real. Não é uma execução do interpretador Actions.

**Correção proposta:** vincular a entrega esportiva à edição confirmada nesta coleta ou bloquear pendências antigas para reconciliação explícita; preservar intenções antigas, snapshots e receipts. Adicionar regressão CLI/workflow demonstrando que liberar 12/10 não envia 05/10. Não apagar pendências para fazer o teste passar. Até a correção e reverificação, permanece P1 aberto na base deste relatório.

### H2-QA-02 — P1 operacional pré-existente: ausência de flag não desativa legado em main

O conteúdo remoto de `.github/workflows/update_rankings.yml` em `main` `833eafa6702bc5be14349a4efcead924c18fa55f` tem cron `0 9 * * 2`, default dispatch `collect-and-deliver`, coleta/entrega condicionadas apenas a `inputs.mode != 'dry-run'`, sem `ATP_RANKING_DELIVERY_ENABLED` e sem o gate FRESH novo. A API de workflow retornou `state=active`.

| Run schedule em main | SHA | Coleta / commit inicial / entrega / receipts | Dry-run |
|---|---|---|---|
| [37489325767, 06/10 15:39:17Z](https://github.com/hmono/Luka-Tennis-Player/actions/runs/37489325767) | `833eafa` | Todas `success` | `skipped` |
| [36589203885, 29/09 15:18:37Z](https://github.com/hmono/Luka-Tennis-Player/actions/runs/36589203885) | `318d7f6` | Todas `success` | `skipped` |

**A etapa success não prova request nem aceite CallMeBot**: outbox vazia pode produzir no-op. Não se consultaram logs ou valores de secrets para inferir envio real. O risco é que um futuro schedule legado ainda execute coleta/entrega sem consultar a flag do PR; depende de trabalho pendente e configuração operacional. A consulta não demonstra que a execução de 13/10 será criada nem quando.

O cron novo/dry-run do PR não protege esse workflow preexistente. Antes de afirmar que a automação inteira está desativada, o operador precisa verificar/tratar o legado em decisão autorizada separadamente; não foi alterado durante esta issue. A homologação do PR deve distinguir claramente segurança da branch draft e operação da default branch.

### H2-QA-03 — P2, telemetria pode atribuir cron atrasado ao outro cron de quinta

`telemetry.py:28`/`:49` escolhe o slot mais recente dentre todas as expressões. O workflow em `update_rankings.yml:46` não passa `github.event.schedule`. Uma ocorrência do cron de quinta 12:00 UTC, criada só às 15:06 e iniciada às 15:07, é reportada como slot 15:05/delay 2 minutos/sem atraso >60, embora aquela ocorrência esteja 187 minutos atrasada. A repro A imprime exatamente esse resultado. Uma ocorrência legítima do segundo cron tem os mesmos timestamps; só estes metadados não distinguem as duas.

A documentação e o resumo já dizem que o slot é inferido. Trata-se de limitação comprovada de observabilidade, sem prova de bypass de freshness ou envio. Recomenda-se passar a expressão cron do evento, registrar creation/actual start/cron separados e expor ambiguidade quando o atraso cruzar múltiplos slots/dias. O intervalo inferido não mede com exatidão toda ocorrência e não observa runs descartadas.

### H2-QA-04 — P1, recuperação da fonte oculta tentativa incerta sem reconciliação humana

Repro independente C: incidente SOURCE_ERROR de 05/10 sofre `transport_timeout` simulado depois da reserva. O próximo CLI `--incidents-only` retorna 1, `delivery_review_required=1`. `incidents.py:210`/`:213` acrescenta `recovered` ao recuperar aquela edição, preservando nonce/error. `update_rankings.py:591` conta revisão somente se o último evento é `provider_in_flight` ou `provider_failed`. Após recovery, o mesmo CLI retorna 0 e `provider_accepted=0`, sem diagnóstico de revisão.

O histórico permanece append-only e não ocorre replay; esta repro não demonstra duplicação nem perda da evidência. Demonstra falso sucesso operacional: recuperação da fonte e reconciliação do provider foram tratadas como fechamento único para fins de visibilidade. O contrato anterior exige que tentativas em quarentena apareçam como falha operacional em reruns e que incerteza exija reconciliação humana. A recuperação da fonte não satisfaz esse requisito. O coordenador confirmou P1 e a necessidade de correção na integração. Recomenda-se contar tentativas não reconciliadas independentemente da recuperação da publicação, preservando nonce, erro e ledger. Até correção/reverificação, permanece aberto na base auditada.

### H2-QA-05 — P2 documental/design: PENDING pode persistir catch-up e recuperação

`update_rankings.py:377` só bloqueia STALE/SOURCE_ERROR; `collect` em `:231`/`:243` passa PENDING para `plan_collection` e journal. A repro A prova criação de snapshot/intenção de 05/10 e recovery de incidente da mesma edição enquanto a esperada é 12/10. O docstring `:352` diz “Only validated current publications may reach sporting persistence”, formulação mais restrita que o código. O [relatório anterior](../ATP_RANKING_HOMOLOGATION_20261013.md) também descreve a coleta em termos da publicação vigente.

PENDING pode significar uma edição antiga válida, já publicada, dentro da graça para a seguinte. Persistir essa edição como histórico e recuperar incidente dessa própria edição pode ser uma política legítima; não foi classificado isoladamente como defeito de dados. `--incidents-only` bloqueia entrega esportiva nesse resultado e dry-run preserva bytes. O problema comprovado de envio está em H2-QA-01. Definir explicitamente se catch-up é autorizado ou se a persistência esportiva exige FRESH; alinhar docs, preview e testes à decisão. Não confundir recuperação de 05/10 com confirmação de 12/10.

## Matriz do fluxo e falhas verificadas

| Cenário | Observação na base | Evidência |
|---|---|---|
| FRESH qualificado | Snapshot/intenção novos ou unchanged; output true quando coleta não falhou | `test_collection_output_allows_sporting_delivery_only_for_fresh_qualified_edition`; repro A |
| PENDING, dados já persistidos | Sem novo snapshot/outbox; output false | Homologação anterior e integração |
| PENDING, histórico ainda não salvo | Catch-up e recuperação possíveis, output false | Repro A / H2-QA-05 |
| STALE exatamente em quinta 12:00 BRT | Snapshot bloqueado; incidente único por edição; coleta retorna 0 com diagnóstico STALE | `test_boundary_multiple_crons_and_stale_recovery_generate_one_intention_each` |
| SOURCE_ERROR identity/http/timeout/schema/unavailable | Sporting files preservados; incidente por classe/edição, collect exit 1 | `test_source_error_classes_before_cutoff_leave_sporting_files_unchanged`, `test_source_error_persists_independent_incident_without_changing_valid_state` |
| SOURCE_ERROR inesperado | Código estável/redigido; sem texto arbitrário no ledger | `test_unexpected_source_exception_is_redacted_and_persisted` |
| Calendário inválido/expirado | Sporting output false; não declara FRESH nem persiste coleta nova | `test_collection_output_allows_sporting_delivery_only_for_fresh_qualified_edition`, testes freshness |
| Fonte regressiva/futura/edição inválida | SOURCE_ERROR, bloqueio | Testes freshness/ITF/source |
| Flag desabilitada, trabalho a enviar | Provider não construído; estado preservado, exit 1 | `test_delivery_release_guard_never_constructs_provider_or_mutates_intent` |
| Dry-run STALE/SOURCE_ERROR/PENDING | Preview sem persistência/provider | Integração e repro A, assert bytes |
| Falha no segundo write de coleta | Journal persiste intenção; replay produz snapshot/outbox sem nova observação | `test_second_write_failure_replays_intention_without_new_observation` |
| Falha no terceiro write de recovery | Journal recupera também ledger | `test_recovery_is_replayed_with_snapshot_and_outbox_after_third_write_failure` |
| Replay com conteúdo concorrente | Falha `collection_transaction_conflict`, sem overwrite | `test_replay_does_not_overwrite_concurrent_receipt_or_other_state` |
| Lock local ocupado | Segundo escritor rejeitado antes do processamento | `test_second_local_writer_is_rejected_before_processing` |
| Dois clones reservam simultaneamente | Um push vence; um `ranking_checkpoint_failed`; uma chamada mock | Repro B com barrier e Git bare local |
| Falha de push da reserva | Zero requests; claim incerto não replayado | Testes delivery/durability/incidents |
| Aceite seguido de crash/falha de write | Claim permanece não reenviável; rerun no-op/falha de revisão | `test_receipt_write_failure_leaves_uncertain_reservation_without_replay`, `test_process_interrupted_after_send_does_not_replay_on_reload` |
| Resultado aceito com checkpoint final falho | Lote interrompido; reserva remota protege próximo clone de replay | Testes incidents/delivery; não comprova receipt final remoto |
| Timeout/transporte/408/5xx/ambígua | Uma tentativa mock; quarentena sem retry automático | Testes providers/delivery/incidents |
| HTTP 429 explícito | Retry limitado dentro do provider; intenção continua retryable após exaustão | Testes providers/incidents; ver limite abaixo |
| Correções sucessivas / A→B→A | Anterior pendente preservada/superseded; hash histórico/revisão incerta fail-closed | Testes update_rankings/delivery |
| Fonte recupera incidente | Evento recovered append-only, intenção de incidente cancelada | Testes incidents; limite de diagnóstico H2-QA-04 |
| Outbox corrupta preexistente | SOURCE_ERROR independente ainda persiste; checkpoint pode publicar ledger sem alterar par esportivo | `test_corrupt_outbox_does_not_block_source_error_persistence_or_delivery`, testes durability |

O workflow `update_rankings.yml:74` checkpointa bundle completo após coleta success/failure, sem rebase; `:82` só entrega após persist success. Quando output falta/é false, usa `--incidents-only`. `:95` tenta checkpoint final após entrega success/failure, mas cancelamento/timeout do job não garante execução desse step. Isso é mitigado pela reserva remota antes de cada request (`durability.py:89`, `update_rankings.py:286`, `incidents.py:281`), não pelo `always()` isolado. Step coleta falho continua falhando a run, sem `continue-on-error`.

## Comandos e resultados executados

Executados na base isolada, sem instalação/alteração de dependências:

```bash
cd /home/ono/luka-h2-22-qa
python3 -m unittest discover -s tests/ranking_alerts
# Ran 222 tests in 25.946s — OK
python3 -m unittest -v tests.ranking_alerts.test_delivery_state tests.ranking_alerts.test_durability tests.ranking_alerts.test_incidents tests.ranking_alerts.test_sprint_integration tests.ranking_alerts.test_freshness tests.ranking_alerts.test_telemetry tests.ranking_alerts.test_workflow_rankings
# Ran 85 tests in 7.438s — OK
python3 /tmp/h2_operational_repro.py
python3 /tmp/h2_git_race.py
python3 /tmp/h2_incident_quarantine_recovery.py
```

`python` sem versão não estava instalado nesse ambiente (`command not found`); `python3` executou todos os testes. Actions configura Python 3.12 via setup-python, portanto não se inferiu defeito do workflow a partir disso.

Consultas externas read-only reproduzíveis, sem conteúdo de logs/secrets:

```bash
gh issue view 22 --repo hmono/Luka-Tennis-Player --json title,body,url,state
gh pr view 18 --repo hmono/Luka-Tennis-Player --json title,body,baseRefName,headRefName,isDraft,url
gh api 'repos/hmono/Luka-Tennis-Player/contents/.github/workflows/update_rankings.yml?ref=main' --jq .content | base64 -d
gh api repos/hmono/Luka-Tennis-Player/actions/workflows/update_rankings.yml --jq '{state,path}'
gh api 'repos/hmono/Luka-Tennis-Player/actions/workflows/update_rankings.yml/runs?event=schedule&per_page=5' --jq '.workflow_runs[] | {id,event,status,conclusion,head_sha,head_branch,created_at,run_started_at,html_url}'
gh api repos/hmono/Luka-Tennis-Player/actions/runs/37489325767/jobs --jq '.jobs[] | {id,conclusion,steps:[.steps[] | {name,status,conclusion}]}'
gh api repos/hmono/Luka-Tennis-Player/actions/runs/36589203885/jobs --jq '.jobs[] | {id,conclusion,steps:[.steps[] | {name,status,conclusion}]}'
```

A suíte cobre propriedades de estado e testes de workflow por inspeção de strings. Ela não interpreta as expressions GitHub nem prova criação automática de uma run schedule. O dry-run remoto no SHA integrado final é responsabilidade do coordenador, fora desta auditoria local.

## Riscos residuais e operação após integração

- A decisão sobre pendências de edições anteriores precisa ser implementada, testada e reverificada; tests verdes na base não cobrem o P1 encontrado.
- GitHub cron não oferece deadline. A extra quinta reduz a espera nominal de STALE, mas atraso/descarte/inatividade e substituição de pending continuam possíveis. Monitorar missing runs externamente e não depender apenas do resumo de uma run que talvez não exista.
- Quarentena privilegia evitar duplicação: reserva publicada seguida de interrupção antes do request pode resultar em alerta nunca enviado. Reserva após aceite sem resultado publicado não prova aceite nem não aceite. Reconciliar explicitamente, sem apagar histórico ou tornar retryable automaticamente.
- `provider_accepted` é reconhecimento de fila, não entrega ao dispositivo. Não há contrato comprovado de idempotência por event_id; exatamente uma mensagem não é prometido.
- HTTP 429 tem no máximo quatro requests por chamada padrão, mas o número acumulado de retries em runs futuras não possui limite global. Continuar registrando attempts e rever necessidade de orçamento total/alerta de exaustão; não foi observado bypass por 429.
- Os helpers Python de baixo nível aceitam provider/checkpoint injetados; guards de flag, lock e caminhos canônicos estão na CLI e workflow. A auditoria não trata chamadas internas diretas como autorização operacional de envio.
- O lock Linux é advisory/local. Outros escritores que não respeitem o grupo/lock não são serializados. Push fast-forward rejeita estado divergente; mudanças remotas não relacionadas podem interromper entrega mesmo sem conflito de ranking. Não fazer rebase automático do claim.
- Journals são locais e não versionados. Um runner descartado antes do checkpoint perde seu journal local; antes de request isso pode perder uma coleta ainda não publicada, depois da reserva remota preserva prevenção de replay. Não se testou falha física de filesystem/host além dos writes/pushes simulados.
- A recuperação da fonte não deve ser confundida com reconciliação de entrega incerta (H2-QA-04), nem a captura antiga PENDING com confirmação da edição esperada (H2-QA-05).
- Sem cronograma oficial vigente e extensão revisada, avaliações bloqueiam em 27/10 03:00 UTC. Instrumentar `ranking_calendar_invalid`/data de expiração antes dessa data sem ampliar calendário por suposição.
- Após merge explicitamente autorizado, primeiro observar schedule com entrega ainda desabilitada: expressão do evento, expected/created/start, SHA/ref realmente usado, freshness, idade, calendário, e quatro writers skipped. Conferir cutoff/quinta e duas publicações novas consecutivas. Ativação/provider real requer autorização separada. O PR não constitui essa autorização.

## Repros independentes preservadas

Os scripts temporários abaixo preservam a evidência sem acrescentar testes executáveis versionados. Para repetir, copiar cada bloco para o nome indicado em `/tmp` e ajustar apenas `sys.path` ao checkout auditado. As duas repros de seleção/revisão usam checkpoints mocks; a repro concorrente usa checkpoints Git reais com remote local. Nenhuma abre conexão ao CallMeBot.

### A — backlog PENDING/FRESH e slot ambíguo

Arquivo temporário: `/tmp/h2_operational_repro.py`.

```python
import sys, json, tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
sys.path.insert(0, '/home/ono/luka-h2-22-qa/scripts')
import update_rankings as u
from ranking_alerts.source import RawRankingObservation, RawDisciplineRanking
from ranking_alerts.domain import RankingObservation, DisciplineRanking, RankingsData, build_snapshot
from ranking_alerts.storage import save_rankings, load_rankings, load_alert_state
from ranking_alerts.incidents import load_incidents, IncidentLedger, plan_source_error, save_incidents
from ranking_alerts.providers import DeliveryReceipt
from ranking_alerts.telemetry import schedule_timing

def at(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
class Source:
    name='itf'
    def __init__(self,date): self.date=date
    def fetch(self): return RawRankingObservation(atp_id='B0UF',name='Luka Bojicic Ono',source='itf',ranking_date=self.date,singles=RawDisciplineRanking(status='ranked',rank=2250,points=None),doubles=RawDisciplineRanking(status='ranked',rank=1417,points=None))
class Provider:
    name='callmebot'; last_attempt_count=1
    def __init__(self): self.messages=[]
    def send(self,*,message,event_id):
        self.messages.append(message.splitlines()[0]); return DeliveryReceipt(provider=self.name,accepted_at='2026-10-13T12:02:00Z',http_status=200)
with tempfile.TemporaryDirectory(prefix='h2-qa-') as d:
    root=Path(d); r=root/'rankings.json'; s=root/'alerts.json'; i=root/'incidents.json'; output=root/'actions-output.txt'
    ob=RankingObservation(atp_id='B0UF',name='Luka Bojicic Ono',source='itf',ranking_date='2026-09-28',singles=DisciplineRanking(rank=2250,points=None,career_high_rank=1827,career_high_date='2025-12-01'),doubles=DisciplineRanking(rank=1417,points=None,career_high_rank=1407,career_high_date='2026-06-22'))
    save_rankings(r,RankingsData(snapshots=(build_snapshot(ob,'2026-09-29T12:00:00Z'),)))
    s.write_text('{"schema_version":1,"outbox":[]}\n')
    ledger=plan_source_error(IncidentLedger(),expected_date='2026-10-05',last_valid_date='2026-09-28',source='itf',cutoff_at='2026-10-08T15:00:00Z',now='2026-10-06T12:00:00Z',error_code='ranking_source_timeout'); save_incidents(i,ledger)
    provider=Provider()
    def run(command,date,instant,incidents_only=False):
        argv=[command,'--rankings-path',str(r),'--state-path',str(s),'--incidents-path',str(i)]
        argv+=['--provider','callmebot'] if command=='deliver' else ['--source','itf']
        if incidents_only: argv+=['--incidents-only']
        out=StringIO(); err=StringIO()
        with patch.object(u,'_selected_source',return_value=Source(date)), patch.object(u.CallMeBotProvider,'from_env',return_value=provider), patch.dict('os.environ',{'ATP_RANKING_DELIVERY_ENABLED':'true','GITHUB_OUTPUT':str(output)}), redirect_stdout(out),redirect_stderr(err):
            rc=u.main(argv,clock=lambda:at(instant),checkpoint=lambda:None)
        return {'rc':rc,'stdout':out.getvalue(),'stderr':err.getvalue()}
    initial=(r.read_bytes(),s.read_bytes(),i.read_bytes())
    preview=run('dry-run','2026-10-05','2026-10-13T12:00:00Z')
    assert initial==(r.read_bytes(),s.read_bytes(),i.read_bytes())
    print('DRY_PENDING',json.dumps(preview))
    first=run('collect','2026-10-05','2026-10-13T12:00:00Z')
    print('COLLECT_PENDING',json.dumps(first)); print('PENDING_STATE',json.dumps({'dates':[x.ranking_date for x in load_rankings(r).snapshots],'outbox_count':len(load_alert_state(s,load_rankings(r)).outbox),'incident_latest':[x['kind'] for x in load_incidents(i).latest().values()],'actions_output':output.read_text()}))
    before=s.read_bytes(); blocked=run('deliver',None,'2026-10-13T12:01:00Z',True); assert before==s.read_bytes(); assert not provider.messages
    print('INCIDENTS_ONLY',json.dumps(blocked))
    second=run('collect','2026-10-12','2026-10-13T12:02:00Z'); print('COLLECT_FRESH',json.dumps(second))
    delivery=run('deliver',None,'2026-10-13T12:03:00Z'); print('DELIVER_AFTER_FRESH',json.dumps({'result':delivery,'messages':provider.messages,'outbox':[{'date':next(x.ranking_date for x in load_rankings(r).snapshots if x.id==v.snapshot_id),'status':v.status} for v in load_alert_state(s,load_rankings(r)).outbox]}))
print('SLOT_AMBIGUITY',json.dumps(schedule_timing(event='schedule',created_at=at('2026-10-15T15:06:00Z'),started_at=at('2026-10-15T15:07:00Z')).__dict__))
```

### B — dois clones realmente concorrentes

Arquivo temporário: `/tmp/h2_git_race.py`.

```python
import sys, tempfile, subprocess, threading, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/home/ono/luka-h2-22-qa/scripts')
import update_rankings as u
from ranking_alerts.domain import DisciplineRanking,RankingObservation,RankingsData,RankingAlertState
from ranking_alerts.collection_transaction import save_collection
from ranking_alerts.durability import GitCheckpoint
from ranking_alerts.providers import DeliveryReceipt
from ranking_alerts.storage import StorageError,load_alert_state,load_rankings

def git(p,*args): return subprocess.run(['git',*args],cwd=p,check=True,capture_output=True,text=True).stdout.strip()
with tempfile.TemporaryDirectory(prefix='h2-git-race-') as d:
    root=Path(d); remote=root/'remote.git'; a=root/'a'; b=root/'b'
    git(root,'init','--bare',str(remote)); git(root,'init','-b','main',str(a)); git(a,'remote','add','origin',str(remote))
    git(a,'config','user.name','QA'); git(a,'config','user.email','qa@example.invalid')
    ob=RankingObservation(atp_id='B0UF',name='Luka Bojicic Ono',source='itf',ranking_date='2026-10-05',singles=DisciplineRanking(rank=2250,points=None),doubles=DisciplineRanking(rank=1417,points=None))
    plan=u.plan_collection(RankingsData(),RankingAlertState(),ob,captured_at='2026-10-06T12:00:00Z')
    save_collection(a/'data/rankings.json',a/'automation/state/ranking_alerts.json',rankings=plan.rankings,state=plan.state)
    git(a,'add','.');git(a,'commit','-m','fixture');git(a,'push','-u','origin','main')
    git(root,'clone','-b','main',str(remote),str(b));git(b,'config','user.name','QA');git(b,'config','user.email','qa@example.invalid')
    barrier=threading.Barrier(2); counts=[]; lock=threading.Lock()
    class Provider:
        name='callmebot';last_attempt_count=1
        def send(self,**kwargs):
            with lock: counts.append(kwargs['event_id'])
            return DeliveryReceipt(provider=self.name,accepted_at='2026-10-06T12:01:00Z',http_status=200)
    def run(repo):
        cp=GitCheckpoint(repo);first=True
        def checkpoint():
            nonlocal first
            if first: first=False;barrier.wait(timeout=10)
            cp()
        try: n=u.deliver(provider=Provider(),rankings_path=repo/'data/rankings.json',state_path=repo/'automation/state/ranking_alerts.json',checkpoint=checkpoint);return {'clone':repo.name,'sent':n}
        except StorageError as e: return {'clone':repo.name,'error':e.code}
    with ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(run,[a,b]))
    assert len(counts)==1,(outcomes,counts)
    remote_state=json.loads(git(remote,'show','main:automation/state/ranking_alerts.json'))
    assert remote_state['outbox'][0]['status']=='sent'
    print(json.dumps({'outcomes':outcomes,'mock_calls':len(counts),'remote_status':remote_state['outbox'][0]['status'],'attempts':remote_state['outbox'][0]['attempts']}))
```

### C — recovery oculta revisão de provider

Arquivo temporário: `/tmp/h2_incident_quarantine_recovery.py`.

```python
import sys,tempfile,json
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
sys.path.insert(0,'/home/ono/luka-h2-22-qa/scripts')
import update_rankings as u
from ranking_alerts.incidents import IncidentLedger,plan_source_error,save_incidents,deliver_incidents,load_incidents,plan_recovery
from ranking_alerts.providers import DeliveryError
class Provider:
    name='callmebot';last_attempt_count=1
    def send(self,**kwargs):raise DeliveryError('transport_timeout',1)
with tempfile.TemporaryDirectory(prefix='h2-quarantine-') as d:
    root=Path(d);i=root/'incidents.json';r=root/'rankings.json';s=root/'alerts.json'
    ledger=plan_source_error(IncidentLedger(),expected_date='2026-10-05',last_valid_date='2026-09-28',source='itf',cutoff_at='2026-10-08T15:00:00Z',now='2026-10-06T12:00:00Z',error_code='ranking_source_timeout');save_incidents(i,ledger)
    try:deliver_incidents(provider=Provider(),path=i,now='2026-10-06T12:01:00Z',checkpoint=lambda:None)
    except DeliveryError:pass
    def main():
        out=StringIO();err=StringIO()
        with redirect_stdout(out),redirect_stderr(err):rc=u.main(['deliver','--provider','callmebot','--incidents-only','--rankings-path',str(r),'--state-path',str(s),'--incidents-path',str(i)],checkpoint=lambda:None)
        return {'rc':rc,'stdout':out.getvalue(),'stderr':err.getvalue()}
    before=main();ledger=load_incidents(i);save_incidents(i,plan_recovery(ledger,ranking_date='2026-10-05',now='2026-10-06T12:02:00Z'));after=main()
    print(json.dumps({'before':before,'after':after,'events':[{'kind':x['kind'],'error_code':x['error_code'],'attempt_id':x.get('attempt_id')} for x in load_incidents(i).events]}))
```
