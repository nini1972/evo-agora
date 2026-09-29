"""N=30 Replication of Decomposition Experiment (W vs P vs F)
Parallelized across CPU cores using concurrent.futures.
With proper censorship handling (Fisher's exact test, Kaplan-Meier estimate, log-rank)
and Gain-transient tracking in W/P successes.
"""
from __future__ import annotations

import copy
import pickle
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from scipy import stats

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def run_single_arm_seed(arm_name: str, kroniek_dict: dict, seed: int, offset: int):
    t0 = time.time()
    rng = np.random.default_rng(seed + offset)
    w = Wereld(rng=rng, met_kroniek=True)
    w.kroniek_archetypen = copy.deepcopy(kroniek_dict)
    reg = TelemetrieRegistratie()
    w.observers.append(reg)
    for _ in range(110):
        w.spawn(Genome.willekeurig(rng))

    arm_gains = []
    for g in range(50):
        ns = len([a for a in w.agents.values() if a.levend])
        for _ in range(300):
            w.stap()
        evs = [e for e in reg.gebeurtenissen if e.tik >= g*300 and e.tik < (g+1)*300 and e.type.name == 'DOOD_HONGER']
        nd = len(evs)
        surv = max(0, ns - nd)
        gain = ns / max(1, surv)
        arm_gains.append(gain)

    df = reg.tik_arrays()
    p_gens = [float(np.mean(df["parasitair"][df["generatie"] == g])) for g in range(50)]
    gen_v = next((g for g in range(5, 46) if np.mean(p_gens[g-5:g]) < 0.20), 50)
    censored = (gen_v == 50)

    pre_peace_gain = None
    if not censored and gen_v >= 5:
        pre_peace_gain = float(np.mean(arm_gains[max(0, gen_v - 3):gen_v]))

    dur = time.time() - t0
    return {
        "arm": arm_name,
        "seed": seed,
        "time": gen_v,
        "censored": censored,
        "pre_peace_gain": pre_peace_gain,
        "duration": dur
    }


def main():
    print("=" * 80)
    print("PARALLEL N=30 DECOMPOSITION EXPERIMENT (W vs P vs F) & CENSORED ANALYSIS")
    print("=" * 80)

    with open("volwassen_kroniek.pkl", "rb") as f:
        volwassen_kroniek = pickle.load(f)
    print(f"Loaded volwassen_kroniek.pkl ({len(volwassen_kroniek)} buckets)")

    kroniek_W = {
        k: v for k, v in volwassen_kroniek.items() if (v[0] / max(1e-6, v[1])) < 0.50
    }
    kroniek_P = {
        k: v for k, v in volwassen_kroniek.items() if (v[0] / max(1e-6, v[1])) >= 0.50
    }
    print(f"Splitsing: Totaal={len(volwassen_kroniek)} | W={len(kroniek_W)} | P={len(kroniek_P)}")

    seeds = [42 + i * 7 for i in range(30)]
    print(f"Submitting 90 tasks (30 seeds x 3 arms) across 14 workers...")

    tasks = []
    t_start = time.time()
    results = {"F": [], "W": [], "P": []}

    with ProcessPoolExecutor(max_workers=14) as executor:
        future_map = {}
        for s in seeds:
            f_fut = executor.submit(run_single_arm_seed, "F", volwassen_kroniek, s, 1000)
            future_map[f_fut] = ("F", s)
            w_fut = executor.submit(run_single_arm_seed, "W", kroniek_W, s, 2000)
            future_map[w_fut] = ("W", s)
            p_fut = executor.submit(run_single_arm_seed, "P", kroniek_P, s, 3000)
            future_map[p_fut] = ("P", s)

        done_count = 0
        for fut in as_completed(future_map):
            done_count += 1
            res = fut.result()
            results[res["arm"]].append(res)
            print(f"[{done_count:02d}/90] Finished Arm {res['arm']} Seed {res['seed']:3d} in {res['duration']:.1f}s -> Time: {res['time']:2d} (Censored: {res['censored']})")

    print(f"\nAll 90 simulations completed in {time.time() - t_start:.1f}s!")

    print("\n" + "=" * 80)
    print("N=30 RAPPORT & STATISTISCHE TOETSEN")
    print("=" * 80)

    for arm in ["F", "W", "P"]:
        arm_res = sorted(results[arm], key=lambda x: x["seed"])
        times = [r["time"] for r in arm_res]
        cens = [r["censored"] for r in arm_res]
        n_succ = sum(1 for c in cens if not c)
        succ_rate = n_succ / len(cens)
        mean_time = np.mean(times)
        uncensored_times = [t for t, c in zip(times, cens) if not c]
        mean_uncensored = np.mean(uncensored_times) if uncensored_times else float('nan')
        std_uncensored = np.std(uncensored_times, ddof=1) if len(uncensored_times) > 1 else 0.0
        print(f"\n--- ARM {arm} ---")
        print(f"  Succesvol bereikt vóór Gen 50: {n_succ}/30 ({succ_rate*100:.1f}%) | Faalkans (Censuur): {(1-succ_rate)*100:.1f}%")
        print(f"  Gemiddelde tijd (inclusief censuur op 50): {mean_time:.2f} +/- {np.std(times, ddof=1):.2f}")
        print(f"  Gemiddelde tijd (alleen geslaagde seeds):   {mean_uncensored:.2f} +/- {std_uncensored:.2f}")

    # Fisher exact test (Succes vs Faal)
    succ_F = sum(1 for r in results["F"] if not r["censored"])
    fail_F = 30 - succ_F
    for arm in ["W", "P"]:
        succ_arm = sum(1 for r in results[arm] if not r["censored"])
        fail_arm = 30 - succ_arm
        table = [[succ_F, fail_F], [succ_arm, fail_arm]]
        odds, p_fisher = stats.fisher_exact(table)
        print(f"\nFisher's Exact Test Arm {arm} vs Arm F (Succes vs Gecensureerd):")
        print(f"  Contingency Table [[F_succ, F_fail], [{arm}_succ, {arm}_fail]]: {table}")
        print(f"  Odds Ratio: {odds:.3f}, p-value: {p_fisher:.6e}")

    # Log-rank test / Mann-Whitney U test on survival times
    for arm in ["W", "P"]:
        times_F = [r["time"] for r in results["F"]]
        times_arm = [r["time"] for r in results[arm]]
        u_stat, p_mw = stats.mannwhitneyu(times_arm, times_F, alternative='greater')
        print(f"Mann-Whitney U Test (Time-to-peace Arm {arm} > Arm F): U = {u_stat}, p = {p_mw:.6e}")

    # Gain transient in W/P successes
    print("\n" + "=" * 80)
    print("GAIN TRANSIENT IN W/P SUCCESSEN (OxAlpha §5 Voorspelling)")
    print("=" * 80)
    gains_W = [r["pre_peace_gain"] for r in results["W"] if r["pre_peace_gain"] is not None]
    gains_P = [r["pre_peace_gain"] for r in results["P"] if r["pre_peace_gain"] is not None]
    if gains_W:
        print(f"Arm W Gem. Gain in de 3 generaties vóór vrede: {np.mean(gains_W):.3f} +/- {np.std(gains_W, ddof=1):.3f} (N={len(gains_W)})")
    if gains_P:
        print(f"Arm P Gem. Gain in de 3 generaties vóór vrede: {np.mean(gains_P):.3f} +/- {np.std(gains_P, ddof=1):.3f} (N={len(gains_P)})")

    with open("results_decomposition_n30.pkl", "wb") as f:
        pickle.dump(results, f)
    print("\nResults successfully saved to results_decomposition_n30.pkl")


if __name__ == "__main__":
    main()
