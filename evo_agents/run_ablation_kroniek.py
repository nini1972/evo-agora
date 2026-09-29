"""Ablation Experiment: De Kroniek (Institutioneel Geheugen) ON vs OFF.

Doel: Wetenschappelijk bewijzen of de vrede en stabiliteit worden afgedwongen
door instituties (De Kroniek) of dat de genen zelf zijn geassimileerd.
Protocol: 10 seeds per arm x 25 generaties (7.500 ticks per run) — zie
`run_experiment(n_generaties=...)` voor het daadwerkelijk gebruikte aantal.

Let op bij interpretatie: bij 25 generaties vanaf een koude start (verse
willekeurige populatie, lege Kroniek) hebben beide armen nog niet het lage
P-regime (0.12-0.17) van de 900k-tick referentie-run bereikt — daar ging
~3100 generaties aan vooraf. Een null-resultaat hier betekent dus niet per
se "Kroniek maakt niets uit"; het kan ook betekenen dat het venster te kort
is om de twee hypotheses te onderscheiden. Zie ook §6 hieronder.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def run_single_arm(seed: int, met_kroniek: bool, n_generaties: int = 30) -> dict:
    rng = np.random.default_rng(seed)
    w = Wereld(rng=rng, met_kroniek=met_kroniek)
    reg = TelemetrieRegistratie()
    w.observers.append(reg)

    # Initiële spawn
    for _ in range(110):
        w.spawn(Genome.willekeurig(rng))

    for _ in range(n_generaties):
        for _ in range(300):
            w.stap()

    d = reg.tik_arrays()
    # Late generaties (gen 15 t/m 30) voor stabiel regime
    mask_laat = d["generatie"] >= 15
    p_gem = float(np.mean(d["parasitair"][mask_laat])) if mask_laat.any() else 0.0
    ehi_gem = float(np.mean(d["ehi"][mask_laat])) if mask_laat.any() else 0.0
    pop_gem = float(np.mean(d["populatie"][mask_laat])) if mask_laat.any() else 0.0
    h100_gem = float(np.mean(d["handels_per_100"][mask_laat])) if mask_laat.any() else 0.0

    # Events tellen
    overvallen = sum(1 for g in reg.gebeurtenissen if g.type.name.startswith("OVERVAL"))
    handels = sum(1 for g in reg.gebeurtenissen if g.type.name.startswith("HANDEL"))
    honger_dood = sum(1 for g in reg.gebeurtenissen if g.type.name == "DOOD_HONGER")

    # Genfrequenties aan einde
    levend = [a for a in w.agents.values() if a.levend]
    coop_eind = float(np.mean([a.genoom.waarde("cooperatie") for a in levend])) if levend else 0.0
    agres_eind = float(np.mean([a.genoom.waarde("agressie") for a in levend])) if levend else 0.0

    return {
        "seed": seed,
        "met_kroniek": met_kroniek,
        "p_gem": p_gem,
        "ehi_gem": ehi_gem,
        "pop_gem": pop_gem,
        "h100_gem": h100_gem,
        "overvallen": overvallen,
        "handels": handels,
        "honger_dood": honger_dood,
        "coop_eind": coop_eind,
        "agres_eind": agres_eind,
    }


def run_experiment(seeds: list[int] | None = None, n_generaties: int = 25):
    if seeds is None:
        seeds = [42, 101, 102, 103, 104, 105, 106, 107, 108, 109]

    print("=" * 70)
    print("[EXPERIMENT] START KRONIEK ABLATIE EXPERIMENT (10 SEEDS PER ARM)")
    print(f"Seeds: {seeds} | Generaties per run: {n_generaties}")
    print("=" * 70)

    resultaten_aan: list[dict] = []
    resultaten_uit: list[dict] = []

    print("\n--- ARM A: MET KRONIEK (Institutioneel Geheugen AAN) ---")
    for i, s in enumerate(seeds):
        res = run_single_arm(seed=s, met_kroniek=True, n_generaties=n_generaties)
        resultaten_aan.append(res)
        print(
            f"Seed {s:3d} | P_gem={res['p_gem']:.2f} | EHI_gem={res['ehi_gem']:.2f} | "
            f"Handels={res['handels']:4d} | Overvallen={res['overvallen']:5d}"
        )

    print("\n--- ARM B: ZONDER KRONIEK (Institutioneel Geheugen UIT) ---")
    for i, s in enumerate(seeds):
        res = run_single_arm(seed=s, met_kroniek=False, n_generaties=n_generaties)
        resultaten_uit.append(res)
        print(
            f"Seed {s:3d} | P_gem={res['p_gem']:.2f} | EHI_gem={res['ehi_gem']:.2f} | "
            f"Handels={res['handels']:4d} | Overvallen={res['overvallen']:5d}"
        )

    # Statistische Samenvatting
    p_aan = np.array([r["p_gem"] for r in resultaten_aan])
    p_uit = np.array([r["p_gem"] for r in resultaten_uit])
    ehi_aan = np.array([r["ehi_gem"] for r in resultaten_aan])
    ehi_uit = np.array([r["ehi_gem"] for r in resultaten_uit])
    h_aan = np.array([r["handels"] for r in resultaten_aan])
    h_uit = np.array([r["handels"] for r in resultaten_uit])
    ov_aan = np.array([r["overvallen"] for r in resultaten_aan])
    ov_uit = np.array([r["overvallen"] for r in resultaten_uit])

    print("\n" + "=" * 70)
    print("[RAPPORT] WETENSCHAPPELIJK EINDRAPPORT (COMPARATIEVE ANALYSE)")
    print("=" * 70)
    print(f"{'Metriek':<30} | {'Met Kroniek (AAN)':<18} | {'Zonder Kroniek (UIT)':<18}")
    print("-" * 70)
    print(f"{'Parasitaire Druk (P_gem)':<30} | {p_aan.mean():.3f} +/- {p_aan.std():.3f}        | {p_uit.mean():.3f} +/- {p_uit.std():.3f}")
    print(f"{'Ecosysteemgezondheid (EHI_gem)':<30} | {ehi_aan.mean():.3f} +/- {ehi_aan.std():.3f}        | {ehi_uit.mean():.3f} +/- {ehi_uit.std():.3f}")
    print(f"{'Gemiddeld Aantal Handels':<30} | {h_aan.mean():.1f} +/- {h_aan.std():.1f}          | {h_uit.mean():.1f} +/- {h_uit.std():.1f}")
    print(f"{'Gemiddeld Aantal Overvallen':<30} | {ov_aan.mean():.1f} +/- {ov_aan.std():.1f}        | {ov_uit.mean():.1f} +/- {ov_uit.std():.1f}")
    print("=" * 70)

    # Effectgrootte (Cohen's d) op parasitisme
    pooled_std = np.sqrt((p_aan.std()**2 + p_uit.std()**2) / 2.0)
    cohens_d = (p_uit.mean() - p_aan.mean()) / max(1e-6, pooled_std)

    # Formele significantietoets: Cohen's d alleen is misleidend bij n=10 en
    # ongelijke varianties (hier vaak het geval — UIT-arm is bimodaal/instabieler
    # dan AAN). Welch-t (robuust tegen ongelijke variantie) + Mann-Whitney U
    # (robuust tegen niet-normaliteit) geven samen een eerlijk oordeel.
    t_stat, t_p = stats.ttest_ind(p_uit, p_aan, equal_var=False)
    _, mw_p = stats.mannwhitneyu(p_uit, p_aan, alternative="two-sided")

    print(f"Effectgrootte Kroniek op Parasitismereductie (Cohen's d): {cohens_d:+.2f}")
    print(f"Welch t-toets (P_uit vs P_aan): t={t_stat:+.2f}, p={t_p:.3f}")
    print(f"Mann-Whitney U-toets (verdelingsvrij): p={mw_p:.3f}")

    significant = t_p < 0.05 and mw_p < 0.05
    if significant and cohens_d > 0.8:
        print("[CONCLUSIE] Zeer groot en statistisch significant effect. De Kroniek is de dragende pijler van de beschaving!")
    elif significant:
        print("[CONCLUSIE] Statistisch significant effect (p<0.05 op beide toetsen). De Kroniek remt criminaliteit effectief af.")
    else:
        print(
            "[CONCLUSIE] Geen statistisch significant verschil aangetoond "
            f"(Welch p={t_p:.3f}, Mann-Whitney p={mw_p:.3f}) ondanks Cohen's d={cohens_d:+.2f}. "
            "LET OP: dit is bij korte, koude-start runs geen bewijs dat de Kroniek "
            "niets doet — het kan ook betekenen dat #generaties te laag is om de "
            "AAN-arm zelf tot het lage-P regime te laten convergeren (zie module-docstring). "
            "Overweeg meer generaties/seeds, of ablatie vanaf een reeds gevestigde "
            "vredestoestand (Kroniek pas uitschakelen na opwarmen) i.p.v. een koude start."
        )


if __name__ == "__main__":
    run_experiment()
