"""Vredesregime Knockout Ablatie-Experiment: De Kroniek in Vredestijd.

Wetenschappelijke Vraagstelling (Ox Alpha Finding C - Re-Test):
"Heeft institutioneel geheugen (De Kroniek) pas haar werkelijke waarde in
een gevestigd Vredesregime (P < 0.20), waar criminaliteit een zeldzaam
risico is en pasgeborenen zónder Kroniek naïef worden en roof-epidemieën ontketenen?"

Protocol:
1. Warmup-fase: 180 generaties (54.000 ticks) mét Kroniek om het stabiele vredesregime te bereiken.
2. Checkpoint-Kloon op Generatie 180:
   - Arm A (Controle): Behoudt De Kroniek (met_kroniek=True).
   - Arm B (Knockout): De Kroniek wordt abrupt uitgeschakeld en gewist (met_kroniek=False).
3. Post-Knockout Observatie: Beide armen draaien 40 generaties verder (gen 180 t/m 220)
   vanaf exact dezelfde toestand en RNG.
4. Statistische Toetsen:
   - Wilcoxon signed-rank test (gepaard) op P_post en Delta P.
   - Staart-overschrijdingsfrequentie (aandeel generaties met P > 0.50 en P > 0.60).
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


def run_single_peace_seed(
    seed: int, warmup_gens: int = 180, post_gens: int = 40
) -> dict:
    t0 = time.time()
    rng = np.random.default_rng(seed)
    w_warm = Wereld(rng=rng, met_kroniek=True)
    reg_warm = TelemetrieRegistratie()
    w_warm.observers.append(reg_warm)

    # 1. Initiële spawn
    for _ in range(110):
        w_warm.spawn(Genome.willekeurig(rng))

    # 2. Warmup-fase naar vredesregime (180 generaties)
    for _ in range(warmup_gens):
        for _ in range(300):
            w_warm.stap()

    d_warm = reg_warm.tik_arrays()
    # Baseline pre-knockout venster: laatste 20 generaties (gen 160 t/m 180)
    mask_pre = (d_warm["generatie"] >= (warmup_gens - 20)) & (d_warm["generatie"] < warmup_gens)
    p_pre = float(np.mean(d_warm["parasitair"][mask_pre])) if mask_pre.any() else 0.0
    ehi_pre = float(np.mean(d_warm["ehi"][mask_pre])) if mask_pre.any() else 0.0
    h100_pre = float(np.mean(d_warm["handels_per_100"][mask_pre])) if mask_pre.any() else 0.0

    # Koppel warm-up observers los voor zuivere deepcopy
    w_warm.observers.clear()

    # 3. Exacte toestand klonen voor Arm A en Arm B
    w_aan = copy.deepcopy(w_warm)
    w_uit = copy.deepcopy(w_warm)

    w_aan.met_kroniek = True
    reg_aan = TelemetrieRegistratie()
    w_aan.observers.append(reg_aan)

    w_uit.met_kroniek = False
    w_uit.kroniek_archetypen.clear()
    reg_uit = TelemetrieRegistratie()
    w_uit.observers.append(reg_uit)

    # 4. Post-knockout fase (40 generaties)
    for _ in range(post_gens):
        for _ in range(300):
            w_aan.stap()
            w_uit.stap()

    d_aan = reg_aan.tik_arrays()
    d_uit = reg_uit.tik_arrays()

    p_post_aan = float(np.mean(d_aan["parasitair"])) if len(d_aan) else 0.0
    p_post_uit = float(np.mean(d_uit["parasitair"])) if len(d_uit) else 0.0

    p_peak_aan = float(np.max(d_aan["parasitair"])) if len(d_aan) else 0.0
    p_peak_uit = float(np.max(d_uit["parasitair"])) if len(d_uit) else 0.0

    # Staart-overschrijdingsfrequenties (fractie van tikken)
    p_arr_aan = d_aan["parasitair"]
    p_arr_uit = d_uit["parasitair"]
    ov_05_aan = float(np.mean(p_arr_aan > 0.50)) if len(p_arr_aan) else 0.0
    ov_05_uit = float(np.mean(p_arr_uit > 0.50)) if len(p_arr_uit) else 0.0
    ov_06_aan = float(np.mean(p_arr_aan > 0.60)) if len(p_arr_aan) else 0.0
    ov_06_uit = float(np.mean(p_arr_uit > 0.60)) if len(p_arr_uit) else 0.0

    ehi_post_aan = float(np.mean(d_aan["ehi"])) if len(d_aan) else 0.0
    ehi_post_uit = float(np.mean(d_uit["ehi"])) if len(d_uit) else 0.0

    h100_post_aan = float(np.mean(d_aan["handels_per_100"])) if len(d_aan) else 0.0
    h100_post_uit = float(np.mean(d_uit["handels_per_100"])) if len(d_uit) else 0.0

    h_aan = sum(1 for g in reg_aan.gebeurtenissen if g.type.name.startswith("HANDEL"))
    h_uit = sum(1 for g in reg_uit.gebeurtenissen if g.type.name.startswith("HANDEL"))

    ov_aan = sum(1 for g in reg_aan.gebeurtenissen if g.type.name.startswith("OVERVAL"))
    ov_uit = sum(1 for g in reg_uit.gebeurtenissen if g.type.name.startswith("OVERVAL"))

    # Traject per 5 generaties
    traj_aan = []
    traj_uit = []
    for g_idx in range(0, post_gens, 5):
        m_a = (d_aan["generatie"] >= warmup_gens + g_idx) & (d_aan["generatie"] < warmup_gens + g_idx + 5)
        m_u = (d_uit["generatie"] >= warmup_gens + g_idx) & (d_uit["generatie"] < warmup_gens + g_idx + 5)
        traj_aan.append(float(np.mean(d_aan["parasitair"][m_a])) if m_a.any() else 0.0)
        traj_uit.append(float(np.mean(d_uit["parasitair"][m_u])) if m_u.any() else 0.0)

    elapsed = time.time() - t0
    return {
        "seed": seed,
        "elapsed": elapsed,
        "p_pre": p_pre,
        "ehi_pre": ehi_pre,
        "h100_pre": h100_pre,
        "p_post_aan": p_post_aan,
        "p_post_uit": p_post_uit,
        "p_peak_aan": p_peak_aan,
        "p_peak_uit": p_peak_uit,
        "ov_05_aan": ov_05_aan,
        "ov_05_uit": ov_05_uit,
        "ov_06_aan": ov_06_aan,
        "ov_06_uit": ov_06_uit,
        "delta_p_aan": p_post_aan - p_pre,
        "delta_p_uit": p_post_uit - p_pre,
        "ehi_post_aan": ehi_post_aan,
        "ehi_post_uit": ehi_post_uit,
        "h100_post_aan": h100_post_aan,
        "h100_post_uit": h100_post_uit,
        "h_aan": h_aan,
        "h_uit": h_uit,
        "ov_aan": ov_aan,
        "ov_uit": ov_uit,
        "traj_aan": traj_aan,
        "traj_uit": traj_uit,
    }


def run_peace_knockout_suite(
    seeds: list[int] | None = None, warmup_gens: int = 180, post_gens: int = 40
):
    if seeds is None:
        # 15 gepaarde seeds voor statistische power
        seeds = [42, 101, 102, 103, 104, 105, 106, 107, 108, 109, 201, 202, 203, 204, 205]

    print("=" * 82)
    print("[EXPERIMENT] VREDESREGIME KNOCKOUT ABLATIE (OX ALPHA FINDING C)")
    print(f"Seeds ({len(seeds)}): {seeds}")
    print(f"Warmup: {warmup_gens} gen (54.000 ticks) | Post-Knockout: {post_gens} gen (12.000 ticks)")
    print("=" * 82)

    results: list[dict] = []
    for idx, s in enumerate(seeds, 1):
        print(f"[{idx:02d}/{len(seeds):02d}] Seed {s:3d} (Warmup {warmup_gens}g + 2x{post_gens}g)...", end="", flush=True)
        res = run_single_peace_seed(s, warmup_gens=warmup_gens, post_gens=post_gens)
        results.append(res)
        print(
            f" Klaar in {res['elapsed']:.1f}s | Pre-P={res['p_pre']:.2f} -> "
            f"Post-AAN={res['p_post_aan']:.2f}, Post-UIT={res['p_post_uit']:.2f} | "
            f"P_max(A={res['p_peak_aan']:.2f}, U={res['p_peak_uit']:.2f})"
        )

    # Arrays voor analyses
    p_pre = np.array([r["p_pre"] for r in results])
    p_aan = np.array([r["p_post_aan"] for r in results])
    p_uit = np.array([r["p_post_uit"] for r in results])
    p_peak_aan = np.array([r["p_peak_aan"] for r in results])
    p_peak_uit = np.array([r["p_peak_uit"] for r in results])
    ov05_aan = np.array([r["ov_05_aan"] for r in results])
    ov05_uit = np.array([r["ov_05_uit"] for r in results])
    ov06_aan = np.array([r["ov_06_aan"] for r in results])
    ov06_uit = np.array([r["ov_06_uit"] for r in results])
    delta_aan = np.array([r["delta_p_aan"] for r in results])
    delta_uit = np.array([r["delta_p_uit"] for r in results])
    h_aan = np.array([r["h_aan"] for r in results])
    h_uit = np.array([r["h_uit"] for r in results])
    ov_aan = np.array([r["ov_aan"] for r in results])
    ov_uit = np.array([r["ov_uit"] for r in results])
    h100_aan = np.array([r["h100_post_aan"] for r in results])
    h100_uit = np.array([r["h100_post_uit"] for r in results])

    # Hypothesetoetsen
    # 1. Wilcoxon Signed-Rank Test (gepaarde verdelingsvrije toets)
    diff_p = p_uit - p_aan
    if np.all(diff_p == 0):
        w_stat, p_wilcoxon = 0.0, 1.0
    else:
        w_stat, p_wilcoxon = stats.wilcoxon(p_uit, p_aan, alternative="two-sided")

    # 2. Paired Student's t-test
    t_paired, p_paired = stats.ttest_rel(p_uit, p_aan)

    # 3. Wilcoxon op staartoverschrijding (P > 0.50)
    diff_ov = ov05_uit - ov05_aan
    if np.all(diff_ov == 0):
        w_ov, p_wilcoxon_ov = 0.0, 1.0
    else:
        w_ov, p_wilcoxon_ov = stats.wilcoxon(ov05_uit, ov05_aan, alternative="two-sided")

    # 4. Gepaarde Cohen's d (op Delta P)
    diff_delta = delta_uit - delta_aan
    cohens_d_paired = float(np.mean(diff_delta) / max(1e-6, np.std(diff_delta, ddof=1)))

    print("\n" + "=" * 82)
    print("[RAPPORT] VREDESREGIME KNOCKOUT EINDRAPPORT (OX ALPHA PROTOCOL)")
    print("=" * 82)
    print(f"{'Metriek':<36} | {'Controle (Kroniek AAN)':<20} | {'Knockout (Kroniek UIT)':<20}")
    print("-" * 82)
    print(f"{'Pre-Knockout P (Gen 160-180)':<36} | {p_pre.mean():.3f} +/- {p_pre.std(ddof=1):.3f}             | {p_pre.mean():.3f} +/- {p_pre.std(ddof=1):.3f}")
    print(f"{'Post-Knockout P (Gen 180-220)':<36} | {p_aan.mean():.3f} +/- {p_aan.std(ddof=1):.3f}             | {p_uit.mean():.3f} +/- {p_uit.std(ddof=1):.3f}")
    print(f"{'Delta P (Post - Pre)':<36} | {delta_aan.mean():+.3f} +/- {delta_aan.std(ddof=1):.3f}            | {delta_uit.mean():+.3f} +/- {delta_uit.std(ddof=1):.3f}")
    print(f"{'Piek Parasitisme (P_max)':<36} | {p_peak_aan.mean():.3f} +/- {p_peak_aan.std(ddof=1):.3f}             | {p_peak_uit.mean():.3f} +/- {p_peak_uit.std(ddof=1):.3f}")
    print(f"{'Staartrisico: Fractie P > 0.50':<36} | {ov05_aan.mean()*100:.1f}% +/- {ov05_aan.std(ddof=1)*100:.1f}%           | {ov05_uit.mean()*100:.1f}% +/- {ov05_uit.std(ddof=1)*100:.1f}%")
    print(f"{'Staartrisico: Fractie P > 0.60':<36} | {ov06_aan.mean()*100:.1f}% +/- {ov06_aan.std(ddof=1)*100:.1f}%           | {ov06_uit.mean()*100:.1f}% +/- {ov06_uit.std(ddof=1)*100:.1f}%")
    print(f"{'Handelstransacties (Post)':<36} | {h_aan.mean():.1f} +/- {h_aan.std(ddof=1):.1f}               | {h_uit.mean():.1f} +/- {h_uit.std(ddof=1):.1f}")
    print(f"{'Handels per 100 Tikken':<36} | {h100_aan.mean():.2f} +/- {h100_aan.std(ddof=1):.2f}               | {h100_uit.mean():.2f} +/- {h100_uit.std(ddof=1):.2f}")
    print(f"{'Aantal Overvallen (Post)':<36} | {ov_aan.mean():.1f} +/- {ov_aan.std(ddof=1):.1f}             | {ov_uit.mean():.1f} +/- {ov_uit.std(ddof=1):.1f}")
    print("=" * 82)

    print("\n[HYPOTHESETOETSEN & EFFECTGROOTTE]")
    print(f"- Wilcoxon Signed-Rank Test (gepaard):      W = {w_stat:.1f}, p = {p_wilcoxon:.4f}")
    print(f"- Paired Student's t-test:                   t = {t_paired:+.3f}, p = {p_paired:.4f}")
    print(f"- Wilcoxon op Staartoverschrijding (P>0.5):  W = {w_ov:.1f}, p = {p_wilcoxon_ov:.4f}")
    print(f"- Gepaarde Cohen's d:                        d = {cohens_d_paired:+.2f}")

    # Tijdsverloop na knockout per 5 generaties
    traj_aan_mat = np.array([r["traj_aan"] for r in results])
    traj_uit_mat = np.array([r["traj_uit"] for r in results])
    print("\n[TIJDSVERLOOP VAN PARASITISME NA KNOCKOUT IN VREDESTIJD]")
    print(f"{'Venster':<22} | {'Controle (AAN)':<16} | {'Knockout (UIT)':<16} | {'Verschil':<12}")
    print("-" * 72)
    for idx in range(traj_aan_mat.shape[1]):
        label = f"Gen +{idx*5:02d} tot +{(idx+1)*5:02d}"
        val_a = traj_aan_mat[:, idx].mean()
        val_u = traj_uit_mat[:, idx].mean()
        diff = val_u - val_a
        print(f"{label:<22} | {val_a:.3f}            | {val_u:.3f}            | {diff:+.3f}")
    print("=" * 82)


if __name__ == "__main__":
    run_peace_knockout_suite()
