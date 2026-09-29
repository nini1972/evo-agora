"""Frontend A: één proces, geen threads. De FuncAnimation-lus stélt zelf de
simulatietikken (stappen_per_frame) en tekent daarna. Ideaal tijdens dev."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

from .genome import GENE_NAMEN
from .telemetry import GebeurtenisType

BG = np.array([0.043, 0.051, 0.071])
KLEUR_VOEDSEL = np.array([0.20, 0.65, 0.30])
KLEUR_ERTS = np.array([0.95, 0.62, 0.15])
EMMER_PALET = [
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#F0E442",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#999999",
    "#111111",
]


class MatplotlibViewer:
    def __init__(self, wereld, registratie, stappen_per_frame: int = 4):
        self.w, self.reg = wereld, registratie
        self.spf = stappen_per_frame
        self.H, self.W = wereld.hoogte, wereld.breedte

        self.fig = plt.figure(figsize=(13.5, 7), facecolor="#101216")
        gs = self.fig.add_gridspec(3, 2, width_ratios=(1.12, 1.0), hspace=0.42)
        self.ax_kaart = self.fig.add_subplot(gs[:, 0])
        self.ax_pop = self.fig.add_subplot(gs[0, 1])
        self.ax_gen = self.fig.add_subplot(gs[1, 1])
        self.ax_inst = self.fig.add_subplot(gs[2, 1])

        # kaart
        self.img = np.tile(BG, (self.H, self.W, 1))
        self.im = self.ax_kaart.imshow(
            self.img,
            origin="lower",
            extent=(-0.5, self.W - 0.5, -0.5, self.H - 0.5),
            interpolation="nearest",
        )
        self.sc_agenten = self.ax_kaart.scatter([], [], s=20, c=[], zorder=3)
        self.sc_vogelvrij = self.ax_kaart.scatter(
            [],
            [],
            s=46,
            marker="X",
            c="crimson",
            edgecolors="black",
            linewidths=0.5,
            zorder=4,
        )
        self.ax_kaart.set_xticks([])
        self.ax_kaart.set_yticks([])
        self.ax_kaart.set_title("Omgeving", color="w")
        for spine in self.ax_kaart.spines.values():
            spine.set_color("#333")

        # demografie: populatie (links) + EHI (rechts-as)
        (self.ln_pop,) = self.ax_pop.plot(
            [], [], lw=1.6, color="#58a6ff", label="populatie"
        )
        self.ax_ehi = self.ax_pop.twinx()
        (self.ln_ehi,) = self.ax_ehi.plot(
            [], [], lw=1.2, ls="--", color="#3fb950", label="EHI"
        )
        self.ax_pop.set_title("Demografie", color="w", fontsize=9)
        self.ax_pop.legend(loc="upper left", fontsize=6, labelcolor="w")

        # genfrequenties
        self.gen_lijnen = {}
        for i, naam in enumerate(GENE_NAMEN):
            dik = naam in ("agressie", "cooperatie", "hebzucht")
            (ln,) = self.ax_gen.plot(
                [],
                [],
                lw=1.8 if dik else 0.8,
                alpha=1.0 if dik else 0.30,
                color=EMMER_PALET[i],
                label=naam if dik else None,
            )
            self.gen_lijnen[naam] = ln
        self.ax_gen.set_ylim(0, 1)
        self.ax_gen.set_title(
            "Genfrequenties μ (dik: kerngenen)", color="w", fontsize=9
        )
        self.ax_gen.legend(loc="upper left", fontsize=6, ncol=3, labelcolor="w")

        # instituten: parasitaire druk, coop-EMA, conflictmult
        (self.ln_par,) = self.ax_inst.plot(
            [], [], lw=1.6, color="#f85149", label="P parasitair"
        )
        (self.ln_coop,) = self.ax_inst.plot(
            [], [], lw=1.6, color="#3fb950", label="κ coop-EMA"
        )
        self.ax_mult = self.ax_inst.twinx()
        (self.ln_mult,) = self.ax_mult.plot(
            [], [], lw=1.0, ls=":", color="#8b949e", label="conflictmult"
        )
        self.ax_inst.set_ylim(0, 1)
        self.ax_inst.set_title("Institutionele druk", color="w", fontsize=9)
        self.ax_inst.legend(loc="upper left", fontsize=6, labelcolor="w")

        for ax in (self.ax_pop, self.ax_gen, self.ax_inst):
            ax.tick_params(colors="#8b949e", labelsize=7)
            ax.set_facecolor("#161b22")
        self.status = self.fig.text(
            0.005,
            0.005,
            "",
            fontsize=7,
            family="monospace",
            color="#c9d1d9",
        )

        self.anim = FuncAnimation(
            self.fig,
            self._frame,
            interval=60,
            cache_frame_data=False,
            blit=False,
        )

    # ── tekenhulpjes ─────────────────────────────────────────────────────
    def _schilder_kaart(self) -> None:
        snap = self.reg.laatste_ruimtelijk()
        self.img[:, :] = BG
        if snap is not None:
            for x, y, res, q in snap.bronnen:
                kleur = KLEUR_VOEDSEL if res == 0 else KLEUR_ERTS
                self.img[y, x] = kleur * (0.18 + 0.82 * min(1.0, q / 12.0))
            self.im.set_data(self.img)
            if snap.agenten:
                offs = np.array([[a[1], a[2]] for a in snap.agenten])
                kols = [EMMER_PALET[a[3][0] * 3 + a[3][1]] for a in snap.agenten]
                maten = np.array([14.0 + 30.0 * a[4] for a in snap.agenten])
                self.sc_agenten.set_offsets(offs)
                self.sc_agenten.set_facecolors(kols)
                self.sc_agenten.set_sizes(maten)
                vrij = [(a[1], a[2]) for a in snap.agenten if a[5]]
                if vrij:
                    self.sc_vogelvrij.set_offsets(np.array(vrij))
                else:
                    self.sc_vogelvrij.set_offsets(np.empty((0, 2)))
        self.fig.canvas.draw_idle()

    def _update_reeksen(self) -> None:
        d = self.reg.tik_arrays()
        if not d:
            return
        stride = max(1, len(d["tik"]) // 1600)
        t = d["tik"][::stride]
        for ln, kolom in ((self.ln_pop, "populatie"), (self.ln_ehi, "ehi")):
            y = d[kolom][::stride]
            ln.set_data(t, y)
        self.ax_pop.set_xlim(0, max(1.0, d["tik"][-1]))
        self.ax_pop.set_ylim(0, max(10.0, d["populatie"].max() * 1.15))
        self.ax_ehi.set_ylim(0, 1)
        for naam, ln in self.gen_lijnen.items():
            i = GENE_NAMEN.index(naam)
            ln.set_data(t, d["gen_gem"][::stride, i])
        self.ax_gen.set_xlim(0, max(1.0, d["tik"][-1]))
        self.ln_par.set_data(t, d["parasitair"][::stride])
        coop = d["coop_ema"][::stride].copy()
        coop = np.where(
            np.isnan(coop),
            np.nanmedian(coop[~np.isnan(coop)])
            if np.any(~np.isnan(coop))
            else 0.5,
            coop,
        )
        self.ln_coop.set_data(t, coop)
        self.ln_mult.set_data(t, d["conflictmult"][::stride])
        self.ax_inst.set_xlim(0, max(1.0, d["tik"][-1]))
        self.ax_mult.set_ylim(0.8, max(1.6, d["conflictmult"].max() * 1.1))

    def _update_status(self) -> None:
        laatste = self.reg.tik_arrays()
        if not laatste:
            self.status.set_text("wachten op telemetrie…")
            return
        i = -1
        gebeurtenissen = self.reg.recente_gebeurtenissen(4)
        regels = [
            f"t={int(laatste['tik'][i])} gen={int(laatste['generatie'][i])} "
            f"N={int(laatste['populatie'][i])} EHI={laatste['ehi'][i]:.2f} "
            f"Gini={laatste['gini_erts'][i]:.2f} "
            f"H'={laatste['shannon'][i]:.2f}"
            + ("  *** EXTINCT ***" if laatste["populatie"][i] == 0 else "")
        ]
        naam = {
            1: "ESCROW",
            2: "CREDIT",
            3: "WANPREST",
            4: "ROOF-W",
            5: "ROOF-X",
            6: "DOOD",
            7: "VOGELVRIJ",
        }
        regels += [
            f"{g.tik:5d} {naam.get(g.type.value, g.type.name):<9} {'#'.join(map(str, g.actor_ids))} "
            f"({g.omvang:.0f})"
            for g in gebeurtenissen
        ]
        self.status.set_text("\n".join(regels))

    def _frame(self, _):
        for _ in range(self.spf):
            self.w.stap()
        self._schilder_kaart()
        self._update_reeksen()
        self._update_status()
        return []

    def run(self) -> None:
        plt.show()
