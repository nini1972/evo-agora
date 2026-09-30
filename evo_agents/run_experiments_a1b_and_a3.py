"""Research Queue Execution:
1. Tier A1b: K/4 Scarcity Test (K ~ 384, 15 seeds)
2. Tier A3: God-Mode Overgrazing Test in War Regime (15 seeds, Paired Control vs God-Mode)
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


# ==============================================================================
# 1. TIER A1b: K/4 SCARCITY EXPERIMENT
# ==============================================================================
def run_single_k4_seed(seed: int, volwassen_kroniek: dict):
    t0 = time.time()
    rng = np.random.default_rng(seed + 7000)
    # K/4: 32 bronnen x 12.0 = 384.0 draagkracht
    w = Wereld(rng=rng, n_bronnen=32, met_kroniek=True)
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
    gen0_3_deaths = 0

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
        if g < 4:
            gen0_3_deaths += nd

    df = reg.tik_arrays()
    p_gens = [float(np.mean(df["parasitair"][df["generatie"] == g])) for g in range(50)] if len(df) else [0.0]*50
    gen_peace = next((g for g in range(5, 46) if np.mean(p_gens[g-5:g]) < 0.20), 50)
    p_mean = float(np.mean(df["parasitair"])) if len(df) else 0.0

    dur = time.time() - t0
    return {
        "seed": seed,
        "draagkracht": w.gov.inst.draagkracht,
        "gen_peace": gen_peace,
        "peace_achieved": (gen_peace < 50),
        "extinct": extinct,
        "g_extinct": g_extinct,
        "min_x": float(min_x),
        "mean_N": float(np.mean(pop_series)),
        "mean_gain": float(np.mean(gain_series)),
        "gen0_3_deaths": gen0_3_deaths,
        "p_mean": p_mean,
        "duration": dur
    }


# ==============================================================================
# 2. TIER A3: GOD-MODE OVERGRAZING EXPERIMENT IN WAR REGIME
# ==============================================================================
def run_single_godmode_pair(seed: int, volwassen_kroniek: dict):
    # Phase 1: Warmup to peace (Gen 0-30)
    rng_master = np.random.default_rng(seed + 9000)
    w_warm = Wereld(rng=rng_master, met_kroniek=True)
    w_warm.kroniek_archetypen = copy.deepcopy(volwassen_kroniek)
    for _ in range(110):
        w_warm.spawn(Genome.willekeurig(rng_master))
    for _ in range(30):
        for _ in range(300):
            w_warm.stap()

    # Clone into Arm A (Control: Knockout + Normal Mortality) and Arm B (God-Mode: Knockout + No Starvation)
    w_ctrl = copy.deepcopy(w_warm)
    w_ctrl.met_kroniek = False
    w_ctrl.kroniek_archetypen.clear()
    w_ctrl.god_mode = False
    reg_ctrl = TelemetrieRegistratie()
    w_ctrl.observers = [reg_ctrl]

    w_god = copy.deepcopy(w_warm)
    w_god.met_kroniek = False
    w_god.kroniek_archetypen.clear()
    w_god.god_mode = True
    reg_god = TelemetrieRegistratie()
    w_god.observers = [reg_god]

    # Run for 40 generations post-knockout (Gen 30 to 70)
    min_x_ctrl, min_x_god = 1.0, 1.0
    x_hist_ctrl, x_hist_god = [], []
    pop_ctrl, pop_god = [], []

    for g in range(40):
        for _ in range(300):
            w_ctrl.stap()
            w_god.stap()
            xc = w_ctrl.gov.gezondheidsindex(w_ctrl.totale_bron())
            xg = w_god.gov.gezondheidsindex(w_god.totale_bron())
            min_x_ctrl = min(min_x_ctrl, xc)
            min_x_god = min(min_x_god, xg)
            x_hist_ctrl.append(xc)
            x_hist_god.append(xg)
        pop_ctrl.append(len([a for a in w_ctrl.agents.values() if a.levend]))
        pop_god.append(len([a for a in w_god.agents.values() if a.levend]))

    df_c = reg_ctrl.tik_arrays()
    df_g = reg_god.tik_arrays()

    p_c = float(np.mean(df_c["parasitair"])) if len(df_c) else 0.0
    p_g = float(np.mean(df_g["parasitair"])) if len(df_g) else 0.0

    # Last 10 generations biomass (gen 60-70)
    x_end_ctrl = float(np.mean(x_hist_ctrl[-3000:]))
    x_end_god = float(np.mean(x_hist_god[-3000:]))

    return {
        "seed": seed,
        "ctrl": {
            "min_x": float(min_x_ctrl),
            "end_x": x_end_ctrl,
            "mean_N": float(np.mean(pop_ctrl)),
            "p_mean": p_c
        },
        "god": {
            "min_x": float(min_x_god),
            "end_x": x_end_god,
            "mean_N": float(np.mean(pop_god)),
            "p_mean": p_g
        }
    }


def main():
    print("=" * 80)
    print("ONDERZOEKSWACHTRIJ: TIER A1b (K/4) EN TIER A3 (GOD-MODE)")
    print("=" * 80)

    with open("volwassen_kroniek.pkl", "rb") as f:
        volwassen_kroniek = pickle.load(f)
    print("Loaded volwassen_kroniek.pkl")

    seeds = [42 + i * 13 for i in range(15)]
    print(f"Seeds ({len(seeds)}): {seeds}")

    # --- 1. TIER A1b: K/4 ---
    print("\n>>> STARTING TIER A1b: K/4 SCARCITY TEST (15 SEEDS) <<<")
    t0_k4 = time.time()
    results_k4 = []
    with ProcessPoolExecutor(max_workers=14) as executor:
        futs = {executor.submit(run_single_k4_seed, s, volwassen_kroniek): s for s in seeds}
        done = 0
        for f in as_completed(futs):
            done += 1
            res = f.result()
            results_k4.append(res)
            print(f"[{done:02d}/15] K/4 Seed {res['seed']:3d} | Vrede: Gen {res['gen_peace']:2d} | N_gem: {res['mean_N']:4.1f} | x_min: {res['min_x']:.3f} | Dood_0_3: {res['gen0_3_deaths']:2d} | Extinct: {res['extinct']}")

    print(f"\nK/4 Completed in {time.time() - t0_k4:.1f}s")
    n_peace_k4 = sum(1 for r in results_k4 if r["peace_achieved"])
    mean_N_k4 = np.mean([r["mean_N"] for r in results_k4])
    min_x_k4 = np.mean([r["min_x"] for r in results_k4])
    deaths_0_3_k4 = np.mean([r["gen0_3_deaths"] for r in results_k4])
    ext_k4 = sum(1 for r in results_k4 if r["extinct"])

    print("--- RESULTAAT TIER A1b (K/4 SCARCITY, K ~ 384) ---")
    print(f"  Vrede bereikt: {n_peace_k4}/15 ({n_peace_k4/15*100:.1f}%) | Gem. tijd: {np.mean([r['gen_peace'] for r in results_k4]):.2f} gen")
    print(f"  Gem. Populatie (N): {mean_N_k4:.1f} +/- {np.std([r['mean_N'] for r in results_k4], ddof=1):.1f}")
    print(f"  Diepste Biomassapunt x_min: {min_x_k4:.3f} +/- {np.std([r['min_x'] for r in results_k4], ddof=1):.3f}")
    print(f"  Oprichtingsdoden (Gen 0-3): {deaths_0_3_k4:.1f} doden/seed")
    print(f"  Extincties: {ext_k4}/15 seeds")

    # --- 2. TIER A3: GOD-MODE ---
    print("\n>>> STARTING TIER A3: GOD-MODE OVERGRAZING IN WAR REGIME (15 SEEDS) <<<")
    t0_god = time.time()
    results_god = []
    with ProcessPoolExecutor(max_workers=14) as executor:
        futs = {executor.submit(run_single_godmode_pair, s, volwassen_kroniek): s for s in seeds}
        done = 0
        for f in as_completed(futs):
            done += 1
            res = f.result()
            results_god.append(res)
            print(f"[{done:02d}/15] God-mode Seed {res['seed']:3d} | Ctrl x_end: {res['ctrl']['end_x']:.3f} (x_min: {res['ctrl']['min_x']:.3f}) | God x_end: {res['god']['end_x']:.3f} (x_min: {res['god']['min_x']:.3f})")

    print(f"\nGod-mode Completed in {time.time() - t0_god:.1f}s")
    ctrl_end_x = np.mean([r["ctrl"]["end_x"] for r in results_god])
    god_end_x = np.mean([r["god"]["end_x"] for r in results_god])
    ctrl_min_x = np.mean([r["ctrl"]["min_x"] for r in results_god])
    god_min_x = np.mean([r["god"]["min_x"] for r in results_god])
    ctrl_N = np.mean([r["ctrl"]["mean_N"] for r in results_god])
    god_N = np.mean([r["god"]["mean_N"] for r in results_god])
    ctrl_P = np.mean([r["ctrl"]["p_mean"] for r in results_god])
    god_P = np.mean([r["god"]["p_mean"] for r in results_god])

    print("--- RESULTAAT TIER A3 (GOD-MODE OVERGRAZING BEWIJS) ---")
    print(f"  Controle (met sterfte): Eind-x = {ctrl_end_x:.3f} | Min-x = {ctrl_min_x:.3f} | N = {ctrl_N:.1f} | P = {ctrl_P:.3f}")
    print(f"  God-mode (zonder hongerdood): Eind-x = {god_end_x:.3f} | Min-x = {god_min_x:.3f} | N = {god_N:.1f} | P = {god_P:.3f}")

    # Save all results
    with open("results_experiments_a1b_a3.pkl", "wb") as f:
        pickle.dump({"k4": results_k4, "godmode": results_god}, f)
    print("\nSaved to results_experiments_a1b_a3.pkl")


if __name__ == "__main__":
    main()
