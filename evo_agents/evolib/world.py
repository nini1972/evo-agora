from __future__ import annotations
import math
import os
from dataclasses import dataclass

import numpy as np

from .agent import Agent
from .ecosystem import EcoInstellingen, EcosysteemGouverneur
from .evolution import EvolutieMotor, Momentopname
from .genome import GENE_NAMEN, Genome
from .policy import RES_ATTR
from .protocol import (
    Actie,
    ActieType,
    Bericht,
    BerichtSigneerder,
    BerichtType,
    Bod,
    Partij,
    Res,
    TegenpartijView,
    Wijze,
    onderhandel,
)
from .telemetry import Gebeurtenis, GebeurtenisType


@dataclass
class Bron:
    res: Res
    x: int
    y: int
    hoeveelheid: float
    capaciteit: float = 12.0
    groei: float = 0.06


@dataclass
class DoelView:
    id: int
    bucket: tuple[int, int]
    vertrouwen: float
    erts_geschat: float
    energie_geschat: float
    energie_fractie: float
    vogelvrij: bool
    agressie_schatting: float


@dataclass
class Perceptie:
    wereld: "Wereld"
    ik: Agent
    bron_op_positie: Bron | None
    buren: list[DoelView]

    def beste_buurcel(self, waarde_fn) -> tuple[int, int] | None:
        wx, wy = self.wereld.breedte, self.wereld.hoogte
        x0, y0 = self.ik.pos
        beste, beste_score = None, -1.0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                bron = self.wereld.grid.get(((x0 + dx) % wx, (y0 + dy) % wy))
                if bron:
                    s = (
                        waarde_fn(bron.res, min(bron.hoeveelheid, 8.0)) / 45.0
                        + 0.05 * float(self.wereld.rng.random())
                    )
                else:
                    s = 0.05 * float(self.wereld.rng.random())
                if s > beste_score:
                    beste, beste_score = (dx, dy), s
        return beste


@dataclass
class Schuldbrief:
    schuldenaar: int
    eiser: int
    partij: Partij
    uiterlijk: int


TICKS_PER_GENERATIE = 300
POPULATIE_DOEL = 110
GERUCHTRADIUS = 6


class Wereld:
    def __init__(
        self,
        breedte: int = 36,
        hoogte: int = 36,
        rng: np.random.Generator | None = None,
        n_bronnen: int = 130,
        met_kroniek: bool = True,
    ):
        self.breedte, self.hoogte = breedte, hoogte
        self.rng = rng or np.random.default_rng()
        self.tick = 0
        self.grid: dict[tuple[int, int], Bron] = {}
        for _ in range(n_bronnen):
            x, y = int(self.rng.integers(breedte)), int(self.rng.integers(hoogte))
            res = Res.VOEDSEL if self.rng.random() < 0.6 else Res.ERTS
            self.grid[(x, y)] = Bron(
                res=res,
                x=x,
                y=y,
                hoeveelheid=float(self.rng.uniform(3, 9)),
            )
        self.agents: dict[int, Agent] = {}
        self.signer = BerichtSigneerder(os.urandom(32))
        self.berichten_log: list[Bericht] = []
        self.schulden: dict[tuple[int, int], Schuldbrief] = {}
        self.vogelvrij_set: set[int] = set()
        self.gov = EcosysteemGouverneur(
            EcoInstellingen(draagkracht=sum(b.capaciteit for b in self.grid.values()))
        )
        # Vaste broncapaciteit per resourcetype (voor voedsel-specifieke telemetrie,
        # zie totale_bron_per_type/ehi_per_type). Natuurlijke bronnen (groei > 0)
        # worden nooit verwijderd, dus deze som blijft constant tijdens de run.
        self.draagkracht_per_type: dict[Res, float] = {
            Res.VOEDSEL: sum(b.capaciteit for b in self.grid.values() if b.res is Res.VOEDSEL),
            Res.ERTS: sum(b.capaciteit for b in self.grid.values() if b.res is Res.ERTS),
        }
        self.motor = EvolutieMotor()
        self.generatie_archief: list[tuple[Genome, Momentopname]] = []
        self._agres_aandeel = 0.0
        self._roofdruk_ema = 0.0
        self._overvallen_deze_tick = 0
        self.kroniek_archetypen: dict[tuple[int, int], tuple[float, float]] = {}
        self.met_kroniek = met_kroniek
        self.god_mode = False
        self.observers: list = []  # duck-typed: na_tik/na_generatie/gebeurtenis
        self.tick_per_gen = TICKS_PER_GENERATIE  # leesbaar voor de telemetrie

    def _meld(
        self,
        type: GebeurtenisType,
        actoren: list[Agent],
        omvang: float = 0.0,
    ) -> None:
        """Enige toegestane koppeling wereld->observatoren. Lees-only, geen RNG."""
        if not self.observers:
            return
        g = Gebeurtenis(
            tik=self.tick,
            type=type,
            actor_ids=tuple(a.id for a in actoren),
            posities=tuple(tuple(a.pos) for a in actoren),
            omvang=float(omvang),
        )
        for o in self.observers:
            o.gebeurtenis(g)

    # ── spawner & perceptie ──────────────────────────────────────────────
    def spawn(self, genoom: Genome) -> Agent:
        pos = (
            int(self.rng.integers(self.breedte)),
            int(self.rng.integers(self.hoogte)),
        )
        a = Agent(genoom, self, pos)
        if self.met_kroniek and self.kroniek_archetypen:
            a.geheugen.archetypen = {
                k: (v[0], v[1]) for k, v in self.kroniek_archetypen.items()
            }
        self.agents[a.id] = a
        return a

    def bouw_perceptie(self, ik: Agent) -> Perceptie:
        wx, wy = self.breedte, self.hoogte
        x0, y0 = ik.pos
        buren: list[DoelView] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for a in self.agents.values():
                    if a.levend and a.id != ik.id and a.pos == ((x0 + dx) % wx, (y0 + dy) % wy):
                        r = self.rng.uniform(0.75, 1.25)  # observatieruis
                        buren.append(
                            DoelView(
                                id=a.id,
                                bucket=a.bucket,
                                vertrouwen=ik.geheugen.vertrouwen(self.tick, a.id, a.bucket),
                                erts_geschat=a.erts * r,
                                energie_geschat=a.energie * r,
                                energie_fractie=a.energie / a.max_energie,
                                vogelvrij=a.vogelvrij,
                                agressie_schatting=min(1.0, a.genoom.waarde("agressie") * r),
                            )
                        )
        return Perceptie(self, ik, self.grid.get(tuple(ik.pos)), buren)

    def tegenpartij_view(self, mij_id: int, ander_id: int) -> TegenpartijView:
        mij, ander = self.agents[mij_id], self.agents[ander_id]
        r = float(self.rng.uniform(0.8, 1.2))
        return TegenpartijView(
            id=ander.id,
            bucket=ander.bucket,
            vertrouwen=mij.geheugen.vertrouwen(self.tick, ander.id, ander.bucket),
            erts_geschat=ander.erts * r,
            energie_fractie=ander.energie / ander.max_energie,
            vogelvrij=ander.vogelvrij,
        )

    # ── notariaat ────────────────────────────────────────────────────────
    def registreer_bericht(
        self,
        zender: int,
        ontvanger: int,
        type: BerichtType,
        bod: Bod | None,
        wijze: Wijze | None,
        ronde: int,
    ) -> Bericht:
        b = Bericht(
            zender,
            ontvanger,
            type,
            bod,
            wijze,
            ronde,
            seq=self.signer.volgende_seq(zender, ontvanger),
        )
        b = Bericht(**{**b.__dict__, "handtekening": self.signer.signeer(b)})
        if not self.signer.verifieer(b, b.seq):  # zou nooit mogen gebeuren
            raise ValueError("berichtintegriteit geschonden")  # bewuste hard fail
        self.berichten_log.append(b)
        return b

    # ── afwikkeling ──────────────────────────────────────────────────────
    def _dra_over(self, gever: Agent, ontvanger: Agent, p: Partij, courtage: bool) -> None:
        n = p.hoeveelheid
        fee = n // 20 if courtage else 0
        gever.geef_af(p.res, n)
        ontvanger.ontvang(p.res, n - fee)  # de wereld eet de courtage op

    def wikkel_af(self, aanbieder: Agent, antwoorder: Agent, bod: Bod, wijze: Wijze):
        geeft, vraagt = bod.geeft, bod.vraagt
        if (
            aanbieder.voorraad(geeft.res) < geeft.hoeveelheid
            or antwoorder.voorraad(vraagt.res) < vraagt.hoeveelheid
        ):
            return None
        if wijze is Wijze.ESCROW:
            self._dra_over(aanbieder, antwoorder, geeft, courtage=True)
            self._dra_over(antwoorder, aanbieder, vraagt, courtage=True)
            aanbieder.onthoud(antwoorder.id, antwoorder.bucket, "handel", "lever", "lever", +1.0)
            antwoorder.onthoud(aanbieder.id, aanbieder.bucket, "handel", "lever", "lever", +1.0)
            aanbieder.stat.handels += 1
            antwoorder.stat.handels += 1
            self._meld(
                GebeurtenisType.HANDEL_ESCROW,
                [aanbieder, antwoorder],
                float(bod.prijs),
            )
            return {"status": "escrow"}
        # CREDIT: beide verplichtingen staan gelijktijdig ter nakoming
        a_ok = aanbieder.voorraad(geeft.res) >= geeft.hoeveelheid and aanbieder.beleid.kom_na(geeft)
        b_ok = antwoorder.voorraad(vraagt.res) >= vraagt.hoeveelheid and antwoorder.beleid.kom_na(vraagt)
        if a_ok and b_ok:
            self._dra_over(aanbieder, antwoorder, geeft, courtage=False)
            self._dra_over(antwoorder, aanbieder, vraagt, courtage=False)
            aanbieder.onthoud(antwoorder.id, antwoorder.bucket, "handel", "lever", "lever", +1.0)
            antwoorder.onthoud(aanbieder.id, aanbieder.bucket, "handel", "lever", "lever", +1.0)
            aanbieder.stat.handels += 1
            antwoorder.stat.handels += 1
            self._meld(
                GebeurtenisType.HANDEL_CREDIT,
                [aanbieder, antwoorder],
                float(bod.prijs),
            )
            return {"status": "credit-ok"}
        if a_ok and not b_ok:
            self._dra_over(aanbieder, antwoorder, geeft, courtage=False)
            self.schulden[(antwoorder.id, aanbieder.id)] = Schuldbrief(
                antwoorder.id, aanbieder.id, vraagt, self.tick + 12
            )
            self.markeer_feit(antwoorder, aanbieder)
            return {"status": "credit-schuld"}
        if b_ok and not a_ok:
            self._dra_over(antwoorder, aanbieder, vraagt, courtage=False)
            self.schulden[(aanbieder.id, antwoorder.id)] = Schuldbrief(
                aanbieder.id, antwoorder.id, geeft, self.tick + 12
            )
            self.markeer_feit(aanbieder, antwoorder)
            return {"status": "credit-schuld"}
        aanbieder.onthoud(
            antwoorder.id, antwoorder.bucket, "handel", "trek-terug", "trek-terug", -0.3
        )
        antwoorder.onthoud(
            aanbieder.id, aanbieder.bucket, "handel", "trek-terug", "trek-terug", -0.3
        )
        return {"status": "geannuleerd"}

    # ── justitie & geruchten ─────────────────────────────────────────────
    def markeer_feit(self, dader: Agent, slachtoffer: Agent) -> None:
        dader.stat.feiten += 1
        self._meld(GebeurtenisType.WANPRESTATIE, [dader, slachtoffer], 1.0)
        slachtoffer.onthoud(dader.id, dader.bucket, "feit", "getuige", "wanprestatie", -1.0)
        wx, wy = self.breedte, self.hoogte
        for g in self.agents.values():
            if not g.levend or g.id in (dader.id, slachtoffer.id):
                continue
            dx = abs(g.pos[0] - dader.pos[0])
            dx = min(dx, wx - dx)
            dy = abs(g.pos[1] - dader.pos[1])
            dy = min(dy, wy - dy)
            if max(dx, dy) <= GERUCHTRADIUS:  # ruimtelijk begrensde roddelpropagatie
                g.onthoud(dader.id, dader.bucket, "gerucht", "getuige", "wanprestatie", -0.7)
        if dader.stat.feiten >= 3:
            dader.vogelvrij = True
            self.vogelvrij_set.add(dader.id)
            self._meld(GebeurtenisType.VOGELVRIJ, [dader], float(dader.stat.feiten))

    def verwerk_schulden(self) -> None:
        vervallen = [k for k, s in self.schulden.items() if self.tick >= s.uiterlijk]
        for sleutel in vervallen:
            s = self.schulden.pop(sleutel)
            schuldenaar = self.agents.get(s.schuldenaar)
            eiser = self.agents.get(s.eiser)
            if schuldenaar is None or eiser is None or not schuldenaar.levend:
                continue
            if (
                schuldenaar.voorraad(s.partij.res) >= s.partij.hoeveelheid
                and schuldenaar.beleid.kom_na(s.partij)
            ):
                self._dra_over(schuldenaar, eiser, s.partij, courtage=False)
                eiser.onthoud(
                    schuldenaar.id,
                    schuldenaar.bucket,
                    "schulden",
                    "incasso",
                    "betaald",
                    +0.8,
                )
            else:
                self.markeer_feit(schuldenaar, eiser)

    # ── actie-uitvoering ─────────────────────────────────────────────────
    def roofdruk_ema(self) -> float:
        return self._roofdruk_ema

    def conflictkostenfactor(self) -> float:
        return self.gov.conflictkostenfactor(self._roofdruk_ema)

    def voer_uit(self, actie: Actie, a: Agent, rng: np.random.Generator) -> float:
        kost = 0.35 + 0.75 * (1.0 - a.genoom.waarde("stofwisseling"))
        wx, wy = self.breedte, self.hoogte
        if actie.type is ActieType.RUST:
            kost *= 0.5
            a.energie = min(a.max_energie, a.energie + 1.5)
        elif actie.type is ActieType.BEWEEG:
            if actie.richting is not None:
                dx, dy = actie.richting
                a.pos = ((a.pos[0] + dx) % wx, (a.pos[1] + dy) % wy)
                # OPTIMALISATIE: Schaal energiekosten naar Euclidische afstand (1.41x duurder bij diagonaal)
                kost += 0.35 * math.sqrt(dx**2 + dy**2)
            else:
                kost += 0.35
        elif actie.type is ActieType.OOGST:
            pos_tup = tuple(a.pos)
            bron = self.grid.get(pos_tup)
            if bron is not None and bron.hoeveelheid >= 0.3:
                max_oogst = 8 if bron.hoeveelheid >= 4.0 else (3 if bron.hoeveelheid >= 2.0 else 1)
                n = min(int(bron.hoeveelheid), max_oogst)
                if n >= 1:
                    bron.hoeveelheid -= n
                    a.ontvang(bron.res, n)
                elif bron.res is Res.VOEDSEL and a.energie < 0.45 * a.max_energie:
                    bron.hoeveelheid -= 0.3
                    a.energie = min(a.max_energie, a.energie + 3.0)
                if bron.groei == 0.0 and bron.hoeveelheid <= 0.05:
                    self.grid.pop(pos_tup, None)
            kost += 0.2
        elif actie.type is ActieType.AANVAL:
            if actie.doel_id is not None:
                doel = self.agents.get(actie.doel_id)
                if doel is not None and doel.levend:
                    self._aanval(a, doel, rng)
            kost += 1.0
        elif actie.type is ActieType.HANDEL:
            if actie.doel_id is not None:
                doel = self.agents.get(actie.doel_id)
                if doel is not None and doel.levend:
                    onderhandel(self, a, doel, rng)
            kost += 0.1
        return kost

    def _aanval(self, aanvaller: Agent, doel: Agent, rng: np.random.Generator) -> None:
        self._overvallen_deze_tick += 1
        ka = (
            6.0
            * (0.4 + aanvaller.genoom.waarde("agressie"))
            * (0.4 + 0.6 * aanvaller.energie / aanvaller.max_energie)
        )
        kd = (
            5.0
            * (0.4 + doel.genoom.waarde("agressie"))
            * (0.4 + 0.6 * doel.energie / doel.max_energie)
        )
        mult = self.conflictkostenfactor()
        if ka > kd * self.rng.uniform(0.8, 1.2):
            roof_erts = min(doel.erts, int(np.ceil(0.35 * doel.erts)))
            roof_voedsel = min(doel.voedsel // 2, 4)
            doel.geef_af(Res.ERTS, roof_erts)
            doel.geef_af(Res.VOEDSEL, roof_voedsel)
            aanvaller.ontvang(Res.ERTS, roof_erts)
            aanvaller.ontvang(Res.VOEDSEL, roof_voedsel)
            if doel.vogelvrij:  # premie: zelffinancierend (L4)
                premie = min(doel.erts, 4)
                doel.geef_af(Res.ERTS, premie)
                aanvaller.ontvang(Res.ERTS, premie)
            doel.energie -= max(4.0, 10.0 + 8.0 * (ka - kd))
            aanvaller.stat.kills += 1
            self._meld(
                GebeurtenisType.OVERVAL_WEL,
                [aanvaller, doel],
                float(roof_erts + roof_voedsel),
            )
            doel.onthoud(aanvaller.id, aanvaller.bucket, "overval", "verdedig", "beroofd", -1.0)
            aanvaller.onthoud(doel.id, doel.bucket, "overval", "roof", "verloor", +0.6)
        else:
            aanvaller.energie -= 5.0 * mult
            doel.energie -= 2.0
            self._meld(GebeurtenisType.OVERVAL_MISLUKT, [aanvaller, doel], 0.0)
            doel.onthoud(aanvaller.id, aanvaller.bucket, "overval", "verdedig", "sloeg-af", -0.5)

    # ── hoofdtik ─────────────────────────────────────────────────────────
    def totale_bron(self) -> float:
        return sum(b.hoeveelheid for b in self.grid.values())

    def totale_bron_per_type(self) -> dict[Res, float]:
        """Som van hoeveelheid, uitgesplitst per Res-type (o.a. voor voedsel-specifieke telemetrie)."""
        totalen = {Res.VOEDSEL: 0.0, Res.ERTS: 0.0}
        for b in self.grid.values():
            totalen[b.res] += b.hoeveelheid
        return totalen

    def ehi_per_type(self) -> dict[Res, float]:
        """Gezondheidsindex (0-1) per resourcetype t.o.v. de vaste draagkracht van dat type."""
        totalen = self.totale_bron_per_type()
        return {
            res: max(0.0, min(1.0, totalen[res] / max(1e-9, self.draagkracht_per_type[res])))
            for res in (Res.VOEDSEL, Res.ERTS)
        }

    def stap(self) -> None:
        levend = [a for a in self.agents.values() if a.levend]
        if levend:
            self._agres_aandeel = float(
                np.mean([a.genoom.waarde("agressie") for a in levend])
            )
        volgorde = self.rng.permutation(len(levend))
        for i in volgorde:
            a = levend[i]
            if not a.levend:
                continue
            kost = a.stap(self.rng)
            a.energie -= kost
        # bronlogistiek: dR = r·max(R_zaad, R)·(1 − R/K) voor actieve natuurlijke bronnen
        for bron in self.grid.values():
            if bron.groei > 0.0:
                groei_delta = (
                    bron.groei
                    * max(0.8, bron.hoeveelheid)
                    * (1.0 - bron.hoeveelheid / bron.capaciteit)
                )
                bron.hoeveelheid = min(
                    bron.capaciteit, bron.hoeveelheid + max(0.0, groei_delta)
                )
        # metabolisme, auto-eten, dood
        voor_dood = list(self.agents.values())
        for a in voor_dood:
            if not a.levend:
                continue
            a.eet_automatisch()
            if a.energie <= 0.0:
                if self.god_mode:
                    a.energie = 0.5
                else:
                    self._meld(GebeurtenisType.DOOD_HONGER, [a], float(a.erts))
                    a.overlijd()
                    pos_tuple = tuple(a.pos)

                    # BUGFIX: Voorkom permanente wildgroei van zelf-regenererende bronnen
                    if pos_tuple in self.grid:
                        # Als er al een bron is, verhoog tijdelijk de hoeveelheid (tot max capaciteit)
                        bron = self.grid[pos_tuple]
                        bron.hoeveelheid = min(
                            bron.capaciteit, bron.hoeveelheid + float(min(6, a.erts + 1))
                        )
                    else:
                        # Spawn een NIET-groeiende, tijdelijke afzetting (groei = 0.0)
                        self.grid[pos_tuple] = Bron(
                            res=Res.ERTS,
                            x=a.pos[0],
                            y=a.pos[1],
                            hoeveelheid=float(min(6, a.erts + 1)),
                            capaciteit=12.0,
                            groei=0.0,  # Kan niet uit zichzelf oneindig groter worden
                        )
                    self.generatie_archief.append((a.genoom, self._momentopname(a)))
        self.verwerk_schulden()

        # Bereken streaming roofdruk
        n_levend = len([a for a in self.agents.values() if a.levend])
        roofdruk_actueel = self._overvallen_deze_tick / max(1, n_levend)
        self._roofdruk_ema = 0.95 * self._roofdruk_ema + 0.05 * roofdruk_actueel
        self._overvallen_deze_tick = 0

        self.tick += 1
        for o in self.observers:
            o.na_tik(self)
        if self.tick % TICKS_PER_GENERATIE == 0:
            self._reproduceer()

    def _momentopname(self, a: Agent) -> Momentopname:
        m = a.stat.momentopname(self.tick)
        m.erts = float(a.erts)
        return m

    # ── generatiewissel ──────────────────────────────────────────────────
    def _reproduceer(self) -> None:
        levend = [a for a in self.agents.values() if a.levend]
        for a in levend:  # iedereen archiveert
            self.generatie_archief.append((a.genoom, self._momentopname(a)))

        genomen = [g for g, _ in self.generatie_archief]
        stats = [s for _, s in self.generatie_archief]
        clusters = (
            len(set(self.motor._clustertoewijzing(genomen)))
            if len(genomen) > 1
            else len(genomen)
        )
        ehi = self.gov.gezondheidsindex(self.totale_bron())
        redding = self.gov.redding_nodig(len(levend), clusters)

        # vruchtbaarheidspoort: wie mag ouder worden hangt af van ecosysteemgezondheid
        vrucht = self.gov.vruchtbaarheidsfactor(ehi)
        ouders = [a for a in levend if a.energie >= 45.0 and self.rng.random() < vrucht]
        if len(ouders) < 2:
            redding = True

        # Demografische draagkracht: cohortgrootte schaalt mee met ecologische gezondheid
        doelgrootte = max(
            self.gov.inst.min_populatie,
            int(round(POPULATIE_DOEL * (0.15 + 0.85 * ehi))),
        )

        kinderen_genomen = self.motor.volgende_generatie(
            genomen, stats, self.rng, doelgrootte, TICKS_PER_GENERATIE, redding
        )

        # Kroniek bijwerken met ervaringen van het vertrekkende cohort (verval 0.9)
        if self.met_kroniek:
            for a in self.agents.values():
                for bucket, (som, n) in a.geheugen.archetypen.items():
                    curr_som, curr_n = self.kroniek_archetypen.get(bucket, (0.0, 0.0))
                    self.kroniek_archetypen[bucket] = (curr_som + som, curr_n + n)
            self.kroniek_archetypen = {
                k: (v[0] * 0.9, v[1] * 0.9) for k, v in self.kroniek_archetypen.items()
            }

        # generatiewissel: hele cohort met pensioen, wereld (bronnen!) blijft bestaan
        for a in self.agents.values():
            if a.levend:
                a.overlijd()
        self.agents.clear()
        self.schulden.clear()
        for g in kinderen_genomen:
            self.spawn(g)

        for o in self.observers:
            o.na_generatie(self, self.motor)

        self.vogelvrij_set.clear()
        self.generatie_archief.clear()

    # ── diagnostiek ──────────────────────────────────────────────────────
    def diagnose(self) -> str:
        levend = [a for a in self.agents.values() if a.levend]
        if not levend:
            return f"t={self.tick:5d}  EXTINCT"
        gem = {n: float(np.mean([a.genoom.waarde(n) for a in levend])) for n in GENE_NAMEN}
        clusters = len(set(self.motor._clustertoewijzing([a.genoom for a in levend])))
        return (
            f"t={self.tick:5d}  pop={len(levend):3d}  EHI={self.gov.gezondheidsindex(self.totale_bron()):.2f} "
            f"clusters={clusters}  agres={gem['agressie']:.2f} coop={gem['cooperatie']:.2f} "
            f"vogelvrij={len(self.vogelvrij_set)}  schulden={len(self.schulden)}"
        )
