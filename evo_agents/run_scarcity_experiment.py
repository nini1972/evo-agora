"""Research Queue: The K/2 Scarcity Experiment.
Tests the Asymmetry Law:
Does institutional memory (De Kroniek) hold peace under severe ecological scarcity (K/2 = 780)?
Or does scarcity break the stationary flow, driving x_min down, N -> 12-18, or causing extinction?

Protocol:
- 15 independent seeds
- Control Arm: K = 1560 (130 sources x 12 cap)
- Scarcity Arm: K/2 = 780 (65 sources x 12 cap, draagkracht = 780)
- Both arms seeded with canonical volwassen_kroniek
- Horizon: 50 generations (300 ticks/gen)
"""
from __future__ import annotations

import copy
import pickle
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def run_single_scarcity_seed(arm_name: str, n_bronnen: int, seed: int, volwassen_kroniek: dict):
    t0 = time.time()
    rng = np.random.default_rng(seed + (5000 if arm_name == "K2" else 1000))
    w = Wereld(rng=rng, n_bronnen=n_bronnen, met_kroniek=True)
    w.kroniek_archetypen = copy.deepcopy(volwassen_kroniek)
    reg = TelemetrieRegistratie()
    w.observers.append(reg)

    for _ in range(110):
        w.spawn(Genome.willekeurig(rng))

    extinct = False
    g_extinct = None
    min_x = 1.0
    pop_series = []
    gain_series = []

    for g in range(50):
        ns = len([a for a in w.agents.values() if a.levend])
        if ns == 0 and not extinct:
            extinct = True
            g_extinct = g
        pop_series.append(ns)

        for _ in range(300):
            w.stap()
            cur_x = w.gov.gezondheidsindex(w.totale_bron())
            if cur_x < min_x:
                min_x = cur_x

        evs = [e for e in reg.gebeurtenissen if e.tik >= g*300 and e.tik < (g+1)*300 and e.type.name == 'DOOD_HONGER']
        nd = len(evs)
        surv = max(0, ns - nd)
        gain = ns / max(1, surv)
        gain_series.append(gain)

    df = reg.tik_arrays()
    p_gens = [float(np.mean(df["parasitair"][df["generatie"] == g])) for g in range(50)] if len(df) else [0.0]*50
    gen_peace = next((g for g in range(5, 46) if np.mean(p_gens[g-5:g]) < 0.20), 50)
    p_mean = float(np.mean(df["parasitair"])) if len(df) else 0.0

    dur = time.time() - t0
    return {
        "arm": arm_name,
        "seed": seed,
        "draagkracht": w.gov.inst.draagkracht,
        "gen_peace": gen_peace,
        "peace_achieved": (gen_peace < 50),
        "extinct": extinct,
        "g_extinct": g_extinct,
        "min_x": float(min_x),
        "mean_N": float(np.mean(pop_series)),
        "mean_gain": float(np.mean(gain_series)),
        "p_mean": p_mean,
        "duration": dur
    }


def main():
    print("=" * 80)
    print("ONDERZOEKSWACHTRIJ: HET K/2 SCHAARSTE-EXPERIMENT (15 SEEDS)")
    print("=" * 80)

    with open("volwassen_kroniek.pkl", "rb") as f:
        volwassen_kroniek = pickle.load(f)
    print("Loaded volwassen_kroniek.pkl")

    seeds = [42 + i * 13 for i in range(15)]
    print(f"Seeds ({len(seeds)}): {seeds}")

    results = {"Control_K": [], "Scarcity_K2": []}
    t_start = time.time()

    with ProcessPoolExecutor(max_workers=14) as executor:
        future_map = {}
        for s in seeds:
            # Control: K = 1560 (130 bronnen)
            f_ctrl = executor.submit(run_single_scarcity_seed, "Control_K", 130, s, volwassen_kroniek)
            future_map[f_ctrl] = ("Control_K", s)
            # Scarcity: K/2 = 780 (65 bronnen)
            f_scarc = executor.submit(run_single_scarcity_seed, "Scarcity_K2", 65, s, volwassen_kroniek)
            future_map[f_scarc] = ("Scarcity_K2", s)

        done = 0
        for fut in as_completed(future_map):
            done += 1
            res = fut.result()
            results[res["arm"]].append(res)
            print(f"[{done:02d}/30] Arm {res['arm']:11s} Seed {res['seed']:3d} | Vrede: Gen {res['gen_peace']:2d} | N_gem: {res['mean_N']:4.1f} | x_min: {res['min_x']:.3f} | Gain: {res['mean_gain']:.2f} | Extinct: {res['extinct']}")

    print(f"\nCompleted all 30 simulations in {time.time() - t_start:.1f}s!")

    print("\n" + "=" * 80)
    print("EMPIRISCHE UITKOMST VAN HET K/2 SCHAARSTE-EXPERIMENT")
    print("=" * 80)

    for arm in ["Control_K", "Scarcity_K2"]:
        data = results[arm]
        n_peace = sum(1 for d in data if d["peace_achieved"])
        n_ext = sum(1 for d in data if d["extinct"])
        mean_N = np.mean([d["mean_N"] for d in data])
        min_x_m = np.mean([d["min_x"] for d in data])
        gain_m = np.mean([d["mean_gain"] for d in data])
        p_m = np.mean([d["p_mean"] for d in data])
        t_peace_m = np.mean([d["gen_peace"] for d in data])

        print(f"\n--- {arm} (Draagkracht K = {data[0]['draagkracht']:.0f}) ---")
        print(f"  Vrede bereikt (<50 gen):   {n_peace}/15 ({n_peace/15*100:.1f}%) [Gem. tijd: {t_peace_m:.2f} gen]")
        print(f"  Gemiddelde Populatie (N):  {mean_N:.1f} +/- {np.std([d['mean_N'] for d in data], ddof=1):.1f}")
        print(f"  Diepste Biomassapunt x_min:{min_x_m:.3f} +/- {np.std([d['min_x'] for d in data], ddof=1):.3f}")
        print(f"  Demografische Gain:        {gain_m:.2f} +/- {np.std([d['mean_gain'] for d in data], ddof=1):.2f}")
        print(f"  Gemiddeld Parasitisme (P): {p_m:.3f}")
        print(f"  Extincties:                {n_ext}/15 seeds")

    with open("results_scarcity_k2.pkl", "wb") as f:
        pickle.dump(results, f)
    print("\nOpgeslagen in results_scarcity_k2.pkl")


if __name__ == "__main__":
    main()
