# Sprint #25 — B: entrega autônoma e auditoria do provedor

Implementação preparada em branch isolada `sprint25/delivery`, base `dc5032a`.
Nenhuma credencial consultada, nenhum WhatsApp enviado, nenhum workflow ativado.
Todos os envios executados pelos testes usam provedores e callbacks locais simulados.

## Contrato de integração

Novo módulo: `scripts/ranking_alerts/autonomous_delivery.py`.
Novo estado obrigatório no bundle Git: `automation/state/ranking_delivery.json`.
O integrador adiciona esse caminho ao `STATE_PATHS` e valida `load_delivery()`
antes de checkpoint. Usa o mesmo `state_lock` dos coletores antigos durante
leitura, planejamento, gravação, reserva, checkpoint e envio. `checkpoint` é
argumento obrigatório; uma exceção impede o envio. A reserva com nonce fica
persistida localmente e publicada no Git antes de qualquer efeito externo.
O runner chama CallMeBot com `max_attempts=1`: backoff fica no estado durável,
sem depender de esperar dentro do processo.

APIs: `load_delivery`, `save_delivery`, `plan_digest`, `plan_weekly_status`,
`plan_operational`, `deliver_autonomously`. Planejadores retornam um novo
`DeliveryLedger`. `plan_digest` recebe `legacy_state` e `legacy_rankings` para
reconhecer receipts de qualquer revisão da mesma edição.
`deliver_autonomously` admite `provider=None` para executar somente a via
operacional quando a configuração esportiva não estiver disponível.

O ledger novo é append-only e schema-validated. Snapshots, outbox e incidentes
anteriores não são regravados nem descartados. A migração reconhece aceite
histórico como aceite do provedor, sem elevar a entrega para dispositivo.
Reservas/falhas antigas ambíguas recebem disposição automática auditável.

## Identidade, periodicidade e recuperação

O digest usa identidade por data oficial da edição, independentemente de os
ranks terem mudado. O integrador produz texto com S/D, delta e CH sobre o
snapshot validado. O status semanal usa a segunda-feira ISO às 09:00 America/Sao_Paulo como identidade
do período; texto contém explicitamente última data verificada e momento da
checagem. Conforme requisito C.2 esclarecido pelo integrador, há um status por
semana independentemente de nova edição; quando houver nova edição, digest e
status possuem intenções distintas. Repetir checagem no período não duplica.

Se uma fonte corrigir a edição antes de uma tentativa aceita ou ambígua, uma
intenção ainda não enviada ou definitivamente rejeitada por 429 é suprimida
com `superseded_revision`; a revisão atual recebe intenção e nonce novos.
A sequência A→B→A preserva as três intenções e envia somente a atual. Um
aceite ou resultado desconhecido estabelece cerca por edição e impede que a
correção provoque novo envio esportivo. Backlog de edições e semanas antigas
é suprimido explicitamente, preservando histórico e evitando uma enxurrada.

| Resultado | Disposição automática | Garantia/limite |
| --- | --- | --- |
| CallMeBot com acknowledgment explícito | `provider_accepted` | Não prova chegada ao dispositivo |
| HTTP 429 definitivamente rejeitado | `retry_wait`, 60/120/240s por padrão | Máximo 4 tentativas externas; depois `rejected` |
| Timeout, 2xx ambíguo, 408/5xx, erro desconhecido | `delivery_unknown`, `possible_loss` | Não repete; mensagem pode ter sido aceita ou perdida |
| Runner interrompido após reserva esportiva | `delivery_unknown`, `possible_loss` | Pode perder até mensagem que nunca chegou a ser enviada |
| Erro HTTP 4xx definitivo | `rejected` | Via operacional recebe alerta |
| Via operacional indisponível/ambígua | retry durável sem limite total, backoff até 1h | Receiver deve deduplicar `event_id` |
| Interrupção da reserva operacional | retry automático durável | Receiver persistente torna replay seguro |

Essa é uma política **at-most-once de tentativas potencialmente aceitas**, com
risco explícito de perda, não exactly-once. Rejeições 429 podem ser reconsultadas
porque comprovam que a tentativa não foi aceita. Não existe estado que exija
reconciliação humana para permitir as próximas edições/semanas.

## Via operacional e observabilidade

Timeout/rejeição esportiva cria evento operacional durável distinto, incluído
no checkpoint; ele é enviado na mesma execução quando houver orçamento, ou
na próxima execução. Erros de fonte podem usar `plan_operational` diretamente.
A via esportiva nunca é usada como fallback da via operacional. O callback de
C `send_operational_alert(event_id, message)` deve retornar True somente após
o receiver independente persistir e deduplicar a identidade. Esse aceite
significa persistência no receiver; não significa entrega do alerta ao operador.
O encaminhamento externo e watchdog são responsabilidade da entrega C.
Provisionar o receiver independente e seu encaminhamento persistente é uma
dependência de implantação inicial; indisponibilidade externa é reportada,
sem inventar sucesso.

O histórico contém canal, tipo, snapshot/período, timestamps, estado,
contagem de reservas, nonce, provedor, HTTP status, código estável, próxima
tentativa e risco. `delivered_to_device` permanece False. Exceções arbitrárias
são reduzidas a códigos allowlisted; respostas, URLs e detalhes do adapter não
são gravados. Mensagens de produto usam dados do domínio, sem credenciais.

## Spike documental: WhatsApp Business Cloud API

Consulta somente documental em 2026-10-13; não há adapter novo nem ativação.
As páginas primárias atuais em developers.facebook.com retornaram 429/erro
na consulta. Por isso a qualificação de contrato **atual** permanece parcial.
Fontes primárias adicionais acessíveis são o SDK e seu código mantidos por
WhatsApp/Meta, marcados como arquivados:

- [Recebimento e configuração de webhook](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/receivingMessages/): requer URL HTTPS pública, verificação e configuração inicial; recomenda token de usuário de sistema, não temporário.
- [Schema de webhook no repositório da Meta](https://github.com/WhatsApp/WhatsApp-Nodejs-SDK/blob/main/src/types/webhooks.ts): status associa ID da mensagem, destinatário e timestamp ao evento.
- [Enum de status no repositório da Meta](https://github.com/WhatsApp/WhatsApp-Nodejs-SDK/blob/main/src/types/enums.ts): diferencia `sent`, `delivered` e `read`.
- [API de envio de texto](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/text/): retorno é resposta do servidor; não constitui receipt de dispositivo.
- [API de templates](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/template/): descreve envio por template e idioma; permissões e adequação atuais exigem qualificação adicional antes de implantação.

Conclusão técnica: webhook com ID oferece base para acompanhar entrega, desde
que receiver seja autenticado, persistente, idempotente e aceite eventos fora
de ordem. Não foi demonstrado endpoint de idempotência por chave do cliente
para resolver o caso em que o POST foi aceito mas sua resposta com ID se
perdeu. Portanto migrar não autoriza prometer exactly-once. A alternativa
imediata implementada é política automática explícita de possível perda com
alerta independente. Nova conta/permissões, templates e hospedagem webhook
seriam provisionamento inicial isolado, não trabalho manual por edição.

## Validação

`python3 -m unittest tests.ranking_alerts.test_autonomous_delivery -v` cobre
**14 testes passaram**, cobrindo: oito semanas simuladas (8 status, 2 digests de nova edição com
ranks iguais), dedup, reservas antes do checkpoint/envio, checkpoint falho,
crash/recovery, timeout/2xx ambíguo, redaction de erro, 429 com backoff e limite,
backlog (incluindo fronteira segunda-feira 09h BRT), histórico/receipts de revisões, A→B→A, e via operacional retry além
do limite esportivo e recuperação de reserva interrompida.

Regressão adicional: providers, delivery_state, incidents, domain e storage: **80 testes passaram**.
`git diff --check` passou. Testes de frontend,
build e runtime publication-driven pertencem ao integrador.
