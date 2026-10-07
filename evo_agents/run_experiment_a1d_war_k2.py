"""Experiment A1d: Oorlogs-K/2 (De Sterke Asymmetriewet).

Protocol (OxAlpha Pre-registratie P0):
1. Warmup: Zaai-vrede tot generatie 30 met canonieke volwassen_kroniek op K = 1536.
2. Checkpoint-Kloon op Gen 30 (gepaarde seeds):
   - Arm A (Oorlog Controle): Knockout Kroniek (met_kroniek=False, archief gewist), K = 1536.
   - Arm B (Oorlog Schaarste): Knockout Kroniek + K/2 (draagkracht gehalveerd naar ~768).
3. Observatiefase: 40 generaties post-knockout (Gen 30 t/m 70) over 15 gepaarde zaden.

Voorgeregistreerde Hypothesen (OxAlpha):
- Arm B Populatie: N_gem -> 15–22 (t.o.v. Arm A ~26–27)
- Arm B Extinctierisico: 1–3 van de 15 seeds
- Arm B Dieptepunt: x_min < 0.03
- Vraag-elasticiteit: gamma_oorlog ≈ 0 (maag regeert, zeef betaalt)
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


def run_single_a1d_seed(seed: int, volwassen_kroniek: dict):
    t0 = time.time()
    rng_master = np.random.default_rng(seed + 11000)

    # 1. Warmup naar vrede (Gen 0 t/m 30)
    w_warm = Wereld(rng=rng_master, met_kroniek=True)
    w_warm.kroniek_archetypen = copy.deepcopy(volwassen_kroniek)
    for _ in range(110):
        w_warm.spawn(Genome.willekeurig(rng_master))
    for _ in range(30):
        for _ in range(300):
            w_warm.stap()

    # 2. Checkpoint-Kloon voor Arm A en Arm B
    w_ctrl = copy.deepcopy(w_warm)
    w_scarc = copy.deepcopy(w_warm)

    # Arm A: Knockout Kroniek, normale K (~1536)
    w_ctrl.met_kroniek = False
    w_ctrl.kroniek_archetypen.clear()
    reg_ctrl = TelemetrieRegistratie()
    w_ctrl.observers = [reg_ctrl]

    # Arm B: Knockout Kroniek + Halveer K (~768)
    w_scarc.met_kroniek = False
    w_scarc.kroniek_archetypen.clear()
    # Behoud 65 bronnen deterministisch via de wereld-RNG
    bron_keys = list(w_scarc.grid.keys())
    w_scarc.rng.shuffle(bron_keys)
    to_keep = set(bron_keys[:65])
    w_scarc.grid = {k: v for k, v in w_scarc.grid.items() if k in to_keep}
    w_scarc.gov.inst.draagkracht = sum(b.capaciteit for b in w_scarc.grid.values())
    reg_scarc = TelemetrieRegistratie()
    w_scarc.observers = [reg_scarc]

    # 3. Post-knockout observatie (40 generaties: Gen 30 t/m 70)
    def observe_arm(w: Wereld, reg: TelemetrieRegistratie):
        min_x = 1.0
        pop_history = []
        extinct = False
        g_extinct = None
        gains = []
        hongerdoden_per_gen = []

        for g in range(40):
            # Aantal levenden aan begin van generatie
            ns = len([a for a in w.agents.values() if a.levend])
            if ns == 0 and not extinct:
                extinct = True
                g_extinct = g + 30

            for _ in range(300):
                w.stap()
                cur_x = w.gov.gezondheidsindex(w.totale_bron())
                if cur_x < min_x:
                    min_x = cur_x

            evs = [e for e in reg.gebeurtenissen if e.tik >= g*300 and e.tik < (g+1)*300 and e.type.name == 'DOOD_HONGER']
            nd = len(evs)
            surv = max(0, ns - nd)
            gain = ns / max(1, surv)
            gains.append(gain)
            hongerdoden_per_gen.append(nd)

            # Echte gemiddelde levende populatie over de generatie
            # (tussen geboorte ns en overlevenden surv)
            # In oorlog sterven velen halverwege, dus N_gem ≈ (ns + surv)/2
            n_eff = (ns + surv) / 2.0
            pop_history.append(n_eff)

        df = reg.tik_arrays()
        p_mean = float(np.mean(df["parasitair"])) if len(df) else 0.0

        # Bereken stabiele post-transitie gemiddelden (laatste 30 generaties: Gen 40 t/m 70)
        n_stabiel = float(np.mean(pop_history[10:]))
        gain_stabiel = float(np.mean(gains[10:]))
        dood_stabiel = float(np.mean(hongerdoden_per_gen[10:]))

        return {
            "min_x": float(min_x),
            "mean_N_stabiel": n_stabiel,
            "mean_gain": gain_stabiel,
            "mean_dood": dood_stabiel,
            "p_mean": p_mean,
            "extinct": extinct,
            "g_extinct": g_extinct,
            "draagkracht": float(w.gov.inst.draagkracht)
        }

    res_ctrl = observe_arm(w_ctrl, reg_ctrl)
    res_scarc = observe_arm(w_scarc, reg_scarc)

    dur = time.time() - t0
    return {
        "seed": seed,
        "ctrl": res_ctrl,
        "scarc": res_scarc,
        "duration": dur
    }


def main():
    print("=" * 80)
    print("EXPERIMENT A1d: OORLOGS-K/2 (DE STERKE ASYMMETRIEWET)")
    print("Protocol: Knockout bij Gen 30 | Controle (K=1536) vs Schaarste (K/2=780)")
    print("Horizon: 40 generaties post-knockout | 15 gepaarde zaden")
    print("=" * 80)

    with open("volwassen_kroniek.pkl", "rb") as f:
        volwassen_kroniek = pickle.load(f)
    print("Geladen: volwassen_kroniek.pkl\n")

    seeds = [42 + i * 13 for i in range(15)]
    print(f"Zaden ({len(seeds)}): {seeds}\n")

    results = []
    t_start = time.time()

    with ProcessPoolExecutor(max_workers=14) as executor:
        future_map = {executor.submit(run_single_a1d_seed, s, volwassen_kroniek): s for s in seeds}
        done = 0
        for fut in as_completed(future_map):
            done += 1
            res = fut.result()
            results.append(res)
            c = res["ctrl"]
            s = res["scarc"]
            print(
                f"[{done:02d}/15] Seed {res['seed']:3d} ({res['duration']:.1f}s) | "
                f"Ctrl N={c['mean_N_stabiel']:4.1f}, x_min={c['min_x']:.3f}, Ext={c['extinct']} | "
                f"K/2 N={s['mean_N_stabiel']:4.1f}, x_min={s['min_x']:.3f}, Ext={s['extinct']}"
            )

    print(f"\nAlle 15 gepaarde simulaties voltooid in {time.time() - t_start:.1f}s!\n")

    # Aggregaties en statistische analyse
    results.sort(key=lambda x: x["seed"])
    ctrl_N = [r["ctrl"]["mean_N_stabiel"] for r in results]
    scarc_N = [r["scarc"]["mean_N_stabiel"] for r in results]

    ctrl_xmin = [r["ctrl"]["min_x"] for r in results]
    scarc_xmin = [r["scarc"]["min_x"] for r in results]

    ctrl_gain = [r["ctrl"]["mean_gain"] for r in results]
    scarc_gain = [r["scarc"]["mean_gain"] for r in results]

    ctrl_dood = [r["ctrl"]["mean_dood"] for r in results]
    scarc_dood = [r["scarc"]["mean_dood"] for r in results]

    ctrl_P = [r["ctrl"]["p_mean"] for r in results]
    scarc_P = [r["scarc"]["p_mean"] for r in results]

    ctrl_ext = sum(1 for r in results if r["ctrl"]["extinct"])
    scarc_ext = sum(1 for r in results if r["scarc"]["extinct"])

    # Berekening van gamma_oorlog (vraag-elasticiteit)
    # N_ratio = scarc_N / ctrl_N
    # K_ratio = K_scarc / K_ctrl = 0.5
    # gamma = ln(N_scarc / N_ctrl) / ln(0.5)
    mean_ctrl_N = np.mean(ctrl_N)
    mean_scarc_N = np.mean(scarc_N)
    n_ratio = mean_scarc_N / mean_ctrl_N
    gamma_oorlog = np.log(n_ratio) / np.log(0.5)

    print("=" * 80)
    print("EMPIRISCH SCOREBORD EXPERIMENT A1d (OORLOGS-K/2)")
    print("=" * 80)
    print(f"{'Metriek':<32} | {'Arm A: Oorlog Controle (K)':<25} | {'Arm B: Oorlog Schaarste (K/2)':<25}")
    print("-" * 88)
    print(f"{'Draagkracht (K)':<32} | {results[0]['ctrl']['draagkracht']:<25.1f} | {results[0]['scarc']['draagkracht']:<25.1f}")
    print(f"{'Gem. Populatie (N_oorlog)':<32} | {mean_ctrl_N:5.1f} +/- {np.std(ctrl_N, ddof=1):4.1f}{'':<14} | {mean_scarc_N:5.1f} +/- {np.std(scarc_N, ddof=1):4.1f}")
    print(f"{'Diepste Biomassapunt (x_min)':<32} | {np.mean(ctrl_xmin):.4f} +/- {np.std(ctrl_xmin, ddof=1):.4f}{'':<12} | {np.mean(scarc_xmin):.4f} +/- {np.std(scarc_xmin, ddof=1):.4f}")
    print(f"{'Demografische Gain':<32} | {np.mean(ctrl_gain):5.2f} +/- {np.std(ctrl_gain, ddof=1):4.2f}{'':<14} | {np.mean(scarc_gain):5.2f} +/- {np.std(scarc_gain, ddof=1):4.2f}")
    print(f"{'Hongerdood per generatie':<32} | {np.mean(ctrl_dood):5.1f} +/- {np.std(ctrl_dood, ddof=1):4.1f}{'':<14} | {np.mean(scarc_dood):5.1f} +/- {np.std(scarc_dood, ddof=1):4.1f}")
    print(f"{'Parasitisme (P)':<32} | {np.mean(ctrl_P):.3f}{'':<20} | {np.mean(scarc_P):.3f}")
    print(f"{'Extincties':<32} | {ctrl_ext}/15 seeds{'':<15} | {scarc_ext}/15 seeds")
    print("-" * 88)
    print(f"Populatiekrimp Ratio (N_K2 / N_K): {n_ratio:.3f} (Voorspelling OxAlpha: ~0.54 of 15-22)")
    print(f"Gemeten Vraag-Elasticiteit in Oorlog (gamma_oorlog): {gamma_oorlog:.3f} (Voorspelling OxAlpha: ~= 0.0)")

    with open("results_experiment_a1d.pkl", "wb") as f:
        pickle.dump(results, f)
    print("\nResultaten opgeslagen in results_experiment_a1d.pkl")


if __name__ == "__main__":
    main()
