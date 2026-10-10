"""Frontend B: Plotly/Dash. Simulatie in een thread; callbacks kopiëren
onder de registratie-lock en bouwen figuren erbuiten."""
from __future__ import annotations

import threading
import time

import numpy as np
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dash_table, dcc, html, no_update
from plotly.subplots import make_subplots

from .telemetry import GebeurtenisType, lttb

DONKER = {
    "backgroundcolor": "#101216",
    "papercolor": "#101216",
    "fontcolor": "#c9d1d9",
    "grid": "#21262d",
}
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
TYPE_NAAM = {e.value: e.name for e in GebeurtenisType}


def _layout(fig: go.Figure, uirevision: str | None = "vast") -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=DONKER["papercolor"],
        plot_bgcolor=DONKER["backgroundcolor"],
        margin=dict(l=36, r=16, t=34, b=28),
        uirevision=uirevision,  # behoud zoom/pan tussen polls
    )
    return fig


class SimulatieRunner(threading.Thread):
    def __init__(self, wereld, stappen_per_slice: int = 4, slaaptijd: float = 0.02):
        super().__init__(daemon=True)
        self.wereld = wereld
        self.slice_ = stappen_per_slice
        self.slaaptijd = slaaptijd
        self.gepauzeerd = False
        self.stap_verzoek = 0
        self.stop_event = threading.Event()

    def run(self) -> None:
        while not self.stop_event.is_set():
            if self.gepauzeerd:
                if self.stap_verzoek > 0:
                    aantal = min(self.stap_verzoek, 25)
                    for _ in range(aantal):
                        try:
                            self.wereld.stap()
                        except Exception as e:
                            print(f"[WAARSCHUWING] Simulatiestap fout opgevangen: {e}")
                    self.stap_verzoek -= aantal
                time.sleep(0.04)
                continue

            for _ in range(self.slice_):
                try:
                    self.wereld.stap()
                except Exception as e:
                    print(f"[WAARSCHUWING] Simulatiestap fout opgevangen: {e}")
            time.sleep(self.slaaptijd)  # geef de GIL aan het dashboard


# ── figuurbouwers ─────────────────────────────────────────────────────────
def fig_kaart(
    reg,
    tik_keuze: int | None = None,
    breedte: int = 36,
    hoogte: int = 36,
) -> go.Figure:
    snap = (
        reg.ruimtelijk_in_de_buurt(tik_keuze)
        if tik_keuze is not None
        else reg.laatste_ruimtelijk()
    )
    fig = go.Figure()
    if snap is None:
        fig.add_annotation(text="geen momentopname beschikbaar", showarrow=False)
        return _layout(fig)
    vx = [b[0] for b in snap.bronnen if b[2] == 0]
    vy = [b[1] for b in snap.bronnen if b[2] == 0]
    vq = [b[3] for b in snap.bronnen if b[2] == 0]
    ox = [b[0] for b in snap.bronnen if b[2] == 1]
    oy = [b[1] for b in snap.bronnen if b[2] == 1]
    oq = [b[3] for b in snap.bronnen if b[2] == 1]
    fig.add_trace(
        go.Scatter(
            x=vx,
            y=vy,
            mode="markers",
            name="voedsel",
            marker=dict(
                symbol="square",
                size=11,
                color="#2ea043",
                opacity=0.75,
                line=dict(width=0),
            ),
            text=[f"q={q:.1f}" for q in vq],
            hoverinfo="x+y+text",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ox,
            y=oy,
            mode="markers",
            name="erts",
            marker=dict(
                symbol="diamond",
                size=11,
                color="#d29922",
                opacity=0.8,
                line=dict(width=0),
            ),
            text=[f"q={q:.1f}" for q in oq],
            hoverinfo="x+y+text",
        )
    )
    if snap.agenten:
        ax = [a[1] for a in snap.agenten]
        ay = [a[2] for a in snap.agenten]
        ak = [EMMER_PALET[a[3][0] * 3 + a[3][1]] for a in snap.agenten]
        asz = [6 + 14 * a[4] for a in snap.agenten]
        ahov = [f"#{a[0]} bucket={a[3]} E={a[4]:.0%}" for a in snap.agenten]
        fig.add_trace(
            go.Scatter(
                x=ax,
                y=ay,
                mode="markers",
                name="agenten",
                marker=dict(size=asz, color=ak, line=dict(width=1, color="#000")),
                text=ahov,
                hoverinfo="text",
            )
        )
        vrij = [a for a in snap.agenten if a[5]]
        if vrij:
            fig.add_trace(
                go.Scatter(
                    x=[a[1] for a in vrij],
                    y=[a[2] for a in vrij],
                    mode="markers",
                    name="vogelvrij",
                    marker=dict(
                        symbol="x",
                        size=15,
                        color="crimson",
                        line=dict(width=2),
                    ),
                )
            )
    d = reg.tik_arrays()
    extinct = bool(len(d) and d["populatie"][-1] == 0)
    fig.update_layout(
        title=f"Omgeving — tik {snap.tik}" + (" — EXTINCT" if extinct else ""),
        xaxis=dict(range=[-0.5, breedte - 0.5], visible=False),
        yaxis=dict(
            range=[-0.5, hoogte - 0.5],
            visible=False,
            scaleanchor="x",
            scaleratio=1,
        ),
    )
    return _layout(fig)


def fig_reeksen(reg, uirevision: str | None = "vast") -> go.Figure:
    d = reg.tik_arrays()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if not d:
        return _layout(fig, uirevision=uirevision)
    t = d["tik"]
    for kolom, kleur, naam in (("populatie", "#58a6ff", "populatie"),):
        tx, ty = lttb(t, d[kolom])
        fig.add_trace(
            go.Scatter(x=tx, y=ty, name=naam, line=dict(color=kleur, width=2))
        )
    for kolom, kleur in (
        ("ehi", "#3fb950"),
        ("ehi_voedsel", "#2ea043"),
        ("ehi_erts", "#8b949e"),
        ("gini_erts", "#f85149"),
        ("shannon", "#d2a8ff"),
        ("parasitair", "#ffa657"),
        ("coop_ema", "#39d353"),
        ("handels_per_100", "#00d2d3"),
    ):
        y = d[kolom]
        mask = ~np.isnan(y)
        if mask.any():
            tx, ty = lttb(t[mask], y[mask])
            fig.add_trace(
                go.Scatter(
                    x=tx,
                    y=ty,
                    name=kolom,
                    line=dict(color=kleur, width=1.4),
                    visible=True if kolom in ("ehi", "ehi_voedsel") else "legendonly",
                ),
                secondary_y=True,
            )
    fig.update_layout(title="Tijdsreeksen", hovermode="x unified", dragmode="zoom")
    # De rangeslider combineert slecht met secondary_y in Plotly.js en verdubbelt
    # de SVG DOM-rendering. We schakelen hem permanent uit: zoom/pan werkt via
    # muis/modebar, en de x-as volgt live automatisch.
    # Door fixedrange=True op beide y-assen te zetten, zoomt de muis (klik-en-sleep
    # of scrollwiel) altijd zuiver horizontaal over het tijdsinterval!
    fig.update_xaxes(rangeslider=dict(visible=False), fixedrange=False)
    fig.update_yaxes(title_text="populatie", secondary_y=False, fixedrange=True)
    fig.update_yaxes(
        title_text="fracties [0–1]", range=[-0.02, 1.02], secondary_y=True, fixedrange=True
    )
    return _layout(fig, uirevision=uirevision)


def fig_evolutie(reg) -> go.Figure:
    gens = reg.generatie_lijst()
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=(
            "genfrequenties per generatie",
            "fenotype-emmers (gestapeld)",
            "fitness & clusters",
        ),
    )
    if not gens:
        for i in range(3):
            fig.add_trace(go.Scatter(x=[], y=[]), row=i + 1, col=1)
        return _layout(fig)
    g = np.array([x.generatie for x in gens])
    namen = (
        "agressie",
        "cooperatie",
        "hebzucht",
        "nieuwsgierigheid",
        "retentie",
        "vergeving",
        "sociabiliteit",
        "risico_aversie",
        "stofwisseling",
    )
    mu = np.array([x.gen_gem for x in gens])  # (G, 9)
    sd = np.array([x.gen_std for x in gens])
    for j, nm in enumerate(namen):
        fig.add_trace(
            go.Scatter(
                x=g,
                y=mu[:, j],
                name=nm,
                legendgroup=nm,
                line=dict(color=EMMER_PALET[j]),
                showlegend=j < 3,
            ),
            row=1,
            col=1,
        )
        if nm in ("agressie", "cooperatie"):
            fig.add_trace(
                go.Scatter(
                    x=np.concatenate([g, g[::-1]]),
                    y=np.concatenate(
                        [mu[:, j] + sd[:, j], (mu[:, j] - sd[:, j])[::-1]]
                    ),
                    fill="toself",
                    opacity=0.15,
                    line_width=0,
                    fillcolor=EMMER_PALET[j],
                    showlegend=False,
                    legendgroup=nm,
                ),
                row=1,
                col=1,
            )
    buckets = np.array([x.bucket_tellingen for x in gens])  # (G, 9)
    restant = buckets.sum(axis=1).astype(float)
    for j in range(9):
        aandeel = np.divide(
            buckets[:, j],
            restant,
            out=np.zeros_like(restant),
            where=restant > 0,
        )
        fig.add_trace(
            go.Scatter(
                x=g,
                y=aandeel,
                stackgroup="emmers",
                name=f"emmer{j}",
                legendgroup=f"e{j}",
                line=dict(width=0.5, color=EMMER_PALET[j]),
                showlegend=j in (0, 2, 6, 8),
            ),
            row=2,
            col=1,
        )
    fig.add_trace(
        go.Scatter(
            x=g,
            y=[x.beste_fitness for x in gens],
            name="beste fitness",
            line=dict(color="#3fb950"),
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=g,
            y=[x.gemiddelde_fitness for x in gens],
            name="gem. fitness",
            line=dict(color="#58a6ff", dash="dot"),
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=g,
            y=[x.n_clusters for x in gens],
            name="clusters",
            yaxis="y6",
            line=dict(color="#f85149", dash="dash"),
        ),
        row=3,
        col=1,
    )
    fig.layout.yaxis6 = dict(
        overlaying="y5", side="right", range=[0, None], title="clusters"
    )
    return _layout(fig)


def fig_gebeurtenissen(reg, venster: int = 25) -> tuple[go.Figure, list[dict]]:
    t, code = reg.gebeurtenis_matrix()
    fig = go.Figure()
    if t.size:
        bins = np.arange(0, t.max() + venster, venster)
        for waarde, kleur in (
            (1, "#3fb950"),
            (2, "#56d364"),
            (4, "#f85149"),
            (5, "#8b949e"),
            (3, "#ffa198"),
            (6, "#6e7681"),
            (7, "#ff7b72"),
        ):
            sel = code == waarde
            if sel.any():
                hist, _ = np.histogram(t[sel], bins=bins)
                fig.add_bar(
                    x=bins[:-1],
                    y=hist,
                    name=TYPE_NAAM.get(waarde, str(waarde)),
                    marker_color=kleur,
                    width=venster * 0.9,
                )
    fig.update_layout(
        barmode="stack", title=f"gebeurtenissen per {venster} tikken"
    )
    _layout(fig)
    rijen = [
        {
            "tik": g.tik,
            "type": g.type.name,
            "actoren": ", ".join(f"#{i}" for i in g.actor_ids),
            "omvang": round(g.omvang, 2),
        }
        for g in reg.recente_gebeurtenissen(40)
    ]
    rijen.reverse()
    return fig, rijen


def fig_faseportret(reg) -> go.Figure:
    """Traject (P_parasitair, EHI) door de tijd - Lotka-Volterra faseportret."""
    d = reg.tik_arrays()
    fig = go.Figure()
    if not d or len(d.get("tik", [])) < 2:
        fig.add_annotation(
            text="onvoldoende telemetrie voor faseportret", showarrow=False
        )
        return _layout(fig)
    p = d["parasitair"]
    ehi = d["ehi"]
    t = d["tik"]
    stride = max(1, len(t) // 800)
    fig.add_trace(
        go.Scatter(
            x=p[::stride],
            y=ehi[::stride],
            mode="lines+markers",
            name="traject",
            line=dict(color="#58a6ff", width=1.5),
            marker=dict(
                size=5,
                color=t[::stride],
                colorscale="Viridis",
                colorbar=dict(title="Tik"),
                showscale=True,
            ),
            text=[
                f"t={int(tik)} P={pv:.2f} EHI={ev:.2f}"
                for tik, pv, ev in zip(t[::stride], p[::stride], ehi[::stride])
            ],
            hoverinfo="text",
        )
    )
    fig.update_layout(
        title="Faseportret: Parasitaire druk (P) vs Ecosysteemgezondheid (EHI)",
        xaxis=dict(title="Parasitaire Druk P", range=[-0.05, 1.05]),
        yaxis=dict(title="Ecosysteemgezondheid EHI", range=[-0.05, 1.05]),
    )
    return _layout(fig)


# ── app-fabriek ───────────────────────────────────────────────────────────
def maak_app(
    reg,
    wereld=None,
    runner: SimulatieRunner | None = None,
    replay: bool = False,
    breedte: int = 36,
    hoogte: int = 36,
) -> Dash:
    app = Dash(__name__)
    laatste_tik = 0
    d = reg.tik_arrays()
    if replay and len(d):
        laatste_tik = int(d["tik"][-1])

    app.layout = html.Div(
        style={
            "backgroundColor": DONKER["backgroundcolor"],
            "fontFamily": "monospace",
            "padding": "14px",
        },
        children=[
            html.H2(
                "EvoAgents — Telemetrie & Visualisatiedashboard",
                style={"color": DONKER["fontcolor"], "marginTop": "0", "marginBottom": "10px"},
            ),
            html.Div(
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "flexWrap": "wrap",
                    "gap": "16px",
                    "marginBottom": "14px",
                    "padding": "10px 14px",
                    "backgroundColor": "#161b22",
                    "borderRadius": "6px",
                    "border": "1px solid #21262d",
                },
                children=[
                    dcc.Checklist(
                        options=[{"label": " ⏸️ Pauzeer", "value": "p"}],
                        id="pauze",
                        value=(["p"] if replay else []),
                        style={"color": "#58a6ff", "fontWeight": "bold"},
                    ),
                    html.Button(
                        "⏭️ Stap (+10)",
                        id="stap-knop",
                        n_clicks=0,
                        style={
                            "backgroundColor": "#21262d",
                            "color": "#c9d1d9",
                            "border": "1px solid #30363d",
                            "borderRadius": "4px",
                            "padding": "5px 12px",
                            "cursor": "pointer",
                            "display": "none" if replay else "inline-block",
                        },
                    ),
                    html.Div(
                        style={
                            "display": "none" if replay else "flex",
                            "alignItems": "center",
                            "gap": "10px",
                            "minWidth": "260px",
                        },
                        children=[
                            html.Span("Snelheid:", style={"color": "#8b949e", "fontSize": 12}),
                            html.Div(
                                style={"flex": 1},
                                children=[
                                    dcc.Slider(
                                        id="snelheid-slider",
                                        min=1,
                                        max=4,
                                        step=1,
                                        marks={
                                            1: {"label": "Rustig", "style": {"color": "#8b949e", "fontSize": 10}},
                                            2: {"label": "Normaal", "style": {"color": "#8b949e", "fontSize": 10}},
                                            3: {"label": "Snel", "style": {"color": "#8b949e", "fontSize": 10}},
                                            4: {"label": "Turbo", "style": {"color": "#58a6ff", "fontSize": 10}},
                                        },
                                        value=2,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Span(id="status", style={"color": "#c9d1d9", "marginLeft": "auto", "fontWeight": "bold"}),
                ],
            ),
            dcc.Slider(
                0,
                max(1, laatste_tik),
                1,
                value=laatste_tik,
                id="scrubber",
                marks=None,
                tooltip={"always_visible": False},
            )
            if replay
            else html.Div(),
            dcc.Tabs(
                id="tabs",
                value="kaart",
                parent_className="custom-tabs",
                className="custom-tabs-container",
                children=[
                    dcc.Tab(label="Kaart", value="kaart"),
                    dcc.Tab(label="Tijdsreeksen", value="reeksen"),
                    dcc.Tab(label="Evolutie", value="evolutie"),
                    dcc.Tab(label="Faseportret", value="faseportret"),
                    dcc.Tab(label="Gebeurtenissen", value="gebeurtenissen"),
                ],
                colors={
                    "border": "#21262d",
                    "primary": "#58a6ff",
                    "background": "#161b22",
                },
            ),
            # ── Permanente containers voor 100% soepele tab-overgangen ──
            html.Div(
                id="container-kaart",
                style={"display": "block"},
                children=[
                    dcc.Graph(
                        id="grafiek-kaart",
                        style={"height": "78vh"},
                        config={"displayModeBar": False},
                    )
                ],
            ),
            html.Div(
                id="container-reeksen",
                style={"display": "none"},
                children=[
                    dcc.Graph(
                        id="grafiek-reeksen",
                        style={"height": "80vh"},
                        config={
                            "displayModeBar": True,
                            "scrollZoom": True,
                            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                            "displaylogo": False,
                        },
                    )
                ],
            ),
            html.Div(
                id="container-evolutie",
                style={"display": "none"},
                children=[
                    dcc.Graph(
                        id="grafiek-evolutie",
                        style={"height": "86vh"},
                        config={"displayModeBar": True, "scrollZoom": True, "displaylogo": False},
                    )
                ],
            ),
            html.Div(
                id="container-faseportret",
                style={"display": "none"},
                children=[
                    dcc.Graph(
                        id="grafiek-faseportret",
                        style={"height": "80vh"},
                        config={"displayModeBar": True, "scrollZoom": True, "displaylogo": False},
                    )
                ],
            ),
            html.Div(
                id="container-gebeurtenissen",
                style={"display": "none"},
                children=[
                    dcc.Graph(
                        id="grafiek-gebeurtenissen",
                        style={"height": "38vh"},
                        config={"displayModeBar": True, "scrollZoom": True, "displaylogo": False},
                    ),
                    dash_table.DataTable(
                        id="tabel-gebeurtenissen",
                        columns=[
                            {"name": c, "id": c}
                            for c in ("tik", "type", "actoren", "omvang")
                        ],
                        data=[],
                        page_size=18,
                        style_table={"height": "34vh", "overflowY": "auto"},
                        style_cell={
                            "backgroundColor": "#161b22",
                            "color": "#c9d1d9",
                            "border": "1px solid #21262d",
                            "fontSize": 12,
                        },
                        style_header={"backgroundColor": "#21262d"},
                    ),
                ],
            ),
            dcc.Interval(
                id="klok",
                interval=750,
                disabled=bool(replay),  # replay: alleen via scrubber
            ),
            dcc.Store(id="niks"),
        ],
    )

    if runner is not None:
        @app.callback(
            Output("niks", "data"),
            Input("pauze", "value"),
            Input("snelheid-slider", "value"),
            Input("stap-knop", "n_clicks"),
            prevent_initial_call=False,
        )
        def bedien_runner(pauze_val, snelheid_val, n_clicks):
            runner.gepauzeerd = "p" in (pauze_val or [])
            if snelheid_val == 1:  # Rustig
                runner.slice_ = 1
                runner.slaaptijd = 0.05  # ~20 ticks/sec
            elif snelheid_val == 2:  # Normaal
                runner.slice_ = 4
                runner.slaaptijd = 0.02  # ~200 ticks/sec
            elif snelheid_val == 3:  # Snel
                runner.slice_ = 25
                runner.slaaptijd = 0.005  # ~5,000 ticks/sec
            elif snelheid_val == 4:  # Turbo
                runner.slice_ = 100
                runner.slaaptijd = 0.001  # ~100,000 ticks/sec

            if n_clicks and n_clicks > 0:
                runner.stap_verzoek += 10
            return None

    # ── Instantane CSS tab-wisseling (geen DOM recreation) ──
    @app.callback(
        Output("container-kaart", "style"),
        Output("container-reeksen", "style"),
        Output("container-evolutie", "style"),
        Output("container-faseportret", "style"),
        Output("container-gebeurtenissen", "style"),
        Input("tabs", "value"),
    )
    def wissel_tab(actieve_tab):
        return (
            {"display": "block" if actieve_tab == "kaart" else "none"},
            {"display": "block" if actieve_tab == "reeksen" else "none"},
            {"display": "block" if actieve_tab == "evolutie" else "none"},
            {"display": "block" if actieve_tab == "faseportret" else "none"},
            {"display": "block" if actieve_tab == "gebeurtenissen" else "none"},
        )

    # ── Gerichte data-update voor alleen het actieve tabblad ──
    @app.callback(
        Output("grafiek-kaart", "figure"),
        Output("grafiek-reeksen", "figure"),
        Output("grafiek-evolutie", "figure"),
        Output("grafiek-faseportret", "figure"),
        Output("grafiek-gebeurtenissen", "figure"),
        Output("tabel-gebeurtenissen", "data"),
        Output("status", "children"),
        Input("klok", "n_intervals"),
        Input("scrubber", "value") if replay else Input("tabs", "value"),
        State("tabs", "value"),
        State("pauze", "value"),
        prevent_initial_call=False,
    )
    def vernieuw_data(_n, _x, actieve_tab, pauze):
        gestopt = "p" in (pauze or [])
        tik_keuze = _x if replay and isinstance(_x, (int, float)) else None

        f_kaart = no_update
        f_reeksen = no_update
        f_evolutie = no_update
        f_fase = no_update
        f_gebeurtenissen = no_update
        tabel_data = no_update

        if actieve_tab == "kaart":
            f_kaart = fig_kaart(reg, tik_keuze, breedte, hoogte)
        elif actieve_tab == "reeksen":
            # Live volgt de x-as automatisch de tijdreeks (uirevision=None).
            # Bij pauze of replay blijft zoom/pan behouden (uirevision="pauze_inspectie").
            ui_rev = "pauze_inspectie" if (gestopt or replay) else None
            f_reeksen = fig_reeksen(reg, uirevision=ui_rev)
        elif actieve_tab == "evolutie":
            f_evolutie = fig_evolutie(reg)
        elif actieve_tab == "faseportret":
            f_fase = fig_faseportret(reg)
        elif actieve_tab == "gebeurtenissen":
            f_gebeurtenissen, tabel_data = fig_gebeurtenissen(reg)

        laatste_rec = reg.laatste_tik_steekproef()
        status = (
            "—"
            if laatste_rec is None
            else (
                f"t={laatste_rec.tik}  N={laatste_rec.populatie}  "
                f"EHI={laatste_rec.ehi:.2f}  EHI(voedsel)={laatste_rec.ehi_voedsel:.2f}  "
                f"Gini={laatste_rec.gini_erts:.2f}  "
                f"P={laatste_rec.parasitair:.2f}  κ={laatste_rec.coop_ema:.2f}  "
                f"H/100t={laatste_rec.handels_per_100}"
                + ("  *** EXTINCT ***" if laatste_rec.populatie == 0 else "")
                + ("  [⏸️ GEPAUZEERD]" if gestopt else "")
            )
        )
        return f_kaart, f_reeksen, f_evolutie, f_fase, f_gebeurtenissen, tabel_data, status

    return app
