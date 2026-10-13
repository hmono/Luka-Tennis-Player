# Sprint #25 C — scheduler e watchdog independente

2026-10-13 UTC. Branch local `sprint25/scheduler`, base `dc5032a`. Implementação pronta para integração; **ativação operacional ainda não realizada**.

## Comportamento implementado

O workflow consulta todos os dias às 12:17 e 18:17 UTC, inclusive fins de semana, sem calendário ATP, PlayerZone, `valid_until` ou revisão manual por edição. Há um ciclo semanal nominal independente às segundas 12:00 UTC, atualmente 09:00 em `America/Sao_Paulo`. `weekly_period(now)` identifica a última segunda 09:00 local; o runtime integrado e seu ledger produzem um status por período, inclusive quando há nova edição. Uma execução atrasada recupera o período atual. O horário é agenda de consulta/status, **não prazo de publicação ATP**. Telemetria informa edição observada/data da checagem, sem exibir cutoff/calendário especulativo como deadline.

O workflow chama `scripts/autonomous_rankings.py run`; a integração root contém coleta/planejamento/checkpoint/envio com persistência antes de rede. A flag original `ATP_RANKING_DELIVERY_ENABLED=true` e `main` continuam obrigatórios. Dispatch inicia em `dry-run`, faz checkout da branch selecionada, não tem secrets de envio no passo de dry-run e chama `run --dry-run`. Esta branch não modifica a flag, secrets, main, estado remoto do workflow ou arquivo de rankings/ledgers produtivos. Nenhuma ação enable é implementada no watchdog; `disabled_manually` é apenas relatado.

## Independência e recuperação

`python3 -m scripts.ranking_alerts.autonomous_scheduler --dry-run` consulta metadados Actions sem criar diretório/SQLite, disparar workflow ou notificar. Após configuração/liberação inicial, o timer systemd fora do GitHub executa a cada dez minutos, com disk/state persistente. Ele monitora:

- `MISSED_RUN`: nenhum ciclo main na última janela vencida (grace 90 minutos).
- `RUN_FAILURE`: última tentativa da janela terminou sem sucesso.
- `SCHEDULER_DELAY`: início >60 minutos após slot estimado.
- `RUN_DURATION`: fila/execução ou duração final >20 minutos.
- `MONITOR_UNAVAILABLE`: API indisponível ou lista truncada; status desconhecido, sem inventar sucesso.
- `WORKFLOW_DISABLED`: nunca reativa workflow desabilitado.

Dispatches de dry-run e branches diferentes de main não mascaram o monitor. `run-name` inclui modo para distinguir dry-run de recuperação. O cron nominal não vem no timestamp da API: janelas são inferidas, e um dispatch autorizado `collect-and-deliver` pode satisfazer uma janela. O monitor observa execução, não prova dados novos ou entrega no dispositivo.

Se autorizado por `ATP_WATCHDOG_RECOVERY_ENABLED=true`, recupera ausência/falha de workflow ativo com no máximo duas solicitações `workflow_dispatch` por slot, separadas por 30 minutos, até seis horas do slot. Cada reserva é fsync/commitada em SQLite antes do request; timeout/crash também consome orçamento, evitando tempestades. Runner/GitHub indisponível pode impedir recuperação: o canal operacional externo continua independente, conforme disponibilidade do próprio host/canal. Alertas deduplicam por código/slot e retomam pendências de disco após indisponibilidade. A recuperação do monitor gera evento `RECOVERED`.

O serviço é um único host com volume local persistente, SQLite FULL e flock compartilhado. Dois processos/clones no mesmo host são serializados. Não é consenso distribuído entre hosts com discos distintos; para HA seria necessário armazenamento/lock comum adequado. Retenção/budget de disco é responsabilidade do provisionamento. Falha do próprio host externo não é detectada por ele; configurar monitor de host/serviço durante a implantação inicial.

## Canal operacional independente com dedup durável

`send_operational_alert(event_id,message)->bool` usa `ATP_OPS_WEBHOOK_URL` (HTTPS) e token opcional, independente do CallMeBot. O receptor deve retornar JSON `{"accepted": true}` **após persistência** e deduplicar `event_id`; apenas HTTP 2xx vazio não basta. O callback respeita a flag de release. Actions usa diretório temporário; o ledger de entrega integrado precisa persistir/repetir os eventos operacionais entre runners até aceite.

O receptor de referência `scripts.ranking_alerts.ops_receiver` contém inbox SQLite durável com unicidade por `event_id`; replay idêntico é aceito sem novo evento, mesmo após restart; mesmo ID com conteúdo distinto é rejeitado. `POST /events` exige bearer token; `GET /health` autenticado retorna contagens. Bind somente em 127.0.0.1; instalar proxy HTTPS. Não há URLs/tokens/bodies nos logs. Opcionalmente encaminha para `ATP_OPS_FORWARD_URL` fora do canal esportivo, com retry a cada minuto até aceite. Após revisão independente, esse destino deve persistir/deduplicar `event_id` e responder explicitamente JSON `accepted: true`; resposta vazia, `accepted: false` ou apenas HTTP 2xx não encerra a intenção. A thread retoma automaticamente após exceções de SQLite/HTTP; `forwarding_failures` fica visível em `/health`. Uma resposta aceita confirma armazenamento/encaminhamento HTTP, **não entrega ao dispositivo**. Encaminhamento ambíguo pode duplicar no destino; o inbox mantém um evento único e o destino recebe `event_id` para dedup se suportada. Não se promete exactly-once na rede.

## Provisionamento inicial — bloqueador real, não executado

Arquivos revisáveis estão em `deployment/atp-watchdog/`. Não instalados, nenhum servidor, credencial, DNS/proxy ou canal de notificações provisionado. A prova de interrupção real do runner depende desta implantação externa; um segundo cron Actions não substituiria este host.

Após autorização inicial, o responsável pela implantação deve fornecer uma máquina Linux/systemd fora do GitHub, relógio sincronizado, Python 3.12, OpenSSL e checkout do commit liberado em `/opt/luka-tennis`, usuário de serviço `atp-watchdog`, disco persistente e egress HTTPS. Instalar os units e exemplos de environment com valores reais, root-owned modo 0600. Configurar HTTPS para o inbox e um destino operacional independente antes de habilitar envio. Token GitHub precisa Actions read para monitoramento; recuperação opcional precisa Actions write, restrito ao repositório. Provisionar uma GitHub App instalada neste repositório, com ID/install ID e chave privada protegida legível apenas pelo usuário/grupo do serviço. O cliente gera JWT RS256 via OpenSSL e renova automaticamente installation access tokens antes de expirar; nenhuma renovação manual por ciclo. Chave pode ficar root:atp-watchdog 0640 em diretório 0750. PAT estático é fallback somente com renovação automática externa; sem ela não satisfaz autonomia indefinida. Habilitar timer/receptor uma vez após aprovação, sem cron manual por edição. Manter flags externas e a flag GitHub coerentes; valores padrão são false. Aprovação de código não autoriza alterar o workflow legado `disabled_manually`.

Validação inicial sugerida: executar CLI `--dry-run`, verificar journal/`GET /health`, liberar o receptor/canal, observar dedup/restart, liberar timer inicialmente sem recuperação, depois testar falha sintética no ambiente de homologação. Habilitar recuperação só após a aprovação de release. Não há comando de implantação executado nesta entrega.

## Validação e limites da evidência

`python3 -m unittest tests.ranking_alerts.test_autonomous_scheduler tests.ranking_alerts.test_telemetry tests.ranking_alerts.test_workflow_rankings tests.ranking_alerts.test_ops_receiver -q`: 22 testes passam. A simulação de oito semanas verifica 112 polls e oito IDs semanais independentemente de nenhuma edição, atraso e novas edições com ranks iguais; neste subpacote são IDs/slots, **não prova da entrega de digests**. A integração root/B precisa executar a simulação do ledger real. Testes de monitor cobrem ausência, falha, atraso, duração, outage API, dedup, retry do canal, workflow desabilitado sem dispatch, gates de release e dry-run sem estado. Teste concorrente usa dois clones Git temporários reais e processos distintos com um volume externo comum; verifica uma reserva de recuperação e um aceite de alerta, sem provar concorrência de writers de ranking.

Auth: renovação/cache automática de installation token, limites de JWT, e aceitação explícita do sink. Receptor: persistência/dedup após restart, conflito de ID, forwarding indisponível e retry após restart. Nenhum request de envio real. `systemd-analyze calendar '*-*-* *:00/10:00 UTC'` normaliza com sucesso; `systemd-analyze verify` dos três units passa. Testes de workflow inspecionam configuração, não executam expressions do serviço GitHub. Suíte Python completa nesta base: `python3 -m unittest discover -s tests/ranking_alerts -q`, 243 testes passaram (execução anterior aos dois testes adicionais de auth/ack, que também passaram na suíte focada). Frontend/build e dry-run ITF real são responsabilidade da integração final.

## Fontes oficiais consultadas em 2026-10-13

GitHub documenta schedule na default branch e possibilidade de atrasos/descarte em alta carga; por isso o monitor externo é necessário: [eventos schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). Permissões Actions read/write e parâmetros ref/inputs: [workflow REST API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event); paginação/metadados: [workflow runs REST API](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-workflow). Timer OnCalendar/Persistent: [manual upstream systemd](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml). Não há garantia técnica de execução/entrega enquanto fonte, GitHub, host externo ou destino estiverem indisponíveis; o resultado comunicado é desconhecido/indisponível.

Autenticação App e expiração automática do installation token: [JWT GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app), [installation access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).
