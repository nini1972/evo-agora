"""Unit tests voor de micro-economische prijs- en handelsmotor."""
import numpy as np
import pytest

from evolib.agent import Agent
from evolib.genome import Genome
from evolib.policy import Beleid, ERTS_WAARDE, VOEDSELENERGIE
from evolib.protocol import Bod, Partij, Res, Wijze, onderhandel
from evolib.world import Wereld


def test_concave_nut_en_afnemende_meeropbrengst():
    """Gossen's eerste wet: marginale utiliteit moet strikt dalend zijn."""
    rng = np.random.default_rng(42)
    w = Wereld(rng=rng)
    g = Genome.willekeurig(rng)
    a = Agent(g, w, (0, 0))
    b = Beleid(a)

    # Marginaal nut van 1e, 2e, 3e eenheid voedsel
    mu_v1 = b.waarde(Res.VOEDSEL, 1) - b.waarde(Res.VOEDSEL, 0)
    mu_v2 = b.waarde(Res.VOEDSEL, 2) - b.waarde(Res.VOEDSEL, 1)
    mu_v3 = b.waarde(Res.VOEDSEL, 3) - b.waarde(Res.VOEDSEL, 2)
    assert mu_v1 > mu_v2 > mu_v3 > 0.0, "Marginale voedselutiliteit moet strikt dalend zijn!"

    # Marginaal nut van 1e, 2e, 3e eenheid erts
    mu_e1 = b.waarde(Res.ERTS, 1) - b.waarde(Res.ERTS, 0)
    mu_e2 = b.waarde(Res.ERTS, 2) - b.waarde(Res.ERTS, 1)
    mu_e3 = b.waarde(Res.ERTS, 3) - b.waarde(Res.ERTS, 2)
    assert mu_e1 > mu_e2 > mu_e3 > 0.0, "Marginale ertsutiliteit moet strikt dalend zijn!"


def test_honger_drijft_reserveringsprijs_op():
    """Als een agent honger heeft (lage energie), stijgt zijn reservatieprijs (rho) voor voedsel."""
    rng = np.random.default_rng(42)
    w = Wereld(rng=rng)
    g = Genome.willekeurig(rng)

    a_vol = Agent(g, w, (0, 0), energie=90.0)
    a_honger = Agent(g, w, (0, 0), energie=10.0)

    rho_vol = a_vol.beleid.reserveringsprijs()
    rho_honger = a_honger.beleid.reserveringsprijs()

    assert rho_honger > rho_vol, f"Hongerige agent moet hogere voedselprijs hebben! ({rho_honger:.2f} vs {rho_vol:.2f})"


def test_onderhandeling_tussen_complementaire_agenten():
    """Agent A heeft voedseloverschot en zoekt erts; Agent B heeft ertsoverschot en zoekt voedsel."""
    rng = np.random.default_rng(42)
    w = Wereld(rng=rng)

    # Maak coöperatieve agenten
    g_coop = Genome(np.array([0.1, 0.9, 0.5, 0.5, 0.5, 0.5, 0.8, 0.3, 0.5]))
    a = Agent(g_coop, w, (0, 0))
    b = Agent(g_coop, w, (0, 1))
    w.agents[a.id] = a
    w.agents[b.id] = b

    # A: rijk aan voedsel (6), geen erts (0)
    a.voedsel = 6
    a.erts = 0
    # B: rijk aan erts (10), weinig voedsel (1)
    b.voedsel = 1
    b.erts = 10

    # Simuleer een succesvolle onderhandeling
    deal = onderhandel(w, a, b, rng)
    assert deal is not None, "Complementaire agenten moeten tot een handelsakkoord komen!"
    assert a.erts > 0, "Agent A moet nu erts bezitten!"
    assert b.voedsel > 1, "Agent B moet nu voedsel hebben ontvangen!"


if __name__ == "__main__":
    test_concave_nut_en_afnemende_meeropbrengst()
    test_honger_drijft_reserveringsprijs_op()
    test_onderhandeling_tussen_complementaire_agenten()
    print("[OK] Alle micro-economische tests zijn geslaagd!")
