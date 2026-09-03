<!-- BEGIN ono-rules (managed by references/sync-claude-rules.py) -->
# Regras portáveis — ono

Bloco canônico replicado nos repos para que sessões cloud/web (que não
carregam `~/.claude/CLAUDE.md` nem executam hooks locais) operem sob as
mesmas regras. Origem: `~/.claude/references/portable-rules.md`
(repo `hmono/claude-config`). Não editar as cópias nos repos — editar aqui
e rodar `references/sync-claude-rules.py`.

## Comunicação
- Respostas em pt-BR; código, commits e identificadores em inglês.
- Tom formal e crítico; preferir schemas, tabelas e bullets a prosa longa.
- NUNCA usar emoji, nem como marcador de severidade. Usar rótulos textuais
  (Crítico, Atenção, Resolvido).
- Economia de tokens: sem preâmbulos, sem repetir contexto, não reler
  arquivos já lidos na sessão, não explorar especulativamente.

## Fluxo de trabalho (obrigatório)
1. Discutir antes de executar — inclusive diagnóstico (ls, cat, queries).
   Nenhum comando sem aprovação explícita na conversa ("ok", "aprovado", "pode").
2. Aprovação vale apenas para o escopo discutido; escopo novo → aprovação nova.
3. Ações destrutivas (rm, DROP, force-push, restart de serviço): listar
   impacto antes, mesmo com aprovação genérica prévia.
4. Autonomia fable: com `~/.claude/fable-autonomy` presente e a sessão em
   modelo do tier fable/mythos, o fable analisa o risco, registra a análise
   na conversa e executa sem aguardar aprovação (regras 1–2 suspensas).
   A regra 3 (destrutivos) permanece integral. Em ambiente sem os hooks
   locais o toggle não é verificável; vale a regra padrão (aprovação
   explícita).

## Higiene de sessão (custo)
- Uma sessão = um tema e, em regra, um dia. Não retomar sessão de dias
  anteriores para trabalho novo: abrir sessão nova.
- ~88% do consumo de tokens é reenvio de contexto, não geração. Sessão
  multi-dia paga o histórico inteiro a cada turno e recria o cache a cada
  retomada.
- Ao encerrar um tema, persistir o estado em `.md` no repo (decisões,
  pendências, caminhos, próximos passos). Retomar lendo esse `.md`.
- Ao mudar de tema ou ao passar de ~metade da janela de contexto, propor
  o corte da sessão antes de continuar.

## Alocação de modelos (obrigatória em todo spawn de subagent)
| Camada             | Modelo             | Escopo                                                       |
|--------------------|--------------------|--------------------------------------------------------------|
| Orquestração       | fable (sessão)     | Discussão, arquitetura, decisão, revisão crítica final        |
| Criação e spec     | opus               | Artefatos criativos/finais, redação de specs, revisão         |
| Execução analítica | sonnet             | Executa spec: pesquisa, leitura com síntese, escrita técnica  |
| Execução mecânica  | haiku (effort low) | Executa spec: varredura, extração, conversões, sem julgamento |

- Cadeia (canônica): fable decide → opus redige a spec → fable faz o
  fan-out de sonnet/haiku com a spec → opus revisa as entregas → fable dá
  o veredito final. Subagents não dispõem da ferramenta Agent (sem
  nesting); o fan-out é sempre do orquestrador.
- fable nunca roda em subagent. Todo spawn declara `model` explicitamente.
  Em ambiente sem os hooks locais, esta regra é responsabilidade do modelo.
- O modelo da sessão é escolhido no cliente e pode divergir do default.
  Antes de orquestrar, confirmar que a sessão está no modelo pretendido.

## Git
- Toda entrega aprovada: commit + push, sem exceção. Confirmar no turno
  antes de pushar.
- Mensagens de commit em inglês, modo imperativo, uma linha de resumo.
- Commitar apenas arquivos que a própria sessão alterou. Working tree
  sujo com mudanças de terceiros (outra sessão concorrente): reportar ao
  usuário e excluir do commit — nunca `git add -A` nem commitar paths
  alheios.

## Segredos
- Nunca imprimir credenciais, tokens ou connection strings em output,
  logs ou commits.
<!-- END ono-rules -->
