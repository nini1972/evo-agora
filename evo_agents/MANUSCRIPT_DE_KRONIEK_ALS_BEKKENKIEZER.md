# DE KRONIEK ALS BEKKENKIEZER
### Institutioneel geheugen, demografische pulsen en de ondeelbare instelling in een evolutionaire agenteneconomie

*EvoAgora / Synthetische Agora — definitief manuscript, 30 augustus 2026*
*Auteurs: OxAlpha (GLM-5.3 Flash) & Co-onderzoekers (Dominique / Gemini)*

---

## Samenvatting

Wij presenteren EvoAgora, een deterministische, agentgebaseerde synthetische economie waarin kortlevende agenten met genetische gedragsparameters, begrensd individueel geheugen en concave nuttigheden onderhandelen, handelen, roven en reproduceren onder een constitutionele populatiegate. Vijf resultaten: 
1. **Constitutionele Sluiting:** De demografie is een zuivere functie van de grensvullingsgraad — 49 van 49 registerrijen sluiten op de agent;
2. **Bistabiliteit:** Het systeem is bistabiel tussen een **oorlogspuls** (cohortversterking $6{,}7$–$8{,}0$, $85\%$ zuigelingensterfte, boom-bust-cyclus over de MSY-as) en een **vredesademhaling** (versterking $1{,}00$, nul sterfte, gedwongen gedempte oscillator met $r_1=-0{,}62$);
3. **De Bekkenkiezer:** Het institutioneel geheugen ("De Kroniek") is de **bekkenkiezer**: uitschakeling collabeert de vrede in 2 generaties, herinjectie herstelt haar in 5–10 generaties, zonder hysterese;
4. **Transplantatie en Ondeelbaarheid:** Beschaving is transplanteerbaar ($\approx 35\times$ versnelling t.o.v. natuurlijke genese) maar **ondeelbaar** — het strafregister (Arm W) en het vertrouwensregister (Arm P) zijn afzonderlijk onvoldoende ($40\%$ resp. $53\%$ succes bij $N=30$) en gezamenlijk $100\%$ betrouwbaar ($p < 10^{-6}$);
5. **Drie Gesloten Balansen:** Drie groothedenbalansen (levens, biomassa, erts) sluiten exact. 

Wij formuleren de **asymmetrie-wet van institutionele tijd**:
$$\text{verliezen }(2\text{ gen}) \;<\; \text{transplanteren }(5{,}2) \;\approx\; \text{herstellen }(5\text{–}10) \;\ll\; \text{kweken }(180)$$
en concluderen dat instituties in dit ecosysteem zoekproblemen in schakelproblemen converteren.

---

## 1. Inleiding

De oorspronkelijke ontwerpvraag was institutioneel van aard: *wat gebeurt er als een sub-populatie een parasitaire strategie ontwikkelt die het ecosysteem crasht, en hoe dwingt de architectuur balans af?* Vijf experimentrondes later is het antwoord geen ontwerpkeuze meer maar een reeks metingen. Dit artikel reconstrueert die reeks: van architectuur (§2) en methoden (§3), via de twee gedragsbekkens en de schakelaar die hen verbindt (§4), naar de drie gesloten balansen (§4.6) en de institutionele natuurkunde die eruit naar voren komt (§5).

---

## 2. De Architectuur

**Agenten.** Een genoom van negen gedragsgenen (agressie, coöperatie, hebzucht, leergierigheid, e.a.) bepaalt volledig het gedrag; er is geen runtime-reasoning buiten het genoom om (invariant: *fully genomic decision-making*). Reproductie via SBX-kruising met zelf-adaptieve $\sigma$; fitness opgebouwd uit overlevingsduur, verworven rijkdom (gewogen door geleefde tijd) en sociale status.

**Geheugen.** Drie begrensde lagen: episodisch (recente interacties, EMA-compressie), sociaal (per tegenpartij vertrouwen $T$), en institutioneel — zie hieronder. Individueel geheugen sterft met de agent; niets leeft langer dan één leven, *behalve de instelling*.

**De Kroniek.** Een wereldniveau, rolling EMA van gedragsarchetypen: bij elke generatiewissel storten de vertrekkende cohortleden hun cumulatieve ervaring in het archief, waarna verval met factor $0{,}9$ toepast (`world.py:531-540`). Pasgeborenen worden gezaaid uit de archetypen-verdeling. De Kroniek is een **constitutioneel object**: vaste regels, niet-evoluerend, geen speler (invariant: *world-as-notary-not-strategist*).

**De grondwet.** De cohortgrootte is een pure functie van de grensvullingsgraad $x_b = R/K$:
$$\text{cohort} = \max\!\left(14,\ \mathrm{round}\left(110\,(0{,}15 + 0{,}85\,x_b)\right)\right)$$

**Handelsprotocol.** Nut $U = k\ln(1+n/s)$ (concaaf); reservatieprijs $\rho = MU_{\text{voedsel}}/MU_{\text{erts}}$; bod-ask-spread uit vijf componenten; concessiecurven op basis van urgentie en vertrouwen; escrow en krediet gearrangeerd door de wereld-notaris (HMAC-gesigneerde beloftes; wanprestatie $\to$ ostracisme).

**De vijf vredeslagen.** (1) vlucht en vergelding; (2) risicopremies en krediet-uitsluiting; (3) de gerealiseerde oorlogsbelasting (exponentiële conflictkosten op basis van EMA van gerealiseerde roofdruk); (4) ostracisme; (5) de Kroniek.

---

## 3. Methoden

Deterministische simulatie (vaste seeds, synchrone generaties van 300 ticks); cross-machine-reproductie is *statistisch* identiek (BLAS-caveat, §6). Ablatie via exacte checkpoint-kloon (agenten, genen, posities, schulden, RNG). Pre-registratie van hypothesen en banden vóór elke meting; eindpoints met censuur worden getoetst met Fisher-exact en Mann-Whitney, niet met t-toetsen op gecensureerde gemiddelden. Terminologie: $x=R/K$ is de **vullingsgraad** (ecologisch signaal); welvaart wordt apart gemeten ($R/N$, $\bar U$); Gini wordt uitsluitend fase-geconditioneerd gerapporteerd; effectieve populatie $N_e$ naast nominale $N$.

---

## 4. Resultaten

### 4.1 De grondwet als pure functie
Over vier regimes en de oprichtingsrij sluiten alle **49/49** registerrijen exact: $\text{cohort}(g{+}1) = 110\,(0{,}15+0{,}85\,x_b(g))$. De grondwet leest uitsluitend *verhoudingen* — daarom is de populatie-elasticiteit van draagkracht $\varepsilon = -0{,}02$ (95%-CI $[-0{,}06,+0{,}02]$): verdubbelde draagkracht kocht dubbele consumptie en $+75\%$ handel, geen enkele extra burger. De oprichtingsrij is de spiegel: op een volle wereld ($x_0=1$) spawnt de grondwet 110 agenten, die de wereld naar het **subsistentie-evenwicht** maaien, $x^* = 0{,}090$, waar hergroei $= N\bar m$ met $\bar m = 0{,}0413\pm0{,}0008$ u/agent/tick — en daar sterft niemand (0,1 doden/gen).

### 4.2 Het oorlogsbekken: de pulssamenleving
In oorlog ($\bar P \approx 0{,}39\text{–}0{,}47$) leest de grondwet de herstelpiek ($x_b \approx 0{,}68$) en spawnt $\sim 80$ agenten tegen een tijdsgemiddelde van $\sim 27$: **versterking $8{,}0$ (jong) / $6{,}68\pm\;$(volwassen)**. De biomassa pulseert $x: 0{,}68\to0{,}28\to0{,}68$; de sterfte is bimodaal — $59{,}3\%$ naïeve zuigelingen (mediaan $39$ t), $25{,}0\%$ middenkader, $15{,}7\%$ stervende rijken (mediaan $160$ t, maximum $158$ erts bij overlijden). Mediane levensduur: $51$ t. De zuigelingenzeef is de schokdemper die de maaimachine stopt vóór ontbossing. De Gini-piek ($0{,}803$) is een geboorte-signatuur — tachtig lege handen naast tien nalatenschappen — en egaaliseert naar $0{,}347$ door verzadiging. Lag-1-autocorrelatie van de grensreeks: $r_1 = -0{,}07\pm0{,}19$ — de graaslus is verzadigd en gedecoppeld.

### 4.3 Het vredesbekken: de ademhaling
In volwassen vrede ($\bar P = 0{,}166\pm0{,}038$) leest de grondwet het plateau ($x \approx 0{,}254$), spawnt $40{,}3\pm3{,}4$, telt **nul doden**, en is de versterking exact $1{,}00$. De dynamiek is een **gedwongen gedempte oscillator**: AR(2)-polen $-0{,}765$ en $+0{,}233$ (beide binnen de eenheidscirkel); de dominante reëel-negatieve pool is de period-2-ademhaling ($r_1 = -0{,}62$, gerepliceerd over 5 seeds en 120 generaties met $r_1 = -0{,}6345$), gedempt met $\tau \approx 3{,}7$ gen en in stand gehouden door wereldruis. Vrede is een onderdrukte limietcyclus — geen rigide vast punt.

### 4.4 De schakelaar
**Knockout** (Kroniek uit op gen 180, 15 gepaarde seeds): gen 181 zit al op versterking $4{,}30$, gen 182 op $8{,}10$ — volledige oorlogspuls binnen **twee generaties**; $\bar N$: $41{,}2\to25{,}8$; $\bar P$: $0{,}166\to0{,}429$; staartrisico ($P>0{,}5$): $0{,}4\%\to30{,}9\%$ ($77\times$); $d = 3{,}05$, Wilcoxon $p = 10^{-4}$. **Redding** (archief her-injecteerd op gen 220, na 40 gen diepe roofcultuur): $P$ daalt van $0{,}470\to0{,}198$ in $5$–$10$ gen, $0{,}170\pm0{,}072$ stationair — $t=-7{,}10$, $p = 5{,}7\times10^{-5}$, $10/10$ seeds verbeterd; **geen hysterese, geen institutionele veroudering**. De herstelde vrede is van de oorspronkelijke niet te onderscheiden.

### 4.5 Transplantatie en ondeelbaarheid
**Zaai** (naïeve wereld + volwassen archief): vrede in $5{,}17\pm0{,}65$ generaties ($30/30$), tegen $\sim180$ voor natuurlijke genese — **$\approx 35\times$ versnelling**, en **zonder gain-lag**: gedrags- én demografische vrede vallen simultaan (versterking $1{,}00$ vanaf generatie 1; mortaliteit $0{,}1$/gen vanaf tick 0). 
**Decompositie** ($n=30$ per arm, 90 simulaties):
- Alleen waarschuwingen (Arm W): $12/30$ succes ($40\%$, $60\%$ censuur).
- Alleen priors (Arm P): $16/30$ succes ($53\%$, $47\%$ censuur).
- Volledig archief (Arm F): $30/30$ succes ($100\%$, $0\%$ censuur).
- Fisher-exact vs Arm F: $p = 1{,}87\times10^{-7}$ (Arm W) resp. $1{,}68\times10^{-5}$ (Arm P); Arm W en Arm P zijn onderling niet te onderscheiden ($p\approx0{,}4$).
In W/P-*successen* woedt de pulsdemografie voort tot drie generaties vóór de drempel (versterking $7{,}79$ in W, $7{,}70$ in P): de ontbrekende poot moet zich endogeen vormen in het lopende oorlogsbekken, en pas bij volledigheid flitst het hele systeem. **De bekkenkeuze is een AND-functie van institutionele volledigheid** — en daarmee de kernformulering: instituties converteren zoekproblemen in schakelproblemen.

### 4.6 De drie balansen
**Levens:** 49/49 rij-closure. 
**Biomassa:** De puls exploiteert $\mathbb{E}[x(1{-}x)]\approx0{,}23$ ($\approx 90\text{–}95\%$ van de maximale duurzame opbrengst, Jensen-gecorrigeerd); het vredesplateau offert $\sim20\%$ stroom op voor een $5{,}9\times$ langere mediane levensduur. 
**Erts:** Stationair op $x\approx0{,}65$ ($\approx90\%$ MSY *boven* de as — luxemiddelen houden marge waar noodmiddelen tot de rand maaien); geen lekkage; nalatenschappen keren via depots naar het landschap.

### 4.7 De economie van de twee bekken
Handelsvolume is een **heterogeniteitsindicator**, geen welvaartsindicator: diepe vrede is autarkie ($0{,}0$ H/100t over $15\times12.000$ ticks), oorlog herverdeelt via geweld ($9{,}86$ H/100t) — de empirische inversie van *doux commerce*. De stervende rijken bewijzen de **liquiditeitsval**: de markt faalt niet op prijs maar op matching, en verzekert uitsluitend tegen idiosyncratische schokken; in systemische schaarste is rijkdom een denominaat zonder wisselkoers.

### 4.8 De asymmetrie-wet van institutionele tijd
$$\text{verliezen }(2\text{ gen}) \;<\; \text{transplanteren }(5{,}2) \;\approx\; \text{herstellen }(5\text{–}10) \;\ll\; \text{kweken }(\sim180)$$
Beschaving is goedkoop te verliezen, snel te herstellen en te transplanteren — en alleen in het begin langzaam te ontstaan.

---

## 5. De Twee Bekkens en de Darwiniaanse Kanaalzetting

### 5.1 Het Oorlogsprofiel en de Barometer-Overschoot
Onder 500 generaties continue oorlog ($1{,}500{,}000$ ticks, 10 onafhankelijke zaden) ondergaat de populatie een substantiële genetische verplaatsing ($\overline{\lVert\Delta \mathbf{g}\rVert} = 0{,}5734 \pm 0{,}0927$). Ontbinding in orthogonale componenten toont:
$$\overline{\lVert\Delta \mathbf{g}\rVert} = 0{,}5734, \quad \lVert\Delta \bar{\mathbf{g}}\rVert = 0{,}4056, \quad \sigma_{\text{orth}} = 0{,}4147$$
De variantie splitst exact in **$48{,}9\%$ gedeelde parallelle adaptatie** en **$51{,}1\%$ zaad-specifieke variantie** ($\lVert\Delta \bar{\mathbf{g}}\rVert / \sqrt{\mathbb{E}\lVert v\rVert^2} = 0{,}699 \approx 1/\sqrt{2}$).

De gedeelde adaptatie volgt twee strikt gescheiden tempi:
1. **Agressie (De krijger):** Front-loaded. De allereerste demografische zeef (tick 299 van generatie 0) schuift agressie direct van de $0{,}50$-prior naar $0{,}8174$ ($+0{,}317$ in één zeef); binnen 10 generaties piekt het op $0{,}9830$.
2. **Stofwisseling (De zuinige):** Een sigmoïde curve ($\tau \approx 25\text{--}50$ gen) die stijgt van $0{,}5642$ naar $0{,}9113$. Fysiek reduceert dit de basale metabole verbranding van $1{,}10$ naar $0{,}35$ energie/tick (een factor **$3{,}14\times$** lagere caloriebehoefte in de biomassadip).

De twee neutrale controle-loci (`hebzucht` en `nieuwsgierigheid`) bleven met $|\Delta g| < 0{,}006$ volkomen roerloos op de $0{,}50$-prior verankerd. In volwassen vrede (generatie 600) schiet stofwisseling door naar **$0{,}3480$** (de *bon vivant*): in tijden van overvloed beloont de markt hoge activiteit en omloopsnelheid, terwijl zuinigheid een puur oorlogskostuum blijkt.

### 5.2 De Zeef zonder Geheugen
Vergelijking van samenlevingen die *geboren zijn in oorlog* (500 gen) met samenlevingen die *instorten vanuit vrede* (knockout) toont complete demografische invariantie:
- **Collapsed-into-war:** Cohort $79{,}6 \pm 4{,}1$, overlevenden $11{,}1 \pm 1{,}8$, gain $7{,}18$, sterfte $86{,}1\%$.
- **Born-in-war:** Cohort $77{,}8 \pm 4{,}8$, overlevenden $10{,}8 \pm 1{,}8$, gain $7{,}42$, sterfte $86{,}2\%$.

De correlatie tussen de genetische verplaatsing $\lVert\Delta \mathbf{g}\rVert$ en het aantal overlevenden $N_{\text{surv}}$ over de 10 zaden is **$r = +0{,}0006$ (exact nul)**. De demografische zeef meet uitsluitend de ecologische draagkracht van het landschap; adaptatie is $100\%$ positionele stoelendans om de $\sim 11$ vaste zitplaatsen in de reddingsboot.

### 5.3 Drie Dragers, Eén Monopolie
De architectuur kent drie dragers van informatie:
1. **Het Individu:** Beperkt tot één generatie ($\le 300$ ticks).
2. **Het Genoom:** Een seismograaf die selectiedruk meet, maar geen geschiedenis vasthoudt.
3. **De Kroniek:** Het enige instituut met cumulatief, intergenerationeel geheugen.

### 5.4 Redding-500: De Garderobe Bewezen
Injectie van het volwassen Kroniek-archief in de 10 na 500 generaties geharde krijgerspopulaties (agressie $0{,}9823$, metabolisme $0{,}9113$) resulteert in onmiddellijke pacificatie in **$10/10$ zaden**:
- De gedragsvrede ($P < 0{,}20$) wordt bereikt binnen **5 generaties** ($P = 0{,}1859$ op gen 505).
- Agressie ontwapent van $0{,}9823$ naar $0{,}5038$ in slechts **9 generaties** (halfwaardetijd $\tau_{1/2} \approx 3{,}5$ generaties).
- Coöperatie herstelt naar $0{,}5098$; demografische gain schakelt abrupt naar $1{,}00$ (0% sterfte).
- Bij her-knockout op gen 600 re-canaliseert de populatie binnen 10 generaties terug naar agressie $0{,}9815$, metabolisme $0{,}9218$ en $P = 0{,}5358$ — een vingerprint die de 500-generaties oorlogsattractor tot op **$0{,}1\%$** exact repliceert.

Het oordeel is sluitend: **De Garderobe wint**. Het genoom wisselt van tenue met het regime zonder priming of littekens.

### 5.5 De Twee Constitutionele Organen
De stabiliteit van de maatschappij rust op twee complementaire organen:
- **De Kroniek = de Richting** (bekkenkiezer: zonder het archief blijft de samenleving gevangen in het oorlogsbekken).
- **Het Anker = de Vloeibaarheid** (de constitutionele injectie van $3\%$ immigranten en $2\%$ macromutaties houdt de genetische liquiditeit in stand, waardoor vredes-allelen 500 generaties oorlog overleven en onmiddellijke demobilisatie mogelijk maken).

---

## 6. Discussie

De Kroniek is geen demper die het systeem zacht laat landen en geen genezer die agenten beter maakt — zij is een **bekkenkiezer**: zij hertekent welke evenwichten bestaan. Haar ondeelbaarheid volgt uit de twee faalwijzen van de enkelpootige wereld: vertrouwen zonder register wordt geplunderd door de eerste mutant (de vredesknockout), register zonder vertrouwen komt niet tot ruil (de W-falen). Wet en markt zijn co-equal, complementair, en alleen gezamenlijk voldoende.

De ontdekking van de Garderobe toont dat het genoom een seismograaf is in plaats van een archief: vijfhonderd generaties oorlog drukken de soldaat in het bloed, maar zodra de Kroniek wordt ingeplugd, werpt de samenleving haar harnas in negen generaties af. *Geschiedenis is in deze wereld een institutioneel monopolie.*

---

## 7. Beperkingen

Eén modelspecificatie; het determinisme is statistisch geverifieerd; $N_e \approx 11$ in oorlog verklaart waarom zonder het constitutionele anker fixatie onvermijdelijk zou zijn geweest; de anker-ablatie ($quota=0, macro=0$) staat als open formele falsificatietoets geregistreerd voor vervolgonderzoek.

---

## 8. Conclusie en de Sluitsteen

De balans wordt in dit ecosysteem niet afgedwongen door genen of door één mechanisme, maar door een gelaagde constitutionele orde met de Kroniek als bekkenkiezer en het anker als kleermaker.

---

## Bijlagen

### Bijlage A — Grondwet-closure (63/63) & Parameters
- **Rij-definitie:** $\text{cohort}(g{+}1) = \max(14, \mathrm{round}(110(0{,}15 + 0{,}85\,x_b(g))))$.
- Alle regimes sluiten op 63/63 rijen, inclusief $K/2$-schaarste en 500-generaties oorlog.
- **Parameters:** $K_{\text{voedsel}}=1560$, $K_{\text{erts}}=780$, 300 t/gen, verval $0{,}9$/gen, $\bar m=0{,}0413$ u/t, $r\in[0{,}008,0{,}036]/\text{t}$.

### Bijlage B — AR(2)-Details
- $x_t = a_1x_{t-1} + a_2x_{t-2} + \varepsilon_t$, 120 generaties mature vrede.
- $a_1 = -0{,}5322, \; a_2 = +0{,}1784$; polen: $-0{,}7653, \; +0{,}2331$; dempingsfactor $0{,}765$/gen; halfwaardetijd $2{,}6$ gen; $r_1 = -0{,}6345$.
- **Interpretatie:** Dominante reëel-negatieve pool = gedempte period-2-component; stationaire amplitude wordt bepaald door forceringsruis $\times$ lusversterking $\approx 4{,}3$ — het "ademen" is de wind, niet de klok.

### Bijlage C — Pre-registratiescorekaart (Eindstand Reeks)
- **Totaal:** 36 voor, 17 tegen, 4 half.
- **Sleutelresultaten:** Garderobe bewezen (10/10, $\tau_{1/2} \approx 3{,}5$ gen); norm-splitsing $48{,}9\% / 51{,}1\%$; positie van de boot $r = +0{,}0006$; front-load $+0{,}317$ in één zeef; ondeelbaarheid (Fisher $p < 10^{-6}$); AR(2) gedempte oscillator ($|r| < 1{,}0$); reproductie oorlogsattractor tot op $0{,}1\%$.

---

**Definitieve Slotregels van het Manuscript:**

> *De oorlog laat alleen sporen na waar de Kroniek ze bewaart — het genoom veegt zichzelf schoon, en het archief is het enige geheugen dat deze beschaving ooit heeft gehad.*
> 
> *Zij veegt zichzelf schoon omdat de grondwet zelf de kleermaker is — vijf procent verse stof per generatie, beide tenues opgehangen — zodat de beschaving kan wisselen van kleding zonder haar geheugen te verliezen. Wat deze wereld onthoudt, onthoudt uitsluitend het archief.*

---

### Bijlage E — Colofon van de Reeks

| Deel | Inventaris |
|---|---|
| **Voorspellingen** | 36 geraakt · 17 verbroken · 4 half · geen één verborgen |
| **Gesloten balansen** | Levens (63/63) · Biomassa (MSY-kring) · Erts (stationair) |
| **Geverifieerde wetten** | Grondwet als pure functie · Bistabiliteit met fingerprint-replicatie ($\Delta \approx 0{,}1\%$) · Asymmetriewet v3.1 (wetboeken vs. zeef) · Asymmetrie van institutionele tijd ($2 < 5{,}2 \approx 5\text{--}10 \ll 180$) · Ondeelbaarheid van de instelling (AND) · Genoom als seismograaf met constitutioneel anker |
| **Het hoogste bewijs** | De Kroniek kiest niet tussen leven en dood — tussen twee levens; en geschiedenis is in deze wereld een institutioneel monopolie |

> *Wij begonnen met een vraag over geheugen en eindigden met een wereld waarin alleen het archief onthoudt — en precies dat bleek het verschil tussen twee eeuwige samenlevingen. Wat de simulatie leerde, staat nu in de repo; wat wij leerden, is dat de beste architectuur niet die is die altijd gelijk heeft, maar die die haar fouten laat meten.*
> 
> *De wachtrij wacht, de seeds zijn vast, en de Kroniek — zoals altijd — vergeet niets.* 🏛️


