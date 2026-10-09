"""Experiment Redding-500: Garderobe of Grafsteen + Re-Knockout Priming Test
1. Fase I: Eeuwige Oorlog (Gen 0 t/m 500, met_kroniek=False) -> harding naar soldaat-fenotype
2. Fase II: Redding-500 (Gen 500 t/m 600, injectie volwassen_kroniek) -> vrede & de-canalizatietoets
3. Fase III: Her-knockout (Gen 600 t/m 650, met_kroniek=False gewist) -> priming & her-kanaalzetting
"""
from __future__ import annotations

import copy
import pickle
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

from evolib.genome import GENE_NAMEN, Genome, N_GENES
from evolib.world import TICKS_PER_GENERATIE, Wereld


def run_single_redding_seed(seed: int, volwassen_kroniek: dict):
    t0 = time.time()
    rng = np.random.default_rng(seed + 42000)
    w = Wereld(rng=rng, met_kroniek=False)

    for _ in range(110):
        w.spawn(Genome.willekeurig(rng))

    total_gens = 650  # 500 oorlog, 100 redding, 50 her-knockout
    gene_history = np.zeros((total_gens, N_GENES))
    p_history = np.zeros(total_gens)
    gain_history = np.zeros(total_gens)
    cohort_history = np.zeros(total_gens)
    surv_history = np.zeros(total_gens)
    xmin_history = np.zeros(total_gens)
    xb_history = np.zeros(total_gens)

    for g in range(total_gens):
        # Fase transities
        if g == 500:
            # INJECTIE VOLWASSEN KRONIEK
            w.met_kroniek = True
            w.kroniek_archetypen = copy.deepcopy(volwassen_kroniek)
        elif g == 600:
            # HER-KNOCKOUT
            w.met_kroniek = False
            w.kroniek_archetypen.clear()

        cohort_size = len([a for a in w.agents.values() if a.levend])
        cohort_history[g] = cohort_size

        min_x = 1.0
        p_ticks = []
        for _ in range(TICKS_PER_GENERATIE - 1):
            w.stap()
            cur_x = w.gov.gezondheidsindex(w.totale_bron())
            if cur_x < min_x:
                min_x = cur_x
            lev = [a for a in w.agents.values() if a.levend]
            if lev:
                p_ticks.append(
                    np.mean([
                        1.0 if (a.genoom.waarde("agressie") > 0.6 and a.genoom.waarde("cooperatie") < 0.3)
                        else 0.0 for a in lev
                    ])
                )

        # Pre-reproductie steekproef
        survivors_at_end = [a for a in w.agents.values() if a.levend]
        n_surv = len(survivors_at_end)
        surv_history[g] = n_surv
        gain_history[g] = cohort_size / max(1, n_surv)

        if survivors_at_end:
            g_mat = np.array([a.genoom.g for a in survivors_at_end])
            gene_history[g] = g_mat.mean(axis=0)
        elif g > 0:
            gene_history[g] = gene_history[g - 1]

        # Tick 299 -> 300 (reproductie)
        w.stap()
        cur_x = w.gov.gezondheidsindex(w.totale_bron())
        if cur_x < min_x:
            min_x = cur_x
        xmin_history[g] = min_x
        xb_history[g] = w.gov.gezondheidsindex(w.totale_bron())
        p_history[g] = float(np.mean(p_ticks)) if p_ticks else 0.0

    dur = time.time() - t0
    return {
        "seed": seed,
        "gene_history": gene_history,
        "p_history": p_history,
        "gain_history": gain_history,
        "cohort_history": cohort_history,
        "surv_history": surv_history,
        "xmin_history": xmin_history,
        "xb_history": xb_history,
        "duration": dur,
    }


def main():
    print("=" * 86)
    print("EXPERIMENT REDDING-500: GARDEROBE OF GRAFSTEEN + HER-KNOCKOUT PRIMING")
    print("10 Zaden parallel (500 gen Oorlog -> 100 gen Redding -> 50 gen Her-knockout)")
    print("=" * 86)

    with open("volwassen_kroniek.pkl", "rb") as f:
        volwassen_kroniek = pickle.load(f)
    print(f"Volwassen kroniek geladen met {len(volwassen_kroniek)} archetypen.\n")

    seeds = [42, 55, 68, 81, 94, 107, 120, 133, 146, 159]
    t_start = time.time()
    results = []

    with ProcessPoolExecutor(max_workers=10) as executor:
        future_map = {
            executor.submit(run_single_redding_seed, s, volwassen_kroniek): s
            for s in seeds
        }
        done = 0
        for fut in as_completed(future_map):
            done += 1
            res = fut.result()
            results.append(res)
            p_redding_eind = np.mean(res["p_history"][590:600])
            agres_redding_eind = res["gene_history"][599, 0]
            metab_redding_eind = res["gene_history"][599, 8]
            print(
                f"[{done:02d}/10] Seed {res['seed']:3d} ({res['duration']:.1f}s) | "
                f"Gen 600: P={p_redding_eind:.3f}, Agres={agres_redding_eind:.3f}, Metab={metab_redding_eind:.3f}"
            )

    print(f"\nAlle 10 runs voltooid in {time.time() - t_start:.1f}s!\n")
    results.sort(key=lambda x: x["seed"])

    with open("results_redding_500.pkl", "wb") as f:
        pickle.dump(results, f)
    print("Opgeslagen in results_redding_500.pkl\n")

    # Analyse
    gh = np.array([r["gene_history"] for r in results])  # (10, 650, 9)
    ph = np.array([r["p_history"] for r in results])     # (10, 650)
    survh = np.array([r["surv_history"] for r in results])
    gainh = np.array([r["gain_history"] for r in results])

    print("=" * 86)
    print("RESULTATEN REDDING-500 (FASE II: GEN 500 -> 600)")
    print("=" * 86)
    print(f"Gen 500 (Oorlogseind):  P={ph[:, 499].mean():.4f} | Agres={gh[:, 499, 0].mean():.4f} | Metab={gh[:, 499, 8].mean():.4f} | Coop={gh[:, 499, 1].mean():.4f}")
    print(f"Gen 520 (Na 20 gen):    P={ph[:, 519].mean():.4f} | Agres={gh[:, 519, 0].mean():.4f} | Metab={gh[:, 519, 8].mean():.4f} | Coop={gh[:, 519, 1].mean():.4f}")
    print(f"Gen 550 (Na 50 gen):    P={ph[:, 549].mean():.4f} | Agres={gh[:, 549, 0].mean():.4f} | Metab={gh[:, 549, 8].mean():.4f} | Coop={gh[:, 549, 1].mean():.4f}")
    print(f"Gen 600 (Na 100 gen):   P={ph[:, 599].mean():.4f} | Agres={gh[:, 599, 0].mean():.4f} | Metab={gh[:, 599, 8].mean():.4f} | Coop={gh[:, 599, 1].mean():.4f}")

    print("\n" + "=" * 86)
    print("RESULTATEN HER-KNOCKOUT (FASE III: GEN 600 -> 650)")
    print("=" * 86)
    print(f"Gen 610 (Na 10 gen KO): P={ph[:, 609].mean():.4f} | Agres={gh[:, 609, 0].mean():.4f} | Metab={gh[:, 609, 8].mean():.4f}")
    print(f"Gen 650 (Na 50 gen KO): P={ph[:, 649].mean():.4f} | Agres={gh[:, 649, 0].mean():.4f} | Metab={gh[:, 649, 8].mean():.4f}")


if __name__ == "__main__":
    main()
