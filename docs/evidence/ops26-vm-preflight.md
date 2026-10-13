# OPS-01 — preflight read-only da VM ONO

**Decisão: HOST_NO_GO para instalar/ativar ATP nesta VM neste estado.**

Issue: [#27](https://github.com/hmono/Luka-Tennis-Player/issues/27), epic #26.
Host observado: `zv-srv-ono`. Janela principal de coleta:
**2026-10-13 19:32:16–19:34:40 UTC**; resumo histórico complementado logo após.
Base de código:
`944e4174444a32ba7182db62f644e5a433dcee67`, branch `ops26/host-preflight`.

A RAM instantânea comporta um orçamento pequeno, mas o disco raiz tem somente
3,14 GiB disponíveis, há pressão de CPU/I/O e existe uma falha FP&A anterior.
O pico completo semanal/mensal FP&A e seu crescimento de armazenamento não foram
demonstrados. Nginx existe, mas HTTPS/proxy para ATP não está provisionado. Um
watchdog e sua própria supervisão na mesma VM não detectam a queda dessa VM.
Esses bloqueios impedem um parecer seguro de capacidade sustentada.

## Escopo e preservação

Somente observação de baixo custo: metadados do kernel/systemd, dois arquivos
sysstat existentes, inventário de versões, configuração de retenção sem conteúdo
de logs, diretivas nginx resumidas e duas requisições HTTPS HEAD sem autenticação.
Não houve benchmark, suíte de testes, coleta ATP, envio, dispatch Actions,
instalação, sudo, reinício, mudança de configurações, expansão de hardware,
leitura de ambientes de processos, credenciais, chaves ou conteúdo privado FP&A.
O único arquivo criado é este relatório no worktree designado.

Não houve varredura ampla nem `du` no disco do host. O único `du` foi no diretório
pequeno `docs/evidence` deste worktree (172.032 bytes antes deste relatório).
Os tamanhos sysstat/nginx foram lidos com `stat`; o journal com
`journalctl --disk-usage`. O checkout primário foi preservado.

O primeiro alerta ao coordenador foi emitido após a amostra inicial: serializar
testes focados, evitar builds e suítes paralelas. O coordenador confirmou testes
serializados com prioridade baixa. Este relatório não executou esses testes.

## Capacidade observada

GiB/MiB são unidades binárias; `free -b` e `df -B1` fornecem bytes. Valores
instantâneos não são picos de operação nem reservas garantidas.

| Item | Evidência e interpretação |
| --- | --- |
| CPU | 2 vCPU x86_64, Intel Xeon Gold 5120 @ 2,20 GHz, KVM, 1 thread/core; nenhum limite adicional na sessão (`cpu.max = max 100000`) |
| Uptime/load inicial | 3 dias 5h17; load 1/5/15 min = 1,25/1,03/0,77 às 19:32:16 |
| RAM total | 8.327.663.616 bytes = 7,76 GiB |
| RAM disponível inicial/final | 6.184.976.384 / 6.138.765.312 bytes = 5,76 / 5,72 GiB |
| RAM usada inicial/final | 2.142.687.232 / 2.188.898.304 bytes; cache é recuperável, por isso `available` é a medida de admissão |
| Swap total/usada | 4.294.963.200 bytes; usada 509.607.936 inicialmente e 500.695.040 ao final, aproximadamente 486/478 MiB; uso de swap existente não prova thrashing atual |
| Disco raiz | `/dev/mapper/ubuntu--vg-ubuntu--lv`, ext4 `rw,relatime`; capacidade `df` 50.403.627.008 bytes = 46,94 GiB |
| Disco usado/disponível inicial | 45.971.615.744 / 3.384.528.896 bytes, **94% usado** |
| Disco usado/disponível final | 45.979.533.312 / 3.376.611.328 bytes = **3,14 GiB disponíveis**; diferença entre amostras não é previsão de crescimento |
| Inodes | 3.145.728 totais, 785.893 usados (25%), 2.359.835 livres |
| Topologia | único disco `sda` 50 GiB, `/boot` ext4 2 GiB, partição LVM 48 GiB para `/`; `/home/ono` e `/tmp` usam o mesmo filesystem raiz |
| Persistência ATP | ext4 local disponível, mas `/opt/luka-tennis`, `/var/lib/atp-ranking-watchdog` e `/var/lib/atp-ops-inbox` inexistentes; volume separado, backup e restore ATP não comprovados |

`vmstat 1 3`: a primeira linha resume desde o boot e **não** foi tratada como
amostra de um segundo. Às 19:32, os dois intervalos seguintes tiveram CPU
user/system/idle de 56/7/37% e 84/16/1% (arredondamento), com 5 e 4 processos
executáveis. Às 19:34, os intervalos foram 34/5/56% e 11/4/86%; iowait 6% e 0%.
A melhora posterior não elimina os picos históricos. `ps` sem argumentos de
processos mostrou `python3` e `dbt` consumindo aproximadamente 90% e 80% de uma
CPU no instante inicial; não se atribui esse consumo ao serviço FP&A sem prova.
`ps %CPU` é uma média de vida do processo, distinta de `vmstat`.

| PSI do kernel | 19:32:18 UTC, avg10/60/300 (%) | 19:34:40 UTC, avg10/60/300 (%) |
| --- | --- | --- |
| CPU some | 11,18 / 11,44 / 6,43 | 8,13 / 9,33 / 8,23 |
| Memória some | 0,01 / 0,16 / 0,07 | 0,00 / 0,04 / 0,05 |
| Memória full | 0,00 / 0,09 / 0,05 | 0,00 / 0,03 / 0,03 |
| I/O some | 1,05 / 5,74 / 13,98 | 5,27 / 8,93 / 12,19 |
| I/O full | 0,47 / 3,83 / 11,68 | 4,32 / 6,72 / 9,56 |

PSI registra tempo de espera das tarefas, não percentual de bytes ou espaço em
disco. O `iostat -dx -y 1 2` final mostrou um segundo sem I/O e outro com `sda`
a 49 reads/s, 552 KiB/s, `r_await=0,88 ms`, `%util=2,10`. Isso prova apenas que
houve um instante tranquilo, sem medir throughput máximo do armazenamento.

## Histórico real, picos conhecidos e lacunas

Reutilizados `/var/log/sysstat/sa12` (252.232 bytes) e `sa13` (206.888 bytes),
sem gerar amostras novas. Foram 143 registros em 12/10 00:10:26–23:50:26 UTC
e 117 em 13/10 00:10:26–19:30:11 UTC. Intervalos aproximadamente de 10 minutos.
Taxas de CPU/I/O são médias de intervalo; RAM/load/runqueue são observações no
registro. Portanto, os máximos abaixo são **picos observados**, não limites
superiores nem cobertura de todos os picos entre registros.

| Métrica | 12/10/2026 | 13/10/2026 até 19:30 |
| --- | --- | --- |
| CPU execução média/máxima por intervalo | 4,28% / 34,37% (21:10:26) | 6,92% / 40,07% (13:00:09) |
| CPU iowait máximo | 36,27% (21:40:26) | 30,40% (15:30:16) |
| CPU idle mínimo | 40,99% (21:40:26) | 38,85% (15:40:18) |
| Load 5 min máximo | 2,93 (21:30:08) | **3,68** (15:50:12), acima dos 2 vCPU |
| Load 1 / 15 min máximos | 3,66 / 2,10 | 3,33 / 2,80 |
| Runqueue máxima observada | 7 (22:40:15) | 6 (10:50:00) |
| MemAvailable mínimo | 5.529.916 KiB = 5,27 GiB (21:40:26) | 5.863.644 KiB = 5,59 GiB (19:20:26) |
| Swap usada máxima | 122.368 KiB = 119,5 MiB | 591.616 KiB = 577,75 MiB |
| Swap pages out máximo/s | 19,98 (21:40:26) | 120,13 (12:50:26) |
| `sda await` máximo | 126,40 ms (03:10:08) | **695,96 ms** (19:10:21) |
| `sda %util` máximo | 69,08% (21:40:26) | 37,73% (15:40:18) |
| `sda` leitura/escrita máximas | 552,42 / 4.021,96 KiB/s | 15.755,03 / 2.248,20 KiB/s |

A média de execução CPU acima é a média aritmética não ponderada dos registros:
`100 - idle - iowait - steal`. Inclui nice e system, não inclui espera I/O.
Os horários dos máximos de métricas diferentes podem divergir. `%util` de um
disco virtual não estabelece capacidade máxima/garantida; latência e PSI são
necessários. Não há baseline histórico do espaço livre, tamanho FP&A ou taxa de
eventos ATP. A janela cobre menos de dois dias, inclui uma segunda-feira, mas
não cobre todo o fechamento mensal nem o job mensal previsto para 15/10.

## FP&A, workloads e controles de não interferência

Inventário às 19:32–19:33: 27 serviços em execução. Além do FP&A: nginx,
node_exporter, journald/rsyslog, cron, SSH, timesyncd, tailscaled, serviços de
desktop/rede/impressão e agentes de desenvolvimento. Processos identificados
por `comm` incluíram uvicorn (~179 MiB RSS), jupyter-lab (~113 MiB), agentes
codex/claude, dbt e Python. RSS individual e MemoryCurrent de cgroup não têm a
mesma contabilidade e não foram somados como se fossem memória exclusiva.

| Unidade FP&A | Estado/recurso observado | Próxima execução UTC |
| --- | --- | --- |
| `fpa-app.service` | active/running; MemoryCurrent 100.204.544 bytes (95,6 MiB), MemoryPeak 114.733.056 (109,4 MiB), 5 tasks; NRestarts=0; CPU acumulada ~219 s desde 12/10 22:05:10 | contínuo |
| `fpa-decurso-aviso.timer` | serviço inativo, último Result=success; pico não disponível | 14/10 09:00 |
| `fpa-decurso-previsto.timer` | serviço inativo, último Result=success; pico não disponível | 14/10 12:00 |
| `fpa-abrir-plan.timer` | serviço inativo, último Result=success; pico não disponível | 15/10 07:00 |
| `fpa-snapshot-previsto.timer` | **serviço failed, Result=exit-code, ExecMainStatus=1**, executado 12/10 07:10:01–07:10:02; CPU ~0,926 s; pico não disponível | 19/10 07:10 |
| `fpa-outbox-export.timer` | último Result=success; CPU ~1,344 s; pico não disponível | 19/10 07:20 |

O cgroup atual de `fpa-app` registra `oom=0`, `oom_kill=0`, `max=0`, `high=0`;
isso não demonstra ausência de OOM histórico no host ou em outros workloads.
`fpa-app` não tem MemoryMax ou CPUQuota configurados; Nice=0. A falha snapshot
é anterior à observação; sua causa não foi investigada em logs privados, nem
foi atribuída à falta de recursos. Deve ser esclarecida pelo responsável FP&A
antes de adicionar um workload ao mesmo disco/CPU.

Existem timers `ono-metrics` e `ono-mm-alerts` (~5 min), `ono-mm-digest` diário,
sysstat (~10 min), logrotate diário e tarefas apt/fwupd/man-db. Todos competem
por CPU/disco, apesar de não serem continuamente ativos. `fwupd-refresh` também
está failed. Métricas existentes usam limites explícitos: node_exporter
MemoryMax=96 MiB, quota=0,2 CPU, Nice=5; ono-metrics 128 MiB/0,5 CPU/Nice=10;
ono-mm-alerts e digest 64 MiB/0,25 CPU/Nice=10. Isso não comprova monitor externo.

Controles necessários para futuro ATP: prioridade baixa (Nice=15), cotas
individuais de CPU/memória, limites de tasks/conexões, taxa e corpo no proxy,
deadline finito, sem coleta/browser/build local, sem sobreposição de watchdog
e sem alterar limites/agendamentos FP&A. As units ATP na base possuem
hardening e watchdog TimeoutStartSec=300, mas **não** possuem cotas de
CPU/RAM/I/O/tasks. Essas propostas não foram aplicadas. Durante investigação,
manter apenas uma suíte focada por vez; interromper novas tarefas de diagnóstico
se pressão/margem deteriorar, sem parar FP&A.

## Orçamento incremental proposto e comparação

Este é um **teto de admissão proposto**, não consumo ATP medido: ATP não foi
iniciado para medir memória/picos. As metas exigem validação fora de produção
e implementação de limites antes de habilitação.

| Recurso ATP | Orçamento máximo proposto | Disponível / condição |
| --- | --- | --- |
| Watchdog oneshot, a cada 10 min | 128 MiB RAM; 0,1 CPU; no máximo 10 CPU-s/ciclo como meta de operação; deadline 300 s já na unit | 144 ciclos/dia; 10 CPU-s/600 s = 0,0167 CPU média; uso real/retries desconhecido |
| Inbox contínuo + SQLite | 256 MiB RAM; 0,1 CPU; conexões/tasks e ingress limitados | soma ATP 384 MiB e 0,2 CPU (10% dos 2 vCPU); nginx incremental dentro da margem, não benchmarkado |
| Disco ATP total | **512 MiB**, incluindo duas bases SQLite/WAL, código, logs e contingência | somente 3,14 GiB livres; após orçamento sobrariam **2,64 GiB**, abaixo da reserva proposta |
| Disco reservado a host/FP&A | **mínimo 5 GiB livres após ATP**, mais crescimento FP&A demonstrado (`G`) | exige antes ≥5,5 GiB + G; déficit atual ≥2,36 GiB + G; não há autorização nem ação de limpeza/expansão |
| RAM reservada a host/FP&A | ≥2 GiB MemAvailable após teto ATP e aumento de pico FP&A validado | mínimo histórico 5,27 GiB − 0,375 = 4,90 GiB; passa só a janela observada; pico mensal desconhecido |
| I/O ATP | meta ≤1 MiB gravado/ciclo watchdog, ≤16 KiB por evento combinado nos dois stores, sem varreduras/bulk reads | metas de orçamento, sem limite de IOPS/latência demonstrado; volume root compartilhado já teve await ~696 ms |

O mínimo histórico de RAM dá margem instantânea para 384 MiB; não autoriza
implantação diante dos bloqueios de disco/I/O/FP&A. Cota de 0,2 CPU limita dano
mas não garante deadline de rede/SQLite em períodos de contenção.

Critérios conservadores propostos para reavaliar HOST_GO, **todos obrigatórios**:

1. Demonstrar ≥5 GiB livres após 512 MiB ATP **e** reserva de crescimento FP&A
   definida pelo responsável; crescimento e retenção sustentáveis sem expandir
   hardware nesta tarefa. Sem `G` conhecido, o gate continua fechado.
2. Baseline real cobrindo pelo menos um ciclo semanal e o fechamento/job mensal,
   incluindo picos e saúde dos jobs FP&A; aclarar a falha snapshot existente.
3. Durante horários críticos, MemAvailable ≥2 GiB após ATP/pico adicional,
   sem novos OOM e sem crescimento sustentado de swap; validar limites ATP.
4. Sem contenção sustentada: load5 ≤1,5 nos 2 vCPU, CPU PSI some avg300 <5%,
   I/O PSI full avg300 <1% e await por intervalo <50 ms, com ≥0,5 CPU livre
   após ATP. Estes são critérios locais conservadores propostos, não SLAs de
   fabricante. Os registros atuais falham vários desses critérios.
5. Limites de recursos, eventos/conexões, retenção segura, HTTPS, persistência,
   restore e monitor externo independente demonstrados antes de ativação.

## Armazenamento, retenção e dependências

`journalctl --disk-usage`: **298,7 MiB**. `systemd-analyze cat-config
systemd/journald.conf` mostrou somente linhas padrão comentadas para Storage,
SystemMaxUse, SystemKeepFree e MaxRetentionSec; **nenhuma política explícita
local de tamanho/prazo comprovada**. Não presumir que o comportamento padrão
reserva espaço para FP&A/ATP. Não foi lido o conteúdo do journal.

Nginx logrotate: diário, 14 rotações, compressão com delaycompress. Rsyslog:
semanal, 4 rotações, compressão com delaycompress. Esses limites de quantidade
não limitam bytes antes da rotação; nenhum size/maxsize apareceu nesses arquivos.
`stat`: access.log 84 bytes, error.log 0 bytes no instante; não é pico de log.

Distribuição proposta dos 512 MiB ATP: 256 MiB para as duas SQLite e arquivos
auxiliares/WAL, 128 MiB código/runtime, 64 MiB logs e 64 MiB contingência.
Blobs Git rastreados nesta base: 173 arquivos, 1.366.474 bytes lógicos; esse
valor não inclui .git, caches, venv ou artefatos. Watchdog/inbox usam biblioteca
padrão Python e OpenSSL; **não precisam Playwright/browser/node_modules**.

Hipótese explícita de retenção para dimensionamento: 30 dias, 8 KiB/evento/store
incluindo uma provisão de overhead, nos dois stores. A 16 eventos novos/dia:
7,5 MiB combinados. A 400/dia: 187,5 MiB combinados, deixando 68,5 MiB dos
256 MiB para índices/WAL/variação. A hipótese precisa de taxa observada e política
de deduplicação/replay acordadas. Não é garantia de tamanho: base e WAL têm
overhead variável. Os limites de flush (8 watchdog, 100 inbox) limitam envio por
tentativa, **não** entrada ou quantidade acumulada. Código na base não faz
DELETE/expiração automática; IDs únicos crescem indefinidamente.

Exigir alertas independentes de tamanho (80% do orçamento), política de
retenção/arquivo com deduplicação/replay validada e backpressure antes de
esgotar o teto. Não apagar eventos pendentes ou chaves de deduplicação para
simular autonomia; é necessária uma política segura e testada. Limite de RAM
não limita disco. Nenhuma quota, limpeza, backup ou rotação foi instalada.

| Dependência | Estado observado |
| --- | --- |
| OS/kernel | Ubuntu 24.04.4 LTS / 6.8.0-146-generic |
| Python | `/usr/bin/python3.12`, 3.12.3, pacote 3.12.3-1ubuntu0.17 |
| OpenSSL | CLI e `ssl.OPENSSL_VERSION`: 3.0.13; pacote 3.0.13-0ubuntu3.16 |
| SQLite | módulo Python 3.45.1, libsqlite3-0 3.45.1-1ubuntu2.8; CLI sqlite3 ausente, não é necessário para os módulos |
| systemd | 255.4-1ubuntu8.17; cgroup v2; startup kernel 3,069 s + userspace 8,777 s = 11,847 s |
| TLS/timezone | ca-certificates 20260601~24.04.1, tzdata 2026c-0ubuntu0.24.04.1; ZoneInfo America/Sao_Paulo resolve |
| Pacotes Python | pip 24.0, requests 2.34.2; Playwright ausente no interpretador do sistema, desnecessário para watchdog/inbox |
| ATP units | watchdog.service, watchdog.timer e inbox.service LoadState=not-found |
| Credenciais/config | arquivos environment ATP inexistentes por teste de metadados; nenhum segredo lido ou criado |
| Usuário/checkout/estado | provisionamento do usuário não verificado; checkout e diretórios de estado inexistentes; pendência de implantação separada |

## Serviços, portas, proxy, relógio e GitHub HTTPS

`ss -lntup` às 19:32:45: TCP 22 e 80 em todas as interfaces IPv4/IPv6,
4000/8000/8888 em IPv4 todas as interfaces; 9100, 631, DNS e portas temporárias
de agentes em loopback; listeners Tailscale também presentes. UDP: DNS,
Tailscale e mDNS. ATP 8765 e HTTPS 443 **não apareciam**. Não inferir exposição
pública: firewall/DNS/ingress externo não foram testados.

Nginx active/running, MemoryCurrent 4.263.936 bytes, MemoryPeak 4.534.272 bytes.
Único site habilitado: symlink `default`. Resumo do arquivo alvo, ignorando
comentários: duas diretivas listen (`80 default_server`, `[::]:80 default_server`),
zero `proxy_pass`, zero `ssl_certificate`. HEAD local `http://127.0.0.1:80/`
respondeu 200 em 1,497 ms. Isso confirma servidor HTTP existente; não demonstra
proxy ATP, certificado válido, renovação, autenticação, limites de ingress ou
alcance externo. Nenhuma chave TLS foi aberta.

Relógio: Etc/UTC, LocalRTC=no, NTP=yes, NTPSynchronized=yes;
systemd-timesyncd active (chrony/ntp inactive). Às 19:33:22:
stratum=2, offset=-46,162 ms, jitter=18,163 ms, root distance=4,623 ms,
delay=300,017 ms, 141 pacotes. Sincronização passa a observação, não prova
continuidade futura.

HEADs sem credencial, às 19:33:22:

| Destino | HTTP | TLS verify result | DNS / conexão / TLS / total (s) |
| --- | --- | --- | --- |
| https://github.com | 200 | 0 (verificação passou) | 0,053297 / 0,057925 / 0,131950 / 0,138132 |
| https://api.github.com | 200 | 0 | 0,003647 / 0,007172 / 0,047844 / 0,052962 |

Isso prova DNS/HTTPS de saída naquele instante. Não valida permissões GitHub
App/Actions, refresh de token, rate limits autenticados, dispatch ou destino de
entrega. `gh issue view` leu somente #27; não houve escrita remota.

## Falha comum e monitor independente

O watchdog fora de Actions reduz dependência do runner/GitHub, mas hospedá-lo
em ONO junto com SQLite, inbox, nginx, node_exporter e ono-mm-alerts mantém
uma falha comum: queda da VM, disco cheio, rede/NTP ou energia afetam monitor e
notificação ao mesmo tempo. Timers Persistent ajudam após retorno, não durante
a interrupção. Um processo local não pode provar que avisou sobre sua própria
indisponibilidade.

Requisito proposto, sem provisionar: monitor em outro provedor/host com domínio
de falha e armazenamento independentes, consultando saúde HTTPS + frescor do
último ciclo/heartbeat de watchdog; checagem a cada 5 min, alerta após 3 falhas
consecutivas (aproximadamente 15 min), canal operacional e credenciais separados
do inbox ONO, com confirmação de teste e recuperação. Node_exporter em loopback
não prova que já existe scraper/alertmanager externo. Existência e cobertura
desse monitor externo **desconhecidas**. Nenhum monitor/canal foi criado ou acionado.

## Comandos reproduzíveis e resultados de falha

Executar somente a leitura, sem sudo, coletando timestamp UTC antes de cada
grupo. As seguintes consultas não incluem conteúdo de secrets/logs/process args.
Nenhum comando de reparo, limpeza ou ativação integra este diagnóstico.

```sh
date -u +'%Y-%m-%dT%H:%M:%SZ'
hostname
uptime
nproc
lscpu
free -b
df -B1 -T / /home/ono /tmp
df -i / /home/ono /tmp
lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS
findmnt -no SOURCE,FSTYPE,OPTIONS /
vmstat 1 3
iostat -dx -y 1 2
cat /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io
ps -eo pid,ppid,comm,%cpu,%mem,rss --sort=-rss
ps -eo pid,ppid,comm,%cpu,%mem,rss --sort=-%cpu
cat /etc/os-release
uname -r
python3.12 --version
openssl version
systemctl --version
systemd-analyze
timedatectl show -p Timezone -p NTPSynchronized -p NTP -p LocalRTC
timedatectl timesync-status --no-pager
systemctl list-units --type=service --state=running --no-pager
systemctl list-timers --all --no-pager
systemctl list-units --failed --no-pager
ss -lntup
journalctl --disk-usage
systemd-analyze cat-config systemd/journald.conf
stat -c '%n bytes=%s' /var/log/sysstat/sa12 /var/log/sysstat/sa13
du -s -B1 docs/evidence
sadf -j /var/log/sysstat/sa12 -- -u -r -q -S -W -d
sadf -j /var/log/sysstat/sa13 -- -u -r -q -S -W -d
```

Para reproduzir limites e peaks FP&A sem `systemctl status`/journal, consultar
as seis units FP&A listadas neste relatório:

```sh
systemctl show fpa-app.service fpa-decurso-aviso.service \
  fpa-decurso-previsto.service fpa-abrir-plan.service \
  fpa-snapshot-previsto.service fpa-outbox-export.service \
  -p Id -p ActiveState -p SubState -p Result -p NRestarts \
  -p MemoryCurrent -p MemoryPeak -p MemoryMax -p CPUUsageNSec \
  -p CPUQuotaPerSecUSec -p IOReadBytes -p IOWriteBytes -p TasksCurrent \
  -p Nice -p IOWeight -p ExecMainStartTimestamp -p ExecMainExitTimestamp \
  -p ExecMainStatus
cat /sys/fs/cgroup/system.slice/fpa-app.service/memory.events
cat /sys/fs/cgroup/user.slice/user-1000.slice/session-202.scope/cpu.max
cat /sys/fs/cgroup/user.slice/user-1000.slice/session-202.scope/memory.max
curl --head --silent --show-error --max-time 15 --output /dev/null \
  --write-out 'http=%{http_code} verify=%{ssl_verify_result} dns=%{time_namelookup}s connect=%{time_connect}s tls=%{time_appconnect}s total=%{time_total}s\n' \
  https://github.com
curl --head --silent --show-error --max-time 15 --output /dev/null \
  --write-out 'http=%{http_code} verify=%{ssl_verify_result} dns=%{time_namelookup}s connect=%{time_connect}s tls=%{time_appconnect}s total=%{time_total}s\n' \
  https://api.github.com
```

O `sadf` foi capturado em memória por Python stdlib e resumido por campo;
máximos e mínimos preservaram os timestamps dos registros. Amostras e esquema
de JSON são reproduzíveis com os comandos acima, sem salvar dumps no host.
O caminho da sessão cgroup é específico à sessão e pode mudar; obter o caminho
atual com `cat /proc/self/cgroup` antes de repetir.

Falhas de observação registradas e tratadas: consulta inicial aos controles
diretamente na raiz cgroup não encontrou cpu.max/memory.max (root não é a
sessão); foi repetida no cgroup correto, sem limites adicionais. Um primeiro
resumo `sadf -r -u` não continha swpused e o parser encerrou com KeyError;
repetido com `-S`, obtendo a tabela completa acima. Dois nomes de módulos
supostos não existiam; foi lido o `ops_receiver.py` real. `ls` dos paths ATP
retornou inexistente. Nada disso foi substituído por mocks ou interpretado
como sucesso. Serviços inativos reportaram peaks/I/O `[not set]`, preservados
como **desconhecidos**, nunca zero.

**Resultado do gate:** HOST_NO_GO permanece. O relatório conclui diagnóstico
read-only e orçamento revisável; não autoriza instalar/ativar, alterar FP&A,
habilitar Actions/flags, enviar WhatsApp ou merge em main.
