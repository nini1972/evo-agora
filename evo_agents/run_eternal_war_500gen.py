"""Experiment #3: De Ewige-Oorlog-Run (500 Generaties zónder Kroniek).

Onderzoekt de Zeef-Ratchet & Metastabiliteit van het Oorlogsbekken:
- Is het oorlogsbekken een permanente attractor of een metastabiele toestand?
- Selecteert de 85% sterftezeef over honderden generaties voor hyper-efficiënte grazers die de dip steeds dieper graven (x_min omlaag, Gain omhoog) tot extinctie volgt?

Protocol:
- 10 onafhankelijke zaden (42, 55, 68, 81, 94, 107, 120, 133, 146, 159)
- Kroniek UIT vanaf gen 0 (met_kroniek = False)
- Duur: 500 generaties (150.000 ticks)
- Pre-geregistreerde hypothesen (OxAlpha):
  * Extinctie in 0–4 van de 10 seeds rond gen 200–400
  * Negatieve trend in x_min over tijd (x_min(t) -> beneden)
  * Positieve trend in Gain over tijd (gain(t) -> omhoog)
  * Indien stabiel: ratchet ontkracht, permanente metastabiliteit bewezen!
"""
from __future__ import annotations

import pickle
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def run_single_eternal_war_seed(seed: int, total_gens: int = 500):
    t0 = time.time()
    rng = np.random.default_rng(seed + 42000)
    w = Wereld(rng=rng, met_kroniek=False)
    reg = TelemetrieRegistratie()
    w.observers.append(reg)

    for _ in range(110):
        w.spawn(Genome.willekeurig(rng))

    extinct = False
    g_extinct = None

    history_cohort = []
    history_surv = []
    history_gain = []
    history_xmin = []
    history_xb = []

    for g in range(total_gens):
        ns = len([a for a in w.agents.values() if a.levend])
        if ns == 0 and not extinct:
            extinct = True
            g_extinct = g

        min_x = 1.0
        for _ in range(300):
            w.stap()
            cur_x = w.gov.gezondheidsindex(w.totale_bron())
            if cur_x < min_x:
                min_x = cur_x

        surv = len([a for a in w.agents.values() if a.levend])
        gain = ns / max(1, surv)
        eb = w.gov.gezondheidsindex(w.totale_bron())

        history_cohort.append(ns)
        history_surv.append(surv)
        history_gain.append(gain)
        history_xmin.append(min_x)
        history_xb.append(eb)

        if extinct and g > g_extinct + 5:
            # Als de populatie uitgestorven is en blijft, kunnen we vroeg stoppen
            break

    df = reg.tik_arrays()
    p_mean = float(np.mean(df["parasitair"])) if len(df) else 0.0

    # Trendberekeningen over de overleefde generaties
    valid_len = len(history_gain)
    gens_arr = np.arange(valid_len)
    slope_gain = float(np.polyfit(gens_arr, history_gain, 1)[0]) if valid_len > 10 else 0.0
    slope_xmin = float(np.polyfit(gens_arr, history_xmin, 1)[0]) if valid_len > 10 else 0.0

    dur = time.time() - t0
    return {
        "seed": seed,
        "extinct": extinct,
        "g_extinct": g_extinct,
        "gens_survived": valid_len,
        "slope_gain": slope_gain,
        "slope_xmin": slope_xmin,
        "mean_gain": float(np.mean(history_gain)),
        "mean_xmin": float(np.mean(history_xmin)),
        "mean_cohort": float(np.mean(history_cohort)),
        "mean_surv": float(np.mean(history_surv)),
        "p_mean": p_mean,
        "history_gain": history_gain,
        "history_xmin": history_xmin,
        "duration": dur
    }


def main():
    print("=" * 86)
    print("EXPERIMENT #3: DE EWIGE-OORLOG-RUN (500 GENERATIES ZONDER KRONIEK)")
    print("Protocol: 10 onafhankelijke zaden | 500 generaties per run | 14 CPU cores")
    print("=" * 86)

    seeds = [42, 55, 68, 81, 94, 107, 120, 133, 146, 159]
    t_start = time.time()
    results = []

    with ProcessPoolExecutor(max_workers=10) as executor:
        futs = {executor.submit(run_single_eternal_war_seed, s, 500): s for s in seeds}
        done = 0
        for f in as_completed(futs):
            done += 1
            res = f.result()
            results.append(res)
            ext_str = f"EXTINCT op Gen {res['g_extinct']}" if res["extinct"] else "OVERLEEFD 500 gen"
            print(
                f"[{done:02d}/10] Seed {res['seed']:3d} ({res['duration']:.1f}s) | "
                f"{ext_str} | Gain-helling: {res['slope_gain']:+.5f}/gen | "
                f"x_min-helling: {res['slope_xmin']:+.6f}/gen | P_gem: {res['p_mean']:.3f}"
            )

    print(f"\nAlle 10 Ewige-Oorlog runs voltooid in {time.time() - t_start:.1f}s!\n")

    n_ext = sum(1 for r in results if r["extinct"])
    mean_gain_slope = np.mean([r["slope_gain"] for r in results])
    mean_xmin_slope = np.mean([r["slope_xmin"] for r in results])

    print("=" * 86)
    print("SCOREBORD EWIGE-OORLOG-RUN (500 GENERATIES)")
    print("=" * 86)
    print(f"Extincties: {n_ext}/10 zaden (Voorspelling OxAlpha: 0-4 rond gen 200-400)")
    print(f"Gem. Gain-trend over tijd:  {mean_gain_slope:+.6f} / generatie")
    print(f"Gem. x_min-trend over tijd: {mean_xmin_slope:+.6f} / generatie")

    with open("results_eternal_war_500gen.pkl", "wb") as f:
        pickle.dump(results, f)
    print("Opgeslagen in results_eternal_war_500gen.pkl!")


if __name__ == "__main__":
    main()
