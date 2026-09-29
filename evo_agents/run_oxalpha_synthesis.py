"""OxAlpha Final Gaps Analysis:
1. Master Warmup & Cache of Volwassen Kroniek (Gen 180)
2. AR(2) Pole Analysis on 120 Generations of Mature Peace (Gen 180-300)
3. Founding Row (Gen 0) Trajectory & Holling / Consumption Calibration
"""
import copy
import pickle
import time
import numpy as np

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def ar2_poles(x):
    x = np.asarray(x, float)
    x = x - x.mean()
    X = np.column_stack([x[1:-1], x[:-2]])
    y = x[2:]
    a1, a2 = np.linalg.lstsq(X, y, rcond=None)[0]
    r = np.roots([1, -a1, -a2])
    return a1, a2, r, np.abs(r)


def main():
    print("=" * 80)
    print("1. MASTER WARMUP & MATURE PEACE AR(2) ANALYSIS")
    print("=" * 80)
    
    rng_master = np.random.default_rng(42)
    w_master = Wereld(rng=rng_master, met_kroniek=True)
    reg_master = TelemetrieRegistratie()
    w_master.observers.append(reg_master)
    for _ in range(110):
        w_master.spawn(Genome.willekeurig(rng_master))

    print("Running warmup to Gen 180...")
    t0 = time.time()
    for g in range(180):
        for _ in range(300):
            w_master.stap()
    print(f"Warmup 180 gen completed in {time.time() - t0:.1f}s")
    
    volwassen_kroniek = copy.deepcopy(w_master.kroniek_archetypen)
    with open("volwassen_kroniek.pkl", "wb") as f:
        pickle.dump(volwassen_kroniek, f)
    print(f"Saved volwassen_kroniek.pkl ({len(volwassen_kroniek)} buckets)")

    # Now run 120 generations of mature peace (Gen 180 to 300)
    print("Running 120 generations of mature peace (Gen 180 - 300)...")
    mature_ehi_boundary = []
    t_mature = time.time()
    for g in range(180, 300):
        for _ in range(300):
            w_master.stap()
        eb = w_master.gov.gezondheidsindex(w_master.totale_bron())
        mature_ehi_boundary.append(eb)
    print(f"Mature peace run completed in {time.time() - t_mature:.1f}s")

    # Fit AR(2) on mature_ehi_boundary
    ehi_series = np.array(mature_ehi_boundary)
    a1, a2, roots, pole_magnitudes = ar2_poles(ehi_series)
    print("\n--- AR(2) RESULTATEN OP MATURE VREDE (120 Generaties) ---")
    print(f"Mean EHI: {ehi_series.mean():.4f}, Std: {ehi_series.std():.4f}")
    print(f"Min: {ehi_series.min():.4f}, Max: {ehi_series.max():.4f}")
    print(f"a1 = {a1:.4f}, a2 = {a2:.4f}")
    print(f"Roots: {roots}")
    print(f"Pole magnitudes |r|: {pole_magnitudes}")
    if np.all(pole_magnitudes < 1.0):
        print(">> INTERPRETATIE: |r| < 1.0 -> GEDWONGEN GEDEMPTE OSCILLATOR!")
        print(">> De Kroniek is een DISSSIPATIEVE DEMPER (schokdemper), GEEN limietcyclus-klok.")
    else:
        print(">> INTERPRETATIE: |r| >= 1.0 -> LIMIETCYCLUS / KLOK.")

    # Lag-1 autocorrelation
    r1 = np.corrcoef(ehi_series[:-1], ehi_series[1:])[0, 1]
    print(f"Lag-1 autocorrelation r1: {r1:.4f}")

    print("\n" + "=" * 80)
    print("2. FOUNDING ROW (GEN 0) CALIBRATION EXPERIMENT")
    print("=" * 80)
    # 10 seeds x Gen 0 on full world (x0 = 1.0)
    # Let's inspect biomass drawdown and consumption
    seeds = [42, 101, 102, 103, 104, 105, 106, 107, 108, 109]
    drawdowns = []
    per_agent_consumptions = []

    for s in seeds:
        rng = np.random.default_rng(s + 1000)
        w = Wereld(rng=rng, met_kroniek=True)
        w.kroniek_archetypen = copy.deepcopy(volwassen_kroniek)
        # Set all resources to 100% full capacity (x0 = 1.0)
        for b in w.grid.values():
            b.hoeveelheid = b.capaciteit
        b_start = w.totale_bron()
        
        for _ in range(110):
            w.spawn(Genome.willekeurig(rng))

        # Track tick-by-tick biomass in gen 0
        b_series = [b_start]
        for _ in range(300):
            w.stap()
            b_series.append(w.totale_bron())
        
        b_end = b_series[-1]
        ehi_b = w.gov.gezondheidsindex(b_end)
        drawdowns.append(ehi_b)
        # Average net loss per agent per tick
        delta_b = b_start - b_end
        per_agent_consumptions.append(delta_b / (110.0 * 300.0))

    print(f"Founding row EHI end (xb) across 10 seeds: {np.mean(drawdowns):.4f} +/- {np.std(drawdowns, ddof=1):.4f}")
    print(f"Net biomass consumption rate per agent per tick: {np.mean(per_agent_consumptions):.4f} +/- {np.std(per_agent_consumptions, ddof=1):.4f}")

if __name__ == "__main__":
    main()
