"""Gebruik:
  python run_dashboard.py --modus live  --seed 42 [--log runs/r42.jsonl]
  python run_dashboard.py --modus dash  --seed 42 [--log runs/r42.jsonl] [--poort 8050]
  python run_dashboard.py --modus replay --bestand runs/r42.jsonl [--poort 8050]
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

# Zorg ervoor dat evolib direct geïmporteerd kan worden
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evolib.ecosystem import EcoInstellingen
from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie
from evolib.world import Wereld


def bouw_wereld(seed: int, log_pad: str | None) -> tuple[Wereld, TelemetrieRegistratie]:
    rng = np.random.default_rng(seed)
    wereld = Wereld(rng=rng)
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
    for _ in range(110):
        wereld.spawn(Genome.willekeurig(rng))
    return wereld, reg


def main() -> None:
    ap = argparse.ArgumentParser(description="EvoAgents Telemetrie & Visualisatie Dashboard")
    ap.add_argument(
        "--modus",
        choices=("live", "dash", "replay"),
        default="dash",
        help="Visualisatiemodus: 'dash' (browser cockpit), 'live' (matplotlib window), 'replay' (historische run scrubben)",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--log", default="runs/run_test.jsonl", help="Bestandspad voor JSONL telemetrie-output")
    ap.add_argument("--bestand", default=None, help="Bestandspad voor JSONL replay input")
    ap.add_argument("--poort", type=int, default=8050, help="HTTP poort voor Dash server")
    args = ap.parse_args()

    if args.modus == "replay":
        bestand = args.bestand or args.log
        assert bestand and os.path.exists(bestand), f"Geldig --bestand vereist voor replay. Gevonden: {bestand}"
        print(f"Laden van replay data uit: {bestand} ...")
        reg = TelemetrieRegistratie.laad_uit_bestand(bestand)
        from evolib.dashboard_dash import maak_app

        app = maak_app(reg, replay=True)
        print(f"\n🚀 Replay dashboard gestart op http://127.0.0.1:{args.poort}/")
        try:
            import waitress
            print(f"⚡ Productie WSGI-server (waitress) actief met multi-threading.")
            waitress.serve(app.server, host="127.0.0.1", port=args.poort, threads=4)
        except ImportError:
            app.run(port=args.poort, debug=False)
        return

    wereld, reg = bouw_wereld(args.seed, args.log)
    print(f"Simulatie geïnitialiseerd (seed={args.seed}, log={args.log})")

    if args.modus == "live":
        from evolib.viz_matplotlib import MatplotlibViewer

        print("Starten van Matplotlib live-kijker...")
        try:
            MatplotlibViewer(wereld, reg).run()
        finally:
            reg.sluit()
    else:
        from evolib.dashboard_dash import SimulatieRunner, maak_app

        runner = SimulatieRunner(wereld)
        runner.start()
        app = maak_app(reg, wereld=wereld, runner=runner)
        print(f"\n🚀 Dash interactief dashboard gestart op http://127.0.0.1:{args.poort}/")
        try:
            try:
                import waitress
                print(f"⚡ Productie WSGI-server (waitress) actief met multi-threading.")
                waitress.serve(app.server, host="127.0.0.1", port=args.poort, threads=4)
            except ImportError:
                app.run(port=args.poort, debug=False)
        finally:
            runner.stop_event.set()
            reg.sluit()


if __name__ == "__main__":
    main()
