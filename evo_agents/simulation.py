"""Main entry point for the EvoAgents simulation."""
from __future__ import annotations
import os
import sys

import numpy as np

# Ensure evolib can be imported if running directly from within or outside folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def main(generaties: int = 25, seed: int = 42, log_pad: str | None = "runs/run_test.jsonl") -> None:
    rng = np.random.default_rng(seed)
    wereld = Wereld(rng=rng)
    reg = None
    if log_pad:
        reg = TelemetrieRegistratie(sink_pad=log_pad)
        reg.koppel_header(
            seed,
            {
                "breedte": wereld.breedte,
                "hoogte": wereld.hoogte,
                "eco": vars(wereld.gov.inst),
                "tick_per_gen": wereld.tick_per_gen,
            },
        )
        wereld.observers.append(reg)

    print("=== Start EvoAgents Simulatie ===")
    try:
        for generatie in range(generaties):
            for _ in range(300):  # TICKS_PER_GENERATIE
                wereld.stap()
            print(f"gen {generatie:02d} | {wereld.diagnose()}")

        print("\nTop-3 Hall-of-Fame genomen:")
        for fit, g in wereld.motor.hof.lijst[:3]:
            print(f"  fitness={fit:.3f}  {g}")
    finally:
        if reg is not None:
            reg.sluit()
            print(f"\nTelemetrie opgeslagen in: {log_pad}")


if __name__ == "__main__":
    main()
