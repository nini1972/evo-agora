"""Drie-lagen geheugen: episodische ringbuffer (recall) ->
reputatie-EMA (O(1)-samenvatting) -> arche type-prior (generalisatie).
Compressie gebeurt STREAMEND bij arrivement; de buffer vult nooit 'het venster'
want beslissingen lezen uitsluitend de samengevatte lagen + top-K gelijkenissen."""
from __future__ import annotations
import hashlib
import math
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Episode:
    tick: int
    peer_id: int
    peer_bucket: tuple[int, int]
    soort: str  # "handel" | "overval" | "gerucht" | "schulden" | "feit" | "vecht"
    mijn_actie: str
    diens_actie: str
    valentie: float  # in [-1, +1]


@dataclass
class Reputatie:
    ema: float = 0.5  # genormaliseerd vertrouwen in [0, 1]
    n: int = 0
    laatste_tick: int = 0
    verraak_count: int = 0


class CasusEncoder:
    """Deterministische feature-hashing embedding (vervangbaar door een
    geleerde encoder: zelfde interface, zelfde cosinus-semantiek)."""
    DIM = 512

    @staticmethod
    def encode(features: list[str]) -> np.ndarray:
        v = np.zeros(CasusEncoder.DIM)
        for f in features:
            h = hashlib.blake2b(f.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % CasusEncoder.DIM
            teken = 1.0 if (h[4] & 1) else -1.0
            v[idx] += teken
        n = float(np.linalg.norm(v))
        return v / n if n > 0.0 else v


class SociaalGeheugen:
    def __init__(
        self,
        vergeving: float,
        retentie: float,
        episodische_cap: int = 24,
        basis_alpha: float = 0.35,
        shrinkage_m: float = 4.0,
    ):
        self.episodisch: deque[Episode] = deque(maxlen=episodische_cap)
        self.episodisch_vec: deque[np.ndarray] = deque(maxlen=episodische_cap)
        self.reputaties: dict[int, Reputatie] = {}
        self.archetypen: dict[tuple[int, int], tuple[float, float]] = {}  # bucket -> (som, n)
        # Asymmetrische leersnelheden uit het 'vergeving'-gen:
        self.alpha_pos = basis_alpha * (0.3 + 0.7 * vergeving)  # wraakzucht: positiefs tellen nauwelijks
        self.alpha_neg = basis_alpha * (1.6 - 0.6 * vergeving)  # wraakzucht: negatiefs wegen dubbel
        self.tau_horizon = 150.0 + 900.0 * retentie  # geheugenverval-schaal
        self.shrinkage_m = shrinkage_m

    # ── schrijven ────────────────────────────────────────────────────────
    def registreer(self, ep: Episode) -> None:
        if len(self.episodisch) == self.episodisch.maxlen:
            self.episodisch.popleft()  # vergeet oudste rauwe episode
            self.episodisch_vec.popleft()
        self.episodisch.append(ep)
        self.episodisch_vec.append(
            CasusEncoder.encode(
                [
                    f"soort={ep.soort}",
                    f"bucket={ep.peer_bucket}",
                    f"ik={ep.mijn_actie}",
                    f"ander={ep.diens_actie}",
                ]
            )
        )
        self._vouw_reputatie(ep)  # logische samenvatting, O(1)
        self._vouw_archetype(ep.peer_bucket, ep.valentie)

    def _vouw_reputatie(self, ep: Episode) -> None:
        rep = self.reputaties.setdefault(ep.peer_id, Reputatie())
        alpha = self.alpha_pos if ep.valentie >= 0.0 else self.alpha_neg
        s = 0.5 + 0.5 * max(-1.0, min(1.0, ep.valentie))
        rep.ema = (1.0 - alpha) * rep.ema + alpha * s
        rep.n += 1
        rep.laatste_tick = ep.tick
        if ep.valentie <= -0.5:
            rep.verraak_count += 1

    def _vouw_archetype(self, bucket: tuple[int, int], valentie: float) -> None:
        som, n = self.archetypen.get(bucket, (0.0, 0))
        self.archetypen[bucket] = (som + (0.5 + 0.5 * valentie), n + 1)

    # ── lezen ────────────────────────────────────────────────────────────
    def archetype_prior(self, bucket: tuple[int, int]) -> float:
        som, n = self.archetypen.get(bucket, (0.0, 0))
        return (som + self.shrinkage_m * 0.5) / (n + self.shrinkage_m)

    def vertrouwen(self, tick: int, peer_id: int, peer_bucket: tuple[int, int]) -> float:
        """Persoonlijke ervaring (met tijdsverval) gegoten met archetype-prior."""
        rep = self.reputaties.get(peer_id)
        prior = self.archetype_prior(peer_bucket)
        if rep is None or rep.n == 0:
            return prior
        vervaging = math.exp(-(tick - rep.laatste_tick) / self.tau_horizon)
        t_persoon = 0.5 + (rep.ema - 0.5) * vervaging
        c = rep.n / (rep.n + 3.0)  # betrouwbaarheid persoonlijke data
        return c * t_persoon + (1.0 - c) * prior

    def gelijkende_casus(
        self, soort: str, peer_bucket: tuple[int, int], mijn_actie: str
    ) -> float | None:
        """Case-based hint: valentie van de meest gelijkende opgeslagen episode."""
        q = CasusEncoder.encode(
            [f"soort={soort}", f"bucket={peer_bucket}", f"ik={mijn_actie}", "ander=*"]
        )
        beste, beste_sim = None, 0.05
        for ep, v in zip(self.episodisch, self.episodisch_vec):
            sim = float(np.dot(q, v))
            if sim > beste_sim:
                beste, beste_sim = ep, sim
        return beste.valentie if beste is not None else None
