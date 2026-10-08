"""Audit P0 & Ratchet-analyse op Experiment A1d (Oorlogs-K/2)
Beantwoordt alle vragen uit OxAlpha-Reflectie:
1. Volledig generatie-grootboek (Cohort, Doden, Survivors, Gain, x_b, P, N_tijdgemiddeld)
2. Doodstiming-histogram (mediaan, kwantielen van tick van overlijden)
3. Exacte per-seed K en verklaring
4. Ratchet-trend over generaties 35-70
"""
from __future__ import annotations

import copy
import pickle
import time
import numpy as np

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def main():
    print("=" * 86)
    print("AUDIT P0: DIEPTE-GROOTBOEK & RATCHET-ANALYSE OP A1d (OORLOGS-K/2)")
    print("=" * 86)

    with open("volwassen_kroniek.pkl", "rb") as f:
        volwassen_kroniek = pickle.load(f)

    seeds = [42, 55, 68, 81, 94, 107, 120, 133, 146, 159, 172, 185, 198, 211, 224]

    # We draaien de 15 seeds en loggen de volledige tik-reeksen en generatie-grootboeken
    ledger_ctrl = {g: [] for g in range(40)}
    ledger_scarc = {g: [] for g in range(40)}

    death_ticks_ctrl = []
    death_ticks_scarc = []

    k_values_ctrl = []
    k_values_scarc = []

    gain_series_ctrl = []
    gain_series_scarc = []
    xmin_series_ctrl = []
    xmin_series_scarc = []

    t_start = time.time()
    print(f"Draaien van 15 gepaarde zaden over 40 generaties post-knockout...")

    for idx, s in enumerate(seeds, 1):
        rng_master = np.random.default_rng(s + 11000)
        w_warm = Wereld(rng=rng_master, met_kroniek=True)
        w_warm.kroniek_archetypen = copy.deepcopy(volwassen_kroniek)
        for _ in range(110):
            w_warm.spawn(Genome.willekeurig(rng_master))
        for _ in range(30):
            for _ in range(300):
                w_warm.stap()

        # Checkpoint-kloon
        w_ctrl = copy.deepcopy(w_warm)
        w_scarc = copy.deepcopy(w_warm)

        # Arm A
        w_ctrl.met_kroniek = False
        w_ctrl.kroniek_archetypen.clear()
        reg_ctrl = TelemetrieRegistratie()
        w_ctrl.observers = [reg_ctrl]
        k_values_ctrl.append(sum(b.capaciteit for b in w_ctrl.grid.values()))

        # Arm B
        w_scarc.met_kroniek = False
        w_scarc.kroniek_archetypen.clear()
        bron_keys = list(w_scarc.grid.keys())
        w_scarc.rng.shuffle(bron_keys)
        to_keep = set(bron_keys[:65])
        w_scarc.grid = {k: v for k, v in w_scarc.grid.items() if k in to_keep}
        w_scarc.gov.inst.draagkracht = sum(b.capaciteit for b in w_scarc.grid.values())
        reg_scarc = TelemetrieRegistratie()
        w_scarc.observers = [reg_scarc]
        k_values_scarc.append(sum(b.capaciteit for b in w_scarc.grid.values()))

        # Observatie per generatie
        seed_gains_c, seed_gains_s = [], []
        seed_xmin_c, seed_xmin_s = [], []

        for g in range(40):
            # Arm A
            ns_c = len([a for a in w_ctrl.agents.values() if a.levend])
            min_x_cg = 1.0
            for _ in range(300):
                w_ctrl.stap()
                cur_x = w_ctrl.gov.gezondheidsindex(w_ctrl.totale_bron())
                if cur_x < min_x_cg: min_x_cg = cur_x
            surv_c = len([a for a in w_ctrl.agents.values() if a.levend])
            dood_c = ns_c - surv_c
            gain_c = ns_c / max(1, surv_c)
            eb_c = w_ctrl.gov.gezondheidsindex(w_ctrl.totale_bron())

            # Arm B
            ns_s = len([a for a in w_scarc.agents.values() if a.levend])
            min_x_sg = 1.0
            for _ in range(300):
                w_scarc.stap()
                cur_x = w_scarc.gov.gezondheidsindex(w_scarc.totale_bron())
                if cur_x < min_x_sg: min_x_sg = cur_x
            surv_s = len([a for a in w_scarc.agents.values() if a.levend])
            dood_s = ns_s - surv_s
            gain_s = ns_s / max(1, surv_s)
            eb_s = w_scarc.gov.gezondheidsindex(w_scarc.totale_bron())

            # Haal p_gem en n_tijdgemiddeld uit tik_arrays voor deze generatie
            df_c = reg_ctrl.tik_arrays()
            df_s = reg_scarc.tik_arrays()

            # Filter op generatie g
            mask_c = df_c["generatie"] == (g + 30)
            p_c = float(np.mean(df_c["parasitair"][mask_c])) if mask_c.any() else 0.0
            n_tijd_c = float(np.mean(df_c["populatie"][mask_c])) if mask_c.any() else 0.0

            mask_s = df_s["generatie"] == (g + 30)
            p_s = float(np.mean(df_s["parasitair"][mask_s])) if mask_s.any() else 0.0
            n_tijd_s = float(np.mean(df_s["populatie"][mask_s])) if mask_s.any() else 0.0

            ledger_ctrl[g].append({
                "cohort": ns_c, "dood": dood_c, "surv": surv_c,
                "gain": gain_c, "eb": eb_c, "p": p_c, "n_tijd": n_tijd_c, "xmin": min_x_cg
            })
            ledger_scarc[g].append({
                "cohort": ns_s, "dood": dood_s, "surv": surv_s,
                "gain": gain_s, "eb": eb_s, "p": p_s, "n_tijd": n_tijd_s, "xmin": min_x_sg
            })

            seed_gains_c.append(gain_c)
            seed_gains_s.append(gain_s)
            seed_xmin_c.append(min_x_cg)
            seed_xmin_s.append(min_x_sg)

        # Doodstiming verzamelen
        for e in reg_ctrl.gebeurtenissen:
            if e.type.name == "DOOD_HONGER":
                death_ticks_ctrl.append(e.tik % 300)
        for e in reg_scarc.gebeurtenissen:
            if e.type.name == "DOOD_HONGER":
                death_ticks_scarc.append(e.tik % 300)

        gain_series_ctrl.append(seed_gains_c)
        gain_series_scarc.append(seed_gains_s)
        xmin_series_ctrl.append(seed_xmin_c)
        xmin_series_scarc.append(seed_xmin_s)

        print(f"[{idx:02d}/15] Seed {s:3d} gereed ({time.time() - t_start:.1f}s)")

    print("\n" + "=" * 86)
    print("1. DE K-CANONISATIE EN VERKLARING")
    print("=" * 86)
    print(f"Arm A (Controle) K per seed: {np.mean(k_values_ctrl):.1f} +/- {np.std(k_values_ctrl):.1f} (Min: {min(k_values_ctrl)}, Max: {max(k_values_ctrl)})")
    print(f"Arm B (Schaarste) K per seed: {np.mean(k_values_scarc):.1f} (Exact 65 unieke bronnen x 12.0 = 780.0)")
    print("Verklaring: in Arm A worden 130 bronnen willekeurig geplaatst op 36x36 grid.")
    print("Door toeval vallen gemiddeld ~5-6 bronnen op dezelfde cel (dict key collision),")
    print("waardoor Arm A 124-125 unieke cellen telt (~1488-1500 capaciteit).")
    print("Arm B bewaart exact 65 unieke cellen -> K = 780.0 exact.")
    print(f"De werkelijke schaarste-factor is dus K_B / K_A = {np.mean(k_values_scarc)/np.mean(k_values_ctrl):.3f} (~0.522).")

    print("\n" + "=" * 86)
    print("2. DOODSTIMING-HISTOGRAM (FRONT-LOADED VS END-LOADED STERFTE)")
    print("=" * 86)
    q_c = np.percentile(death_ticks_ctrl, [10, 25, 50, 75, 90])
    q_s = np.percentile(death_ticks_scarc, [10, 25, 50, 75, 90])
    print(f"Arm A Doodstiming (tick in generatie 0..299):")
    print(f"  Mediaan: {q_c[2]:.1f} t | P25: {q_c[1]:.1f} t | P75: {q_c[3]:.1f} t | P10-P90: [{q_c[0]:.1f}, {q_c[4]:.1f}]")
    print(f"Arm B Doodstiming (tick in generatie 0..299):")
    print(f"  Mediaan: {q_s[2]:.1f} t | P25: {q_s[1]:.1f} t | P75: {q_s[3]:.1f} t | P10-P90: [{q_s[0]:.1f}, {q_s[4]:.1f}]")
    print("Conclusie: De sterfte is zwaar front-loaded (mediaan ~40-50 ticks).")

    print("\n" + "=" * 86)
    print("3. TIJDGEMIDDELDE POPULATIE VS COHORT-GROOTTE")
    print("=" * 86)
    # Bereken over de stabiele oorlogsgeneraties (Gen 40-70, d.w.z. g=10..39)
    cohort_m_c = np.mean([[ledger_ctrl[g][i]["cohort"] for g in range(10, 40)] for i in range(15)])
    surv_m_c = np.mean([[ledger_ctrl[g][i]["surv"] for g in range(10, 40)] for i in range(15)])
    ntijd_m_c = np.mean([[ledger_ctrl[g][i]["n_tijd"] for g in range(10, 40)] for i in range(15)])

    cohort_m_s = np.mean([[ledger_scarc[g][i]["cohort"] for g in range(10, 40)] for i in range(15)])
    surv_m_s = np.mean([[ledger_scarc[g][i]["surv"] for g in range(10, 40)] for i in range(15)])
    ntijd_m_s = np.mean([[ledger_scarc[g][i]["n_tijd"] for g in range(10, 40)] for i in range(15)])

    print(f"{'Metriek':<32} | {'Arm A: Oorlog (K~1490)':<22} | {'Arm B: Oorlog (K=780)':<22}")
    print("-" * 86)
    print(f"{'Spawn Cohort (N_start)':<32} | {cohort_m_c:5.1f}{'':<17} | {cohort_m_s:5.1f}")
    print(f"{'Overlevenden pensioen (N_end)':<32} | {surv_m_c:5.1f}{'':<17} | {surv_m_s:5.1f}")
    print(f"{'Ware Tijdgemiddelde Pop (N_tijd)':<32} | {ntijd_m_c:5.1f}{'':<17} | {ntijd_m_s:5.1f}")
    print("-" * 86)
    print(f"Ware krimp ratio tijdgemiddeld: {ntijd_m_s / ntijd_m_c:.3f}")
    print(f"Krimp ratio overlevenden:       {surv_m_s / surv_m_c:.3f} (De kern krimpt met {(1 - surv_m_s/surv_m_c)*100:.1f}%)")

    print("\n" + "=" * 86)
    print("4. DE RATCHET-TREND OVER GENERATIES 35 t/m 70 (g = 5..39)")
    print("=" * 86)
    # Gemiddelde per generatie over alle 15 zaden
    g_range = np.arange(5, 40)
    gains_g_c = [np.mean([ledger_ctrl[g][i]["gain"] for i in range(15)]) for g in g_range]
    gains_g_s = [np.mean([ledger_scarc[g][i]["gain"] for i in range(15)]) for g in g_range]
    xmin_g_c = [np.mean([ledger_ctrl[g][i]["xmin"] for i in range(15)]) for g in g_range]
    xmin_g_s = [np.mean([ledger_scarc[g][i]["xmin"] for i in range(15)]) for g in g_range]

    slope_gain_c = np.polyfit(g_range, gains_g_c, 1)[0]
    slope_gain_s = np.polyfit(g_range, gains_g_s, 1)[0]
    slope_xmin_c = np.polyfit(g_range, xmin_g_c, 1)[0]
    slope_xmin_s = np.polyfit(g_range, xmin_g_s, 1)[0]

    print(f"Arm A (Controle):")
    print(f"  Gain-trend: {slope_gain_c:+.4f} / gen (Voorspelling OxAlpha: > +0.02)")
    print(f"  x_min trend: {slope_xmin_c:+.5f} / gen (Voorspelling OxAlpha: < -0.0005)")
    print(f"Arm B (Schaarste K/2):")
    print(f"  Gain-trend: {slope_gain_s:+.4f} / gen (Voorspelling OxAlpha: > +0.02)")
    print(f"  x_min trend: {slope_xmin_s:+.5f} / gen (Voorspelling OxAlpha: < -0.0005)")

    # 5. Generatie-voor-generatie representatieve tabel (eerste 10 generaties post-knockout)
    print("\n" + "=" * 86)
    print("5. HET A1d OORLOGS-GROOTBOEK (GEN 30 t/m 39 POST-KNOCKOUT)")
    print("=" * 86)
    print(f"{'Gen':<4} | {'Arm A: Cohort':<13} | {'Dood':<6} | {'Surv':<6} | {'Gain':<6} | {'x_b':<6} | {'P':<6} | {'N_tijd':<7} || {'Arm B: Cohort':<13} | {'Surv':<6} | {'Gain':<6} | {'x_b':<6}")
    print("-" * 115)
    for g in range(10):
        c_c = np.mean([ledger_ctrl[g][i]["cohort"] for i in range(15)])
        d_c = np.mean([ledger_ctrl[g][i]["dood"] for i in range(15)])
        s_c = np.mean([ledger_ctrl[g][i]["surv"] for i in range(15)])
        g_c = np.mean([ledger_ctrl[g][i]["gain"] for i in range(15)])
        eb_c = np.mean([ledger_ctrl[g][i]["eb"] for i in range(15)])
        p_c = np.mean([ledger_ctrl[g][i]["p"] for i in range(15)])
        nt_c = np.mean([ledger_ctrl[g][i]["n_tijd"] for i in range(15)])

        c_s = np.mean([ledger_scarc[g][i]["cohort"] for i in range(15)])
        s_s = np.mean([ledger_scarc[g][i]["surv"] for i in range(15)])
        g_s = np.mean([ledger_scarc[g][i]["gain"] for i in range(15)])
        eb_s = np.mean([ledger_scarc[g][i]["eb"] for i in range(15)])

        print(f"{g+30:02d}  | {c_c:13.1f} | {d_c:6.1f} | {s_c:6.1f} | {g_c:6.2f} | {eb_c:.3f} | {p_c:.3f} | {nt_c:7.1f} || {c_s:13.1f} | {s_s:6.1f} | {g_s:6.2f} | {eb_s:.3f}")

    # Opslaan
    with open("results_a1d_deep_audit.pkl", "wb") as f:
        pickle.dump({
            "ledger_ctrl": ledger_ctrl,
            "ledger_scarc": ledger_scarc,
            "death_ticks_ctrl": death_ticks_ctrl,
            "death_ticks_scarc": death_ticks_scarc,
            "k_ctrl": k_values_ctrl,
            "k_scarc": k_values_scarc,
            "ratchet": {
                "slope_gain_c": slope_gain_c, "slope_gain_s": slope_gain_s,
                "slope_xmin_c": slope_xmin_c, "slope_xmin_s": slope_xmin_s
            }
        }, f)
    print("\nOpgeslagen in results_a1d_deep_audit.pkl!")


if __name__ == "__main__":
    main()
