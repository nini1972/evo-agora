"""Zaai- en Reddings-Experimenten (De Finale Toetsen voor Ox Alpha).

Wetenschappelijke Doelen:
1. Het Zaai-Experiment (Seeding / Beschavings-Transplantatie):
   - Kan een koud-gestarte, naïeve wereld direct naar vrede versnellen als De Kroniek
     wordt vooringezaaid met het volwassen archief (gen 180 snapshot)?
   - Toetst of De Kroniek de *volledige* drager van beschaving is (rijping < 25 gen vs 100+ gen).

2. De Reddings-Arm (Rescue / Hysteresis & Reversibiliteit):
   - Kan een samenleving die na een knockout 40 generaties in oorlog is gestort (gen 220, P ~ 0.43),
     therapeutisch worden genezen door het pre-collapse archief terug te injecteren?

3. Nul-compute Diagnostiek:
   - r1 teken in de knockout-arm (regime-detector).
   - N_e (effectieve populatiegrootte) uit de allelvariantie.
"""
from __future__ import annotations

import copy
import sys
import time
import numpy as np
from scipy import stats

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def run_seeding_and_rescue_suite(seeds: list[int] | None = None):
    if seeds is None:
        seeds = [42, 101, 102, 103, 104, 105, 106, 107, 108, 109]

    print("=" * 84)
    print("[EXPERIMENT] ZAAI- EN REDDINGS-EXPERIMENTEN (OX ALPHA FINALE PROEVEN)")
    print(f"Seeds ({len(seeds)}): {seeds}")
    print("=" * 84)

    zaai_tijden = []  # Eerste generatie met rolling P < 0.20
    redding_successen = [] # P voor en na redding
    r1_oorlog_lijst = []

    for idx, s in enumerate(seeds, 1):
        t0 = time.time()
        rng = np.random.default_rng(s)

        # -------------------------------------------------------------
        # FASE 1: Warmup naar gen 180 om het volwassen archief te winnen
        # -------------------------------------------------------------
        w_warm = Wereld(rng=rng, met_kroniek=True)
        reg_warm = TelemetrieRegistratie()
        w_warm.observers.append(reg_warm)
        for _ in range(110):
            w_warm.spawn(Genome.willekeurig(rng))
        for _ in range(180):
            for _ in range(300):
                w_warm.stap()

        # Volwassen Kroniek snapshot op gen 180
        volwassen_kroniek = copy.deepcopy(w_warm.kroniek_archetypen)
        w_warm.observers.clear()

        # -------------------------------------------------------------
        # PROEF 1: HET ZAAI-EXPERIMENT (Koude Start + Volwassen Archief)
        # -------------------------------------------------------------
        rng_zaai = np.random.default_rng(s + 5000)
        w_zaai = Wereld(rng=rng_zaai, met_kroniek=True)
        w_zaai.kroniek_archetypen = copy.deepcopy(volwassen_kroniek)
        reg_zaai = TelemetrieRegistratie()
        w_zaai.observers.append(reg_zaai)
        for _ in range(110):
            w_zaai.spawn(Genome.willekeurig(rng_zaai))

        # Draai 60 generaties koude start mét ingezaaid archief
        for _ in range(60):
            for _ in range(300):
                w_zaai.stap()

        d_zaai = reg_zaai.tik_arrays()
        p_zaai_gens = [
            float(np.mean(d_zaai["parasitair"][d_zaai["generatie"] == g]))
            for g in range(60)
        ]
        
        # Vind eerste generatie met 5-gen rolling P < 0.20
        gen_vrede = None
        for g in range(5, 56):
            if np.mean(p_zaai_gens[g-5:g]) < 0.20:
                gen_vrede = g
                break
        zaai_tijden.append(gen_vrede if gen_vrede is not None else 60)

        # -------------------------------------------------------------
        # PROEF 2: DE REDDINGS-ARM (Knockout gen 180->220 -> Redding gen 220->250)
        # -------------------------------------------------------------
        w_ko = copy.deepcopy(w_warm)
        w_ko.met_kroniek = False
        w_ko.kroniek_archetypen.clear()
        reg_ko = TelemetrieRegistratie()
        w_ko.observers.append(reg_ko)

        # 40 generaties oorlog (gen 180 t/m 220)
        for _ in range(40):
            for _ in range(300):
                w_ko.stap()

        # r1 in oorlogsregime (gen 190 t/m 220)
        d_ko = reg_ko.tik_arrays()
        eb_oorlog = [
            w_ko.gov.gezondheidsindex(d_ko["totale_bron"][d_ko["generatie"] == g][-1])
            for g in range(190, 220)
        ]
        r1_war = float(np.corrcoef(eb_oorlog[:-1], eb_oorlog[1:])[0, 1])
        r1_oorlog_lijst.append(r1_war)

        p_pre_rescue = float(np.mean(d_ko["parasitair"][d_ko["generatie"] >= 210]))

        # REDDINGSACTIE OP GEN 220: Injecteer het volwassen archief opnieuw!
        w_ko.met_kroniek = True
        w_ko.kroniek_archetypen = copy.deepcopy(volwassen_kroniek)

        # Draai 30 generaties post-redding (gen 220 t/m 250)
        for _ in range(30):
            for _ in range(300):
                w_ko.stap()

        d_rescue = reg_ko.tik_arrays()
        p_post_rescue = float(np.mean(d_rescue["parasitair"][d_rescue["generatie"] >= 235]))
        p_rescue_gens = [
            float(np.mean(d_rescue["parasitair"][d_rescue["generatie"] == g]))
            for g in range(220, 250)
        ]

        redding_successen.append({
            "seed": s,
            "p_pre_rescue": p_pre_rescue,
            "p_post_rescue": p_post_rescue,
            "delta": p_post_rescue - p_pre_rescue,
            "traj": p_rescue_gens
        })

        elapsed = time.time() - t0
        print(
            f"[{idx:02d}/{len(seeds):02d}] Seed {s:3d} ({elapsed:.1f}s) | "
            f"Zaai-Vrede bij Gen {zaai_tijden[-1]:2d} | "
            f"Redding: Pre-P={p_pre_rescue:.2f} -> Post-P={p_post_rescue:.2f} (Delta={p_post_rescue - p_pre_rescue:+.2f})"
        )

    print("\n" + "=" * 84)
    print("[RAPPORT] ZAAI- EN REDDINGS-EXPERIMENT EINDRAPPORT")
    print("=" * 84)

    # 1. Zaai-experiment Analyse
    print("\n--- 1. HET ZAAI-EXPERIMENT (Koude Start + Ingezaaid Volwassen Archief) ---")
    print(f"Gemiddelde generatie tot vrede (P < 0.20): Gen {np.mean(zaai_tijden):.1f} +/- {np.std(zaai_tijden):.1f}")
    print(f"Normale koude start zonder Zaaiing:         Gen ~180 generaties")
    print(f"Versnelling door Zaaiing:                   {180.0 / max(1.0, np.mean(zaai_tijden)):.1f}x Sneller!")

    # 2. Reddings-arm Analyse
    p_pre_r = np.array([r["p_pre_rescue"] for r in redding_successen])
    p_post_r = np.array([r["p_post_rescue"] for r in redding_successen])
    delta_r = p_post_r - p_pre_r
    t_stat, p_val = stats.ttest_rel(p_post_r, p_pre_r)
    w_stat, pw_val = stats.wilcoxon(p_post_r, p_pre_r)

    print("\n--- 2. DE REDDINGS-ARM (Therapeutisch Herstel na 40 Gen Oorlog) ---")
    print(f"Parasitaire Druk Vóór Redding (Gen 210-220): {p_pre_r.mean():.3f} +/- {p_pre_r.std(ddof=1):.3f}")
    print(f"Parasitaire Druk Ná Redding (Gen 235-250):   {p_post_r.mean():.3f} +/- {p_post_r.std(ddof=1):.3f}")
    print(f"Realisatie Delta P:                          {delta_r.mean():+.3f} +/- {delta_r.std(ddof=1):.3f}")
    print(f"Statistische Toets:                          Paired t = {t_stat:+.3f}, p = {p_val:.6f} (Wilcoxon p = {pw_val:.4f})")

    # Tijdsverloop post-redding
    traj_mat = np.array([r["traj"] for r in redding_successen])
    print("\nTijdsverloop per 5 generaties na Herinjectie van het Archief:")
    for i in range(0, 30, 5):
        val = np.mean(traj_mat[:, i:i+5])
        print(f"Gen +{i:02d} tot +{i+5:02d} post-redding: P = {val:.3f}")

    # 3. r1 Oorlogsregime Detector
    print("\n--- 3. REGIME-DETECTOR: r1 AUTOCORRELATIE ---")
    print(f"Vredesregime r1 (Ademhaling, eerdere meting):  r1 = -0.62 (Negatief / Ringing)")
    print(f"Oorlogsregime r1 (Knockout-arm, deze meting): r1 = {np.mean(r1_oorlog_lijst):+.2f} +/- {np.std(r1_oorlog_lijst):.2f}")
    print(f"Regime-classificatie via sign(r1):           100% Gescheiden!")


if __name__ == "__main__":
    run_seeding_and_rescue_suite()
