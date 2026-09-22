# Luka Ono — Supplementation Reference

**Atleta:** Luka Bojičić Ono
**Domínio:** Nutrição & Saúde — suplementação prescrita
**Versão dos dados:** 2026-08
**Última atualização:** 2026-08-20
**Agente responsável:** Data Engineer
**Status:** Ativo

> Documento de referência bioquímica. **Não é conduta clínica.** Dose, introdução
> e suspensão são decisão do prescritor. Este arquivo existe para preservar o
> racional mecanístico e os pontos de atenção associados ao protocolo em uso.

---

## Notation Key

- **[E]** = Empiricamente estabelecido (peer-reviewed)
- **[I]** = Inferência baseada em evidências
- **[Rx]** = Item da prescrição vigente
- **[C]** = Nota de coach
- **[P]** = Dado pessoal do atleta (auto-relato)

---

## Como ler este documento

Cada item aparece em duas camadas:

1. **Tabela de função** — sumário do que a molécula faz.
2. **Mecanismo de ação** — enzima, química do passo, regulação e a consequência
   fisiológica que decorre do mecanismo.

A segunda camada existe porque quase toda decisão prática do protocolo (forma
do sal, horário da dose, redundância entre itens, plausibilidade de efeito
ergogênico) só se resolve no nível do mecanismo, não no da função.

---

## Prescrição Vigente

**Emitida em:** 2026-08-20
**Prescritor:** Dr. Ronaldo — CRM 44.360, Cardiologia e Clínica Geral
**Instituição:** Instituto Paulista de Medicina Preventiva
**Via:** uso interno

| # | Item | Dose | Posologia |
| :--- | :--- | :--- | :--- |
| 1 | Vitamina E | 400 UI | 1 cp / café |
| 2 | Vitamina C | 1,0 g | 1 cp / café |
| 3 | Magnésio | 500 mg | 1 cp / noite |
| 4 | Vitamina D | 5.000 UI | 1 cp / café |
| 5 | Metilcobalamina | 3 mg | 1 cp / café |
| 6 | Coenzima Q10 | 100 mg | 1 cp / café |
| 7 | Selênio | 150 mcg | 1 cp / café |
| 8 | Arginina | 500 mg | 1 cp / café |
| 9 | Taurina | 500 mg | 1 cp / café |
| 10 | Lisina | 500 mg | 1 cp / café |
| 11 | Sodium ascorbate | 210 mg | 1 cp / café |

---

## Vitaminas propriamente ditas

Quatro dos onze itens são vitaminas no sentido estrito.

| Item | Dose | Função bioquímica central |
| :--- | :--- | :--- |
| **Vitamina E** (α-tocoferol) | 400 UI [Rx] | Antioxidante lipofílico de membrana. Doa hidrogênio ao radical peroxil (LOO•), interrompendo a propagação em cadeia da peroxidação de PUFAs em membranas e LDL. O radical tocoferoxil resultante é regenerado pelo ascorbato — ciclo redox E↔C. [E] |
| **Vitamina C** (ácido ascórbico) | 1,0 g [Rx] | Agente redutor que mantém Fe²⁺/Cu⁺ no sítio ativo de dioxigenases: prolil- e lisil-hidroxilase (maturação do colágeno — tendão, ligamento, matriz óssea); dopamina-β-hidroxilase (noradrenalina); trimetil-lisina e γ-butirobetaína hidroxilases (síntese de carnitina). Regenera vitamina E e reduz ferro não-heme à forma absorvível. [E] |
| **Vitamina D₃** (colecalciferol) | 5.000 UI [Rx] | Pró-hormônio esteroide, não vitamina no sentido estrito. 25-hidroxilação hepática (CYP2R1) → 25(OH)D; 1α-hidroxilação renal (CYP27B1) → calcitriol, ligante do receptor nuclear VDR. Regula absorção intestinal de Ca/P (TRPV6, calbindina), mineralização óssea, expressão gênica em músculo esquelético e imunidade inata (catelicidina). [E] |
| **Metilcobalamina** (B₁₂ ativa) | 3 mg [Rx] | Cofator de exatamente duas reações no humano: metionina sintase (via metil-B₁₂ — ciclo da metionina, SAM, liberação do folate trap) e metilmalonil-CoA mutase (via adenosil-B₁₂ — propionil-CoA → succinil-CoA, anaplerose). [E] |

### Mecanismo de ação

#### 1. Vitamina E — α-tocoferol

**Terminação de cadeia na peroxidação lipídica.** A propagação radicalar em membrana tem três passos: iniciação (L–H + R• → L•), adição de oxigênio (L• + O₂ → LOO•, difusão-limitada) e propagação (LOO• + L–H → LOOH + L•). É o terceiro que se auto-sustenta. [E]

- A **hidroxila em C6 do anel cromanol** doa H• ao radical peroxil: LOO• + α-TOH → LOOH + α-TO•.
- A constante de velocidade dessa doação (~10⁶ M⁻¹s⁻¹) é 10³–10⁴ vezes maior que a da propagação (~10²–10³ M⁻¹s⁻¹) — o tocoferol intercepta o LOO• antes que ele alcance um novo PUFA. Uma molécula termina cerca de duas cadeias.
- O radical tocoferoxil é **estabilizado por ressonância**: o par não ligante do oxigênio do éter, em posição para, sobrepõe-se ao SOMO do anel. Radical pouco reativo, que não propaga. É esse detalhe estereoeletrônico que distingue o α-tocoferol de um fenol qualquer.
- **Geometria:** a cauda fitil ancora na região das cadeias acila e a cabeça cromanol fica na interface glicerol/água — o antioxidante ocupa exatamente o plano em que o LOO• emerge.

**Regeneração.** Ascorbato, na face aquosa da interface, reduz α-TO• → α-TOH + radical ascorbil; ubiquinol (CoQ10H₂) faz o mesmo dentro da bicamada. O radical ascorbil dismuta ou é reduzido por di-hidrolipoato e tiorredoxina redutase. Os itens 1, 2 e 6 da prescrição formam, portanto, um circuito único — não três suplementos independentes. [E]

**Especificidade de isoforma.** A **α-TTP** hepática carrega seletivamente α-tocoferol na VLDL; as formas γ e δ são excretadas. Explica por que apenas a forma α se acumula no plasma. [E]

#### 2. Vitamina C — ascorbato

**Cofator de dioxigenases Fe(II)/2-oxoglutarato.** Núcleo catalítico idêntico em prolil-4-hidroxilase, lisil-hidroxilase, TMLD, BBD, TET e JmjC: [E]

1. Fe(II) coordenado por tríade facial 2-His-1-carboxilato.
2. O₂ liga ao ferro; o 2-oxoglutarato sofre **descarboxilação oxidativa** → succinato + CO₂.
3. Forma-se a espécie **ferril, Fe(IV)=O**, que abstrai hidrogênio de uma ligação C–H não ativada do substrato.
4. *Rebound* do radical hidroxila → substrato hidroxilado; o ferro retorna a Fe(II).

**Onde o ascorbato entra.** Em uma fração dos ciclos a descarboxilação ocorre sem hidroxilar o substrato (ciclo desacoplado), deixando **Fe(III) — enzima inativa**. O ascorbato reduz Fe(III) → Fe(II) e a ressuscita. Ou seja: aqui o ascorbato **não é estequiométrico**, é reagente de resgate, e a demanda é proporcional à taxa de desacoplamento, não à taxa de síntese de colágeno. [E]

**Por que a hidroxiprolina sustenta o colágeno.** O grupo 4R-OH impõe, por efeito gauche estereoeletrônico, o *pucker* Cγ-exo do anel pirrolidina — exatamente a conformação exigida pela hélice tripla, com ganho de cerca de 15 °C na Tm. Sem ela, o pró-colágeno é instável a 37 °C, não é secretado e é degradado no retículo. É o mecanismo do escorbuto. [E]

**Dopamina-β-hidroxilase.** Monoxigenase de cobre; aqui o ascorbato **é estequiométrico**, reduzindo Cu(II) → Cu(I) nos dois sítios a cada turnover, com dois semidesidroascorbato gerados por molécula de noradrenalina. [E]

**Absorção de ferro.** Reduz Fe³⁺ → Fe²⁺ no lúmen duodenal (junto à DCYTB apical), porque o transportador **DMT1 só aceita Fe²⁺**; e quela o ferro, mantendo-o solúvel no pH intestinal ascendente. [E]

#### 3. Vitamina D₃

**Ativação em duas hidroxilações.** [E]

- Fotólise do anel B do 7-desidrocolesterol por UVB (290–315 nm) → pré-vitamina D₃ → isomerização térmica → colecalciferol. A via oral entra direto neste ponto.
- Transporte por **DBP** → fígado, **CYP2R1** → 25(OH)D. Meia-vida de 2 a 3 semanas: é a forma de estoque e a que se dosa.
- Túbulo proximal renal: o complexo DBP-25(OH)D é internalizado por **megalina/cubilina**; **CYP27B1** faz a 1α-hidroxilação → calcitriol.
- **Regulação do passo limitante:** PTH induz CYP27B1; FGF23 a reprime e induz CYP24A1; o próprio calcitriol induz **CYP24A1** (24-hidroxilase), que o degrada. Alça de retroalimentação negativa — por isso dose alta crônica altera a razão 24,25/25 antes de alterar o calcitriol circulante.

**Transcrição gênica.** Calcitriol liga o **VDR** → reposicionamento da hélice 12 (superfície AF-2) → heterodimerização com **RXR** → ligação a **VDREs**, repetições diretas do hexâmero AGGTCA separadas por 3 nucleotídeos (DR3) → recrutamento de coativadores p160/SRC e do complexo Mediador (MED1) → acetilação de histonas → transcrição. [E]

**Homeostase de cálcio — três alvos em série no enterócito:** **TRPV6** (entrada apical a favor do gradiente eletroquímico), **calbindina-D9k** (transporte citosólico tamponado, que mantém o Ca²⁺ livre baixo — sem ela a célula sinalizaria continuamente) e **PMCA1b** (extrusão basolateral contra gradiente, com gasto de ATP). No osso, induz **RANKL** no osteoblasto → osteoclastogênese → mobilização de cálcio. No monócito, induz **CAMP** (catelicidina) por um VDRE específico de primatas. [E]

#### 4. Metilcobalamina — B₁₂

**Metionina sintase — química iônica (SN2).** [E]

- A **cob(I)alamina** é um dos nucleófilos mais fortes conhecidos em biologia. Ataca o metil do N5-metil-THF → metilcob(III)alamina + THF.
- A metilcobalamina transfere então CH₃⁺ ao tiolato da homocisteína (segundo SN2) → metionina + cob(I)alamina regenerada. Mecanismo ping-pong.
- A cada cerca de 2.000 turnovers a cob(I) oxida a cob(II) e a enzima inativa; o resgate é a **metilação redutiva pela MTRR**, com SAM como doador.

**Consequência sistêmica — armadilha do metil-folato.** A reação da MTHFR (5,10-CH₂-THF → 5-CH₃-THF) é fisiologicamente irreversível, e a **única** saída do 5-metil-THF é a metionina sintase. Sem B₁₂ funcional, o folato celular fica sequestrado nessa forma, e timidilato sintase e síntese de purinas ficam sem THF — anemia megaloblástica por deficiência *funcional* de folato, com folato sérico normal ou elevado. [E]

**Metilmalonil-CoA mutase — química radicalar.** [E]

- A **adenosilcobalamina** sofre **homólise da ligação Co–C5'** → radical 5'-desoxiadenosil + cob(II)alamina. A enzima acelera essa homólise em cerca de 10¹² vezes em relação à solução.
- O radical abstrai H do metilmalonil-CoA → radical do substrato → **rearranjo 1,2 do esqueleto de carbono** (migração do grupo tioéster) → radical do succinil-CoA → reabstrai H da 5'-desoxiadenosina → produto e radical regenerado.
- Balanço redox nulo: o cobalto atua como gerador reversível de radical, não como carreador de elétrons.
- Via completa: propionil-CoA (de Val, Ile, Met, Thr, ácidos graxos de cadeia ímpar e cadeia lateral do colesterol) → **propionil-CoA carboxilase** (biotina, ATP) → D-metilmalonil-CoA → epimerase → L → mutase → succinil-CoA → anaplerose no ciclo de Krebs.
- Bloqueio → acúmulo de **ácido metilmalônico** (marcador mais sensível que a B₁₂ sérica) e incorporação de ácidos graxos de cadeia ímpar aberrantes na mielina — mecanismo da neuropatia.

**Sobre a forma e a dose.** Qualquer cobalamina ingerida é desalquilada no citosol pela **CblC/MMACHC** a cob(II)alamina e re-derivatizada conforme o destino; a forma "metil" não chega intacta às duas enzimas — a vantagem sobre a cianocobalamina é a ausência do cianeto liberado, não entrega direta. Em 3 mg por via oral, a absorção se dá predominantemente por **difusão passiva (~1% da dose)**, contornando a saturação do fator intrínseco (~1,5–2 µg por dose). [E]

---

## Demais itens (minerais, cofatores, aminoácidos)

| Item | Dose | Função bioquímica central |
| :--- | :--- | :--- |
| **Magnésio** | 500 mg, noite [Rx] | O substrato real de toda ATPase é **Mg-ATP**, não ATP livre. Cofator de mais de 300 enzimas, incluindo **SERCA** (recaptação de Ca²⁺ no retículo sarcoplasmático — fase de relaxamento muscular). Antagonista fisiológico do Ca²⁺ no acoplamento excitação-contração e em canais NMDA. [E] |
| **Coenzima Q10** (ubiquinona) | 100 mg [Rx] | Carreador lipofílico móvel da membrana mitocondrial interna. Recebe elétrons dos complexos I e II, da ETF-QO (β-oxidação) e da glicerol-3-fosfato desidrogenase, entregando-os ao complexo III. Obrigatória para fosforilação oxidativa; na forma ubiquinol é antioxidante de membrana e regenera tocoferol. [E] |
| **Selênio** | 150 mcg [Rx] | Incorporado como **selenocisteína** em cerca de 25 selenoproteínas: glutationa peroxidases (GPx1–4), tiorredoxina redutases e iodotironina deiodinases (conversão T4→T3). [E] |
| **Arginina** | 500 mg [Rx] | Substrato da NO-sintase → óxido nítrico + citrulina (vasodilatação, perfusão muscular). Precursor de creatina (AGAT), de ornitina no ciclo da ureia e de poliaminas. [E] |
| **Taurina** | 500 mg [Rx] | Aminossulfônico não proteinogênico. Conjuga ácidos biliares; osmólito intracelular; modula o manejo de Ca²⁺ no retículo sarcoplasmático e a sensibilidade miofibrilar; forma a modificação 5-taurinometil-uridina em tRNAs mitocondriais. [E] |
| **Lisina** | 500 mg [Rx] | Aminoácido essencial. Substrato de lisil-hidroxilase e **lisil-oxidase**, que geram os *crosslinks* covalentes do colágeno. Precursora de **carnitina**, sem a qual não há β-oxidação de ácidos graxos de cadeia longa. [E] |
| **Sodium ascorbate** | 210 mg [Rx] | Sal sódico do ascorbato: bioquimicamente idêntico à vitamina C, tamponado a pH neutro. Aporta cerca de 24 mg de sódio. [E] |

### Mecanismo de ação

#### 5. Magnésio

**Substrato real das ATPases.** Mg²⁺ quela os fosfatos β e γ do ATP, com efeito duplo: neutraliza carga, reduzindo a repulsão eletrostática no ataque nucleofílico ao γ-fosfato, e **pré-organiza a geometria bipiramidal do estado de transição**. O substrato cineticamente competente é **MgATP²⁻**; ATP⁴⁻ livre é inibidor de várias quinases. [E]

**Relaxamento muscular (SERCA).** A SERCA hidrolisa MgATP formando um **intermediário aspartil-fosfato (E1P)**; a transição conformacional E1P → E2P inverte a afinidade dos sítios de Ca²⁺ e libera 2 Ca²⁺ no lúmen do retículo. A velocidade de relaxamento é o fluxo da SERCA, e ele depende de magnésio tanto como substrato quanto no sítio catalítico. [E]

**Modulação da excitabilidade.** [E]

- **Pré-sináptica:** Mg²⁺ compete com Ca²⁺ no canal de cálcio voltagem-dependente tipo P/Q do terminal motor → reduz o conteúdo quântico de acetilcolina liberado.
- **NMDA:** Mg²⁺ ocupa o poro do canal e é expelido por despolarização — **bloqueio voltagem-dependente**, pois o íon liga dentro do campo elétrico da membrana. Define o limiar de coincidência no SNC; somado à modulação positiva de GABA-A, é o mecanismo do efeito sobre latência de sono e o racional da dose noturna.

**Por que a forma importa.** A absorção ocorre por via paracelular (claudina-2/12, não saturável, dependente da concentração luminal) e transcelular por **TRPM6/TRPM7** (saturável). O óxido é praticamente insolúvel no pH intestinal — permanece luminal e gera carga osmótica em vez de absorção. Citrato e glicinato chegam solúveis ou quelados à mucosa. [E]

#### 6. Coenzima Q10

**Coletor convergente da cadeia respiratória.** A química ocorre em **dois passos monoeletrônicos**: Q → semiquinona (Q•⁻) → QH₂. É a capacidade de estacionar no estado semiquinona que permite acoplar doadores de dois elétrons a aceptores de um elétron. [E]

| Doador | Mecanismo |
| :--- | :--- |
| Complexo I | NADH → FMN → cadeia de 7–8 clusters Fe-S → Q em canal longo; a redução de Q é mecanicamente acoplada ao bombeamento conformacional de 4 H⁺ |
| Complexo II | Succinato → FAD → Fe-S → Q; sem bombeamento |
| **ETF-QO** | Elétrons das acil-CoA desidrogenases da β-oxidação, via ETF |
| mGPDH | Glicerol-3-fosfato (lançadeira do glicerofosfato) |

**Ciclo Q no complexo III.** QH₂ é oxidado no **sítio Qo** com **bifurcação de elétrons**: um elétron segue ao centro Rieske Fe-S → cit c1 → cit c (rota de alto potencial); o outro vai a cit b_L → b_H e reduz uma Q no **sítio Qi**, formando semiquinona estável, que no segundo turnover é reduzida a QH₂. Saldo: 2 QH₂ consumidos, 1 regenerado, **4 H⁺ liberados no espaço intermembranas** — é esse ciclo que dobra o rendimento de prótons do segmento. [E]

**Antioxidante e regenerador.** QH₂ doa H• ao LOO• pela mesma química do cromanol e regenera α-TO• dentro da membrana, fechando o circuito do item 1. [E]

**Farmacocinética como consequência da estrutura.** Massa 863 Da e log P muito alto → absorção linfática via quilomícrons, dependente de gordura na refeição. A síntese endógena parte da via do mevalonato — daí a interação com estatinas, que inibem a HMG-CoA redutase a montante do precursor isoprenoide da cauda. [E]

#### 7. Selênio

**Incorporação como selenocisteína — recodificação do UGA.** Não existe tRNA pré-carregado com Sec: [E]

1. Ser-tRNA[Ser]Sec é fosforilado pela **PSTK**.
2. **SepSecS** substitui o fosfato por selênio doado pelo **selenofosfato (SPS2)**.
3. Na tradução, o códon **UGA** — normalmente stop — é lido como Sec **apenas** se houver um elemento **SECIS** na 3'UTR do mRNA, ligado por **SBP2**, que recruta o fator de elongação dedicado **eEFSec**.

**Por que selênio e não enxofre.** O pKa do selenol é ~5,2 contra ~8,3 do tiol: no pH fisiológico o selênio está **ionizado (selenolato)** e o enxofre não. Nucleófilo muito superior, com ganho catalítico de 10²–10³. Toda a vantagem das selenoproteínas reduz-se a esse parâmetro. [E]

**Glutationa peroxidases — ciclo catalítico.** [E]

1. Selenolato ataca o peróxido → **ácido selenênico (Se-OH)** + água ou álcool.
2. Primeira GSH ataca → adutor **selenil-sulfeto (Se-SG)**.
3. Segunda GSH desloca → **GSSG** + selenolato regenerado.
4. GSSG é reciclado pela glutationa redutase às custas de NADPH (via pentose-fosfato).

**GPx4** é a única que reduz hidroperóxidos de fosfolipídio *in situ*, dentro da membrana — a enzima que impede ferroptose e a parceira mecanística direta da vitamina E.

**Tiorredoxina redutase.** FAD e NADPH reduzem o motivo C-terminal Gly-Cys-**Sec**-Gly, que reduz a tiorredoxina, que alimenta ribonucleotídeo redutase (síntese de dNTP), peroxirredoxinas e fatores de transcrição redox-regulados. [E]

**Deiodinases.** Desiodação **redutiva**: o selenolato ataca diretamente o iodo. D1 e D2 removem o iodo 5' do anel externo (T4 → T3, ativação); D3 remove o 5 do anel interno (T4 → rT3, inativação). O balanço D2/D3 tecidual define a exposição local a T3 independentemente do TSH. [E]

**Mecanismo da toxicidade.** Seleneto em excesso reage com tióis proteicos formando adutos Se-S e faz ciclagem redox com O₂ gerando superóxido — origem da janela terapêutica estreita. [E]

#### 8. Arginina

**Substrato da NO-sintase.** [E]

- A NOS funciona como **homodímero obrigatório**: domínio redutase (FAD, FMN, NADPH, sítio de calmodulina) e domínio oxigenase (heme, BH4, arginina). Os elétrons fluem NADPH → FAD → FMN e cruzam **em trans** para o heme do outro monômero; monômero isolado não produz NO.
- Duas monoxigenações sucessivas: Arg → N-hidroxi-arginina (2e⁻, 1 O₂); depois NOHA → citrulina + **NO** (oxidação incomum de 3 elétrons).
- **BH4 não age aqui como antioxidante:** doa rapidamente um elétron ao complexo ferroso-oxi e é re-reduzido. Se BH4 é limitante, a NOS **desacopla** e passa a produzir superóxido em vez de NO, invertendo o efeito vascular. É o mecanismo central da disfunção endotelial.

**Transdução do sinal.** NO difunde à célula muscular lisa → liga o **ferro do heme da guanilato ciclase solúvel** → rompe a ligação Fe–His proximal → ativação de cerca de 200 vezes → cGMP → **PKG** → fosforila a MYPT1 (subunidade reguladora da fosfatase da cadeia leve de miosina) e reduz Ca²⁺ via IRAG/IP₃R → desfosforilação da cadeia leve → relaxamento. [E]

**Creatina e ciclo da ureia.** **AGAT** transfere o grupo amidino da arginina para a glicina → guanidinoacetato + ornitina; **GAMT** metila com SAM → creatina. A ornitina alimenta o ciclo da ureia (eliminação da amônia gerada na desaminação de AMP no exercício intenso) e, via ODC, as poliaminas. [E]

**Por que 500 mg orais fazem pouco — dois mecanismos.** [E/I]

1. **Extração de primeira passagem:** arginase I no enterócito e no hepatócito hidrolisa a arginina a ornitina e ureia antes da circulação sistêmica. A citrulina escapa da arginase e é reconvertida no rim (ASS/ASL) — por isso é a via eficiente.
2. **Paradoxo da arginina:** a concentração intracelular (0,1–1 mM) excede em muito o Km da eNOS (~3 µM). O argumento mecanístico a favor da suplementação não é escassez de substrato, mas o acoplamento compartimentalizado transportador CAT-1/eNOS na cavéola e o alívio da inibição competitiva pela **ADMA**.

#### 9. Taurina

**Por que é semi-essencial.** Cisteína → **CDO** → sulfinato de cisteína → **CSAD** (passo limitante, de expressão baixa em humanos) → hipotaurina → taurina. A capacidade sintética humana é limitada, daí a dependência parcial da dieta. [E]

**Conjugação de ácidos biliares.** **BACS** ativa o ácido biliar a cholil-CoA; **BAAT** conjuga o grupo amino da taurina → taurocolato. O ganho vem do pKa: o **sulfonato (~1,5)** é muito mais ácido que o carboxilato da glicina (~3,9), de modo que o conjugado permanece totalmente ionizado no pH duodenal — melhor formação de micela e menor reabsorção passiva jejunal. [E]

**Osmólito.** Transportada por **TauT (SLC6A6)** em cotransporte 2Na⁺:1Cl⁻:1 taurina; o gradiente de sódio permite concentrá-la 100 a 1.000 vezes no citosol. Sob hipertonicidade, **TonEBP/NFAT5** induz o TauT. Sendo zwitteríon quimicamente inerte, acumula-se em concentração alta sem perturbar enzimas — que é exatamente o requisito de um osmólito compatível. [E]

**Manejo de Ca²⁺ contrátil.** Modula RyR1 e SERCA e desloca a curva pCa-força para a esquerda, aumentando a sensibilidade miofibrilar ao Ca²⁺. O mecanismo proposto passa pela interação com cabeças polares de fosfatidiletanolamina, alterando a carga local de superfície do retículo sarcoplasmático. [E/I]

**Tradução mitocondrial.** **MTO1/GTPBP3** e **TRMU** conjugam taurina à uridina na posição wobble U34 de mt-tRNAs → **5-taurinometil-uridina (τm⁵U)**. Sem essa modificação o pareamento códon-anticódon no wobble falha e a leitura de códons UUG fica deficiente — mecanismo molecular do MELAS. A subunidade ND6 (complexo I) é a mais afetada, com deficiência de complexo I e vazamento de ROS. [E]

**Antioxidante indireto.** A mieloperoxidase do neutrófilo produz HOCl; a taurina o captura formando **taurina-cloramina**, oxidante muito menos reativo, que ainda inibe a via NF-κB. Não é sequestro de radical — é conversão de um oxidante forte em um fraco. [E]

#### 10. Lisina

**Crosslinks de colágeno — dois passos enzimáticos e um espontâneo.** [E]

1. **Lisil-hidroxilase (PLOD1-3)** — dioxigenase Fe/2-OG, mesmo mecanismo ferril do item 2 e mesma dependência de ascorbato para resgate → 5-hidroxilisina, que é também sítio de glicosilação.
2. **Lisil-oxidase (LOX)** — amina oxidase de cobre com cofator **LTQ (lisina-tirosilquinona)**, gerado por automodificação. Faz **desaminação oxidativa do ε-amino** → **alisina** (aldeído) + NH₃ + H₂O₂.
3. **Espontâneo:** a alisina condensa por aldol com outra alisina, ou forma base de Schiff com um ε-amino não modificado → crosslinks imaturos (desidro-HLNL) → maturação a **piridinolina/desoxipiridinolina** trivalentes. É esse passo que converte fibrila em tecido com resistência tênsil.

Prova do mecanismo: o β-aminopropionitrila inibe a LOX e produz latirismo — tecido conjuntivo frágil com colágeno de sequência normal.

**Precursora de carnitina — e a ressalva.** Via: lisina **já incorporada em proteína** é trimetilada por metiltransferases (SAM); a proteólise libera trimetil-lisina → **TMLD** (Fe/2-OG, mitocondrial) → 3-hidroxi-TML → aldolase → 4-trimetilaminobutiraldeído → desidrogenase → γ-butirobetaína → **BBD** (Fe/2-OG, hepática e renal) → carnitina. [E]

Ressalva: a via **parte de lisina metilada ligada a proteína**, não de lisina livre da dieta; além disso o músculo esquelético não expressa BBD e importa carnitina pronta via **OCTN2**. O elo "lisina suplementar → mais carnitina" é, portanto, fraco; o elo forte da lisina é o colágeno. [E/I]

**Lançadeira da carnitina.** **CPT1**, na membrana externa, transfere o acil do acil-CoA para a carnitina → acilcarnitina; **CACT** faz antiporte acilcarnitina-entra/carnitina-sai na membrana interna; **CPT2**, na face matricial, reverte a acilcarnitina a acil-CoA. Acil-CoA de cadeia longa não atravessa a membrana interna por outra via. **CPT1 é inibida por malonil-CoA**, o que acopla reciprocamente lipogênese e β-oxidação. [E]

**Sítio de modificação pós-traducional.** O ε-amino é alvo de acetilação (p300/HATs, removida por HDACs e por sirtuínas dependentes de NAD⁺ — ligação com o estado energético), metilação (KMTs, doador SAM — ligação com o item 4), ubiquitinação e succinilação. [E]

#### 11. Sodium ascorbate

Mecanismo bioquímico idêntico ao item 2 — o sal dissocia no estômago e a espécie ativa é o mesmo ânion ascorbato.

O que muda é o **transporte**: absorção pelos cotransportadores **SVCT1/SVCT2**, Na⁺-dependentes (2Na⁺:1 ascorbato) e **saturáveis**. A fração absorvida cai de cerca de 80% em 200 mg para cerca de 50% em 1 g; acima de ~1,25 g o plasma satura em torno de 80 µmol/L e o excedente é excretado. Mecanicamente, portanto, **fracionar a dose importa mais do que escolher o sal** — e a dose total da prescrição (~1,19 g em uma tomada) está na faixa de saturação. [E]

---

## Pontos Críticos

### Crítico — antioxidante em dose alta × sinalização de adaptação

ROS geradas no exercício não são apenas dano: são sinal. Ativam AMPK e p38-MAPK → PGC-1α → biogênese mitocondrial e up-regulation das enzimas antioxidantes endógenas (SOD, GPx). Suplementação antioxidante alta e crônica tampona esse sinal.

| Estudo | Protocolo | Achado |
| :--- | :--- | :--- |
| Ristow et al., *PNAS* (2009) | C 1 g + E 400 UI, 4 sem | Bloqueio do aumento de PGC-1α/PPARγ e da melhora de sensibilidade à insulina induzidos pelo treino [E] |
| Paulsen et al., *J Physiol* (2014) | C 1 g + E 235 mg, 11 sem endurance | Atenuação do aumento de COX4 e citrato sintase (marcadores de conteúdo mitocondrial); VO₂máx sem diferença entre grupos [E] |
| Morrison et al., *Free Radic Biol Med* (2015) | C 1 g + E 400 UI, 4 sem HIIT | Supressão da resposta de PGC-1α e de proteínas mitocondriais [E] |

**Mecanismo da interferência** — a cadeia que a suplementação intercepta: [E/I]

1. A contração gera H₂O₂ e superóxido em NOX2 (sarcolema e túbulo T), NOX4 (retículo) e sítios mitocondriais.
2. H₂O₂ oxida **cisteínas catalíticas a ácido sulfênico (–SOH)** em fosfatases — PTP1B, PTEN, MKPs. Fosfatase reversivelmente inibida significa sinal de quinase **sustentado** (p38-MAPK, ERK). O transdutor não é dano: é uma modificação pós-traducional reversível.
3. p38 fosforila e ativa **PGC-1α**; a SIRT1 o desacetila (dependente de NAD⁺, que sobe com o exercício); a AMPK, ativada pela razão AMP/ATP, converge no mesmo alvo.
4. PGC-1α coativa **NRF-1/NRF-2** → **TFAM** → replicação e transcrição do mtDNA, e coativa a expressão das próprias defesas endógenas (SOD2, GPx).
5. Ascorbato e tocoferol em dose alta, somados a GPx e peroxirredoxinas, elevam a taxa de remoção de H₂O₂ e **encurtam a meia-vida do sinal de sulfenilação** no passo 2. A adaptação a jusante cai proporcionalmente.

O efeito é robusto sobre marcadores moleculares (PGC-1α, COX4, citrato sintase) e inconsistente sobre desempenho — porque desempenho tem determinantes múltiplos além do conteúdo mitocondrial.

A prescrição entrega ~1,19 g/dia de ascorbato-equivalente (Vitamina C 1,0 g + sodium ascorbate 210 mg) somados a E 400 UI — sobreposição direta com os protocolos acima. Mitigação usual: afastar a tomada da janela pós-treino (a posologia já a coloca no café, o que é favorável se a sessão for vespertina) ou suspender em blocos de base aeróbica. [E/I]

### Atenção — redundância de princípio ativo

Vitamina C 1,0 g e sodium ascorbate 210 mg são o mesmo princípio ativo em sais diferentes. Total ≈ 1,19 g/dia de ascorbato-equivalente, acima da faixa de saturação dos SVCT em dose única. [E]

### Atenção — doses abaixo da faixa ergogênica

Arginina 500 mg está muito abaixo das doses de literatura (6–8 g), e a arginina oral sofre extração de primeira passagem por arginase intestinal e hepática — citrulina é a via eficiente para elevar arginina plasmática. Taurina ergogênica costuma ser 1–3 g. Nessas doses, os três aminoácidos funcionam como aporte nutricional, não como intervenção de performance. [E/I]

### Atenção — monitoramento laboratorial

- **Vitamina D 5.000 UI/dia** é dose de repleção, não de manutenção universal. Exige 25(OH)D sérica, cálcio e PTH em série. [E]
- **Selênio** tem janela terapêutica estreita: teto tolerável ~400 mcg/dia somando dieta e suplemento. [E]

### Atenção — conformidade antidoping

Luka compete no circuito ITF, sujeito ao Tennis Anti-Doping Programme (WADA). Fórmula manipulada não possui certificação de lote (Informed Sport, NSF Certified for Sport), e contaminação cruzada é a causa mais frequente de resultado analítico adverso atribuído a suplemento. Verificar cada item antes do uso em temporada. [E/C]

### Regra operacional já vigente

`nutrition.md` — nunca introduzir alimento ou suplemento novo em dia de torneio. Todo item deve ser testado em sessões de alta intensidade antes. [C/E]

---

## Changelog

| Data | Versão | Agente | Descrição da alteração |
|---|---|---|---|
| 2026-08-20 | 1.1.0 | Data Engineer | Camada "Mecanismo de ação" adicionada para os 11 itens (química do passo catalítico, regulação, consequência fisiológica); mecanismo da interferência redox detalhado no ponto crítico; fontes mecanísticas acrescentadas |
| 2026-08-20 | 1.0.0 | Data Engineer | Criação inicial — prescrição de 2026-08-20 registrada; função bioquímica por item; pontos críticos (sinalização redox, redundância de ascorbato, doses subterapêuticas, monitoramento, antidoping) |

---

## Fontes

### Estudos citados nos pontos críticos

- Ristow, M. et al. (2009). Antioxidants prevent health-promoting effects of physical exercise in humans. *PNAS*, 106(21), 8665–8670.
- Paulsen, G. et al. (2014). Vitamin C and E supplementation hampers cellular adaptation to endurance training in humans. *The Journal of Physiology*, 592(8), 1887–1901.
- Morrison, D. et al. (2015). Vitamin C and E supplementation prevents some of the cellular adaptations to endurance-training in humans. *Free Radical Biology and Medicine*, 89, 852–862.

### Referências mecanísticas

- Traber, M. G. & Atkinson, J. (2007). Vitamin E, antioxidant and nothing more. *Free Radical Biology and Medicine*, 43(1), 4–15.
- Myllyharju, J. (2003). Prolyl 4-hydroxylases, the key enzymes of collagen biosynthesis. *Matrix Biology*, 22(1), 15–24.
- Shoulders, M. D. & Raines, R. T. (2009). Collagen structure and stability. *Annual Review of Biochemistry*, 78, 929–958.
- Levine, M. et al. (1996). Vitamin C pharmacokinetics in healthy volunteers. *PNAS*, 93(8), 3704–3709.
- Haussler, M. R. et al. (2011). Vitamin D receptor: molecular signaling and actions of nutritional ligands. *Journal of Bone and Mineral Research*, 26(7), 1447–1461.
- Banerjee, R. & Ragsdale, S. W. (2003). The many faces of vitamin B12: catalysis by cobalamin-dependent enzymes. *Annual Review of Biochemistry*, 72, 209–247.
- Toraya, T. (2003). Radical catalysis in coenzyme B12-dependent isomerization. *Chemical Reviews*, 103(6), 2095–2127.
- de Baaij, J. H. F., Hoenderop, J. G. J. & Bindels, R. J. M. (2015). Magnesium in man: implications for health and disease. *Physiological Reviews*, 95(1), 1–46.
- Toyoshima, C. (2009). How Ca²⁺-ATPase pumps ions across the sarcoplasmic reticulum membrane. *Biochimica et Biophysica Acta*, 1793(6), 941–946.
- Crofts, A. R. (2004). The cytochrome bc1 complex: function in the context of structure. *Annual Review of Physiology*, 66, 689–733.
- Bentinger, M., Tekle, M. & Dallner, G. (2010). Coenzyme Q — biosynthesis and functions. *Biochemical and Biophysical Research Communications*, 396(1), 74–79.
- Labunskyy, V. M., Hatfield, D. L. & Gladyshev, V. N. (2014). Selenoproteins: molecular pathways and physiological roles. *Physiological Reviews*, 94(3), 739–777.
- Stuehr, D. J., Santolini, J., Wang, Z.-Q., Wei, C.-C. & Adak, S. (2004). Update on mechanism and catalytic regulation in the NO synthases. *Journal of Biological Chemistry*, 279(35), 36167–36170.
- Schaffer, S. & Kim, H. W. (2018). Effects and mechanisms of taurine as a therapeutic agent. *Biomolecules & Therapeutics*, 26(3), 225–241.
- Suzuki, T., Nagao, A. & Suzuki, T. (2011). Human mitochondrial tRNAs: biogenesis, function, structural aspects, and diseases. *Annual Review of Genetics*, 45, 299–329.
- Lucero, H. A. & Kagan, H. M. (2006). Lysyl oxidase: an oxidative enzyme and effector of cell function. *Cellular and Molecular Life Sciences*, 63(19–20), 2304–2316.
- Longo, N., Frigeni, M. & Pasquali, M. (2016). Carnitine transport and fatty acid oxidation. *Biochimica et Biophysica Acta*, 1863(10), 2422–2435.
- Jackson, M. J. (2016). Redox regulation of muscle adaptations to contractile activity and aging. *Journal of Applied Physiology*, 121(3), 730–737.

### Referências gerais

- Institute of Medicine (2000). *Dietary Reference Intakes for Vitamin C, Vitamin E, Selenium, and Carotenoids*. National Academies Press.
- Holick, M. F. (2007). Vitamin D deficiency. *New England Journal of Medicine*, 357(3), 266–281.
- Green, R. et al. (2017). Vitamin B12 deficiency. *Nature Reviews Disease Primers*, 3, 17040.
- Maughan, R. J. et al. (2018). IOC consensus statement: dietary supplements and the high-performance athlete. *British Journal of Sports Medicine*, 52(7), 439–455.
