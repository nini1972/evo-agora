"""Decompositie-Experiment (W vs P vs F) & Zaai-Grootboek (Gain-Lag Analyse).

Wetenschappelijke Vragen (Ox Alpha Finale P0):
1. Decompositie W/P/F:
   - Welk component van De Kroniek draagt de beschavingstransplantatie?
   - Arm W (Waarschuwingen / Strafregister: buckets met som/n < 0.50)
   - Arm P (Priors / Vertrouwensregister: buckets met som/n >= 0.50)
   - Arm F (Vol Archief: alle buckets)

2. Het Zaai-Grootboek:
   - Hoe evolueert de demografie (Cohort, Dood, Survivors, Gain) generatie-voor-generatie
     in de eerste 15 generaties na zaaiing?
   - Is er een 'Gain-Lag' tussen gedragsvrede (P < 0.20) en demografische vrede (Gain -> 1.00)?
"""
from __future__ import annotations

import copy
import time
import numpy as np
from scipy import stats

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def run_decomposition_and_zaai_grootboek_suite(seeds: list[int] | None = None):
    if seeds is None:
        seeds = [42, 101, 102, 103, 104, 105, 106, 107, 108, 109]

    print("=" * 86)
    print("[EXPERIMENT] DECOMPOSITIE (W vs P vs F) & ZAAI-GROOTBOEK (GAIN-LAG)")
    print(f"Seeds ({len(seeds)}): {seeds}")
    print("=" * 86)

    # 1. Warmup naar gen 180 om het canonieke volwassen archief te winnen
    print("--> Bezig met master warmup (180 gen) voor volwassen archief snapshot...", end="", flush=True)
    t_w0 = time.time()
    rng_master = np.random.default_rng(42)
    w_master = Wereld(rng=rng_master, met_kroniek=True)
    reg_master = TelemetrieRegistratie()
    w_master.observers.append(reg_master)
    for _ in range(110):
        w_master.spawn(Genome.willekeurig(rng_master))
    for _ in range(180):
        for _ in range(300):
            w_master.stap()
    volwassen_kroniek = copy.deepcopy(w_master.kroniek_archetypen)
    print(f" Klaar in {time.time() - t_w0:.1f}s ({len(volwassen_kroniek)} buckets in archief)!\n")

    # Splitsing van het archief
    kroniek_W = {
        k: v for k, v in volwassen_kroniek.items() if (v[0] / max(1e-6, v[1])) < 0.50
    }
    kroniek_P = {
        k: v for k, v in volwassen_kroniek.items() if (v[0] / max(1e-6, v[1])) >= 0.50
    }
    print(f"Archief-samenstelling: Totaal={len(volwassen_kroniek)} | W (Waarschuwingen)={len(kroniek_W)} | P (Priors)={len(kroniek_P)}\n")

    tijden_F, tijden_W, tijden_P = [], [], []
    zaai_grootboeken = []  # per generatie stats over gen 0 t/m 15

    for idx, s in enumerate(seeds, 1):
        t0 = time.time()

        # -------------------------------------------------------------
        # ARM F: Vol Archief (Full)
        # -------------------------------------------------------------
        rng_f = np.random.default_rng(s + 1000)
        w_f = Wereld(rng=rng_f, met_kroniek=True)
        w_f.kroniek_archetypen = copy.deepcopy(volwassen_kroniek)
        reg_f = TelemetrieRegistratie()
        w_f.observers.append(reg_f)
        for _ in range(110):
            w_f.spawn(Genome.willekeurig(rng_f))

        seed_ledger = []
        for g in range(50):
            es = w_f.gov.gezondheidsindex(w_f.totale_bron())
            ns = len([a for a in w_f.agents.values() if a.levend])
            for _ in range(300):
                w_f.stap()
            eb = w_f.gov.gezondheidsindex(w_f.totale_bron())
            evs = [e for e in reg_f.gebeurtenissen if e.tik >= g*300 and e.tik < (g+1)*300 and e.type.name == 'DOOD_HONGER']
            nd = len(evs)
            surv = ns - nd
            # parasitisme in deze generatie uit telemetry
            df_g = reg_f.tik_arrays()
            m_g = df_g["generatie"] == g
            p_gen = float(np.mean(df_g["parasitair"][m_g])) if m_g.any() else 0.0
            
            if g < 15:
                seed_ledger.append({
                    "gen": g,
                    "cohort": ns,
                    "dood": nd,
                    "survivors": max(0, surv),
                    "gain": ns / max(1, surv),
                    "ehi_boundary": eb,
                    "ehi_start": es,
                    "p_gem": p_gen
                })

        zaai_grootboeken.append(seed_ledger)

        df = reg_f.tik_arrays()
        p_gens_f = [float(np.mean(df["parasitair"][df["generatie"] == g])) for g in range(50)]
        gen_v_f = next((g for g in range(5, 46) if np.mean(p_gens_f[g-5:g]) < 0.20), 50)
        tijden_F.append(gen_v_f)

        # -------------------------------------------------------------
        # ARM W: Alleen Waarschuwingen (Strafregister / som/n < 0.50)
        # -------------------------------------------------------------
        rng_w = np.random.default_rng(s + 2000)
        w_w = Wereld(rng=rng_w, met_kroniek=True)
        w_w.kroniek_archetypen = copy.deepcopy(kroniek_W)
        reg_w = TelemetrieRegistratie()
        w_w.observers.append(reg_w)
        for _ in range(110):
            w_w.spawn(Genome.willekeurig(rng_w))
        for _ in range(50):
            for _ in range(300):
                w_w.stap()

        dw = reg_w.tik_arrays()
        p_gens_w = [float(np.mean(dw["parasitair"][dw["generatie"] == g])) for g in range(50)]
        gen_v_w = next((g for g in range(5, 46) if np.mean(p_gens_w[g-5:g]) < 0.20), 50)
        tijden_W.append(gen_v_w)

        # -------------------------------------------------------------
        # ARM P: Alleen Coöperatieve Priors (som/n >= 0.50)
        # -------------------------------------------------------------
        rng_p = np.random.default_rng(s + 3000)
        w_p = Wereld(rng=rng_p, met_kroniek=True)
        w_p.kroniek_archetypen = copy.deepcopy(kroniek_P)
        reg_p = TelemetrieRegistratie()
        w_p.observers.append(reg_p)
        for _ in range(110):
            w_p.spawn(Genome.willekeurig(rng_p))
        for _ in range(50):
            for _ in range(300):
                w_p.stap()

        dp = reg_p.tik_arrays()
        p_gens_p = [float(np.mean(dp["parasitair"][dp["generatie"] == g])) for g in range(50)]
        gen_v_p = next((g for g in range(5, 46) if np.mean(p_gens_p[g-5:g]) < 0.20), 50)
        tijden_P.append(gen_v_p)

        elapsed = time.time() - t0
        print(
            f"[{idx:02d}/{len(seeds):02d}] Seed {s:3d} ({elapsed:.1f}s) | "
            f"Vrede bij: Arm F (Vol) = Gen {gen_v_f:2d} | "
            f"Arm W (Waarsch) = Gen {gen_v_w:2d} | "
            f"Arm P (Priors) = Gen {gen_v_p:2d}"
        )

    print("\n" + "=" * 86)
    print("[RAPPORT] DECOMPOSITIE-EXPERIMENT (W vs P vs F)")
    print("=" * 86)
    print(f"Arm F (Vol Archief):           Gen {np.mean(tijden_F):.1f} +/- {np.std(tijden_F, ddof=1):.1f}  (Baseline Zaai)")
    print(f"Arm W (Alleen Waarschuwingen): Gen {np.mean(tijden_W):.1f} +/- {np.std(tijden_W, ddof=1):.1f}")
    print(f"Arm P (Alleen Priors):         Gen {np.mean(tijden_P):.1f} +/- {np.std(tijden_P, ddof=1):.1f}")
    print(f"Koude Start Zónder Zaaiing:    Gen ~180 generaties")

    # Toetsen W vs F en P vs F
    tw, pw = stats.ttest_rel(tijden_W, tijden_F)
    tp, pp = stats.ttest_rel(tijden_P, tijden_F)
    print(f"\nStatistische Vergelijking t.o.v. Vol Archief (Arm F):")
    print(f"- Arm W vs Arm F: Paired t = {tw:+.3f}, p = {pw:.4f}")
    print(f"- Arm P vs Arm F: Paired t = {tp:+.3f}, p = {pp:.4f}")

    # 2. Zaai-Grootboek & Gain-Lag Analyse
    print("\n" + "=" * 86)
    print("[RAPPORT] HET ZAAI-GROOTBOEK (GAIN-LAG ANALYSE GEN 0 t/m 14)")
    print("=" * 86)
    print(f"{'Gen':<4} | {'Cohort (N_start)':<16} | {'Hongerdood':<12} | {'Survivors':<11} | {'Gain':<8} | {'EHI_bound':<10} | {'Parasitisme (P)':<14}")
    print("-" * 86)
    for g in range(15):
        c_m = np.mean([zg[g]["cohort"] for zg in zaai_grootboeken])
        d_m = np.mean([zg[g]["dood"] for zg in zaai_grootboeken])
        s_m = np.mean([zg[g]["survivors"] for zg in zaai_grootboeken])
        g_m = np.mean([zg[g]["gain"] for zg in zaai_grootboeken])
        eb_m = np.mean([zg[g]["ehi_boundary"] for zg in zaai_grootboeken])
        p_m = np.mean([zg[g]["p_gem"] for zg in zaai_grootboeken])
        print(f"{g:02d}   | {c_m:16.1f} | {d_m:12.1f} | {s_m:11.1f} | {g_m:8.2f} | {eb_m:10.3f} | {p_m:14.3f}")


if __name__ == "__main__":
    run_decomposition_and_zaai_grootboek_suite()
