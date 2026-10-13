# Ops27 — viabilidade Cloudflare Workers + D1

Data: 2026-10-13 UTC. Base `main@944e417`; ownership exclusivo deste relatório.
Referências de escopo: [issue #33](https://github.com/hmono/Luka-Tennis-Player/issues/33),
[PR #32 draft](https://github.com/hmono/Luka-Tennis-Player/pull/32), head Ops26
`a21143f`. Foram lidos runbook Ops26, relatórios de host, watchdog, inbox,
integração e revisão independente antes da análise. O runtime/CI Ops27 e sua
homologação pertencem às outras frentes; este parecer não certifica seus testes.

## Decisão e limite da evidência

**`CLOUDFLARE_CONDITIONAL_GO` para continuar a PoC isolada.** Não foi identificada
incompatibilidade fundamental de plataforma para watchdog de dez minutos e
inbox durável de baixo volume. **`CLOUDFLARE_GO` operacional não foi demonstrado**:
plano, quotas restantes e uso real da conta são `NOT_VERIFIED`. Permanecem
`HOST_NO_GO` para ONO, `SINK_NO_GO`, `STAGING_NO_GO` e `ACTIVATION_NO_GO`.
Se o aceite exigir resultado estritamente binário, classificar como
`CLOUDFLARE_NO_GO` para implantação **neste momento**, por falta de evidência,
sem interpretar isso como rejeição técnica da arquitetura.

Workers Paid é a hipótese recomendada para staging futuro: o Free exige prova
de CPU por invocação que ainda não existe. Cron independe do agendador Actions;
a API GitHub continua dependência observada. Workers Builds serve CI/deploy e
não é watchdog, estado persistente ou supervisor externo.

## Auditoria factual da conta, somente leitura

| Observação executada | Resultado | O que permite concluir |
| --- | --- | --- |
| Inspeção de nomes de variáveis Cloudflare do ambiente | Nenhuma variável `CLOUDFLARE*`/`CF_*` | Não há credencial de API neste ambiente de execução por esses nomes |
| Metadados do arquivo Wrangler existente | OAuth e refresh presentes; expiração `2026-06-20T06:36:10.694Z`; escopos incluem account read e vários write | Há configuração histórica; a credencial está expirada. Valores nunca impressos ou copiados para relatório |
| Um `GET https://api.cloudflare.com/client/v4/accounts`, bearer somente em memória | HTTP **403**; sem corpo/headers privados em output | Autenticação/listagem não qualificada. Não distingue sozinho expiração de outro motivo de recusa |
| `gh secret list`, apenas nomes | `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID` existem | Valores, validade, permissões e plano não são observáveis por esta leitura |
| Workflow Pages versionado no SHA base | Usa os dois secrets; deploy em push main | Integração Pages configurada, sem comprovar Workers/D1 habilitados ou uso/cobrança atual |

Não houve refresh OAuth, login, leitura de valores de secrets GitHub, consulta
de logs Wrangler, token mint GitHub App, deploy, alteração de subscriptions,
DNS, cron, D1 ou contas. A consulta autenticada falhou antes de obter account ID;
inventário Workers/D1/cron, subscriptions, analytics e limites remanescentes não
foram consultados. Nenhum token, chave, refresh, URL secreta ou account ID foi
registrado. O acesso histórico possui escopos amplos e não deve ser reutilizado
como identidade operacional mínima.

| Dado real necessário | Estado | Próxima evidência read-only |
| --- | --- | --- |
| Workers Free/Paid/Enterprise e modelo Standard/legado | `NOT_VERIFIED` | Plano/subscriptions e modelo efetivo de cada Worker |
| Requests/CPU e saldo mensal/dia compartilhado | `NOT_VERIFIED` | Analytics/billing com período UTC e outros workloads |
| Cron utilizado/restante, Worker enabled | `NOT_VERIFIED` | Inventário scripts + schedules e settings |
| D1 quota/DBs/GB/rows utilizados e armazenamento production | `NOT_VERIFIED` | Inventário D1, métricas/billing e versão |
| workers.dev, custom route/TLS, secrets/bindings disponíveis | `NOT_VERIFIED` | Metadados de subdomínio, rotas e nomes de bindings, sem valores |
| Workers Builds integração/limites restantes | `NOT_VERIFIED` | Configuração de build e consumo da conta |
| Host persistente alternativo já contratado/disponível | `NOT_VERIFIED` | Inventário fornecido por owner + preflight read-only separado |

## Matriz pública de compatibilidade

Documentação oficial consultada nesta data; limites públicos não equivalem a
saldo disponível da conta. Workers limits estava atualizado em **2026-10-12**.

| Recurso | Free | Paid | Consequência para Ops27 |
| --- | --- | --- | --- |
| Requests | 100.000/dia | Sem teto de requests do plano | Orçamento deve incluir health e ingress abusivo |
| CPU Cron `<1h` | 10 ms | 30 s | Dez minutos usa faixa `<1h`; Free não homologado |
| Memória isolate | 128 MB | 128 MB | Limitar payload/paginação; não carregar fila inteira |
| Fetch subrequests/invocação | 50 | 10.000 default | Batches limitados e sem redirects |
| Conexões aguardando headers | 6 | 6 | Forwarding serial/bounded |
| Cron/account | 5 | 250 | Precisa pelo menos um livre |
| Secret/env por valor | 5 KB | 5 KB | Validar tamanho/formato da chave antes do provisioning |
| Wall time Cron | 15 min | 15 min | Pode sobrepor próximo ciclo de 10 min; lease durável obrigatório |

Fonte: [Workers limits](https://developers.cloudflare.com/workers/platform/limits/).
O teto Paid de 10.000 subrequests é atual; referências antigas de 1.000 não
devem reger o fetch budget. O teto D1 abaixo é independente.

| D1 | Free | Paid | Consequência |
| --- | --- | --- | --- |
| DB máxima | 500 MB | 10 GB | 5 GB Free/account não permite DB Free de 5 GB |
| Storage/account | 5 GB | 1 TB | Saldo real não verificado |
| DBs/account | 10 | 50.000 | DB de staging separada requer quota |
| Queries/invocação | 50 | 1.000 | Contar statements de batch, além de fetch |
| Query/batch deadline | 30 s | 30 s | Queries indexadas; migração/arquivo em chunks |
| Time Travel | 7 dias | 30 dias | Recuperação local ao fornecedor; backup externo separado |

Fonte: [D1 limits](https://developers.cloudflare.com/d1/platform/limits/).
Cada DB processa queries serialmente; overload é uma falha a tratar. Esses
limites não concedem transação envolvendo fetch externo.

`*/10 * * * *` é proposta em UTC; alteração de triggers pode propagar por até
15 minutos. A implementação deve tolerar ciclo perdido, atrasado ou repetido,
com detecção por `scheduledTime` e ledger. Não há SLA/always-on comprovado.
Fonte: [Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/).

HTTPS `workers.dev` oferece caminho de staging sem alteração de DNS produtivo,
mas disponibilidade/subdomínio/controles efetivos precisam de confirmação.
Fonte: [workers.dev](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/).
Ack exige commit D1 aguardado no handler; `waitUntil()` depois de responder não
é evidência de commit anterior ao ack. Estado em memória não sobrevive ao
descarte de isolate. Threads, systemd, flock e filesystem SQLite Ops26 exigem
substituição por contratos D1, não tradução literal.

## Estimativa mensal e limites de custo

**Modelo de capacidade, não medição nem oferta comercial.** Assumir mês de
30 dias; 144 crons/dia = **4.320/mês** (31 dias = 4.464). Health externo a cada
5 min = **8.640 GET/mês**. Admitir até 100 eventos novos/dia = **3.000/mês**.
Invocações totais = **15.960/mês**. Reservar CPU conservadora de 100 ms/cron e
10 ms/HTTP: `4320*100 + (8640+3000)*10 = 548.400 CPU-ms/mês`.
Esses valores são hipóteses; Free falha se Cron consumir 100 ms, pois seu teto
por invocação é 10 ms, mesmo que requests/dia caibam. Paid oferece margem.

Budget proposto por cron: até sete chamadas GitHub (token mint + metadata +
cinco páginas), oito tentativas sink e um heartbeat externo: **16 fetches**;
até 40 statements D1. Dois dispatches são por **slot**, nunca por cron, e
permanecem desativados. Em modo de recuperação futuro, replanejar budget para
até 18 fetches. Deadline total de ciclo proposto 240 s e de HTTP 15 s; o corpo
também deve obedecer deadline e limite. CPU não inclui espera de rede/D1.
Um backlog de oito por ciclo tem capacidade teórica de 1.152 tentativas/dia,
reduzida por retries, cooldowns, falhas e deadlines; não é garantia de entrega.

Para D1, estimar 100 linhas lidas/cron + 10/health + 10/evento =
**548.400 rows read/mês**. Escritas estimadas: 20/cron + 10/evento =
**116.400 rows written/mês**, incluindo provisão de índices; medir
`meta.rows_read/rows_written` e size efetivos. Escritas em índices/deletes
também consomem quota; uma tabela sem índices pode transformar esse modelo
em full scans repetidos. Fonte: [D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/).

| Item | Franquia/tarifa pública atual | Estimativa dedicada, hipóteses acima |
| --- | --- | --- |
| Workers Paid Standard | US$5/mês; 10M requests +30M CPU-ms incluídos; excedentes US$0,30/M requests e US$0,02/M CPU-ms | US$5/mês; excesso modelado zero |
| D1 Paid | 25B reads +50M writes/mês e5GB; excesso US$0,001/M reads, US$1/M writes, US$0,75/GB-mês | Incremento modelado zero dentro da franquia |
| Workers Builds opcional | Free3.000/Paid6.000 min/mês; Paid excesso US$0,005/min; timeout20min | Hipótese20 builds x3min =60min, sem excesso |
| Supervisão Healthchecks candidato | Hobbyist US$0/20 checks; Business US$20/mês | Conta/slot não verificados; orçamento público US$0 ou20 |
| Backup fora Cloudflare + sink + operador | Sem recurso identificado/contrato observado | **Custo NOT_VERIFIED**, não zero |

Fontes: [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[Builds pricing](https://developers.cloudflare.com/workers/ci-cd/builds/limits-and-pricing/),
[Healthchecks pricing](https://healthchecks.io/pricing/).
Piso dedicado modelado **US$5/mês + monitor + backup + sink + operação**, antes
de impostos/câmbio. Se a conta já paga Workers, incremental pode ser zero
dentro do saldo: **isso não foi verificado**. Franquias são compartilhadas;
calcular marginal como `fatura(uso_existente+ATP)-fatura(uso_existente)`, incluindo
upgrade se necessário. Não afirmar US$5 como custo total homologado.
Workers Logs muda de pricing em 2026-12-01 conforme aviso público; revisão de
custo necessária antes dessa data. Logs não devem guardar conteúdo/secrets.

Quota de abuso não é controlada apenas por bearer/CPU: requests negados e
full scans também custam. Projetar tamanho8KiB, autenticação antes de D1,
rate-limit/admission, orçamento diário, limite de tentativas/ciclo, alertas de
billing e CPU configurada. Uma suspensão por custo deve preservar pending;
falha de admissão retorna erro, não `accepted:true`. Plano Paid não é hard cap
financeiro e não comprova SLA.

## Storage, retenção e backup

Com 3.000 eventos/mês, assumir 4KiB de conteúdo+índices por evento:
**11,72MiB/mês**; corpo máximo8KiB daria23,44MiB/mês antes de índices/overhead.
90 dias de hot history modelados =35,16MiB, com fator2 de planejamento
~=70,32MiB. Se cada cron criar linha adicional de1KiB sem compactação, cresce
4,22MiB/mês; estados singleton atualizados evitam esse histórico ilimitado.
Um ano de tombstones de256B/evento ~=8,79MiB, ou17,58MiB com fator2.
Tombstone não tem TTL autorizado: horizonte anual é cálculo, não permissão de
apagar após um ano. Pending não expira. Crescimento contínuo continua existindo.

Proposta de retenção: arquivar conteúdo concluído após90dias somente após
export verificado, preservando `event_id`, hash canônico, ack e reservas no
ledger; nunca apagar pending nem identidades necessárias a replay/recovery.
Definir primeiro horizonte máximo de replay/migração; sem isso, dedup persiste.
Alertar inicialmente em100MiB,250MiB e70% do limite real; dimensionar com DB
size observado. Health inclui pending count/oldest age/last forward,
storage error/backpressure e cron/observação frescos.

D1 `batch()` é transação com rollback da sequência em erro. Usar UNIQUE e SQL
condicional para insert/dedup/conflito, lease/reserva de dois dispatches e
outbox; um `SELECT` seguido de check JS e `UPDATE` separado não é atomicidade.
O ack só segue sucesso durável; conflito recebe409. Leases com fencing evitam
que um handler antigo confirme trabalho reclamado por outro. Fonte:
[D1 batch e sessions](https://developers.cloudflare.com/d1/worker-api/d1-database/).
Incerteza entre commit de intenção e efeito externo não desaparece com D1:
preservar identidade e dedup no destino; dispatch ambíguo consome reserva.

Time Travel está sempre habilitado no storage production e não cobra histórico
ou restore adicional. Isso não cobre indisponibilidade/comprometimento da conta
Cloudflare. Fonte: [D1 Time Travel](https://developers.cloudflare.com/d1/reference/time-travel/).
Proposta: export diário criptografado para outro fornecedor, manifest/hash,
owner e teste isolado de restore; metas Ops26 RPO24h/RTO4h continuam não
demonstradas. Export agendado deve executar fora ONO e fora Actions se usado
para desastre GitHub. Restaurar ledger antigo pode duplicar alertas/dispatches:
reconciliar IDs/tombstones e reservas posteriores antes de religar. Rollback de
código conserva DB/ledger corrente. Não foi criado backup nem ensaiado restore.

## GitHub App, RS256 e separação de privilégios

Workers suporta import/sign RSASSA-PKCS1-v1_5. Fonte:
[Workers WebCrypto](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/).
Ensaio local sem dependência nova: Node24.20.0, `nice -n15`, chave RSA2048
sintética em memória, export/import PKCS8, private `extractable:false`, assinatura
de256bytes. Verificação por WebCrypto e `createVerify('RSA-SHA256')`/OpenSSL
passaram; zero requests de token real. **Não é benchmark de CPU Cloudflare nem
teste workerd.** Testes runtime/renovação são responsabilidade da frente PoC.

JWT proposto `alg=RS256`, `iat=now-60`, `exp=now+540`, issuer App/client ID.
PKCS1 PEM `RSA PRIVATE KEY` não é PKCS8 `PRIVATE KEY`: converter em provisioning
autorizado ou suportar wrapper validado, sem armazenar chave em repo. Verificar
tamanho5KB com fixture2048/4096; não assumir que toda chave cabe. Fonte:
[GitHub JWT](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app).

Instalação restrita a este repo e Actions read; token pede explicitamente repo
e `permissions:{actions:'read'}`. Expira em1h; renovar automaticamente antes de
60s restantes e após um GET401 no máximo uma vez; nunca repetir POST ambíguo.
Tokens são opacos, sem pressupor comprimento/prefixo. Fonte:
[GitHub installation token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app).
Actions write só em autorização futura e App/grant revisados; também permite
enable/disable/rerun, não só dispatch. Fonte:
[GitHub workflow API](https://docs.github.com/en/rest/actions/workflows).
Não conceder contents/workflows/secrets/admin. Cooldowns403/429 e reservas
persistem em D1. Cache de token em isolate é otimização, não requisito de vida.

Separar Worker watchdog (chave App) e receiver (somente ingress/sink secrets),
ou registrar explicitamente risco de um único principal combinado. Secret é
binding criptografado, mas todo código daquele Worker pode acessá-lo; trocar
Unix UID por dois handlers no mesmo Worker não preserva isolamento Ops26.
Fonte: [Workers secrets](https://developers.cloudflare.com/workers/configuration/secrets/).
Identidade de deploy/Builds é distinta da App de monitor; restringir repositório,
branch e deploy para que PR não alcance DB/secrets produtivos. Integração Builds
GitHub pode fazer deploy automático em push e criar previews: não conectar
automaticamente durante esta exploração. Fonte:
[Workers Builds GitHub](https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/github-integration/).

## Alternativa persistente e supervisão independente

| Critério | Workers Paid + D1 | Host externo persistente já disponível + Ops26 Python/SQLite |
| --- | --- | --- |
| Disponibilidade factual | Pages configurado; plano/runtime ainda NOT_VERIFIED | Nenhum host alternativo identificado nas evidências: NOT_VERIFIED |
| Hardware ONO/FP&A | Zero serviço adicional ONO | Zero serviço ONO se host separado; proibido recolocar em ONO |
| Estado/cron | D1 e scheduled gerenciados; limites e quota compartilhados | SQLite WAL/FULL + timer; capacidade/fsync/backup precisam preflight |
| Compatibilidade | Portar contratos de locking, identidade, fairness e retenção | Reutiliza runtime Ops26 revisado; P2 ainda requer fechamento |
| Confiabilidade | Workers/D1/conta compartilham falha; monitor fora fornecedor | OS/disco/energia/rede/TLS compartilham falha; monitor fora host |
| Custo total | Piso modelado US$5 + sink/backup/monitor/operação | Marginal hardware pode ser0 se já contratado; capacidade e custos não demonstrados |
| Dependência operacional | Menos patching OS; IAM/quotas/plataforma e restauração | Patching OS, systemd, TLS, quotas, backup e supervisão próprios |
| Tempo até homologação | PoC nova + conta + staging + sink/monitor | Pode reduzir portabilidade; hoje depende de inventário/preflight inexistente |

Não fabricar a existência de um VPS alternativo nem comprar/expandir hardware
para resolver a comparação. Se Cloudflare falhar nos gates, owner deve indicar
host externo existente; só então um preflight separado decide HOST_GO.

Monitor candidato concreto: **Healthchecks.io** recebe heartbeat dead-man e sua
FAQ informa servidores Hetzner, PostgreSQL com standby e backup AWS; portanto
há base pública para separar execução/estado de Cloudflare e Actions. A FAQ
também explicita failover manual e equipe de uma pessoa, com possíveis outages
longos. Fonte: [Healthchecks FAQ](https://healthchecks.io/docs/faq/).
Não houve criação de conta/check, ping, integração ou mensagem. Independência
de DNS/ingress/canal e contrato/SLA ainda precisa staging; hospedagem declarada
não prova ausência completa de dependências Cloudflare em toda a cadeia.

Proposta: heartbeat Cron10min/grace15min enviado **após commit do progresso**;
observação GitHub malsucedida preserva heartbeat de vida mas aciona check de
observação separado. Supervisor externo a cada5min valida `/health` autenticado,
idade do último scheduled<=25min, último sucesso GitHub<=30min fora cooldown
explicado, pendência mais antiga<=30min e progresso de forwarding quando pending>0.
Três falhas consecutivas notificam canal externo e recuperação. Heartbeat
sozinho não prova ingress TLS/backlog; health200 sozinho não prova cron/forward.
Precisa qualificar tanto ausência total quanto Worker vivo com fila bloqueada.

Destino: canal operacional separado do WhatsApp esportivo, com owner e prova
de visibilidade. Mattermost **não está homologado**: Ops26 observa serviços
ONO `ono-mm-alerts`, não verifica endpoint/canal/host do servidor ou recepção.
Webhook Mattermost documentado responde `200` texto `ok`, que não satisfaz
`{accepted:true,event_id}` nem demonstra dedup do efeito visível. Fonte:
[Mattermost incoming webhook](https://docs.mattermost.com/developers/integrate/webhooks/incoming).
Adicionar outbox antes de webhook sem dedup no destino deixa janela de duplicata
após post/ack perdido. Exigir adapter/provedor com dedup/reconciliação de post
qualificados; até lá `SINK_NO_GO`. Aceite de D1 não é entrega no dispositivo.

## Riscos e gates P0/P1/P2

| Prioridade | Risco/bloqueio | Evidência para fechar |
| --- | --- | --- |
| P0 operacional | Conta/quota/custo desconhecidos | Leitura autenticada válida e budget aprovado; sem concluir GO por Pages |
| P0 operacional | Sink e monitor externos inexistentes/não qualificados | Evento sintético durável, replay/ack perdido sem duplicata visível, alerta independente de perda Worker |
| P0 escopo | Provisioning/deploy/ativação não autorizado | Autorização específica para staging separada, depois autorização de produção vinculada a SHA |
| P1 potencial | Corrida D1 reserva/episode/leases | Atomic batch/conditional SQL + testes workerd de concorrência e restart; máx2/slot |
| P1 potencial | Mesmo principal receiver lê App key | Dois Workers/bindings mínimos ou risco residual explicitamente aceito |
| P1 potencial | Cron/ack/body lento, sobreposição e perda de isolate | Deadline total, commit antes ack, lease/fencing, cron perdido/desabilitado e restart |
| P1 operacional | Restore rebobina dedup/reservas | Restore isolado + reconciliação de ledger, RPO/RTO e backup externo verificados |
| P2 admissão | Starvation e crescimento indefinido Ops26 | Seleção justa/retry indexado, oldest age/progress/backpressure, arquivo e tombstones seguros |
| P2 | Free CPU, custos de abuso e uso compartilhado | Medição CPU/rows/size real, limites/instrumentação/billing e ensaio de quota |
| P2 | Monitor único, canal humano, mudança fornecedor | Owners, escalonamento secundário, rotação/revogação automatizada e custo revisado |

Nenhum P0/P1 de plataforma fundamental foi demonstrado nesta pesquisa;
os itens potenciais são exigências de projeto/homologação, não bugs reproduzidos
no runtime Ops27 ainda não revisado. Não existe passo humano semanal por
publicação no projeto, mas autorização inicial, rotação/revogação de chave,
desastre, mudança de contrato e manutenção de quotas exigem responsáveis.

Próxima dependência: acesso **read-only válido** da conta para concluir
inventário/plano/consumo, já dentro do escopo de pesquisa autorizado. A próxima
autorização de escrita é staging isolado nominal (Workers/D1/Secrets
de staging, App Actions read, monitor e sink sintéticos), com teto de custo,
rollback e owners definidos. Este relatório não executa nem concede essa
autorização. O workflow produtivo permanece `disabled_manually`; flag de entrega,
WhatsApp, VM/FP&A, DNS, secrets e PR32 draft não foram alterados.

## Verificação do artefato

Pesquisa oficial via browsing, leituras locais/GitHub descritas, um GET Cloudflare
sanitizado e ensaio criptográfico sintético. Sem dependency install/build,
serviço novo, D1 real, recurso Cloudflare, dispatch ou notificação. Antes do
commit: `git diff --check`; commit limitado a este relatório, sem push/comment.
