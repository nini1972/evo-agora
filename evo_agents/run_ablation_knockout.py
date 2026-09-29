"""Warm Checkpoint Knockout Ablation Experiment: De Kroniek ON vs OFF.

Methodologie:
1. Warmup-fase: Laat de simulatie 50 generaties (15.000 ticks) evolueren mét Kroniek,
   totdat de bevolking en het institutionele geheugen (De Kroniek) volledig gevestigd zijn.
2. Knockout-splitsing op Generatie 50:
   - Arm A (Controle): Behoudt De Kroniek (met_kroniek=True).
   - Arm B (Knockout): De Kroniek wordt plotseling UITGEZET (met_kroniek=False en
     kroniek_archetypen gewist voor alle toekomstige cohorten).
3. Post-Knockout Observatie: Beide armen draaien 30 generaties verder (gen 50 t/m 80)
   vanaf exact dezelfde toestand en RNG.
"""
from __future__ import annotations

import copy
import numpy as np
from scipy import stats

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def run_knockout_single_seed(
    seed: int, warmup_gens: int = 50, post_gens: int = 30
) -> dict:
    rng = np.random.default_rng(seed)
    w_warm = Wereld(rng=rng, met_kroniek=True)
    reg_warm = TelemetrieRegistratie()
    w_warm.observers.append(reg_warm)

    # 1. Initiële spawn
    for _ in range(110):
        w_warm.spawn(Genome.willekeurig(rng))

    # 2. Warmup-fase (50 generaties)
    for _ in range(warmup_gens):
        for _ in range(300):
            w_warm.stap()

    d_warm = reg_warm.tik_arrays()
    mask_pre = (d_warm["generatie"] >= (warmup_gens - 10)) & (d_warm["generatie"] < warmup_gens)
    p_pre = float(np.mean(d_warm["parasitair"][mask_pre])) if mask_pre.any() else 0.0
    ehi_pre = float(np.mean(d_warm["ehi"][mask_pre])) if mask_pre.any() else 0.0

    # Koppel warm-up observers los voor zuivere deepcopy
    w_warm.observers.clear()

    # 3. Exacte toestand kopiëren voor Arm A en Arm B
    w_aan = copy.deepcopy(w_warm)
    w_uit = copy.deepcopy(w_warm)

    w_aan.met_kroniek = True
    reg_aan = TelemetrieRegistratie()
    w_aan.observers.append(reg_aan)

    w_uit.met_kroniek = False
    w_uit.kroniek_archetypen.clear()
    reg_uit = TelemetrieRegistratie()
    w_uit.observers.append(reg_uit)

    # 4. Post-knockout fase (30 generaties)
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

    ehi_post_aan = float(np.mean(d_aan["ehi"])) if len(d_aan) else 0.0
    ehi_post_uit = float(np.mean(d_uit["ehi"])) if len(d_uit) else 0.0

    h_aan = sum(1 for g in reg_aan.gebeurtenissen if g.type.name.startswith("HANDEL"))
    h_uit = sum(1 for g in reg_uit.gebeurtenissen if g.type.name.startswith("HANDEL"))

    ov_aan = sum(1 for g in reg_aan.gebeurtenissen if g.type.name.startswith("OVERVAL"))
    ov_uit = sum(1 for g in reg_uit.gebeurtenissen if g.type.name.startswith("OVERVAL"))

    # Traject na knockout per 5 generaties
    traj_aan = []
    traj_uit = []
    for g_idx in range(0, post_gens, 5):
        m_a = (d_aan["generatie"] >= warmup_gens + g_idx) & (d_aan["generatie"] < warmup_gens + g_idx + 5)
        m_u = (d_uit["generatie"] >= warmup_gens + g_idx) & (d_uit["generatie"] < warmup_gens + g_idx + 5)
        traj_aan.append(float(np.mean(d_aan["parasitair"][m_a])) if m_a.any() else 0.0)
        traj_uit.append(float(np.mean(d_uit["parasitair"][m_u])) if m_u.any() else 0.0)

    return {
        "seed": seed,
        "p_pre": p_pre,
        "ehi_pre": ehi_pre,
        "p_post_aan": p_post_aan,
        "p_post_uit": p_post_uit,
        "p_peak_aan": p_peak_aan,
        "p_peak_uit": p_peak_uit,
        "delta_p_aan": p_post_aan - p_pre,
        "delta_p_uit": p_post_uit - p_pre,
        "ehi_post_aan": ehi_post_aan,
        "ehi_post_uit": ehi_post_uit,
        "h_aan": h_aan,
        "h_uit": h_uit,
        "ov_aan": ov_aan,
        "ov_uit": ov_uit,
        "traj_aan": traj_aan,
        "traj_uit": traj_uit,
    }


def run_knockout_experiment(
    seeds: list[int] | None = None, warmup_gens: int = 50, post_gens: int = 30
):
    if seeds is None:
        seeds = [42, 101, 102, 103, 104, 105, 106, 107, 108, 109]

    print("=" * 78)
    print("[EXPERIMENT] WARM CHECKPOINT KNOCKOUT ABLATIE (KRONIEK ON vs OFF)")
    print(f"Seeds ({len(seeds)}): {seeds} | Warmup: {warmup_gens} gen | Post-Knockout: {post_gens} gen")
    print("=" * 78)

    results: list[dict] = []
    for s in seeds:
        print(f"--> Bezig met Seed {s:3d} (Warmup {warmup_gens} gen + 2x {post_gens} gen post-knockout)...", end="", flush=True)
        res = run_knockout_single_seed(s, warmup_gens=warmup_gens, post_gens=post_gens)
        results.append(res)
        print(f" Klaar! (Pre-P={res['p_pre']:.2f} -> Post-AAN={res['p_post_aan']:.2f}, Post-UIT={res['p_post_uit']:.2f})")

    # Statistische analyses
    p_pre = np.array([r["p_pre"] for r in results])
    p_aan = np.array([r["p_post_aan"] for r in results])
    p_uit = np.array([r["p_post_uit"] for r in results])
    p_peak_aan = np.array([r["p_peak_aan"] for r in results])
    p_peak_uit = np.array([r["p_peak_uit"] for r in results])
    delta_aan = np.array([r["delta_p_aan"] for r in results])
    delta_uit = np.array([r["delta_p_uit"] for r in results])
    h_aan = np.array([r["h_aan"] for r in results])
    h_uit = np.array([r["h_uit"] for r in results])
    ov_aan = np.array([r["ov_aan"] for r in results])
    ov_uit = np.array([r["ov_uit"] for r in results])

    # Hypothesetoetsen
    t_welch, p_welch = stats.ttest_ind(p_uit, p_aan, equal_var=False)
    u_val, p_mw = stats.mannwhitneyu(p_uit, p_aan, alternative="two-sided")
    t_paired, p_paired = stats.ttest_rel(p_uit, p_aan)

    pooled_sd = np.sqrt((p_aan.std(ddof=1)**2 + p_uit.std(ddof=1)**2) / 2.0)
    cohens_d = (p_uit.mean() - p_aan.mean()) / max(1e-6, pooled_sd)

    print("\n" + "=" * 78)
    print("[RAPPORT] RESULTATEN NA INSTITUTIONELE KNOCKOUT (GEN 50 -> 80)")
    print("=" * 78)
    print(f"{'Metriek':<32} | {'Arm A: Controle (Kroniek AAN)':<20} | {'Arm B: Knockout (Kroniek UIT)':<20}")
    print("-" * 78)
    print(f"{'Pre-Knockout P (Gen 40-50)':<32} | {p_pre.mean():.3f} +/- {p_pre.std(ddof=1):.3f}             | {p_pre.mean():.3f} +/- {p_pre.std(ddof=1):.3f}")
    print(f"{'Post-Knockout P (Gen 50-80)':<32} | {p_aan.mean():.3f} +/- {p_aan.std(ddof=1):.3f}             | {p_uit.mean():.3f} +/- {p_uit.std(ddof=1):.3f}")
    print(f"{'Delta P (Post - Pre)':<32} | {delta_aan.mean():+.3f} +/- {delta_aan.std(ddof=1):.3f}            | {delta_uit.mean():+.3f} +/- {delta_uit.std(ddof=1):.3f}")
    print(f"{'Piek Parasitisme (P_max)':<32} | {p_peak_aan.mean():.3f} +/- {p_peak_aan.std(ddof=1):.3f}             | {p_peak_uit.mean():.3f} +/- {p_peak_uit.std(ddof=1):.3f}")
    print(f"{'Handelstransacties':<32} | {h_aan.mean():.1f} +/- {h_aan.std(ddof=1):.1f}               | {h_uit.mean():.1f} +/- {h_uit.std(ddof=1):.1f}")
    print(f"{'Aantal Overvallen':<32} | {ov_aan.mean():.1f} +/- {ov_aan.std(ddof=1):.1f}             | {ov_uit.mean():.1f} +/- {ov_uit.std(ddof=1):.1f}")
    print("=" * 78)

    print("\n[STATISTISCHE TOETSEN]")
    print(f"- Paired Student's t-test (per-seed gepaard): t = {t_paired:+.3f}, p = {p_paired:.4f}")
    print(f"- Welch t-test (ongelijke variantie):        t = {t_welch:+.3f}, p = {p_welch:.4f}")
    print(f"- Mann-Whitney U (verdelingsvrij):           U = {u_val:.1f}, p = {p_mw:.4f}")
    print(f"- Effectgrootte (Cohen's d):                 d = {cohens_d:+.2f}")

    # Tijdsverloop na knockout
    traj_aan_mat = np.array([r["traj_aan"] for r in results])
    traj_uit_mat = np.array([r["traj_uit"] for r in results])
    print("\n[TIJDSVERLOOP VAN PARASITISME NA KNOCKOUT]")
    print(f"{'Venster':<18} | {'Controle (AAN)':<16} | {'Knockout (UIT)':<16} | {'Verschil':<12}")
    print("-" * 65)
    for idx in range(traj_aan_mat.shape[1]):
        label = f"Gen +{idx*5:02d} tot +{(idx+1)*5:02d}"
        val_a = traj_aan_mat[:, idx].mean()
        val_u = traj_uit_mat[:, idx].mean()
        diff = val_u - val_a
        print(f"{label:<18} | {val_a:.3f}            | {val_u:.3f}            | {diff:+.3f}")
    print("=" * 78)


if __name__ == "__main__":
    run_knockout_experiment()
