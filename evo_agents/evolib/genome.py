"""Genetische code: 9 gedragsgenen + een zelfadaptieve sigma-vector."""
from __future__ import annotations
import numpy as np

GENE_NAMEN = (
    "agressie",
    "cooperatie",
    "hebzucht",
    "nieuwsgierigheid",
    "retentie",
    "vergeving",
    "sociabiliteit",
    "risico_aversie",
    "stofwisseling",
)
N_GENES = len(GENE_NAMEN)
SIGMA_MIN, SIGMA_MAX = 0.005, 0.35


class Genome:
    __slots__ = ("g", "sigma")

    def __init__(self, g, sigma=None):
        self.g = np.clip(np.asarray(g, dtype=np.float64), 0.0, 1.0)
        if sigma is None:
            self.sigma = np.full(N_GENES, 0.12)
        else:
            self.sigma = np.clip(np.asarray(sigma, dtype=np.float64), SIGMA_MIN, SIGMA_MAX)

    @classmethod
    def willekeurig(cls, rng: np.random.Generator) -> "Genome":
        return cls(rng.random(N_GENES), rng.uniform(0.03, 0.20, N_GENES))

    def waarde(self, naam: str) -> float:
        return float(self.g[GENE_NAMEN.index(naam)])

    def afstand(self, other: "Genome") -> float:
        return float(np.linalg.norm(self.g - other.g))

    def fenotype_bucket(self) -> tuple[int, int]:
        """Compressie naar 3x3 arche type-grid: (agressie-tier, cooperatie-tier)."""
        a = min(int(self.waarde("agressie") * 3), 2)
        c = min(int(self.waarde("cooperatie") * 3), 2)
        return (a, c)

    @classmethod
    def sbx_kruising(
        cls, p1: "Genome", p2: "Genome", rng: np.random.Generator, eta: float = 15.0
    ) -> "Genome":
        """Simulated Binary Crossover; kinderen clusteren rond de ouders."""
        u = rng.random(N_GENES)
        beta = np.where(
            u <= 0.5,
            (2.0 * u) ** (1.0 / (eta + 1.0)),
            (1.0 / (2.0 * np.maximum(1e-12, 1.0 - u))) ** (1.0 / (eta + 1.0)),
        )
        c1 = 0.5 * ((1.0 + beta) * p1.g + (1.0 - beta) * p2.g)
        c2 = 0.5 * ((1.0 - beta) * p1.g + (1.0 + beta) * p2.g)
        g = c1 if rng.random() < 0.5 else c2
        return cls(g, 0.5 * (p1.sigma + p2.sigma))

    def muteer(self, rng: np.random.Generator, p_macro: float = 0.02) -> "Genome":
        """Zelfadaptieve Gauss-mutatie (Schwefel) + macromutatie tegen stagnatie."""
        tau = 1.0 / np.sqrt(2.0 * N_GENES)
        self.sigma = np.clip(
            self.sigma * np.exp(tau * rng.standard_normal(N_GENES)),
            SIGMA_MIN,
            SIGMA_MAX,
        )
        self.g = np.clip(self.g + self.sigma * rng.standard_normal(N_GENES), 0.0, 1.0)
        if rng.random() < p_macro:
            self.g[rng.integers(N_GENES)] = rng.random()
        return self

    def kopie(self) -> "Genome":
        return Genome(self.g.copy(), self.sigma.copy())

    def __repr__(self) -> str:
        return "Genome({" + ", ".join(
            f"{n}: {self.g[i]:.2f}" for i, n in enumerate(GENE_NAMEN)
        ) + "})"
