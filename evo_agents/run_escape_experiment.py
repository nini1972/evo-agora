"""Escape-Experiment (Resource Draagkracht Verdubbeling).

Wetenschappelijke Vraagstelling (Ox Alpha Prio 1):
"Is het hardnekkige EHI ≈ 0.31 evenwicht een Demografisch Anker (Malthusiaanse val:
extra biomassa wordt direct geconsumeerd door een grotere populatie N) of een Biofysische Pin
(fysieke oogst/groei-limiet waardoor EHI verdubbelt naar ~0.60)?"

Protocol:
- Arm A (Controle): Standaard node capaciteit K = 12.0 (Draagkracht = 1560.0).
- Arm B (Behandeling): Verdubbelde node capaciteit K = 24.0 (Draagkracht = 3120.0).
- 15 gepaarde seeds x 100 generaties (30.000 ticks per run).
- Evaluatie over stationair venster (generaties 50 t/m 100).
"""
from __future__ import annotations

import time
import numpy as np
from scipy import stats

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld, Bron, Res


def bouw_wereld_met_capaciteit(
    seed: int, capaciteit_factor: float = 1.0
) -> tuple[Wereld, TelemetrieRegistratie]:
    rng = np.random.default_rng(seed)
    w = Wereld(rng=rng, met_kroniek=True)
    
    # Pas capaciteiten van alle bronnen aan
    for bron in w.grid.values():
        bron.capaciteit = 12.0 * capaciteit_factor
        bron.hoeveelheid = float(min(bron.capaciteit, bron.hoeveelheid * capaciteit_factor))
    
    # Herbereken totale draagkracht in de EcosysteemGouverneur
    w.gov.inst.draagkracht = sum(b.capaciteit for b in w.grid.values())
    
    reg = TelemetrieRegistratie()
    w.observers.append(reg)

    for _ in range(110):
        w.spawn(Genome.willekeurig(rng))

    return w, reg


def run_escape_single_seed(
    seed: int, n_generaties: int = 100
) -> dict:
    t0 = time.time()

    # Arm A: Standaard K (1.0x)
    w_a, reg_a = bouw_wereld_met_capaciteit(seed, capaciteit_factor=1.0)
    for _ in range(n_generaties):
        for _ in range(300):
            w_a.stap()

    # Arm B: Verdubbelde K (2.0x)
    w_b, reg_b = bouw_wereld_met_capaciteit(seed, capaciteit_factor=2.0)
    for _ in range(n_generaties):
        for _ in range(300):
            w_b.stap()

    d_a = reg_a.tik_arrays()
    d_b = reg_b.tik_arrays()

    # Stationair venster: generaties 50 t/m 100
    m_a = d_a["generatie"] >= 50
    m_b = d_b["generatie"] >= 50

    ehi_a = float(np.mean(d_a["ehi"][m_a])) if m_a.any() else 0.0
    ehi_b = float(np.mean(d_b["ehi"][m_b])) if m_b.any() else 0.0

    pop_a = float(np.mean(d_a["populatie"][m_a])) if m_a.any() else 0.0
    pop_b = float(np.mean(d_b["populatie"][m_b])) if m_b.any() else 0.0

    bron_a = float(np.mean(d_a["totale_bron"][m_a])) if m_a.any() else 0.0
    bron_b = float(np.mean(d_b["totale_bron"][m_b])) if m_b.any() else 0.0

    p_a = float(np.mean(d_a["parasitair"][m_a])) if m_a.any() else 0.0
    p_b = float(np.mean(d_b["parasitair"][m_b])) if m_b.any() else 0.0

    h_a = sum(1 for g in reg_a.gebeurtenissen if g.type.name.startswith("HANDEL"))
    h_b = sum(1 for g in reg_b.gebeurtenissen if g.type.name.startswith("HANDEL"))

    elapsed = time.time() - t0
    return {
        "seed": seed,
        "elapsed": elapsed,
        "ehi_a": ehi_a,
        "ehi_b": ehi_b,
        "pop_a": pop_a,
        "pop_b": pop_b,
        "bron_a": bron_a,
        "bron_b": bron_b,
        "p_a": p_a,
        "p_b": p_b,
        "h_a": h_a,
        "h_b": h_b,
    }


def run_escape_suite(seeds: list[int] | None = None, n_generaties: int = 100):
    if seeds is None:
        seeds = [42, 101, 102, 103, 104, 105, 106, 107, 108, 109, 201, 202, 203, 204, 205]

    print("=" * 82)
    print("[EXPERIMENT] DRAAGKRACHT ESCAPE-EXPERIMENT (OX ALPHA PRIORITEIT 1)")
    print(f"Seeds ({len(seeds)}): {seeds} | Generaties per arm: {n_generaties}")
    print("=" * 82)

    results: list[dict] = []
    for idx, s in enumerate(seeds, 1):
        print(f"[{idx:02d}/{len(seeds):02d}] Seed {s:3d}...", end="", flush=True)
        res = run_escape_single_seed(s, n_generaties=n_generaties)
        results.append(res)
        print(
            f" Klaar in {res['elapsed']:.1f}s | EHI (1x={res['ehi_a']:.2f}, 2x={res['ehi_b']:.2f}) | "
            f"Pop (1x={res['pop_a']:.1f}, 2x={res['pop_b']:.1f}) | Bron (1x={res['bron_a']:.0f}, 2x={res['bron_b']:.0f})"
        )

    # Statistische aggregatie
    ehi_a = np.array([r["ehi_a"] for r in results])
    ehi_b = np.array([r["ehi_b"] for r in results])
    pop_a = np.array([r["pop_a"] for r in results])
    pop_b = np.array([r["pop_b"] for r in results])
    bron_a = np.array([r["bron_a"] for r in results])
    bron_b = np.array([r["bron_b"] for r in results])
    p_a = np.array([r["p_a"] for r in results])
    p_b = np.array([r["p_b"] for r in results])

    # Toetsen
    t_ehi, p_ehi = stats.ttest_rel(ehi_b, ehi_a)
    w_ehi, pw_ehi = stats.wilcoxon(ehi_b, ehi_a)

    t_pop, p_pop = stats.ttest_rel(pop_b, pop_a)
    w_pop, pw_pop = stats.wilcoxon(pop_b, pop_a)

    t_bron, p_bron = stats.ttest_rel(bron_b, bron_a)

    print("\n" + "=" * 82)
    print("[RAPPORT] ESCAPE-EXPERIMENT RESULTATEN (STATIONAIR VENSTER GEN 50-100)")
    print("=" * 82)
    print(f"{'Metriek':<36} | {'Arm A (Capaciteit 1.0x)':<20} | {'Arm B (Capaciteit 2.0x)':<20}")
    print("-" * 82)
    print(f"{'Draagkracht (K_totaal)':<36} | 1560.0               | 3120.0")
    print(f"{'Totale Biomassa (R_gem)':<36} | {bron_a.mean():.1f} +/- {bron_a.std(ddof=1):.1f}          | {bron_b.mean():.1f} +/- {bron_b.std(ddof=1):.1f}")
    print(f"{'Ecosysteemgezondheid (EHI_gem)':<36} | {ehi_a.mean():.3f} +/- {ehi_a.std(ddof=1):.3f}             | {ehi_b.mean():.3f} +/- {ehi_b.std(ddof=1):.3f}")
    print(f"{'Populatiegrootte (N_gem)':<36} | {pop_a.mean():.1f} +/- {pop_a.std(ddof=1):.1f}             | {pop_b.mean():.1f} +/- {pop_b.std(ddof=1):.1f}")
    print(f"{'Parasitaire Druk (P_gem)':<36} | {p_a.mean():.3f} +/- {p_a.std(ddof=1):.3f}             | {p_b.mean():.3f} +/- {p_b.std(ddof=1):.3f}")
    print("=" * 82)

    print("\n[STATISTISCHE ANALYSE & HYPOTHESETOETSEN]")
    print(f"- Biomassa-stijging:         t = {t_bron:+.3f} (Verhouding: {bron_b.mean()/max(1, bron_a.mean()):.2f}x)")
    print(f"- EHI Paired t-test:         t = {t_ehi:+.3f}, p = {p_ehi:.4f} (Wilcoxon p = {pw_ehi:.4f})")
    print(f"- Populatie Paired t-test:   t = {t_pop:+.3f}, p = {p_pop:.4f} (Wilcoxon p = {pw_pop:.4f})")

    # Conclusie
    pop_ratio = pop_b.mean() / max(1.0, pop_a.mean())
    ehi_diff = ehi_b.mean() - ehi_a.mean()
    print("\n[WETENSCHAPPELIJKE CONCLUSIE]")
    if abs(ehi_diff) < 0.05 and pop_ratio > 1.4:
        print("-> DEMOGRAFISCH ANKER (MALTHUSIAANSE VAL) BEVESTIGD:")
        print(f"   EHI blijft nagenoeg constant ({ehi_a.mean():.2f} vs {ehi_b.mean():.2f}), terwijl de populatie")
        print(f"   groeit met {((pop_ratio - 1.0) * 100):.1f}% ({pop_a.mean():.1f} -> {pop_b.mean():.1f} agenten).")
        print("   Alle extra ecologische capaciteit wordt direct geabsorbeerd door demografische expansie!")
    elif ehi_b.mean() > 1.4 * ehi_a.mean():
        print("-> BIOFYSISCHE PIN BEVESTIGD:")
        print(f"   EHI stijgt significant van {ehi_a.mean():.2f} naar {ehi_b.mean():.2f}.")
    else:
        print(f"-> GEMENGD EFFECT: EHI delta = {ehi_diff:+.3f}, Populatie groei = {((pop_ratio - 1.0) * 100):.1f}%.")


if __name__ == "__main__":
    run_escape_suite()
