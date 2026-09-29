"""Minimale onderhandelingstaal met cryptografische integriteit.
Bedrogdetectie = (1) HMAC-handtekeningen + replay-bescherming,
(2) notariële afwikkeling door de wereld (escrow / schuldenledger),
(3) sociaal: feiten + geruchten in de geheugens van getuigen."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from enum import Enum, auto

MAX_RONDES = 3
MAX_LOT = 8          # protocolmaximum voedsel-eenheden per bod
P_MIN = 0.05         # prijsklem: erts per voedsel
P_MAX = 40.0


class Res(Enum):
    VOEDSEL = 0
    ERTS = 1


@dataclass(frozen=True)
class Partij:
    res: Res
    hoeveelheid: int


@dataclass(frozen=True)
class Bod:
    """Ruilvoorstel met expliciete prijsconventie.
    Canoniek: P = erts per 1 voedsel, richting-onafhankelijk.
    kant='ASK': bieder verkoopt voedsel (geeft=VOEDSEL, vraagt=ERTS).
    kant='BID': bieder koopt voedsel   (geeft=ERTS, vraagt=VOEDSEL)."""

    geeft: Partij
    vraagt: Partij

    @property
    def kant(self) -> str:
        return "ASK" if self.geeft.res is Res.VOEDSEL else "BID"

    @property
    def prijs(self) -> float:
        """Gerealiseerde canonieke prijs (erts per voedsel) uit de integers."""
        if self.kant == "ASK":
            return self.vraagt.hoeveelheid / max(1, self.geeft.hoeveelheid)
        return self.geeft.hoeveelheid / max(1, self.vraagt.hoeveelheid)

    @classmethod
    def met_prijs(cls, kant: str, prijs: float, lot_voedsel: int) -> "Bod":
        """Realiseer canonieke prijs P in gehele hoeveelheden (deterministisch):
        tegen = max(1, round(lot·P)). De lot-optimizer in policy evalueert
        precies díze integer-termen, dus de quote is exact wat geoptimaliseerd is."""
        p = float(min(P_MAX, max(P_MIN, prijs)))
        lot = max(1, int(lot_voedsel))
        tegen = max(1, int(round(lot * p)))
        if kant == "ASK":
            return cls(Partij(Res.VOEDSEL, lot), Partij(Res.ERTS, tegen))
        return cls(Partij(Res.ERTS, tegen), Partij(Res.VOEDSEL, lot))

    @classmethod
    def van_ratio(cls, geeft: Partij, vraagt: Partij) -> "Bod":
        return cls(geeft, vraagt)

    def valideer_fysisch(self, eiser_voorraad_geef: int) -> bool:
        if self.geeft.hoeveelheid <= 0 or self.vraagt.hoeveelheid <= 0:
            return False
        if self.geeft.hoeveelheid > MAX_LOT or self.vraagt.hoeveelheid > MAX_LOT:
            return False
        return eiser_voorraad_geef >= self.geeft.hoeveelheid


class Wijze(Enum):
    ESCROW = auto()  # wereld als notaris: atomisch, 5% courtage, geen risico
    CREDIT = auto()  # op vertrouwen: gratis, risico op wanprestatie


class BerichtType(Enum):
    OPEN = auto()
    TEGENBOD = auto()
    ACCEPTEER = auto()
    WEIGER = auto()


@dataclass(frozen=True)
class Bericht:
    zender: int
    ontvanger: int
    type: BerichtType
    bod: Bod | None
    wijze: Wijze | None
    ronde: int
    seq: int
    handtekening: bytes = b""


@dataclass(frozen=True)
class TegenpartijView:
    """Alles wat een agent officieel over een ander 'ziet' tijdens handelen."""
    id: int
    bucket: tuple[int, int]
    vertrouwen: float
    erts_geschat: float
    energie_fractie: float
    vogelvrij: bool


class ActieType(Enum):
    BEWEEG = auto()
    OOGST = auto()
    AANVAL = auto()
    HANDEL = auto()
    RUST = auto()


@dataclass(frozen=True)
class Actie:
    type: ActieType
    doel_id: int | None = None
    bron_xy: tuple[int, int] | None = None
    richting: tuple[int, int] | None = None


class BerichtSigneerder:
    """HMAC-notariaat. Monotone seq per (zender, ontvanger) => replay-detectie."""

    def __init__(self, sessiesleutel: bytes):
        self.sleutel = sessiesleutel
        self._seq: dict[tuple[int, int], int] = {}

    def volgende_seq(self, zender: int, ontvanger: int) -> int:
        k = (zender, ontvanger)
        self._seq[k] = self._seq.get(k, 0) + 1
        return self._seq[k]

    def _payload(self, b: Bericht) -> bytes:
        return repr(
            (
                b.zender,
                b.ontvanger,
                b.type.name,
                str(b.bod),
                str(b.wijze),
                b.ronde,
                b.seq,
            )
        ).encode("utf-8")

    def signeer(self, b: Bericht) -> bytes:
        return hmac.new(self.sleutel, self._payload(b), hashlib.blake2b).digest()

    def verifieer(self, b: Bericht, verwachte_seq: int) -> bool:
        if b.seq != verwachte_seq:  # replay of gap
            return False
        return hmac.compare_digest(b.handtekening, self.signeer(b))


def onderhandel(wereld, a, b, rng):
    """Afwisselende-biedingen FSM met ronde-doorgifte voor concessiecurven."""
    va = wereld.tegenpartij_view(a.id, b.id)
    vb = wereld.tegenpartij_view(b.id, a.id)
    aanbieder, antwoorder = a, b
    bod, wijze = aanbieder.beleid.openingsbod(va, rng)
    if bod is None:
        return None
    for ronde in range(MAX_RONDES):
        wereld.registreer_bericht(
            aanbieder.id,
            antwoorder.id,
            BerichtType.OPEN if ronde == 0 else BerichtType.TEGENBOD,
            bod,
            wijze,
            ronde,
        )
        view = vb if antwoorder is b else va
        beslissing, tegenbod, tegenwijze = antwoorder.beleid.evalueer_bod(
            bod, wijze, view, ronde, rng
        )
        if beslissing == "ACCEPTEER":
            wereld.registreer_bericht(
                antwoorder.id,
                aanbieder.id,
                BerichtType.ACCEPTEER,
                bod,
                wijze,
                ronde,
            )
            return wereld.wikkel_af(aanbieder, antwoorder, bod, wijze)
        if beslissing == "WEIGER" or tegenbod is None:
            wereld.registreer_bericht(
                antwoorder.id,
                aanbieder.id,
                BerichtType.WEIGER,
                None,
                None,
                ronde,
            )
            return None
        aanbieder, antwoorder = antwoorder, aanbieder
        bod, wijze = tegenbod, (tegenwijze or wijze)
    return None
