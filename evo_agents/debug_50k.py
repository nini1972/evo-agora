"""Diagnostic runner to analyze dynamics up to 60k ticks."""
import numpy as np
from evolib.world import Wereld
from evolib.genome import Genome
from evolib.telemetry import TelemetrieRegistratie

def run_diagnostics(ticks=60000, seed=42):
    rng = np.random.default_rng(seed)
    w = Wereld(rng=rng)
    reg = TelemetrieRegistratie()
    w.observers.append(reg)

    # Initial spawn
    for _ in range(110):
        w.spawn(Genome.willekeurig(rng))

    print(f"=== Start 60k Diagnostic Run (seed={seed}) ===")
    
    for gen in range(ticks // 300):
        for _ in range(300):
            w.stap()
        
        # Generation stats
        t = w.tick
        levend = len([a for a in w.agents.values() if a.levend])
        ehi = w.gov.gezondheidsindex(w.totale_bron())
        agres = w._agres_aandeel
        coop = float(np.mean([a.genoom.waarde("cooperatie") for a in w.agents.values() if a.levend])) if levend else 0.0
        curiosity = float(np.mean([a.genoom.waarde("nieuwsgierigheid") for a in w.agents.values() if a.levend])) if levend else 0.0
        metabolism = float(np.mean([a.genoom.waarde("stofwisseling") for a in w.agents.values() if a.levend])) if levend else 0.0
        
        if gen % 10 == 0 or gen >= (ticks // 300) - 5:
            # count recent events in last 300 ticks
            recent = [g.type.name for g in reg.gebeurtenissen if g.tik >= t - 300]
            from collections import Counter
            c = Counter(recent)
            print(f"Gen {gen:03d} | t={t:5d} | pop={levend:3d} | EHI={ehi:.2f} | agres={agres:.2f} | coop={coop:.2f} | cur={curiosity:.2f} | met={metabolism:.2f} | events: {dict(c)}")

if __name__ == "__main__":
    run_diagnostics()
