"""Ecosysteemgouverneur: GEEN strategie, uitsluitend negatieve terugkoppelingen
die de fysica van de simulatie vormgeven (cf. draagkracht, seizoenen, justitie)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class EcoInstellingen:
    draagkracht: float = 1560.0  # som van alle broncapaciteiten
    vruchtbaar_drempel: float = 0.45
    conflict_cap: float = 0.60  # max. tolerant aandeel agressieve fenotypes
    min_populatie: int = 14
    min_clusters: int = 4


class EcosysteemGouverneur:
    def __init__(self, instellingen: EcoInstellingen | None = None):
        self.inst = instellingen or EcoInstellingen()

    def gezondheidsindex(self, totaal_bron: float) -> float:
        return max(0.0, min(1.0, totaal_bron / self.inst.draagkracht))

    def vruchtbaarheidsfactor(self, ehi: float) -> float:
        """Demografische poort: bij lage EHI daalt de reproductiekans steil naar 0.04.
        Breekt het Malthusiaanse armoede-evenwicht en geeft biomassa ruimte om te herstellen."""
        if ehi < self.inst.vruchtbaar_drempel:
            # Kwadratische demping onder drempel (0.45): bij EHI 0.20 is vruchtbaarheid slechts ~0.08
            return max(0.04, 0.50 * ((ehi / self.inst.vruchtbaar_drempel) ** 2))
        else:
            # Lineaire schaling richting 1.0 bij overvloed
            return min(
                1.0,
                0.50
                + 0.50
                * (
                    (ehi - self.inst.vruchtbaar_drempel)
                    / (1.0 - self.inst.vruchtbaar_drempel)
                ),
            )

    def conflictkostenfactor(self, roofdruk_ema: float) -> float:
        """Frequentie-afhankelijke selectie op gerealiseerde roofdruk (EMA).
        Wanneer roofdruk boven drempel θ = 0.03 stijgt, schiet de belasting op oorlog omhoog."""
        drempel = 0.03
        if roofdruk_ema <= drempel:
            return 1.0
        overschot = roofdruk_ema - drempel
        return 1.0 + 5.0 * (overschot**2)

    def redding_nodig(self, n_levend: int, n_clusters: int) -> bool:
        return n_levend < self.inst.min_populatie or n_clusters < self.inst.min_clusters
