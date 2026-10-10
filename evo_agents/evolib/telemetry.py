"""Telemetrielaag: stabiele datacontracten + ringbuffer-registratie +
JSONL-sink. Lees-only t.o.v. de wereld, RNG-vrij, thread-safe."""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from bisect import bisect_left
from collections import deque
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum

import numpy as np

from .genome import GENE_NAMEN, N_GENES
from .protocol import Res

TELEMETRI_SCHEMA = "evotelemetry/v1"


# ── 1. Datacontracten (bevroren; frontends kennen niets anders) ───────────
class GebeurtenisType(Enum):
    HANDEL_ESCROW = 1
    HANDEL_CREDIT = 2
    WANPRESTATIE = 3
    OVERVAL_WEL = 4
    OVERVAL_MISLUKT = 5
    DOOD_HONGER = 6
    VOGELVRIJ = 7


@dataclass(frozen=True)
class TikSteekproef:
    tik: int
    generatie: int
    populatie: int
    totale_bron: float
    ehi: float
    conflictmult: float
    vruchtbaarheid: float
    vogelvrij: int
    open_schulden: int
    parasitair: float  # aandeel (agressie>.6 & cooperatie<.3)
    coop_ema: float  # NaN vóór eerste relevante gebeurtenis
    gini_erts: float
    shannon: float
    gen_gem: tuple[float, ...]  # lengte 9, volgorde GENE_NAMEN
    gen_std: tuple[float, ...]
    bucket_tellingen: tuple[int, ...]  # lengte 9, index = a*3+c
    handels_per_100: int = 0
    totale_voedsel: float = 0.0
    totale_erts: float = 0.0
    ehi_voedsel: float = 0.0
    ehi_erts: float = 0.0


@dataclass(frozen=True)
class GeneratieSteekproef:
    generatie: int
    beste_fitness: float
    gemiddelde_fitness: float
    n_clusters: int
    hof_top: tuple[tuple[float, tuple[float, ...]], ...]
    component_gem: tuple[float, ...]  # gem. bijdragen: lev/rijkdom/nakom/overl/handel/straf
    gen_gem: tuple[float, ...] = ()
    gen_std: tuple[float, ...] = ()
    bucket_tellingen: tuple[int, ...] = ()


@dataclass(frozen=True)
class Gebeurtenis:
    tik: int
    type: GebeurtenisType
    actor_ids: tuple[int, ...]
    posities: tuple[tuple[int, int], ...]
    omvang: float


@dataclass(frozen=True)
class RuimtelijkeMomentopname:
    tik: int
    bronnen: tuple[tuple[int, int, int, float], ...]  # x, y, res-int, hoeveelheid
    agenten: tuple[tuple[int, int, int, tuple[int, int], float, bool], ...]
    # id, x, y, bucket, energiefractie, vogelvrij


# ── 2. Metrieken (exacte definities) ──────────────────────────────────────
def gini(waarden: np.ndarray) -> float:
    w = np.sort(np.asarray(waarden, dtype=float))
    n = w.size
    totaal = w.sum()
    if n == 0 or totaal <= 0.0:
        return 0.0
    cumsom = np.cumsum(w).sum()
    return float((n + 1.0 - 2.0 * cumsom / totaal) / n)


def shannon(tellingen: np.ndarray) -> float:
    p = tellingen[tellingen > 0].astype(float)
    tot = p.sum()
    if tot == 0.0:
        return 0.0
    p /= tot
    return float(-(p * np.log(p)).sum())


def lttb(xs: np.ndarray, ys: np.ndarray, m: int = 900) -> tuple[np.ndarray, np.ndarray]:
    """Largest-Triangle-Three-Buckets: downsampling met vormbehoud."""
    n = xs.size
    if m >= n or m < 3:
        return xs, ys
    kx = np.empty(m)
    ky = np.empty(m)
    kx[0], ky[0] = xs[0], ys[0]
    kx[-1], ky[-1] = xs[-1], ys[-1]
    emmer = (n - 2) / (m - 2)
    a = 0
    for i in range(1, m - 1):
        s = min(max(int(math.floor((i - 1) * emmer)) + 1, 1), n - 1)
        e = min(max(int(math.floor(i * emmer)) + 1, s + 1), n)
        sv = min(max(int(math.floor(i * emmer)) + 1, 1), n - 1)
        ev = min(max(int(math.floor((i + 1) * emmer)) + 1, sv + 1), n)
        gem_x = float(xs[sv:ev].mean()) if ev > sv else float(xs[-1])
        gem_y = float(ys[sv:ev].mean()) if ev > sv else float(ys[-1])
        ax, ay = xs[a], ys[a]
        opp = np.abs((gem_x - ax) * (ys[s:e] - ay) - (gem_y - ay) * (xs[s:e] - ax))
        k = s + int(np.argmax(opp))
        kx[i], ky[i] = xs[k], ys[k]
        a = k
    return kx, ky


# ── 3. JSON-hulp (Enum-veilig) ────────────────────────────────────────────
def _json_klaar(o):
    if isinstance(o, Enum):
        return o.name
    if isinstance(o, (tuple, list)):
        return [_json_klaar(v) for v in o]
    if isinstance(o, dict):
        return {k: _json_klaar(v) for k, v in o.items()}
    return o


# ── 4. Registratie ────────────────────────────────────────────────────────
_COOP_GEWICHT = {
    GebeurtenisType.HANDEL_ESCROW: 1.0,
    GebeurtenisType.HANDEL_CREDIT: 1.0,
    GebeurtenisType.OVERVAL_WEL: 0.0,
}


class TelemetrieRegistratie:
    def __init__(
        self,
        sink_pad: str | None = None,
        cap_tikken: int = 20000,
        cap_gebeurtenissen: int = 60000,
        cap_ruimtelijk: int = 1500,
        ruimtelijk_interval: int = 5,
    ):
        self.lock = threading.RLock()
        self.tikken: deque[TikSteekproef] = deque(maxlen=cap_tikken)
        self.generaties: deque[GeneratieSteekproef] = deque(maxlen=512)
        self.gebeurtenissen: deque[Gebeurtenis] = deque(maxlen=cap_gebeurtenissen)
        self.ruimtelijk: deque[RuimtelijkeMomentopname] = deque(maxlen=cap_ruimtelijk)
        self.ruimtelijk_interval = ruimtelijk_interval
        self.header: dict = {"schema": TELEMETRI_SCHEMA}
        self._coop_ema = float("nan")
        self._ruimtelijk_teller = 0
        self._handels_historie: deque[int] = deque(maxlen=2000)
        self._cached_tik_arrays: dict[str, np.ndarray] | None = None
        self._cached_tik_array_tik: int = -1
        self._sink = None
        if sink_pad:
            self.open_sink(sink_pad)

    # ── sink ─────────────────────────────────────────────────────────────
    def open_sink(self, pad: str, overschrijven: bool = True) -> None:
        os.makedirs(os.path.dirname(pad) or ".", exist_ok=True)
        self._sink = open(pad, "w" if overschrijven else "a", encoding="utf-8")
        self._schrijf("header", self.header)

    def koppel_header(self, seed: int, config: dict) -> None:
        self.header.update(
            {
                "seed": int(seed),
                "tijdstip": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "config_hash": hashlib.sha1(
                    repr(sorted(config.items())).encode("utf-8")
                ).hexdigest()[:12],
                "config": config,
            }
        )
        if self._sink is not None:
            self._schrijf("header", self.header)

    def _schrijf(self, soort: str, obj) -> None:
        if self._sink is None:
            return
        data = asdict(obj) if is_dataclass(obj) else obj
        self._sink.write(
            json.dumps(
                {"soort": soort, "data": _json_klaar(data)},
                allow_nan=True,
            )
            + "\n"
        )
        self._sink.flush()

    # ── observer-API (door Wereld aangeroepen) ───────────────────────────
    def na_tik(self, wereld) -> None:
        levend = [a for a in wereld.agents.values() if a.levend]
        if not math.isnan(self._coop_ema):
            self._coop_ema = 0.999 * self._coop_ema + 0.001 * 0.50
        n = len(levend)
        if n:
            genmat = np.array([a.genoom.g for a in levend])
            gem = genmat.mean(axis=0)
            std = genmat.std(axis=0)
            buckets = np.zeros(9, dtype=int)
            for a in levend:
                buckets[a.bucket[0] * 3 + a.bucket[1]] += 1
            parasitair = float(
                np.mean(
                    [
                        1.0
                        if (
                            a.genoom.waarde("agressie") > 0.6
                            and a.genoom.waarde("cooperatie") < 0.3
                        )
                        else 0.0
                        for a in levend
                    ]
                )
            )
        else:
            gem = np.zeros(N_GENES)
            std = np.zeros(N_GENES)
            buckets = np.zeros(9, dtype=int)
            parasitair = 0.0
        bron_tot = wereld.totale_bron()
        ehi = wereld.gov.gezondheidsindex(bron_tot)
        h100 = sum(1 for t in self._handels_historie if t >= wereld.tick - 100)
        bron_per_type = wereld.totale_bron_per_type()
        ehi_per_type = wereld.ehi_per_type()
        rec = TikSteekproef(
            tik=wereld.tick,
            generatie=wereld.tick // max(1, getattr(wereld, "tick_per_gen", 300)),
            populatie=n,
            totale_bron=round(bron_tot, 2),
            ehi=ehi,
            conflictmult=wereld.conflictkostenfactor(),
            vruchtbaarheid=wereld.gov.vruchtbaarheidsfactor(ehi),
            vogelvrij=len(wereld.vogelvrij_set),
            open_schulden=len(wereld.schulden),
            parasitair=parasitair,
            coop_ema=self._coop_ema,
            gini_erts=gini(np.array([a.erts for a in levend]) if n else np.zeros(1)),
            shannon=shannon(buckets),
            gen_gem=tuple(float(v) for v in gem),
            gen_std=tuple(float(v) for v in std),
            bucket_tellingen=tuple(int(v) for v in buckets),
            handels_per_100=h100,
            totale_voedsel=round(bron_per_type[Res.VOEDSEL], 2),
            totale_erts=round(bron_per_type[Res.ERTS], 2),
            ehi_voedsel=ehi_per_type[Res.VOEDSEL],
            ehi_erts=ehi_per_type[Res.ERTS],
        )
        with self.lock:
            self.tikken.append(rec)
            self._schrijf("tik", rec)
            self._misschien_ruimtelijk(wereld)

    def na_generatie(self, wereld, motor) -> None:
        arch = list(wereld.generatie_archief)
        if not arch:
            return
        genomen = [g for g, _ in arch]
        stats = [s for _, s in arch]
        tpg = max(1, getattr(wereld, "tick_per_gen", 300))
        f = motor._ruwe_fitness(genomen, stats, tpg)
        w = motor.w
        comp = (
            float(np.mean([(s.levensduur / tpg) * w.levensduur for s in stats])),
            float(np.mean([(s.erts / 40.0) * w.rijkdom for s in stats])),
            float(np.mean([s.nakomelingen * w.nakomelingen for s in stats])),
            float(np.mean([float(s.leeft) * w.overleefd for s in stats])),
            float(np.mean([min(s.handels, 20) / 20.0 * w.handel for s in stats])),
            float(np.mean([-min(s.feiten, 3) / 3.0 * w.feiten_straf for s in stats])),
        )
        genmat = np.array([g.g for g in genomen])
        gem = genmat.mean(axis=0) if len(genomen) else np.zeros(N_GENES)
        std = genmat.std(axis=0) if len(genomen) else np.zeros(N_GENES)
        buckets = np.zeros(9, dtype=int)
        for g in genomen:
            b = g.fenotype_bucket()
            buckets[b[0] * 3 + b[1]] += 1
        rec = GeneratieSteekproef(
            generatie=wereld.tick // tpg,
            beste_fitness=float(f.max()),
            gemiddelde_fitness=float(f.mean()),
            n_clusters=len(set(motor._clustertoewijzing(genomen))),
            hof_top=tuple(
                (round(fit, 4), tuple(float(v) for v in g.g))
                for fit, g in motor.hof.lijst[:3]
            ),
            component_gem=comp,
            gen_gem=tuple(float(v) for v in gem),
            gen_std=tuple(float(v) for v in std),
            bucket_tellingen=tuple(int(v) for v in buckets),
        )
        with self.lock:
            self.generaties.append(rec)
            self._schrijf("generatie", rec)

    def gebeurtenis(self, g: Gebeurtenis) -> None:
        if g.type in (GebeurtenisType.HANDEL_ESCROW, GebeurtenisType.HANDEL_CREDIT):
            self._handels_historie.append(g.tik)
        wgt = _COOP_GEWICHT.get(g.type)
        if wgt is not None:
            self._coop_ema = (
                wgt
                if math.isnan(self._coop_ema)
                else 0.92 * self._coop_ema + 0.08 * wgt
            )
        with self.lock:
            self.gebeurtenissen.append(g)
            self._schrijf("gebeurtenis", g)

    def _misschien_ruimtelijk(self, wereld) -> None:
        self._ruimtelijk_teller += 1
        if self._ruimtelijk_teller % self.ruimtelijk_interval != 0:
            return
        bronnen = tuple(
            (b.x, b.y, int(b.res.value), round(b.hoeveelheid, 2))
            for b in wereld.grid.values()
            if b.hoeveelheid > 0.05
        )
        agenten = tuple(
            (
                a.id,
                a.pos[0],
                a.pos[1],
                (a.bucket[0], a.bucket[1]),
                round(a.energie / a.max_energie, 3),
                bool(a.vogelvrij),
            )
            for a in wereld.agents.values()
            if a.levend
        )
        snap = RuimtelijkeMomentopname(tik=wereld.tick, bronnen=bronnen, agenten=agenten)
        self.ruimtelijk.append(snap)
        self._schrijf("ruimtelijk", snap)

    # ── lees-API (kopieer-onder-lock; teken buiten de lock!) ─────────────
    def laatste_tik_steekproef(self) -> TikSteekproef | None:
        """Geeft de meest recente tik-steekproef terug in O(1) zonder array-conversies."""
        with self.lock:
            return self.tikken[-1] if self.tikken else None

    def tik_arrays(self) -> dict[str, np.ndarray]:
        with self.lock:
            if not self.tikken:
                return {}
            laatste_tik_nr = self.tikken[-1].tik
            if self._cached_tik_arrays is not None and self._cached_tik_array_tik == laatste_tik_nr:
                return self._cached_tik_arrays
            buf = list(self.tikken)

        veld = lambda naam: np.array([getattr(r, naam) for r in buf], dtype=float)
        uit = {
            k: veld(k)
            for k in (
                "tik",
                "generatie",
                "populatie",
                "totale_bron",
                "ehi",
                "conflictmult",
                "vruchtbaarheid",
                "vogelvrij",
                "open_schulden",
                "parasitair",
                "coop_ema",
                "gini_erts",
                "shannon",
                "handels_per_100",
                "totale_voedsel",
                "totale_erts",
                "ehi_voedsel",
                "ehi_erts",
            )
        }
        uit["gen_gem"] = np.array([r.gen_gem for r in buf])  # (T, 9)
        uit["gen_std"] = np.array([r.gen_std for r in buf])
        uit["buckets"] = np.array([r.bucket_tellingen for r in buf], dtype=int)

        with self.lock:
            self._cached_tik_arrays = uit
            self._cached_tik_array_tik = laatste_tik_nr
        return uit

    def generatie_lijst(self) -> list[GeneratieSteekproef]:
        with self.lock:
            return list(self.generaties)

    def laatste_ruimtelijk(self) -> RuimtelijkeMomentopname | None:
        with self.lock:
            return self.ruimtelijk[-1] if self.ruimtelijk else None

    def ruimtelijk_in_de_buurt(self, tik: int) -> RuimtelijkeMomentopname | None:
        with self.lock:
            if not self.ruimtelijk:
                return None
            tiks = [s.tik for s in self.ruimtelijk]
            i = bisect_left(tiks, tik)
            i = min(i, len(tiks) - 1)
            return self.ruimtelijk[i]

    def gebeurtenis_matrix(self) -> tuple[np.ndarray, np.ndarray]:
        with self.lock:
            buf = list(self.gebeurtenissen)
        if not buf:
            return np.zeros(0), np.zeros(0)
        return (
            np.array([g.tik for g in buf], dtype=float),
            np.array([g.type.value for g in buf], dtype=int),
        )

    def recente_gebeurtenissen(self, k: int = 50) -> list[Gebeurtenis]:
        with self.lock:
            buf = list(self.gebeurtenissen)
        return buf[-k:]

    # ── replay ───────────────────────────────────────────────────────────
    @classmethod
    def laad_uit_bestand(cls, pad: str) -> "TelemetrieRegistratie":
        reg = cls()
        enum_terug = {e.name: e for e in GebeurtenisType}
        with open(pad, encoding="utf-8") as fh:
            for regel in fh:
                regel = regel.strip()
                if not regel:
                    continue
                try:
                    bericht = json.loads(regel)
                except Exception:
                    continue
                soort, d = bericht.get("soort"), bericht.get("data")
                if not soort or not d:
                    continue
                if soort == "header":
                    reg.header = d
                elif soort == "tik":
                    if "gen_gem" in d:
                        d["gen_gem"] = tuple(d["gen_gem"])
                    if "gen_std" in d:
                        d["gen_std"] = tuple(d["gen_std"])
                    if "bucket_tellingen" in d:
                        d["bucket_tellingen"] = tuple(d["bucket_tellingen"])
                    reg.tikken.append(TikSteekproef(**d))
                elif soort == "generatie":
                    if "hof_top" in d:
                        d["hof_top"] = tuple(
                            (fit, tuple(g)) for fit, g in d["hof_top"]
                        )
                    if "component_gem" in d:
                        d["component_gem"] = tuple(d["component_gem"])
                    if "gen_gem" in d:
                        d["gen_gem"] = tuple(d["gen_gem"])
                    if "gen_std" in d:
                        d["gen_std"] = tuple(d["gen_std"])
                    if "bucket_tellingen" in d:
                        d["bucket_tellingen"] = tuple(d["bucket_tellingen"])
                    reg.generaties.append(GeneratieSteekproef(**d))
                elif soort == "gebeurtenis":
                    if isinstance(d.get("type"), str):
                        d["type"] = enum_terug.get(
                            d["type"], GebeurtenisType.HANDEL_ESCROW
                        )
                    if "actor_ids" in d:
                        d["actor_ids"] = tuple(d["actor_ids"])
                    if "posities" in d:
                        d["posities"] = tuple(tuple(p) for p in d["posities"])
                    reg.gebeurtenissen.append(Gebeurtenis(**d))
                elif soort == "ruimtelijk":
                    if "bronnen" in d:
                        d["bronnen"] = tuple(tuple(b) for b in d["bronnen"])
                    if "agenten" in d:
                        d["agenten"] = tuple(
                            (a[0], a[1], a[2], tuple(a[3]), a[4], a[5])
                            for a in d["agenten"]
                        )
                    reg.ruimtelijk.append(RuimtelijkeMomentopname(**d))
        return reg

    def sluit(self) -> None:
        if self._sink is not None:
            self._sink.close()
            self._sink = None
