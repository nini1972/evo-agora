from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from .genome import N_GENES, Genome


@dataclass
class Momentopname:
    levensduur: int
    erts: float
    nakomelingen: int
    handels: int
    feiten: int
    leeft: bool


@dataclass
class FitnessGewichten:
    levensduur: float = 1.0
    rijkdom: float = 1.0
    nakomelingen: float = 1.6
    overleefd: float = 0.3
    handel: float = 0.1
    feiten_straf: float = 0.6


class HalVanFaam:
    """Genetische verzekeringspolis: elite-genomen van eerdere generaties."""

    def __init__(self, capaciteit: int = 40):
        self.capaciteit = capaciteit
        self.lijst: list[tuple[float, Genome]] = []

    def werk_bij(self, genoom: Genome, fitness: float) -> None:
        self.lijst.append((fitness, genoom.kopie()))
        self.lijst.sort(key=lambda t: t[0], reverse=True)
        del self.lijst[self.capaciteit:]

    def steekproef(self, rng: np.random.Generator) -> Genome:
        _, g = self.lijst[int(rng.integers(len(self.lijst)))]
        return g.kopie()


class EvolutieMotor:
    def __init__(
        self,
        gewichten: FitnessGewichten | None = None,
        elite: int = 2,
        toernooi_k: int = 3,
        delta_soort: float = 0.35,
        sigma_share: float = 0.30,
        max_clusteraandeel: float = 0.5,
        immigrant_quota: float = 0.03,
    ):
        self.w = gewichten or FitnessGewichten()
        self.elite = elite
        self.k = toernooi_k
        self.delta_soort = delta_soort * np.sqrt(N_GENES)
        self.sigma_share = sigma_share * np.sqrt(N_GENES)
        self.max_clusteraandeel = max_clusteraandeel
        self.immigrant_quota = immigrant_quota
        self.hof = HalVanFaam()

    # ── Gecorrigeerde fitness ─────────────────────────────────────────────
    def _ruwe_fitness(
        self,
        genomen: list[Genome],
        stats: list[Momentopname],
        tick_per_gen: int,
    ) -> np.ndarray:
        w = self.w
        f = np.array(
            [
                w.levensduur * (s.levensduur / max(1, tick_per_gen))
                + w.rijkdom * (s.erts / 40.0) * (s.levensduur / max(1, tick_per_gen))
                + w.nakomelingen * s.nakomelingen
                + w.overleefd * float(s.leeft)
                + w.handel * min(s.handels, 20) / 20.0
                # BUGFIX: Schaal direct naar de vogelvrij-drempel (3 feiten) van world.py
                - w.feiten_straf * min(s.feiten, 3) / 3.0
                for s in stats
            ]
        )
        return f

    def _rang_normaliseer(self, f: np.ndarray) -> np.ndarray:
        n = len(f)
        orde = np.argsort(f)
        rangen = np.empty(n)
        rangen[orde] = np.arange(n) / max(1, n - 1)
        return rangen

    def _fitness_sharing(self, genomen: list[Genome], rang: np.ndarray) -> np.ndarray:
        """Niching: F' = F / massa. Hoge dichtheid van gelijkbare genomen => korting.
        Dit is de genetische arm van de anti-parasiet-verdediging."""
        g = np.array([x.g for x in genomen])
        d = np.linalg.norm(g[:, None, :] - g[None, :, :], axis=2)
        massa = np.exp(-((d / self.sigma_share) ** 2)).sum(axis=1)
        return rang / massa

    # ── clustering (greedy leaders) ──────────────────────────────────────
    def _clustertoewijzing(self, genomen: list[Genome]) -> list[int]:
        leiders: list[Genome] = []
        toewijzing: list[int] = []
        for g in genomen:
            for i, l in enumerate(leiders):
                if g.afstand(l) < self.delta_soort:
                    toewijzing.append(i)
                    break
            else:
                leiders.append(g)
                toewijzing.append(len(leiders) - 1)
        return toewijzing

    # ── selectie-operatoren ──────────────────────────────────────────────
    def _toernooi(self, fitness: np.ndarray, rng: np.random.Generator) -> int:
        idx = rng.integers(0, len(fitness), size=self.k)
        return int(idx[np.argmax(fitness[idx])])

    # ── Gecorrigeerde hoofdsimulatielus ───────────────────────────────────
    def volgende_generatie(
        self,
        genomen: list[Genome],
        stats: list[Momentopname],
        rng: np.random.Generator,
        doelgrootte: int,
        tick_per_gen: int,
        redding: bool,
    ) -> list[Genome]:
        n = len(genomen)
        if n < 2:
            return [Genome.willekeurig(rng) for _ in range(doelgrootte)]

        ruw = self._ruwe_fitness(genomen, stats, tick_per_gen)
        beste_i = int(np.argmax(ruw))
        self.hof.werk_bij(genomen[beste_i], float(ruw[beste_i]))

        rang = self._rang_normaliseer(ruw)
        gedeeld = self._fitness_sharing(genomen, rang)
        clusters = self._clustertoewijzing(genomen)
        cap = max(2, int(self.max_clusteraandeel * doelgrootte))

        kinderen: list[Genome] = [
            genomen[beste_i].kopie() for _ in range(min(self.elite, doelgrootte))
        ]
        telling: dict[int, int] = {}

        # Initialiseer telling voor de elite die we zojuist hebben toegevoegd
        for elite_kind in kinderen:
            beste_c, beste_d = 0, float("inf")
            gezien: set[int] = set()
            for i, c in enumerate(clusters):
                if c in gezien:
                    continue
                gezien.add(c)
                d = elite_kind.afstand(genomen[i])
                if d < beste_d:
                    beste_c, beste_d = c, d
            telling[beste_c] = telling.get(beste_c, 0) + 1

        def cluster_van_kind(kind: Genome) -> int:
            beste_c, beste_d = 0, float("inf")
            gezien: set[int] = set()
            for i, c in enumerate(clusters):
                if c in gezien:
                    continue
                gezien.add(c)
                d = kind.afstand(genomen[i])
                if d < beste_d:
                    beste_c, beste_d = c, d
            return beste_c

        def reserve_bron() -> Genome:
            if redding and self.hof.lijst and rng.random() < 0.67:
                k = self.hof.steekproef(rng).kopie()
                k.muteer(rng)
                return k
            return Genome.willekeurig(rng)

        # TOERNOOI LUS MET HARDE DIVERSITEITS-CHECK
        # BUGFIX: Stagnatiebewaking. Als alle kandidaten telkens op dezelfde
        # (volle) cluster uitkomen — bv. na een genetische bottleneck waarbij
        # er maar één cluster overblijft — kan de cap nooit voldaan worden en
        # loopt deze lus anders voor altijd door (permanente deadlock van de
        # generatiewissel). Na genoeg mislukte pogingen staan we de cap-check
        # toe te negeren zodat de lus altijd termineert.
        mislukte_pogingen = 0
        max_pogingen = max(200, 20 * doelgrootte)
        while len(kinderen) < doelgrootte:
            r = rng.random()
            if r < self.immigrant_quota:
                kind = Genome.willekeurig(rng)
            elif redding and rng.random() < 0.40:
                kind = self.hof.steekproef(rng).kopie()
                kind.muteer(rng)
            else:
                p1 = genomen[self._toernooi(gedeeld, rng)]
                p2 = genomen[self._toernooi(gedeeld, rng)]

                if p1.afstand(p2) < 0.08:  # Inteelt-barrière activeert
                    kind = reserve_bron()
                else:
                    # BUGFIX: Veilig kruisen en muteren op een kopie, niet op de levende ouders
                    kind = Genome.sbx_kruising(p1.kopie(), p2.kopie(), rng)
                    kind.muteer(rng)

            c_idx = cluster_van_kind(kind)

            # BUGFIX: Als het kind (of de reserve) de cluster-cap overschrijdt,
            # weigeren we het genoom direct en proberen we het in de volgende lus-iteratie opnieuw.
            if telling.get(c_idx, 0) >= cap and mislukte_pogingen < max_pogingen:
                mislukte_pogingen += 1
                continue  # Gooi het kind weg, voorkom cluster-explosie

            mislukte_pogingen = 0
            telling[c_idx] = telling.get(c_idx, 0) + 1
            kinderen.append(kind)

        return kinderen[:doelgrootte]
