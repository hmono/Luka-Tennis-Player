# ATP Ops26 — preparação desativada e gates operacionais

Base: `main@944e417`. Escopo: revisão de código e artefatos no repositório,
sem instalação ou ativação. Evidências: `docs/evidence/ops26-*.md`.

## Decisão e alternativa de host

O preflight da ONO indica `HOST_NO_GO`: disco a 94%, cerca de 3,15 GiB
livres, contenção de CPU/I/O e cobertura insuficiente dos picos FP&A.
Nenhuma preparação em `/etc`, `/opt`, `/var/lib`, systemd, proxy, DNS,
firewall ou conta de serviço deve ocorrer nesta sprint. Não ampliar a VM,
limpar seus arquivos ou deslocar os workloads FP&A para acomodar ATP.

A alternativa é um host persistente já disponível, separado da ONO e do
GitHub Actions, sujeito a novo preflight e autorização de operação. Não foi
selecionado ou provisionado um host alternativo. O runner efêmero de CI só
valida código; não substitui watchdog, SQLite, TLS ou canal operacional.

Orçamento proposto para admissão futura, ainda não homologado sob carga:
128 MiB para watchdog + 256 MiB para inbox; proxy incremental ainda a medir;
0,2 CPU no total para os dois processos ATP; 512 MiB para código/estado/logs
e cópia local limitada. Exigir pelo menos 5 GiB livres **após** essa reserva,
além do crescimento previsto pelo owner FP&A. O orçamento de disco precisa
de quota/monitoramento e retenção implementados antes de operação contínua.

## Bootstrap desligado, somente como artefatos versionados

Os templates estão em `deployment/atp-watchdog/`. Não há instalador que possa
contornar o gate. Todos os exemplos mantêm as quatro flags de entrega,
watchdog, recuperação e receptor em `false`, com credenciais vazias.
Validar os arquivos sem instalar:

```sh
systemd-analyze verify deployment/atp-watchdog/atp-ranking-watchdog.service \
  deployment/atp-watchdog/atp-ranking-watchdog.timer \
  deployment/atp-watchdog/atp-ops-inbox.service
python3 -m unittest discover -s tests/ranking_alerts
```

Na ONO, executar somente testes isolados de baixo custo, serializados e com
prioridade reduzida. Frontend e build devem usar o workflow existente de
regressão em PR, sem deploy. Não executar uma coleta real nesta sprint.

Depois de novo `HOST_GO` e autorização explícita para instalação, a operação
deverá criar usuários distintos sem login para watchdog e inbox; checkout
imutável do SHA revisado em `/opt/luka-tennis`; estado separado e persistente
em `/var/lib/atp-ranking-watchdog` e `/var/lib/atp-ops-inbox`, modo `0700`;
envs root-owned `0600`; chave App fora do checkout, legível apenas por root e
pelo principal do watchdog (arquivo `0440`, diretório `0750`). O receptor não
deve ler a chave App. Validar permissões efetivas antes de qualquer start.
Copiar templates não concede autorização para `enable`, `start` ou despacho.

## Credenciais e permissões, provisionamento uma vez

Criar/instalar uma GitHub App restrita a `hmono/Luka-Tennis-Player` somente
em etapa autorizada. O modo de monitoramento usa Actions read; Actions write
fica condicionado à futura liberação de recuperação. Não conceder escrita
de contents, workflows, secrets ou administração. Tokens de instalação devem
ser limitados ao repositório e permissão solicitados e renovados automaticamente.
Revogação de App/chave exige operação de credencial e não pode ser resolvida
por retries infinitos. Registrar owner, rotação planejada da chave e alarme de
falha de renovação sem imprimir JWT, bearer, URL com segredo ou respostas.

O escopo explícito do token evita herdar todos os repositórios/permissões da
instalação, conforme a [API oficial de GitHub Apps](https://docs.github.com/en/rest/apps/apps?apiVersion=2022-11-28#create-an-installation-access-token-for-an-app).
Dry-run não deve emitir token App nem criar banco, enviar alerta ou despachar.
Os testes usam credenciais sintéticas e transporte substituído por mocks.

## HTTPS e destino operacional

Provisionar DNS/certificado com renovação automática, proxy HTTPS que encaminhe
somente `/events` e `/health` ao loopback do inbox, limite de corpo 8192 bytes,
timeout e rate limit. Separar bearer de entrada e credencial do destino.
Validar certificado/cadeia/hostname reais em staging autorizado; mocks não
comprovam TLS. Não abrir a porta do processo Python na rede pública.

O destino deve ser independente do WhatsApp esportivo e persistir `event_id`
com conteúdo antes de responder `{"accepted":true,"event_id":"<mesmo ID>"}`.
Ambos os saltos validam o ID da confirmação. Repetição com conteúdo
igual aceita sem duplicar; conteúdo conflitante rejeita. Resposta 2xx vazia,
`false` ou valor numérico não encerra a intenção. Timeout após persistência
pode gerar replay com o mesmo ID: o destino deduplica. Aceite durável não
comprova leitura ou entrega em dispositivo.

Não há provedor/destino real homologado: `SINK_NO_GO`. Um webhook genérico
não cumpre esse contrato por definição. Caso o provedor escolhido não ofereça
idempotência, um adaptador persistente deve ser construído e homologado de
ponta a ponta; não basta acrescentar um header.

## Persistência, backup, retenção e rollback

Manter estado fora do checkout e nunca restaurar SQLite de backup antigo
sobre o ledger corrente para acompanhar rollback de código. Usar a API de
backup do SQLite para snapshot consistente; não copiar apenas o arquivo DB
enquanto WAL está ativo. Validar `PRAGMA integrity_check` na cópia e ensaiar
restauração em caminho isolado, incluindo replay e tentativas reservadas.
Backup externo criptografado e owner de restauração ainda precisam ser
provisionados. Meta proposta: backup diário, RPO 24 h, RTO 4 h; metas não
comprovadas e dependentes do contrato operacional aprovado.

IDs aceitos e reservas de recuperação protegem contra reenvio: não apagar
esses registros por idade sem preservar tombstones de deduplicação. Nunca
eliminar pendências para aliviar espaço. O estado atual não implementa
retenção automática segura; isso bloqueia operação indefinida. Planejar
compactação/arquivamento transacional com tombstones, limite por tenant e
alerta preventivo de espaço antes da admissão de produção. Não rodar VACUUM
ou testes de disco cheio na ONO.

Rollback de código exige compatibilidade com o schema/ledger atual e teste em
cópia. O procedimento de incidente, quando operação estiver autorizada, deve
primeiro suspender apenas os serviços ATP e preservar DB/WAL/SHM para análise;
nunca reiniciar FP&A como tentativa de recuperação ATP. Nenhuma suspensão foi
executada nesta sprint.

## Falhas, supervisão e dependências humanas

O timer renova a observação a cada dez minutos. Ausência/falha de run, API
indisponível e workflow desabilitado têm identidades deduplicadas. Recuperação
futura tem orçamento de duas reservas por slot e backoff de 30 minutos;
workflow desabilitado nunca é reativado pelo watchdog. HTTP ambíguo não concede
tentativa extra. A fila operacional preserva pendências e reenvia o mesmo ID.

Um monitor **fora do host** precisa verificar o último ciclo bem-sucedido do
watchdog, saúde/progresso do inbox, idade da pendência mais antiga, capacidade
e expiração TLS, com destino independente. HTTP 200 do inbox sozinho não
prova que forwarding está avançando. A queda da própria VM não é detectável
pelo watchdog que roda nela. Esse monitor não foi provisionado.

Não se exige intervenção por edição, semana ou falha transitória recuperável.
Permanecem humanas: autorização inicial, instalação da App, posse de DNS e
canal, escolha do host, rotação/revogação de chave, desastre/perda de disco,
mudança de permissões ou contrato do provedor e manutenção de capacidade.
Recorrências planejadas devem ter owner e automação/alertas, sem declarar
autonomia ilimitada antes de validar esses mecanismos.

## Critérios para reabrir os gates

1. Novo host com capacidade e isolamento demonstrados, mais autorização de
   escrita no host; ONO permanece bloqueada enquanto o preflight falhar.
2. App/credenciais mínimas, TLS real, destino idempotente e monitor externo
   provisionados; backup/restauração e retenção validados.
3. Staging isolado com medição antes/depois, falhas API/SQLite/restart e replay,
   sem endpoints/provedores esportivos reais. Revisor confirma zero P0/P1 de
   código abertos e aceita explicitamente riscos operacionais residuais.
4. Autorização produtiva separada, vinculada a SHA e evidências. Esta sprint
   não satisfaz nem executa essa autorização: `ACTIVATION_NO_GO`.
