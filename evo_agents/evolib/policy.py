"""Economische beslisser: concaaf nut, reservatieprijzen, bid-ask spreads
met risicopremie, concessiecurven en exacte lot-optimalisatie.

Contracten:
- Alle prijsbeslissingen zijn deterministisch gegeven (staat, view, ronde);
  `rng` bestaat uitsluitend voor interfacecompatibiliteit.
- Elke drempel is genomisch geparametriseerd of een kalibratieconstante.
- Integratie: Kroniek -> vertrouwen -> premie; roofdruk_ema -> premie/escrow;
  wraakterm in u_aanval; geen interactie met de √d-fix in evolution.py."""
from __future__ import annotations

import math
import numpy as np

from .protocol import (
    Actie,
    ActieType,
    Bod,
    MAX_LOT,
    MAX_RONDES,
    P_MAX,
    P_MIN,
    Partij,
    Res,
    TegenpartijView,
    Wijze,
)

# ── kalibratieconstanten (wereldfysica, geen strategie) ───────────────────
VOEDSELENERGIE = 11.0     # energie per voedsel-eenheid
ERTS_WAARDE = 6.0         # basisschaal ertsnut
S_ERTS = 10.0             # verzadigingsschaal erts (log-kromme)
GAMMA_0, GAMMA_1 = 0.80, 1.60   # hongergevoeligheid: γ = γ0 + γ1·stofwisseling
M_MAX = 0.35              # maximale strategische marge (hebzucht)
PI_MAX = 0.35             # maximale kredietpremie bij T=0, risico_aversie=1 (was 0.60)
PI_SYS = 0.25             # systeemrisico-opslag bij maximale roofdruk (was 0.50)
C_T = 0.15                # trust-versneller op de biedmarge
U_MAX = 0.25              # urgentie-concessie (honger) op de biedmarge
KAPPA_MIN, KAPPA_MAX = 0.30, 0.85   # concessieretentie-band
DELTA_MIN, DELTA_MAX = 0.02, 0.60   # biedmarge-band
SIGMA_CAP = 1.20          # maximale ask-opslag boven de reservatieprijs
THETA_ACCEPT = 0.08       # basisacceptatiedrempel (nut-eenheden) (was 0.15)
THETA_DEADLINE = 0.35     # drempelkrimp in de lastronde
THETA_OPEN_REL = 0.04     # minimale relatieve ruilwinst om te openen (was 0.15)
T_MIN_HANDEL = 0.12       # harde uitsluiting (ostracisme)
T_ESCROW = 0.55           # onder dit vertrouwen: escrow verplicht (was 0.60)
ROOFDRUK_ESCROW = 0.05    # boven deze roofdruk-EMA: vlucht naar escrow

RES_ATTR = {Res.VOEDSEL: "voedsel", Res.ERTS: "erts"}


class Beleid:
    """Genomisch geparametriseerd economisch beslisser."""

    def __init__(self, agent):
        self.a = agent

    # ══════════════ 1. UTILITEITSCURVEN (eis 1) ══════════════
    def _honger(self) -> float:
        return float(np.clip(1.0 - self.a.energie / self.a.max_energie, 0.0, 1.0))

    def _k_voedsel(self) -> float:
        """Exponentiële hongeropdrijving: k_v = V·e^{γ·h}, γ genomisch."""
        gamma = GAMMA_0 + GAMMA_1 * self.a.genoom.waarde("stofwisseling")
        return VOEDSELENERGIE * math.exp(gamma * self._honger())

    def _k_erts(self) -> float:
        """Lineaire hebzucht-shift op de schaal; kromme blijft log-concaaf."""
        return ERTS_WAARDE * (0.7 + 0.6 * self.a.genoom.waarde("hebzucht"))

    def _s_voedsel(self) -> float:
        """Fysiologische satiatieschaal: voedsel-eenheden van leeg naar vol."""
        return max(1.0, self.a.max_energie / VOEDSELENERGIE)

    def _voedsel_reserve(self) -> int:
        return max(0, int(1.2 * self.a.genoom.waarde("risico_aversie")))

    def _erts_reserve(self) -> int:
        return max(0, int(0.8 * self.a.genoom.waarde("risico_aversie")))

    def waarde(self, res: Res, n: float) -> float:
        """Totaal nut van voorraad n: U(n) = k·ln(1 + n/s).
        Concaaf en verzadigend; MU = k/(s+n) > 0 voor alle n (eis 1).
        Signatuur onveranderd -> wereld.beste_buurcel blijft werken."""
        n = max(0.0, float(n))
        if res is Res.VOEDSEL:
            return self._k_voedsel() * math.log1p(n / self._s_voedsel())
        return self._k_erts() * math.log1p(n / S_ERTS)

    def _delta_nut(self, res: Res, voorraad: float, delta: float) -> float:
        """Exacte nutswijziging van Δ eenheden — géén linearisatie (CoT stap 6).
        delta > 0: ontvangen (conciève winst); delta < 0: afgeven (convexe kost)."""
        k = self._k_voedsel() if res is Res.VOEDSEL else self._k_erts()
        s = self._s_voedsel() if res is Res.VOEDSEL else S_ERTS
        n = max(0.0, float(voorraad))
        if delta >= 0.0:
            return k * math.log((s + n + delta) / (s + n))
        q = min(-delta, n)
        if q <= 0.0:
            return 0.0
        return -k * math.log((s + n) / (s + n - q))

    # ══════════════ 2. RESERVATIEPRIJS & SCHATTINGEN ══════════════
    def reserveringsprijs(self) -> float:
        """ρ = MU_voedsel/MU_erts bij huidige voorraden: de interne wisselkoers
        (hoeveel erts één marginaal voedsel waard is). CoT stap 5."""
        mu_v = self._k_voedsel() / (self._s_voedsel() + max(0.0, self.a.voedsel))
        mu_e = self._k_erts() / (S_ERTS + max(0.0, self.a.erts))
        if mu_e <= 1e-9 or math.isnan(mu_e):
            raw_rho = P_MAX
        elif math.isnan(mu_v) or math.isinf(mu_v):
            raw_rho = P_MAX
        else:
            raw_rho = mu_v / mu_e
        if math.isnan(raw_rho) or math.isinf(raw_rho):
            raw_rho = 1.0
        return float(min(P_MAX, max(P_MIN, raw_rho)))

    def reservatieprijs(self) -> float:
        """Alias voor reserveringsprijs."""
        return self.reserveringsprijs()

    def _geschatte_reservering(self, view: TegenpartijView) -> float:
        """ρ-schatting van de tegenpartij uit publieke informatie alleen.
        Genen onobserveerbaar -> populatieprior (γ̄ = γ0+γ1/2, k̄_erts = W);
        voedselvoorraad onzichtbaar -> prior 2. Fouten worden door de
        onderhandeling geabsorbeerd; de schatting kiest slechts richting/size."""
        h_ander = float(np.clip(1.0 - view.energie_fractie, 0.0, 1.0))
        k_v = VOEDSELENERGIE * math.exp((GAMMA_0 + 0.5 * GAMMA_1) * h_ander)
        mu_v = k_v / (self._s_voedsel() + 2.0)
        mu_e = ERTS_WAARDE / (S_ERTS + max(0.0, view.erts_geschat))
        if mu_e <= 1e-9 or math.isnan(mu_e):
            raw_rho = P_MAX
        elif math.isnan(mu_v) or math.isinf(mu_v):
            raw_rho = P_MAX
        else:
            raw_rho = mu_v / mu_e
        if math.isnan(raw_rho) or math.isinf(raw_rho):
            raw_rho = 1.0
        return float(min(P_MAX, max(P_MIN, raw_rho)))

    # ══════════════ 3. PREMIES, MARGES, WIJZE ══════════════
    def _kredietpremie(self, wijze: Wijze, view: TegenpartijView) -> float:
        """Opslag voor afwikkelrisico op de eigen kostpoot.
        ESCROW: notaris garandeert; courtage (n//20) is nul bij lots < 20 -> premie 0.
        CREDIT: default-risico (trust) + systeemrisico (roofdruk-EMA, macro-koppeling)."""
        if wijze is Wijze.ESCROW:
            return 0.0
        r_a = self.a.genoom.waarde("risico_aversie")
        roofdruk = getattr(self.a.wereld, "_roofdruk_ema", 0.0)
        return min(1.0, PI_MAX * r_a * (1.0 - view.vertrouwen) + PI_SYS * roofdruk)

    def _kies_wijze(self, view: TegenpartijView) -> Wijze:
        """Vlucht naar veiligheid: wantrouwen of oorlogsdruk -> escrow;
        krediet is voorbehouden aan vertrouwde relaties in vredestijden."""
        roofdruk = getattr(self.a.wereld, "_roofdruk_ema", 0.0)
        if view.vertrouwen < T_ESCROW or roofdruk >= ROOFDRUK_ESCROW:
            return Wijze.ESCROW
        return Wijze.CREDIT

    # ══════════════ 4. CONCESSIECURVEN (eis 3) ══════════════
    def _concessie_kappa(self, kant: str, view: TegenpartijView) -> float:
        """Retentie van de openingsmarge: κ hoog = geduldig.
        Trust versnelt sluiten (eis 3); hebzucht vertraagt; urgentie versnelt."""
        g = self.a.genoom.waarde("hebzucht")
        h = self._honger()
        T = view.vertrouwen if not (math.isnan(view.vertrouwen) or math.isinf(view.vertrouwen)) else 0.5
        if kant == "BID":  # koper: honger + vertrouwen = concessiedruk
            x = ((1.0 - h) + (1.0 - T) + g) / 3.0
        else:               # verkoper: voedseloverschot (lage h) + vertrouwen
            x = (h + (1.0 - T) + g) / 3.0
        return KAPPA_MIN + (KAPPA_MAX - KAPPA_MIN) * float(np.clip(x, 0.0, 1.0))

    def _planningsprijs(
        self,
        kant: str,
        ronde: int,
        rho: float,
        premie: float,
        view: TegenpartijView,
    ) -> float:
        """Stateless concessiepad: P(t) = walk + (target − walk)·κ^t (CoT stap 8).
        ASK daalt monotoon naar ρ·(1+premie); BID stijgt naar ρ·(1−δ_min)."""
        g = self.a.genoom.waarde("hebzucht")
        kappa = self._concessie_kappa(kant, view)
        daling = (kappa ** max(0, ronde)) if (not math.isnan(kappa) and not math.isinf(kappa)) else 0.5
        if kant == "ASK":
            sigma_vol = min(SIGMA_CAP, M_MAX * g + premie)
            p = rho * (1.0 + premie + (sigma_vol - premie) * daling)
        else:
            h = self._honger()
            delta_min = DELTA_MIN + premie
            T_val = view.vertrouwen if not (math.isnan(view.vertrouwen) or math.isinf(view.vertrouwen)) else 0.5
            delta_vol = min(
                DELTA_MAX,
                max(
                    delta_min,
                    M_MAX * g
                    + DELTA_MIN
                    + premie
                    - U_MAX * h
                    - C_T * T_val,
                ),
            )
            p = rho * (1.0 - delta_min - (delta_vol - delta_min) * daling)
        if math.isnan(p) or math.isinf(p) or p <= 0:
            p = rho if (not math.isnan(rho) and not math.isinf(rho) and rho > 0) else 1.0
        return float(min(P_MAX, max(P_MIN, p)))

    def _acceptatiedrempel(self, ronde: int) -> float:
        """θ krimpt 35% in de lastronde: geen-deal is ook een kost (deadline-effect)."""
        g = self.a.genoom.waarde("hebzucht")
        theta = THETA_ACCEPT * (0.6 + 0.8 * g)
        return theta * (1.0 - THETA_DEADLINE * (ronde / max(1, MAX_RONDES - 1)))

    # ══════════════ 5. EXACTE LOT-OPTIMALISATIE (CoT stap 6) ══════════════
    def _optimum_lot(self, kant: str, prijs: float) -> int:
        """Winstmaximerend integer-lot bij gegeven prijs, geëvalueerd op de
        GEREALISEERDE integer-termen (c = max(1, round(q·P))). Concaviteit
        maakt de netto-winst concief in q; de grid search is daarmee exact."""
        if math.isnan(prijs) or math.isinf(prijs) or prijs <= 0.0:
            return 0
        a = self.a
        beste_q, beste_net = 0, 0.0
        if kant == "BID":
            budget = a.erts - self._erts_reserve()
            for q in range(1, MAX_LOT + 1):
                raw_c = q * prijs
                if math.isnan(raw_c) or math.isinf(raw_c):
                    break
                c = max(1, int(round(raw_c)))
                if c > budget:
                    break
                netto = (
                    self._delta_nut(Res.VOEDSEL, a.voedsel, q)
                    - self._delta_nut(Res.ERTS, a.erts, -c)
                )
                if netto > beste_net:
                    beste_q, beste_net = q, netto
            return beste_q
        beschikbaar = a.voedsel - self._voedsel_reserve()
        for q in range(1, min(MAX_LOT, beschikbaar) + 1):
            raw_c = q * prijs
            if math.isnan(raw_c) or math.isinf(raw_c):
                break
            c = max(1, int(round(raw_c)))
            netto = (
                self._delta_nut(Res.ERTS, a.erts, c)
                - self._delta_nut(Res.VOEDSEL, a.voedsel, -q)
            )
            if netto > beste_net:
                beste_q, beste_net = q, netto
        return beste_q

    # ══════════════ 6. OPENINGSBOD (eis 2) ══════════════
    def openingsbod(self, view: TegenpartijView, rng=None):
        """Kies richting via geschatte zone van overeenkomst, open agressief
        (ronde 0 van het eigen concessiepad), sizeer via exacte lot-optimalisatie.
        Return: (Bod, Wijze) of (None, None)."""
        a = self.a
        if view.vogelvrij or view.vertrouwen < T_MIN_HANDEL:
            return None, None
        rho = self.reserveringsprijs()
        rho_ander = self._geschatte_reservering(view)
        wijze = self._kies_wijze(view)
        premie = self._kredietpremie(wijze, view)

        vloer_ask = rho * (1.0 + premie)                 # mijn walk-away als verkoper
        plafond_bid = rho * (1.0 - DELTA_MIN - premie)   # mijn walk-away als koper
        kandidaten: list[tuple[float, str, float, int]] = []

        if a.voedsel - self._voedsel_reserve() >= 1 and rho_ander >= vloer_ask:
            p0 = self._planningsprijs("ASK", 0, rho, premie, view)
            q0 = self._optimum_lot("ASK", p0)
            if q0 >= 1:
                kandidaten.append((rho_ander - vloer_ask, "ASK", p0, q0))
        if a.erts - self._erts_reserve() >= 1 and plafond_bid >= rho_ander:
            p0 = self._planningsprijs("BID", 0, rho, premie, view)
            q0 = self._optimum_lot("BID", p0)
            if q0 >= 1:
                kandidaten.append((plafond_bid - rho_ander, "BID", p0, q0))

        if not kandidaten:
            return None, None
        surplus, kant, p0, q0 = max(kandidaten, key=lambda k: k[0])
        if surplus <= THETA_OPEN_REL * rho:              # transactiekost drempel
            return None, None
        return Bod.met_prijs(kant, p0, q0), wijze

    # ══════════════ 7. MARKT-EVALUATIE & TEGENBOD (eis 3) ══════════════
    def evalueer_bod(
        self,
        bod: Bod,
        wijze: Wijze,
        view: TegenpartijView,
        ronde: int = 0,
        rng=None,
    ):
        """Beoordeel binnenkomend bod op EXACTE totalen (met risicopremie op de
        kostpoot), accepteer via drempel θ(ronde) of via de shortcut
        ('beter dan mijn eigen nú volgende concessie'), anders tel ik af
        langs mijn eigen concessiepad."""
        a = self.a
        if view.vogelvrij or view.vertrouwen < T_MIN_HANDEL:
            return "WEIGER", None, None
        premie = self._kredietpremie(wijze, view)
        rho = self.reserveringsprijs()

        if bod.geeft.res is Res.VOEDSEL:
            # ─ binnenkomende ASK: ik koop voedsel, betaal erts ─
            q, c = bod.geeft.hoeveelheid, bod.vraagt.hoeveelheid
            winst = self._delta_nut(Res.VOEDSEL, a.voedsel, q)
            kost = self._delta_nut(Res.ERTS, a.erts, -c) * (1.0 + premie)
            p_in = c / max(1, q)
            p_next = self._planningsprijs("BID", ronde + 1, rho, premie, view)
            betaalbaar = a.erts - self._erts_reserve() >= c
            if betaalbaar and (
                (winst - kost) >= self._acceptatiedrempel(ronde)
                or (p_in <= p_next and winst > kost)
            ):
                return "ACCEPTEER", None, None
            kant = "BID"
        else:
            # ─ binnenkomende BID: ik verkoop voedsel, ontvang erts ─
            c, q = bod.geeft.hoeveelheid, bod.vraagt.hoeveelheid
            winst = self._delta_nut(Res.ERTS, a.erts, c)
            kost = self._delta_nut(Res.VOEDSEL, a.voedsel, -q) * (1.0 + premie)
            p_in = c / max(1, q)
            p_next = self._planningsprijs("ASK", ronde + 1, rho, premie, view)
            leverbaar = a.voedsel - self._voedsel_reserve() >= q
            if leverbaar and (
                (winst - kost) >= self._acceptatiedrempel(ronde)
                or (p_in >= p_next and winst > kost)
            ):
                return "ACCEPTEER", None, None
            kant = "ASK"

        if ronde + 1 >= MAX_RONDES:
            return "WEIGER", None, None
        q_t = self._optimum_lot(kant, p_next)
        if q_t < 1:
            return "WEIGER", None, None
        return "TEGENBOD", Bod.met_prijs(kant, p_next, q_t), None

    # ══════════════ 8. ACTIEKEUZE (nieuwe concaaf nut-fundament) ═══════════
    def waarde_perceptie_cel(self, res: Res, n: float) -> float:
        return self.waarde(res, n)

    def kies_actie(self, perceptie, rng: np.random.Generator) -> Actie:
        a, g = self.a, self.a.genoom
        kandidaten: list[tuple[float, Actie]] = []
        energief = a.energie / a.max_energie

        # RUSTEN
        u_rust = 1.2 * (1.0 - energief) * (0.5 + g.waarde("stofwisseling")) - 0.1
        kandidaten.append((u_rust, Actie(ActieType.RUST)))

        # OOGSTEN
        bron = perceptie.bron_op_positie
        if bron is not None and bron.hoeveelheid >= 1.0:
            n = min(int(bron.hoeveelheid), 8)
            w = self.waarde(bron.res, n)
            u_oogst = 1.0 + 1.8 * (w / 12.0)
            kandidaten.append((u_oogst, Actie(ActieType.OOGST, bron_xy=(bron.x, bron.y))))

        # AANVALLEN / HANDELEN per buur
        heeft_vijand = False
        for t in perceptie.buren:
            if t.vertrouwen < 0.20:
                heeft_vijand = True
            u_a = self.u_aanval(t)
            if u_a > 0.0:
                kandidaten.append((u_a, Actie(ActieType.AANVAL, doel_id=t.id)))
            u_h = self.u_handel(t)
            if u_h > 0.0:
                kandidaten.append((u_h, Actie(ActieType.HANDEL, doel_id=t.id)))

        # VERPLAATSEN / VLUCHTEN (Waarde-gevoelig & Zelfbehoud)
        cel = perceptie.beste_buurcel(self.waarde)
        if cel is not None:
            wx, wy = a.wereld.breedte, a.wereld.hoogte
            buur_bron = a.wereld.grid.get(((a.pos[0] + cel[0]) % wx, (a.pos[1] + cel[1]) % wy))
            if buur_bron is None:
                basis_score = 0.35
            else:
                basis_score = 0.35 + 1.9 * min(
                    1.0,
                    self.waarde(buur_bron.res, min(buur_bron.hoeveelheid, 8.0)) / 45.0,
                )
            score = basis_score * (1.0 + 0.3 * g.waarde("nieuwsgierigheid"))
            # Smoor de neiging om weg te lopen als we al op een bron staan
            if bron is not None and bron.hoeveelheid >= 2.0:
                score *= 0.2
            # VLUCHTREFLEX: Als we gewond/verzwakt zijn en er is een vijand nabij, vlucht!
            if heeft_vijand and energief < 0.45:
                score += 3.5 * (1.0 - energief) * (0.6 + g.waarde("risico_aversie"))
            kandidaten.append((score, Actie(ActieType.BEWEEG, richting=cel)))

        # Numeriek stabiele Softmax
        scores = np.array([s for s, _ in kandidaten], dtype=np.float64)
        tau = 0.05 + 0.60 * g.waarde("nieuwsgierigheid")
        scaled_scores = scores / max(1e-6, tau)
        scaled_scores -= np.max(scaled_scores)
        p = np.exp(scaled_scores)
        p_sum = float(p.sum())
        p = np.full(len(p), 1.0 / len(p)) if p_sum <= 0 else p / p_sum
        idx = int(rng.choice(len(kandidaten), p=p))
        return kandidaten[idx][1]

    def u_aanval(self, t) -> float:
        """Inclusief de WRAAKTERM-upgrade en zelfbehoud bij letsel/honger."""
        a, g, mem = self.a, self.a.genoom, self.a.geheugen
        T = t.vertrouwen
        energief = a.energie / a.max_energie
        kracht_mij = 6.0 * (0.4 + g.waarde("agressie")) * (0.4 + 0.6 * energief)
        kracht_doel = 5.0 * (0.4 + t.agressie_schatting) * (0.4 + 0.6 * t.energie_fractie)
        p_win = 1.0 / (1.0 + math.exp(-1.5 * (kracht_mij - kracht_doel)))
        buit = 0.35 * t.erts_geschat * ERTS_WAARDE + 0.25 * t.energie_geschat
        mult = a.wereld.conflictkostenfactor()           # macro-roofdruk belasting
        vergelding = 0.8 * kracht_doel * (1.0 - T)       # wraakterm
        risico = (
            (1.0 - p_win) * (3.0 + 0.5 * kracht_doel)
            + 1.5 * mult
            + g.waarde("risico_aversie") * vergelding
        )
        relatie_kosten = 0.0 if t.vogelvrij else g.waarde("cooperatie") * 8.0 * T
        premie = 0.5 * t.erts_geschat * ERTS_WAARDE if t.vogelvrij else 0.0

        # Zelfbehoud: gewonde/verzwakte agenten gaan niet suïcidaal in de aanval
        zelfbehoud_straf = 0.0
        if energief < 0.40:
            zelfbehoud_straf = 5.0 * (1.0 - energief / 0.40) * (0.5 + g.waarde("risico_aversie"))

        u = (
            g.waarde("agressie") * (p_win * buit + premie)
            - g.waarde("risico_aversie") * risico
            - relatie_kosten
            - zelfbehoud_straf
            - 1.0
        )
        hint = mem.gelijkende_casus("vecht", t.bucket, "aanval")
        if hint is not None:
            u += 0.6 * hint
        return u

    def u_handel(self, t) -> float:
        """Handelsaantrekkelijkheid schaalt met de geschatte ruilwinst
        (|ρ_zelf − ρ_ander|): concaviteit maakt buren waardevollere handelspartners."""
        a, g = self.a, self.a.genoom
        if t.vogelvrij or t.vertrouwen < T_MIN_HANDEL:
            return -999.0
        rho = self.reserveringsprijs()
        rho_ander = self._geschatte_reservering(t)
        zone = abs(rho - rho_ander) / max(rho, 1e-9)
        potentie = 3.5 * (1.0 + g.waarde("sociabiliteit")) * (1.0 + min(2.0, zone))
        risico = 4.5 * (1.0 - t.vertrouwen)
        return (
            g.waarde("cooperatie") * potentie * t.vertrouwen
            + 0.8 * potentie
            - risico * g.waarde("risico_aversie")
            - 0.8
        )

    # ══════════════ 9. NAKOMING (concaaf consistent) ══════════════
    def kom_na(self, leverbinding: Partij) -> bool:
        """Rationale nakoming: EXACTE marginale leveringskost (log-delta, geen
        linearisatie) tegen de verwachte toekomstkosten van wanprestatie
        (premiejacht, verloren handelsrelaties, Kroniek-eskalatie via feiten)."""
        a, g = self.a, self.a.genoom
        voorraad = a.voorraad(leverbinding.res)
        reserve = (
            self._voedsel_reserve()
            if leverbinding.res is Res.VOEDSEL
            else self._erts_reserve()
        )
        if voorraad - reserve < leverbinding.hoeveelheid:
            return False  # overlevingsreserve > schuld
        lever_kost = -self._delta_nut(
            leverbinding.res, voorraad, -leverbinding.hoeveelheid
        )
        verwachte_kost = (
            3.5 * (1.0 + g.waarde("risico_aversie"))
            + g.waarde("cooperatie") * 14.0
            + 2.0 * (a.stat.feiten + 1)
        )
        return lever_kost <= verwachte_kost
