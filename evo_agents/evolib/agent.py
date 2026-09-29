from __future__ import annotations
import itertools
from dataclasses import dataclass

import numpy as np

from .genome import Genome
from .memory import Episode, SociaalGeheugen
from .policy import RES_ATTR, Beleid
from .protocol import Actie, ActieType, Res


@dataclass
class AgentStatistiek:
    geboorte_tick: int = 0
    dood_tick: int | None = None
    nakomelingen: int = 0
    feiten: int = 0  # geregistreerde wanprestaties
    kills: int = 0
    handels: int = 0

    def momentopname(self, tick: int) -> "Momentopname":
        leeft = self.dood_tick is None
        from .evolution import Momentopname

        return Momentopname(
            levensduur=(self.dood_tick or tick) - self.geboorte_tick,
            erts=-1.0,  # wordt door de wereld ingevuld
            nakomelingen=self.nakomelingen,
            handels=self.handels,
            feiten=self.feiten,
            leeft=leeft,
        )


class Agent:
    _ids = itertools.count(1)

    def __init__(
        self,
        genoom: Genome,
        wereld,
        positie: tuple[int, int],
        energie: float = 70.0,
    ):
        self.id = next(Agent._ids)
        self.genoom = genoom
        self.wereld = wereld
        self.pos = positie
        self.energie = energie
        self.max_energie = 90.0 + 50.0 * (1.0 - genoom.waarde("stofwisseling"))  # geen gratis lunch
        self.voedsel: int = 2
        self.erts: int = 0
        self.levend = True
        self.vogelvrij = False
        self.stat = AgentStatistiek(geboorte_tick=wereld.tick)
        self.geheugen = SociaalGeheugen(
            vergeving=genoom.waarde("vergeving"),
            retentie=genoom.waarde("retentie"),
        )
        self.beleid = Beleid(self)

    @property
    def bucket(self) -> tuple[int, int]:
        return self.genoom.fenotype_bucket()

    def voorraad(self, res: Res) -> int:
        return getattr(self, RES_ATTR[res])

    def ontvang(self, res: Res, n: int) -> None:
        setattr(self, RES_ATTR[res], getattr(self, RES_ATTR[res]) + n)

    def geef_af(self, res: Res, n: int) -> None:
        setattr(self, RES_ATTR[res], getattr(self, RES_ATTR[res]) - n)

    def neem_waar(self):
        return self.wereld.bouw_perceptie(self)

    def stap(self, rng: np.random.Generator) -> float:
        """Eén besliscyclus. Geeft de metabole kost van deze tick terug."""
        actie = self.beleid.kies_actie(self.neem_waar(), rng)
        return self.wereld.voer_uit(actie, self, rng)

    def eet_automatisch(self) -> None:
        if self.energie < 0.6 * self.max_energie and self.voedsel > 0:
            self.voedsel -= 1
            self.energie = min(self.max_energie, self.energie + 11.0)

    def onthoud(
        self,
        peer_id: int,
        peer_bucket: tuple[int, int],
        soort: str,
        mijn_actie: str,
        diens_actie: str,
        valentie: float,
    ) -> None:
        self.geheugen.registreer(
            Episode(
                self.wereld.tick,
                peer_id,
                peer_bucket,
                soort,
                mijn_actie,
                diens_actie,
                valentie,
            )
        )

    def overlijd(self) -> None:
        self.levend = False
        self.stat.dood_tick = self.wereld.tick
