#!/usr/bin/env python3
"""Génère le site statique de la Veille Marque & Communication (nogues.app/veille-cm/).

Usage :
  python3 scripts/build.py                 # site complet dans dist/
  python3 scripts/build.py --preview FILE  # aperçu en page unique (vues par ancre)
"""
import argparse
import csv
import hashlib
import html
import json
import math
import re
import shutil
from collections import OrderedDict
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"
DATA = json.loads((ROOT / "content/editions.json").read_text(encoding="utf-8"))
SITE, POLICY = DATA["site"], DATA["editorialPolicy"]
AXES = OrderedDict((ax["id"], ax) for ax in DATA["axes"])
AXIS_INDEX = {key: i for i, key in enumerate(AXES)}
EDITIONS = sorted(DATA["editions"], key=lambda e: e["date"], reverse=True)
LATEST = EDITIONS[0]
BASE_URL = SITE["url"]
BASE_PATH = urlparse(BASE_URL).path
TIMING = {"week": "Actualité de la semaine", "context": "Actu hors période", "observation": "Dispositif observé"}
TIMING_CLASS = {"context": "st-context", "observation": "st-observation"}
PRIORITY = {"Critique": "pr-critique", "Important": "pr-important", "À surveiller": "pr-surveiller"}
RING = {"Critique": 0, "Important": 1, "À surveiller": 2}
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
WORDS = {0: "Zéro", 1: "Un", 2: "Deux", 3: "Trois", 4: "Quatre", 5: "Cinq", 6: "Six", 7: "Sept", 8: "Huit", 9: "Neuf", 10: "Dix", 11: "Onze", 12: "Douze"}
NAV = [("", "La veille", "veille"), ("axes/", "Les axes", "axes"), ("methode/", "La méthode", "methode"), ("sources/", "Sources", "sources"), ("archives/", "Archives", "archives")]


# ---------------------------------------------------------------- utilitaires
def a(value):
    return html.escape(str(value), quote=True)


def t(value):
    """Texte affiché : échappement et espaces insécables à la française."""
    s = html.escape(str(value), quote=False)
    s = re.sub(r" ([:])", " \\1", s)
    s = re.sub(r" ([;?!])", " \\1", s)
    for old, new in (("« ", "« "), (" »", " »"), (" %", " %"), (" M€", " M€")):
        s = s.replace(old, new)
    return s


ARROW = '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M7 17 17 7M9 7h8v8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def ext(url, label, css=""):
    if not url.startswith("https://"):
        raise ValueError(f"URL non HTTPS : {url}")
    cls = f' class="{a(css)}"' if css else ""
    return f'<a{cls} href="{a(url)}" target="_blank" rel="noopener noreferrer">{t(label)}{ARROW}<span class="sr-only"> (nouvel onglet)</span></a>'


def asset_version(name):
    return hashlib.sha256((ASSETS / name).read_bytes()).hexdigest()[:10]


class Ctx:
    """Contexte de rendu : site multipage (liens relatifs) ou aperçu en page unique (ancres)."""

    def __init__(self, mode="site", depth=0, absolute=False):
        self.mode, self.depth, self.absolute = mode, depth, absolute

    @property
    def prefix(self):
        if self.absolute:
            return BASE_PATH
        return "../" * self.depth if self.depth else "./"

    def href(self, route):
        if self.mode == "preview":
            view = {"": "veille", "axes/": "axes", "methode/": "methode", "sources/": "sources", "archives/": "archives"}.get(route, "veille")
            return f"#{view}"
        if route == "":
            return self.prefix
        return self.prefix + route

    def signal(self, key):
        return f"#signal-{key}"


# ---------------------------------------------------------------- validation
def validate():
    if len({e["id"] for e in EDITIONS}) != len(EDITIONS) or len({e["date"] for e in EDITIONS}) != len(EDITIONS):
        raise ValueError("Identifiant ou date d’édition en double")
    for ed in EDITIONS:
        start, end = date.fromisoformat(ed["periodStart"]), date.fromisoformat(ed["periodEnd"])
        day = date.fromisoformat(ed["date"])
        if not (start <= end <= day) or (end - start).days > 6:
            raise ValueError(f"Fenêtre de collecte invalide : {ed['id']}")
        sig = {s["id"]: s for s in ed["signals"]}
        if len(sig) != len(ed["signals"]):
            raise ValueError("Signal en double")
        if len(ed["signals"]) > POLICY["maxSignals"] or len(ed["actions"]) > POLICY["maxActions"]:
            raise ValueError("Plafonds éditoriaux dépassés")
        if POLICY.get("requireHorschamp") and not any(s["axis"] == "horschamp" for s in ed["signals"]):
            raise ValueError("Chaque édition doit compter un regard hors champ")
        if ed["featuredSignal"] not in sig:
            raise ValueError("Signal à retenir inconnu")
        for s in ed["signals"]:
            if s["axis"] not in AXES or not s["sources"] or s["priority"] not in PRIORITY or s["timing"] not in TIMING:
                raise ValueError(f"Signal incomplet : {s['id']}")
            pub = date.fromisoformat(s["publicationDate"])
            if s["timing"] == "week" and not start <= pub <= end:
                raise ValueError(f"Actualité publiée hors fenêtre : {s['id']}")
            if s["timing"] == "context" and pub >= start:
                raise ValueError(f"Un contexte doit précéder la fenêtre : {s['id']}")
            for src in s["sources"]:
                if not src["url"].startswith("https://"):
                    raise ValueError(f"Source non HTTPS : {src['url']}")
        if any(act["signal"] not in sig for act in ed["actions"]):
            raise ValueError("Une suite pointe vers un signal inconnu")
        if [p["id"] for p in ed["perspectives"]] != ["panorama", "fil-rouge", "tensions", "concurrence"]:
            raise ValueError("Les quatre regards doivent garder leur ordre")
        if any(k not in sig for p in ed["perspectives"] for k in p["signals"]):
            raise ValueError("Un regard pointe vers un signal inconnu")
        horizon = day + timedelta(days=POLICY["agendaHorizonDays"])
        for item in ed["agenda"]:
            d = date.fromisoformat(item["date"])
            if not day <= d <= horizon or item["status"] not in ("Confirmé", "Indicatif") or item["axis"] not in AXES:
                raise ValueError(f"Échéance invalide : {item['title']}")
            if not item["source"]["url"].startswith("https://"):
                raise ValueError("Source d’agenda non HTTPS")
        if ed.get("word") and ed["word"]["signal"] not in sig:
            raise ValueError("Le mot de la semaine pointe vers un signal inconnu")


def reading_minutes(ed):
    words = len((ed["intro"] + " " + ed["stake"]).split())
    for s in ed["signals"]:
        words += len((s["title"] + " " + s["fact"] + " " + s["implication"]).split())
    return max(1, round(words / 210))


# ---------------------------------------------------------------- dessins vectoriels
def polar(r, deg):
    rad = math.radians(deg)
    return r * math.cos(rad), r * math.sin(rad)


def arc_path(cx, cy, r, a0, a1):
    x0, y0 = polar(r, a0)
    x1, y1 = polar(r, a1)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{cx + x0:.2f} {cy + y0:.2f}A{r} {r} 0 {large} 1 {cx + x1:.2f} {cy + y1:.2f}"


def mark_svg(cls="mark"):
    """Logo : le point rouge commun aux veilles, qui rayonne en trois arcs."""
    arcs = "".join(f'<path class="m-arc m-a{i}" d="{arc_path(12, 20, r, -55, 55)}"/>' for i, r in enumerate((10, 15.5, 21), 1))
    return f'<svg class="{cls}" viewBox="0 0 40 40" aria-hidden="true"><circle class="m-dot" cx="12" cy="20" r="6"/>{arcs}</svg>'


def favicon_svg():
    arcs = "".join(f'<path d="{arc_path(12, 20, r, -55, 55)}" fill="none" stroke="#4000BF" stroke-width="3" stroke-linecap="round" opacity="{o}"/>' for r, o in ((10, 1), (15.5, .65), (21, .35)))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><circle cx="12" cy="20" r="6.5" fill="#FF3E52"/>{arcs}</svg>\n'


def hero_waves_svg():
    cx, cy = 120, 220
    static = "".join(f'<path class="w-arc w-static" pathLength="1" style="stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.3s {0.15 * i:.2f}s cubic-bezier(.3,.7,.2,1) forwards" d="{arc_path(cx, cy, r, -58, 58)}"/>' for i, r in enumerate((62, 112, 162, 212)))
    emit = "".join(f'<path class="w-arc w-emit w-e{i}" d="{arc_path(cx, cy, 212, -58, 58)}"/>' for i in (1, 2, 3))
    sats = []
    for r, deg, cls in ((112, -30, "w-sat"), (162, 22, "w-sat-r"), (212, -12, "w-sat"), (62, 40, "w-sat-r")):
        x, y = polar(r, deg)
        sats.append(f'<circle class="{cls}" cx="{cx + x:.1f}" cy="{cy + y:.1f}" r="{5 if cls == "w-sat-r" else 4}"/>')
    return f'<svg class="hero-waves" viewBox="0 0 440 440" aria-hidden="true">{static}{emit}<g class="w-orbit">{"".join(sats)}</g><circle class="w-dot" cx="{cx}" cy="{cy}" r="16"/></svg>'


def radar_svg(ed, ctx):
    rings = (62, 112, 162)
    mids = (34, 87, 137)
    parts = ['<svg class="radar" viewBox="-200 -200 400 400" role="img" aria-labelledby="radar-title radar-desc">',
             '<title id="radar-title">Radar des huit axes</title>',
             f'<desc id="radar-desc">{t(len(ed["signals"]))} signaux placés par axe et par criticité : critique au centre, important dans l’anneau médian, à surveiller à l’extérieur.</desc>',
             '<defs><linearGradient id="sweep-grad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="sw0"/><stop offset="1" class="sw1"/></linearGradient></defs>']
    for i, key in enumerate(AXES):
        a0, a1 = -90 + 45 * i, -45 + 45 * i
        x0, y0 = polar(rings[-1], a0)
        x1, y1 = polar(rings[-1], a1)
        parts.append(f'<path class="r-sector" data-sector="{a(key)}" d="M0 0L{x0:.2f} {y0:.2f}A{rings[-1]} {rings[-1]} 0 0 1 {x1:.2f} {y1:.2f}Z"/>')
    parts.append(f'<circle class="r-ring-1" r="{rings[0]}"/>')
    parts += [f'<circle class="r-ring" r="{r}"/>' for r in rings]
    for i in range(8):
        x, y = polar(rings[-1], -90 + 45 * i)
        parts.append(f'<line class="r-spoke" x1="0" y1="0" x2="{x:.2f}" y2="{y:.2f}"/>')
    sx, sy = polar(rings[-1], -40)
    parts.append(f'<path class="r-sweep" fill="url(#sweep-grad)" d="M0 0L{sx:.2f} {sy:.2f}A{rings[-1]} {rings[-1]} 0 0 1 {rings[-1]} 0Z"/>')
    for i, ax in enumerate(AXES.values()):
        x, y = polar(184, -67.5 + 45 * i)
        parts.append(f'<text class="r-label" x="{x:.1f}" y="{y:.1f}">{t(ax["number"])}</text>')
    groups = OrderedDict()
    for s in ed["signals"]:
        groups.setdefault((s["axis"], RING[s["priority"]]), []).append(s)
    delay = 0
    for (axis, ring), items in groups.items():
        start = -90 + 45 * AXIS_INDEX[axis]
        for j, s in enumerate(items):
            ang = start + 45 * (j + 1) / (len(items) + 1)
            x, y = polar(mids[ring], ang)
            label = f'{AXES[axis]["number"]} {AXES[axis]["short"]} · {s["priority"]} · {s["title"]}'
            parts.append(f'<a href="{ctx.signal(s["id"])}" aria-label="{a(label)}"><title>{t(label)}</title><circle class="r-dot rd-{a(s["timing"])} r-dot-in" style="animation-delay:{0.35 + 0.07 * delay:.2f}s" cx="{x:.1f}" cy="{y:.1f}" r="8"/></a>')
            delay += 1
    parts.append('<circle class="r-center" r="4.5"/></svg>')
    return "".join(parts)


def axis_icon(i):
    a0, a1 = -90 + 45 * i, -45 + 45 * i
    x0, y0 = polar(19, a0)
    x1, y1 = polar(19, a1)
    return f'<svg class="axis-icon" viewBox="-22 -22 44 44" aria-hidden="true"><circle class="ai-bg" r="19"/><path class="ai-on" d="M0 0L{x0:.2f} {y0:.2f}A19 19 0 0 1 {x1:.2f} {y1:.2f}Z"/><circle class="ai-dot" r="3.2"/></svg>'


def timeline_svg(ed, numbers):
    start = date.fromisoformat(ed["date"])
    days = POLICY["agendaHorizonDays"]
    x0, span, y = 20, 960, 70

    def x_of(d):
        return x0 + span * (d - start).days / days

    parts = ['<svg class="timeline" viewBox="0 0 1000 150" role="img" aria-labelledby="tl-title"><title id="tl-title">Frise des échéances sur 90 jours</title>',
             f'<line class="t-base" x1="{x0}" y1="{y}" x2="{x0 + span}" y2="{y}"/><line class="t-prog" x1="{x0}" y1="{y}" x2="{x0 + span}" y2="{y}"/>']
    d = start
    while (d - start).days <= days:
        if d.weekday() == 0 and d != start:
            xx = x_of(d)
            parts.append(f'<line class="t-tick" x1="{xx:.1f}" y1="{y - 12}" x2="{xx:.1f}" y2="{y + 12}"/>')
        if d.day == 1 or d == start:
            xx = x_of(d)
            parts.append(f'<text class="t-month" x="{xx + (0 if d == start else 4):.1f}" y="22">{t(MONTHS[d.month - 1])}</text>')
            if d != start:
                parts.append(f'<line class="t-tick" x1="{xx:.1f}" y1="28" x2="{xx:.1f}" y2="{y + 18}"/>')
        d += timedelta(days=1)
    parts.append(f'<circle class="t-now" cx="{x0}" cy="{y}" r="7"/><text class="t-today" x="{x0}" y="{y + 62}">Édition du {t(ed["dateLabel"])}</text>')
    for n, item in numbers:
        xx = x_of(date.fromisoformat(item["date"]))
        cls = "t-ev" if item["status"] == "Confirmé" else "t-ev-ind"
        ty = y - 18 if n % 2 else y + 30
        parts.append(f'<a href="#agenda-{n}" aria-label="{a(str(n) + ". " + item["dateLabel"] + " : " + item["title"])}"><circle class="{cls}" cx="{xx:.1f}" cy="{y}" r="9"/><text class="t-num" x="{xx:.1f}" y="{ty}">{n}</text></a>')
    parts.append("</svg>")
    return "".join(parts)


def poles_svg():
    boxes = [
        ("Marketing de l’offre", "Définir, structurer et valoriser les offres", "Veille Concurrents & ESR", False),
        ("Communication & Marque", "Construire les récits et faire rayonner", "Veille Marque & Communication", True),
        ("Growth, Digital & Data", "Activer, convertir et mesurer", "Veille IA & Web", False),
    ]
    parts = ['<svg class="poles-svg" viewBox="0 0 1000 260" role="img" aria-labelledby="poles-title poles-desc"><title id="poles-title">Trois pôles, trois veilles</title>',
             '<desc id="poles-desc">La Direction Marketing, Communication et Développement compte trois pôles ; chaque veille épouse principalement les missions de l’un d’eux.</desc>',
             '<text class="p-head" x="500" y="18" text-anchor="middle">DIRECTION MARKETING, COMMUNICATION &amp; DÉVELOPPEMENT</text>']
    for i, (title, sub, veille, on) in enumerate(boxes):
        x = 20 + i * 330
        cx = x + 145
        parts.append(f'<rect class="{"p-box-on" if on else "p-box"}" x="{x}" y="40" width="290" height="104" rx="22"/>')
        parts.append(f'<text class="p-title" x="{cx}" y="84" text-anchor="middle">{t(title)}</text><text class="p-sub" x="{cx}" y="110" text-anchor="middle">{t(sub)}</text>')
        parts.append(f'<path class="p-line" d="M{cx} 150V206"/><circle class="p-dot" cx="{cx}" cy="214" r="7"/>')
        parts.append(f'<text class="p-veille" x="{cx}" y="244" text-anchor="middle">{t(veille)}{" · ici" if on else ""}</text>')
    parts.append("</svg>")
    return "".join(parts)


def fam_mark(kind):
    if kind == "esr":
        return '<svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="15" style="fill:var(--red)"/></svg>'
    if kind == "iaweb":
        return '<svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="7" style="fill:var(--red)"/><circle cx="20" cy="20" r="15" fill="none" style="stroke:var(--red)" stroke-width="2.4" stroke-dasharray="3 4"/></svg>'
    return mark_svg("fam-mark")


# ---------------------------------------------------------------- composants
def chip(text, cls="", dot=False):
    d = '<i class="dot" aria-hidden="true"></i>' if dot else ""
    return f'<span class="chip {cls}">{d}{t(text)}</span>'


def sig_chips(s):
    ax = AXES[s["axis"]]
    out = chip(f'{ax["number"]} · {ax["short"]}', "chip-axis") + chip(s["priority"], PRIORITY[s["priority"]], True)
    if s["timing"] != "week":
        out += chip(TIMING[s["timing"]], TIMING_CLASS[s["timing"]])
    return out + chip(s["label"])


def sig_details(s):
    srcs = "".join(f'<li>{ext(x["url"], x["publisher"] + " — " + x["name"])}<span>{t(x["type"])} · {t(x["date"])}</span></li>' for x in s["sources"])
    return f'<details class="more"><summary>Dates, sources et limites<span class="plus" aria-hidden="true">+</span></summary><div class="more-body"><p class="muted">{t(s["status"])} · {t(s["dateLabel"])}</p><p>{t(s["limits"])}</p><ul class="src-list">{srcs}</ul></div></details>'


def sig_body_parts(s):
    first = s["sources"][0]
    head = f'<div class="sig-top">{sig_chips(s)}</div><h3 class="sig-title">{t(s["title"])}</h3><p class="sig-date">{t(s["dateLabel"])}</p>'
    fact = f'<p class="sig-fact">{t(s["fact"])}</p><p class="sig-read"><b>Notre lecture</b>{t(s["verdict"])}</p>'
    for_pole = f'<div class="sig-for"><span class="label">Pour le pôle Communication &amp; Marque</span><p>{t(s["implication"])}</p></div>'
    foot = f'<div class="sig-foot"><span class="roadmap">Feuille de route · {t(s["roadmap"])}</span>{ext(first["url"], first["publisher"], "pill-link")}</div>'
    return head, fact, for_pole, foot


def sig_tile(s, layout):
    head, fact, for_pole, foot = sig_body_parts(s)
    common = f'id="signal-{a(s["id"])}" data-item="{a(s["axis"])}"'
    if layout == "case":
        flag = '<p class="case-flag"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3.5" fill="currentColor"/></svg>Le cas d’école de la semaine</p>'
        minis = ""
        for i, part in enumerate(s.get("analysis", []), 1):
            q = " q" if i == len(s["analysis"]) else ""
            minis += f'<div class="mini{q}"><span class="mini-n">0{i}</span><h4>{t(part["title"])}</h4><p>{t(part["text"])}</p></div>'
        return f'<article class="tile sig wide case s-12" {common}>{flag}{head}<div class="sig-cols"><div>{fact}{for_pole}{foot}</div><div><span class="label">Décryptage · appréciation éditoriale, sans mesure de résultat</span><div class="case-parts">{minis}</div></div></div>{sig_details(s)}</article>'
    if layout == "outside":
        flag = '<p class="outside-flag"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 18 18 4M9 4h9v9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>Le pas de côté · regard hors enseignement supérieur</p>'
        return f'<article class="tile sig wide outside s-12" {common}>{flag}{head}<div class="sig-cols"><div>{fact}</div><div>{for_pole}{foot}</div></div>{sig_details(s)}</article>'
    if layout == "wide":
        return f'<article class="tile sig wide s-12" {common}>{head}<div class="sig-cols"><div>{fact}</div><div>{for_pole}{foot}</div></div>{sig_details(s)}</article>'
    return f'<article class="tile sig s-6" {common}>{head}{fact}{for_pole}{foot}{sig_details(s)}</article>'


def signal_tiles(ed):
    case = [s for s in ed["signals"] if s.get("caseStudy")]
    outside = [s for s in ed["signals"] if s["axis"] == "horschamp" and not s.get("caseStudy")]
    rest = [s for s in ed["signals"] if s not in case and s not in outside]
    rest.sort(key=lambda s: RING[s["priority"]])
    critical = [s for s in rest if s["priority"] == "Critique"]
    regular = [s for s in rest if s["priority"] != "Critique"]
    out = "".join(sig_tile(s, "case") for s in case)
    out += "".join(sig_tile(s, "wide") for s in critical)
    for i, s in enumerate(regular):
        last_odd = len(regular) % 2 == 1 and i == len(regular) - 1
        out += sig_tile(s, "wide" if last_odd else "regular")
    out += "".join(sig_tile(s, "outside") for s in outside)
    return out


def links_row(ed, keys, label="Revenir aux signaux"):
    sig = {s["id"]: s for s in ed["signals"]}
    return f'<div class="links-row"><span>{t(label)}</span>' + "".join(f'<a href="#signal-{a(k)}">{t(sig[k]["actor"])}</a>' for k in keys) + "</div>"


# ---------------------------------------------------------------- page « La veille »
def edition_body(ed, ctx):
    sig = {s["id"]: s for s in ed["signals"]}
    feat = sig[ed["featuredSignal"]]
    minutes = reading_minutes(ed)
    n_sig, n_act, n_agenda = len(ed["signals"]), len(ed["actions"]), len(ed["agenda"])
    counts = {k: sum(s["axis"] == k for s in ed["signals"]) for k in AXES}
    week = sum(s["timing"] == "week" for s in ed["signals"])
    ctxs = sum(s["timing"] == "context" for s in ed["signals"])

    hero = f'''<section class="sec"><div class="bento">
<div class="tile hero rise">{hero_waves_svg()}
<div class="hero-meta">{chip(ed["status"] + " · " + ed["dateLabel"], "chip-live", True)}{chip("Fenêtre du " + ed["period"])}</div>
<h1>Marque.<br>Récits.<br><span>Rayonnement.</span></h1>
<p class="hero-sub">La veille hebdomadaire du pôle Communication &amp; Marque de TBS Education : ce qui change dans la façon dont les marques se racontent, se diffusent et se prouvent.</p>
</div>
<aside class="tile feature rise" aria-label="Le signal à retenir"><span class="label">Le signal à retenir</span><p class="feature-fact">{t(ed["featuredFact"])}</p><h2 class="feature-title">{t(ed["featuredTitle"])}</h2><p class="feature-note">{t(ed["featuredNote"])}</p>
<div class="feature-foot"><span class="when">{t(ed["featuredLabel"])}</span><a class="btn" href="{ctx.signal(feat["id"])}">Lire le cas d’école</a>{ext(feat["sources"][0]["url"], feat["sources"][0]["publisher"], "btn btn-ghost")}</div></aside>
</div>
<div class="bento" style="margin-top:14px">
<div class="tile stat rise"><span class="stat-num">{n_sig:02d}</span><span class="stat-label">signaux retenus, sourcés et datés</span></div>
<div class="tile stat rise"><span class="stat-num">{n_act:02d}</span><span class="stat-label">suites proposées, à arbitrer</span></div>
<div class="tile stat rise"><span class="stat-num">{n_agenda:02d}</span><span class="stat-label">échéances dans les 90 jours</span></div>
<div class="tile stat rise"><span class="stat-num">{minutes:02d}<small>min</small></span><span class="stat-label">pour lire l’essentiel</span></div>
</div>
<div class="bento" style="margin-top:14px">
<div class="tile summary"><span class="label label-red">L’essentiel en 30 secondes</span><p class="lead">{t(ed["intro"])}</p></div>
<div class="tile stake"><span class="label">Enjeux pour le pôle</span><p>{t(ed["stake"])}</p></div>
</div></section>'''

    legend = ""
    for ax in AXES.values():
        n = counts[ax["id"]]
        dis = " disabled" if n == 0 else ""
        legend += f'<li><button type="button" data-filter="{a(ax["id"])}" aria-pressed="false"{dis}><span class="legend-num">{t(ax["number"])}</span><span class="legend-name">{t(ax["name"])}</span><span class="legend-count">{n}</span></button></li>'
    chips = f'<button type="button" class="filter is-active" data-filter="all" aria-pressed="true">Tous <span>{n_sig}</span></button>'
    chips += "".join(f'<button type="button" class="filter" data-filter="{a(ax["id"])}" aria-pressed="false"{" disabled" if counts[ax["id"]] == 0 else ""}>{t(ax["short"])} <span>{counts[ax["id"]]}</span></button>' for ax in AXES.values())
    timing_note = f"{week} actualités de la semaine et {ctxs} contextes antérieurs, signalés comme tels."
    radar = f'''<section class="sec" data-filter-scope data-nouns="signal|signaux" aria-labelledby="radar-h">
<div class="sec-head"><div><p class="kicker">Le radar de la semaine</p><h2 class="sec-title" id="radar-h">Huit axes. <em>{t(WORDS.get(n_sig, n_sig))} signaux.</em></h2></div><p class="sec-note">Chaque point est un signal, placé sur l’axe de sa mission et sur l’anneau de sa criticité. Cliquez un axe pour filtrer.</p></div>
<div class="bento">
<div class="tile radar-tile">{radar_svg(ed, ctx)}<div class="radar-keys"><span><i class="k-week"></i>Actualité de la semaine</span><span><i class="k-context"></i>Contexte antérieur</span><span>Centre : critique · milieu : important · bord : à surveiller</span></div></div>
<div class="tile legend-tile"><span class="label">Filtrer par axe</span><ul class="legend">{legend}</ul><p class="legend-note">{t(timing_note)} Un axe vide n’est pas une absence d’actualité : rien n’a atteint le niveau de preuve requis.</p><button type="button" class="filter legend-all is-active" data-filter="all" aria-pressed="true">Afficher tous les axes</button></div>
</div>
<div class="sec-head" style="margin-top:56px"><div><p class="kicker">Une sélection, pas une revue de presse</p><h2 class="sec-title">Ce qui mérite <em>votre attention.</em></h2></div><span class="count-line" data-count aria-live="polite">{n_sig} signaux</span></div>
<div class="filters" role="group" aria-label="Filtrer les signaux par axe">{chips}</div>
<div class="bento">{signal_tiles(ed)}<div class="empty" data-empty hidden><h3>Aucun signal retenu sur cet axe cette semaine.</h3><p>La sélection est volontairement courte : ce n’est pas une preuve d’absence d’actualité.</p></div></div>
</section>'''

    tabs, panels = "", ""
    for i, p in enumerate(ed["perspectives"]):
        text = ed["intro"] if p["id"] == "panorama" else p["text"]
        tabs += f'<button type="button" class="seg-btn" role="tab" id="tab-{a(p["id"])}" aria-controls="panel-{a(p["id"])}" aria-selected="{"true" if i == 0 else "false"}">{t(p["name"])}</button>'
        panels += f'<section class="regard" role="tabpanel" id="panel-{a(p["id"])}" aria-labelledby="tab-{a(p["id"])}"><span class="label">0{i + 1} · {t(p["name"])}</span><h3 class="regard-q">{t(p["question"])}</h3><p class="regard-text">{t(text)}</p>{links_row(ed, p["signals"])}</section>'
    regards = f'''<section class="sec" aria-labelledby="regards-h"><div class="sec-head"><div><p class="kicker">Prendre du recul</p><h2 class="sec-title" id="regards-h">Une édition. <em>Quatre regards.</em></h2></div><p class="sec-note">Quatre angles pour relier les signaux avant d’en tirer des suites.</p></div>
<div class="bento"><div class="tile regards" data-tabs><div class="regards-nav"><div class="seg" role="tablist" aria-label="Choisir un regard" hidden>{tabs}</div></div><div>{panels}</div></div></div></section>'''

    kpis = ""
    for k in DATA["kpis"]:
        keys = ed.get("kpiLinks", {}).get(k["id"], [])
        row = links_row(ed, keys, "Signaux utiles") if keys else ""
        if k["id"] == "anticipation":
            row = row.replace("</div>", '<a href="#agenda">Frise des 90 jours</a></div>', 1) if row else ""
        kpis += f'<div class="tile kpi"><span class="kpi-val">{t(k["value"])}</span><h3 class="kpi-name">{t(k["name"])}</h3><p class="kpi-text">{t(k["text"])}</p>{row}</div>'
    objectives = f'''<section class="sec" aria-labelledby="kpi-h"><div class="sec-head"><div><p class="kicker">Aligné sur la feuille de route du pôle</p><h2 class="sec-title" id="kpi-h">Ce que sert <em>cette édition.</em></h2></div><p class="sec-note">Les trois objectifs chiffrés du pôle, et les signaux qui les éclairent cette semaine.</p></div><div class="bento">{kpis}</div></section>'''

    items = sorted(ed["agenda"], key=lambda x: x["date"])
    numbered = list(enumerate(items, 1))
    months = OrderedDict()
    for n, it in numbered:
        d = date.fromisoformat(it["date"])
        months.setdefault(f"{MONTHS[d.month - 1]} {d.year}", []).append((n, it))
    cols = ""
    for month, rows in months.items():
        lis = ""
        for n, it in rows:
            ind = "" if it["status"] == "Confirmé" else " ind"
            note = f'<p class="agenda-note">{t(it["note"])}</p>' if it.get("note") else ""
            ax = AXES[it["axis"]]
            lis += f'<li class="agenda-item" id="agenda-{n}"><span class="agenda-n{ind}">{n}</span><div><p class="agenda-date">{t(it["dateLabel"])}</p><h4 class="agenda-title">{t(it["title"])}</h4><p class="agenda-why">{t(it["why"])}</p>{note}</div><div class="agenda-meta">{chip(it["status"], "pr-important" if it["status"] == "Confirmé" else "st-context")}{chip(ax["number"] + " · " + ax["short"], "chip-axis")}{ext(it["source"]["url"], it["source"]["publisher"])}</div></li>'
        cols += f'<div class="agenda-col"><h3>{t(month.capitalize())}</h3><ol>{lis}</ol></div>'
    end = date.fromisoformat(ed["date"]) + timedelta(days=POLICY["agendaHorizonDays"])
    agenda = f'''<section class="sec" id="agenda" aria-labelledby="agenda-h"><div class="sec-head"><div><p class="kicker">Anticiper plutôt que subir</p><h2 class="sec-title" id="agenda-h">Les 90 prochains jours, <em>d’un coup d’œil.</em></h2></div><p class="sec-note">Salons, calendrier post-bac, échéances réglementaires et publications attendues, jusqu’au {end.day} {MONTHS[end.month - 1]} {end.year}. Une date indicative se confirme avant d’engager des moyens.</p></div>
<div class="bento"><div class="tile agenda-tile"><div class="timeline-box">{timeline_svg(ed, numbered)}</div><div class="agenda-keys"><span><i class="agenda-n" style="width:14px;height:14px"></i>Date confirmée</span><span><i class="agenda-n ind" style="width:14px;height:14px"></i>Date indicative</span></div><div class="agenda-cols">{cols}</div></div></div></section>'''

    heading = {0: "Aucune suite <em>à engager.</em>", 1: "Une piste. <em>Pas un engagement.</em>", 2: "Deux pistes. <em>Pas deux engagements.</em>", 3: "Trois pistes. <em>Pas trois engagements.</em>"}[n_act]
    suites = ""
    for i, act in enumerate(ed["actions"], 1):
        suites += f'<div class="tile suite"><span class="suite-n">0{i}</span><span class="suite-h">{t(act["horizon"])} · à arbitrer</span><h3 class="suite-title">{t(act["title"])}</h3><p class="suite-owner">{t(act["owner"])}</p><p class="suite-res"><b>Livrable attendu</b>{t(act["result"])}</p><a href="#signal-{a(act["signal"])}">Signal d’origine : {t(sig[act["signal"]]["actor"])}</a></div>'
    actions = f'''<section class="sec" aria-labelledby="suites-h"><div class="sec-head"><div><p class="kicker">De la veille à la suite utile</p><h2 class="sec-title" id="suites-h">{heading}</h2></div></div><div class="bento">{suites}</div><p class="fine">Pilotes, moyens et calendrier à confirmer par la responsable du pôle. Ces pistes ne constituent pas des engagements des équipes.</p></section>'''

    word = ""
    if ed.get("word"):
        w = ed["word"]
        word = f'<div class="tile word"><span class="label">Le mot de la semaine</span><p class="word-term">{t(w["term"])}</p><blockquote>{t(w["definition"])}</blockquote><p class="word-ctx">{t(w["context"])} <a href="#signal-{a(w["signal"])}">Voir le signal</a></p><p class="word-ctx">{t(w["caution"])}</p></div>'
    cov = ""
    for key, ax in AXES.items():
        text = ed["coverage"].get(key, "Aucun signal retenu.")
        empty = " empty-axis" if counts[key] == 0 else ""
        cov += f'<li class="{empty.strip()}"><b>{t(ax["number"])}</b><span><strong>{t(ax["name"])}</strong>{t(text)}</span></li>'
    closing = f'''<section class="sec"><div class="bento">{word}<div class="tile coverage"><span class="label">Couverture de l’édition</span><p class="muted" style="font-size:14px">{t(ed["notice"])}</p><ul class="cov-list">{cov}</ul></div></div></section>'''

    family = f'''<section class="sec" aria-labelledby="fam-h"><div class="bento"><div class="tile family"><div><p class="kicker">La famille des veilles</p><h2 class="sec-title" id="fam-h" style="font-size:clamp(24px,3vw,32px)">Trois veilles, <em>une même exigence.</em></h2></div>
<div class="fam-grid"><a class="fam-card" href="https://nogues.app/veille-esr/" target="_blank" rel="noopener noreferrer">{fam_mark("esr")}<h3>Veille Concurrents &amp; ESR</h3><p>Offre, admissions, marché et stratégies des écoles concurrentes.</p></a>
<div class="fam-card is-here">{fam_mark("cm")}<span class="fam-here">Vous êtes ici</span><h3>Veille Marque &amp; Communication</h3><p>Marque, récits, influence, événements et pilotage de la fonction communication.</p></div>
<a class="fam-card" href="https://veilleiaweb.digital/" target="_blank" rel="noopener noreferrer">{fam_mark("iaweb")}<h3>Veille IA &amp; Web</h3><p>IA, SEO/GEO, architectures web et data marketing.</p></a></div></div></div>
<p class="edition-foot">Édition publiée le {t(ed["dateLabel"])} · Europe/Paris · <a href="{ctx.href("editions/" + ed["id"] + "/") if ctx.mode == "site" else "#veille"}">Lien permanent</a></p></section>'''

    return hero + radar + regards + objectives + agenda + actions + closing + family


# ---------------------------------------------------------------- pages secondaires
def page_hero(kicker, title_html, intro):
    return f'<section class="sec"><div class="bento"><div class="tile page-hero"><p class="kicker">{t(kicker)}</p><h1>{title_html}</h1><p>{t(intro)}</p></div></div></section>'


def axes_body(ctx):
    tiles = ""
    for i, ax in enumerate(AXES.values()):
        out = " is-outside" if ax["id"] == "horschamp" else ""
        tiles += f'<article class="tile axis-tile{out}"><div class="axis-head"><span class="axis-num">{t(ax["number"])}</span>{axis_icon(i)}</div><h3 class="axis-name">{t(ax["name"])}</h3><p class="axis-mission">{t(ax["mission"])}</p><p class="axis-desc">{t(ax["description"])}</p><p class="axis-q">{t(ax["question"])}</p></article>'
    bounds = "".join(f'<div class="tile bound"><h3>{t(b["title"]).replace("≠", "<i>≠</i>")}</h3><p>{t(b["text"])}</p></div>' for b in DATA["boundaries"])
    return (page_hero("Le périmètre", "Sept missions.<br><span>Un pas de côté.</span>", "Les axes suivent les sept missions du pôle Communication & Marque, plus un regard hors champ. Ils structurent la collecte : ce ne sont pas huit rubriques à remplir chaque semaine.")
            + f'<section class="sec" aria-labelledby="poles-h"><div class="sec-head"><div><p class="kicker">Trois pôles, trois veilles</p><h2 class="sec-title" id="poles-h">Chaque veille épouse <em>un pôle.</em></h2></div><p class="sec-note">Les trois veilles se lisent par tous ; le schéma indique le pôle dont chacune suit le mieux les missions.</p></div><div class="bento"><div class="tile poles"><div class="poles-box">{poles_svg()}</div></div></div></section>'
            + f'<section class="sec" aria-labelledby="axes-h"><div class="sec-head"><div><p class="kicker">Les huit axes</p><h2 class="sec-title" id="axes-h">Un axe principal <em>par signal.</em></h2></div><p class="sec-note">Le secteur coloré situe chaque axe sur le radar de l’édition.</p></div><div class="bento">{tiles}</div></section>'
            + f'<section class="sec" aria-labelledby="bounds-h"><div class="sec-head"><div><p class="kicker">Ce que la veille laisse aux autres</p><h2 class="sec-title" id="bounds-h">Des frontières <em>claires.</em></h2></div></div><div class="bento">{bounds}</div></section>')


def method_body(ctx):
    steps = [
        ("Collecter", "Partir des sources.", "Trois recherches par axe sur la fenêtre du lundi au dimanche. Priorité aux sources N1 (officielles, plateformes, établissements, réseaux de l’enseignement supérieur), puis N2 (presse spécialisée), toujours recoupées. Contenus promotionnels non sourcés et articles réservés non lus écartés."),
        ("Qualifier", "Garder les bonnes dates.", "Publication, événement, période des données et consultation ne se confondent pas. Trois statuts restent visibles : actualité de la semaine, contexte antérieur, dispositif observé. Une page non datée est une observation, pas une nouveauté."),
        ("Évaluer", "Quatre critères.", "Impact pour le pôle, urgence d’action, fiabilité de la source, convergence avec d’autres signaux. Chaque signal est rattaché à un objectif ou à un enjeu de la feuille de route du pôle."),
        ("Sélectionner", "Publier peu.", f"De {POLICY['targetMinSignals']} à {POLICY['maxSignals']} signaux, dont au moins un pas de côté hors enseignement supérieur et un cas d’école décrypté. Aucun remplissage : un sujet sans preuve suffisante n’est pas ajouté."),
        ("Anticiper", "Voir 90 jours devant.", "Une frise des salons, temps forts, calendriers officiels, échéances réglementaires et publications attendues, qui distingue le confirmé de l’indicatif. Elle sert l’objectif d’anticipation du pôle."),
        ("Proposer", "Une suite bornée.", f"Zéro à {POLICY['maxActions']} suites : vérifier, comparer, tester, préparer ou surveiller. Chacune indique une mission pilote proposée, un livrable attendu et un horizon. Rien n’engage automatiquement les équipes."),
    ]
    st = "".join(f'<div class="tile step"><span class="step-k">0{i}<small>{t(k)}</small></span><h3>{t(h)}</h3><p>{t(p)}</p></div>' for i, (k, h, p) in enumerate(steps, 1))
    levels = [("Critique", "pr-critique", "Impact à moins de 30 jours, ou obligation déjà applicable. Vérification et décision sans délai."),
              ("Important", "pr-important", "Impact entre un et six mois. Planification et approfondissement recommandés."),
              ("À surveiller", "pr-surveiller", "Signal émergent ou horizon plus lointain. Pas d’action immédiate, suivi éditorial.")]
    lv = "".join(f'<div class="tile level">{chip(n, c, True)}<p>{t(d)}</p></div>' for n, c, d in levels)
    limits = [("Pas d’exhaustivité", "L’absence d’un signal ne signifie pas l’absence d’activité. Les limites de couverture restent écrites dans chaque édition."),
              ("Pas de performance inventée", "Une campagne visible ne dit rien de son coût ni de son effet sur la considération. Aucun résultat n’est déduit d’un dispositif observé."),
              ("Pas d’avis juridique", "Les textes réglementaires sont résumés pour éclairer la communication. Leur application à TBS Education se valide avec le juridique."),
              ("Pas de social listening", "La veille observe l’environnement de la marque. Le suivi des mentions de TBS Education reste une mission outillée du pôle.")]
    lim = "".join(f'<div class="tile limit"><h3>{t(h)}</h3><p>{t(p)}</p></div>' for h, p in limits)
    fonts = "Les polices Manrope, Oswald et Playfair Display sont hébergées avec le site, sans appel à un service tiers." if ctx.mode == "site" else "Dans cet aperçu, les polices sont chargées depuis Google Fonts ; le site publié les héberge lui-même."
    prose = f'''<div class="tile prose"><h3>Rythme et format</h3><p>Publication chaque lundi, sur la fenêtre du lundi au dimanche précédents. L’essentiel se lit en cinq à dix minutes ; le cas d’école, les limites et les sources se déplient à la demande.</p><h3>Production et relecture</h3><p>Collecte et première rédaction assistées par IA (Manus.im), selon un prompt public versionné dans le dépôt du projet. Chaque édition est relue avant publication ; le script de génération refuse une édition qui sort des règles.</p><h3>Une publication de veille, pas une position officielle</h3><p>Les analyses et suites sont des propositions de travail à arbitrer par la responsable du pôle. Elles ne remplacent ni les décisions des équipes, ni la validation juridique, ni les positions institutionnelles de TBS Education.</p><h3>Vie privée</h3><p>Ce site ne dépose aucun cookie de suivi, ne charge aucun outil de mesure d’audience et ne collecte aucune donnée. Seule votre préférence de thème clair ou sombre peut être enregistrée dans votre navigateur. {t(fonts)}</p></div>'''
    return (page_hero("La méthode", "Moins de bruit.<br><span>Plus de discernement.</span>", "Une veille utile distingue le fait, notre lecture et la suite possible. La méthode reprend celle de la Veille Concurrents & ESR et la grille de criticité de la Veille IA & Web, adaptées aux missions du pôle.")
            + f'<section class="sec"><div class="sec-head"><div><p class="kicker">Le circuit</p><h2 class="sec-title">Six étapes, <em>chaque semaine.</em></h2></div></div><div class="bento">{st}</div></section>'
            + f'<section class="sec"><div class="sec-head"><div><p class="kicker">Prioriser</p><h2 class="sec-title">Trois niveaux <em>de criticité.</em></h2></div></div><div class="bento">{lv}</div></section>'
            + f'<section class="sec"><div class="sec-head"><div><p class="kicker">Les limites</p><h2 class="sec-title">Ce que la veille <em>ne promet pas.</em></h2></div></div><div class="bento">{lim}</div></section>'
            + f'<section class="sec"><div class="bento">{prose}</div></section>')


def sources_body(ctx):
    rows = list(csv.DictReader((ROOT / "content/sources.csv").open(encoding="utf-8", newline=""), delimiter=";"))
    families = list(OrderedDict.fromkeys(r["famille"] for r in rows))
    fam_id = {f: f"fam{i}" for i, f in enumerate(families)}
    refs = OrderedDict()
    for s in LATEST["signals"]:
        for src in s["sources"]:
            refs.setdefault(src["url"], src)
    for it in LATEST["agenda"]:
        refs.setdefault(it["source"]["url"], {"url": it["source"]["url"], "publisher": it["source"]["publisher"], "name": "Agenda · " + it["title"], "type": "Échéance", "date": it["dateLabel"]})
    lis = "".join(f'<li>{ext(r["url"], r["publisher"] + " — " + r["name"])}<span>{t(r["type"])} · {t(r["date"])}</span></li>' for r in refs.values())
    chips = f'<button type="button" class="filter is-active" data-filter="all" aria-pressed="true">Toutes <span>{len(rows)}</span></button>'
    chips += "".join(f'<button type="button" class="filter" data-filter="{fam_id[f]}" aria-pressed="false">{t(f)} <span>{sum(r["famille"] == f for r in rows)}</span></button>' for f in families)
    cards = ""
    for r in rows:
        axes = " · ".join(AXES[x]["short"] for x in r["axes"].split(","))
        lvl = "pr-important" if r["niveau"] == "N1" else "pr-surveiller"
        cards += f'<article class="tile src-card" data-item="{fam_id[r["famille"]]}"><div class="src-top"><span>{t(r["famille"])}</span>{chip(r["niveau"], lvl, True)}</div><h3>{t(r["source"])}</h3><p>{t(r["role"])}</p><p class="muted"><b>Limite</b> · {t(r["limite"])}</p><p class="muted">Axes · {t(axes)}</p>{ext(r["url"], "Consulter", "pill-link")}</article>'
    return (page_hero("La traçabilité", "Des sources.<br><span>Pas des suppositions.</span>", "Les références de l’édition courante, puis le corpus surveillé chaque semaine, classé par famille et par niveau de fiabilité.")
            + f'<section class="sec"><div class="bento"><div class="tile refs"><span class="label">Édition du {t(LATEST["dateLabel"])}</span><h2 class="tile-title" style="margin-bottom:18px">{len(refs)} références consultables</h2><ul class="src-list">{lis}</ul></div></div></section>'
            + f'<section class="sec" data-filter-scope data-nouns="source|sources"><div class="sec-head"><div><p class="kicker">Le corpus de surveillance</p><h2 class="sec-title">Où regarder <em>chaque semaine.</em></h2></div><span class="count-line" data-count aria-live="polite">{len(rows)} sources</span></div><p class="sec-note" style="margin-bottom:16px">N1 : sources officielles, plateformes, établissements et réseaux de l’enseignement supérieur. N2 : presse spécialisée, à recouper avec la source primaire. Un relais d’annonce ne vaut pas confirmation.</p><div class="filters" role="group" aria-label="Filtrer le corpus par famille">{chips}</div><div class="bento">{cards}<div class="empty" data-empty hidden><h3>Aucune source dans cette sélection.</h3></div></div></section>')


def archives_body(ctx):
    cards = ""
    for i, ed in enumerate(EDITIONS):
        status = "Édition courante" if i == 0 else "Archive"
        href = ctx.href("editions/" + ed["id"] + "/") if ctx.mode == "site" else "#veille"
        cards += f'<a class="tile arch" href="{href}"><span class="label label-red">{t(status)} · {t(ed["dateLabel"])}</span><h2>{t(ed["title"])}</h2><p>Fenêtre du {t(ed["period"])} · {len(ed["signals"])} signaux · {len(ed["actions"])} suites · {len(ed["agenda"])} échéances</p></a>'
    note = "Aucune édition antérieure : l’édition pilote ouvre la série. Aucune archive fictive n’est créée." if len(EDITIONS) == 1 else f"{len(EDITIONS) - 1} édition(s) antérieure(s), conservées avec leurs sources et leurs limites."
    return page_hero("La mémoire de la veille", "Les éditions.<br><span>Sans perdre le fil.</span>", "Chaque édition garde une page permanente, avec sa fenêtre, ses sources, ses limites et ses suites.") + f'<section class="sec"><div class="bento">{cards}<div class="arch-note">{t(note)}</div></div></section>'


def notfound_body(ctx):
    return page_hero("Page introuvable", "Ce lien n’existe pas.<br><span>Revenons à l’essentiel.</span>", "L’adresse demandée ne correspond à aucune page de la veille.") + f'<section class="sec"><a class="btn" href="{ctx.href("")}">Revenir à l’édition courante</a></section>'


# ---------------------------------------------------------------- enveloppe
SUN = '<svg class="i-sun" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="4.2" stroke="currentColor" stroke-width="1.8"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>'
MOON = '<svg class="i-moon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 14.6A8.4 8.4 0 0 1 9.4 4a8.4 8.4 0 1 0 10.6 10.6Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>'
THEME_INIT = "try{var t=localStorage.getItem('veille-cm-theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}catch(e){}"


def nav_html(ctx, active):
    links = ""
    for route, label, key in NAV:
        cur = ' aria-current="page"' if key == active else ""
        links += f'<a href="{ctx.href(route)}"{cur}>{t(label)}</a>'
    return f'<header class="nav"><div class="wrap nav-in"><a class="brand" href="{ctx.href("")}" aria-label="Veille Marque et Communication, édition courante">{mark_svg()}<span class="brand-text"><b>Veille</b><small>Marque &amp; Communication</small></span></a><nav class="nav-links" aria-label="Navigation principale">{links}</nav><button type="button" class="theme-btn" data-theme-toggle aria-label="Changer de thème">{SUN}{MOON}</button></div></header>'


def footer_html(ctx):
    fonts = "Polices hébergées avec le site" if ctx.mode == "site" else "Aperçu"
    return f'''<footer class="foot"><div class="wrap"><div class="foot-in"><div class="foot-brand">{mark_svg()}<div><b>Veille Marque &amp; Communication</b><p>{t(SITE["baseline"])}</p></div></div><div class="foot-links"><a href="{ctx.href("methode/")}">Méthode et limites</a><a href="{ctx.href("sources/")}">Sources</a>{ext("https://nogues.app/veille-esr/", "Veille Concurrents & ESR")}{ext("https://veilleiaweb.digital/", "Veille IA & Web")}{ext("https://nogues.app/", "nogues.app")}</div></div><div class="foot-legal"><span>TBS Education · {t(SITE["team"])} · Prototype éditorial sourcé</span><span>Sans cookies de suivi · Sans mesure d’audience · {t(fonts)}</span></div></div></footer>'''


def shell(route, title, description, body, active, depth, absolute=False):
    ctx = Ctx("site", depth, absolute)
    p = ctx.prefix
    canonical = BASE_URL + route
    robots = '<meta name="robots" content="noindex">' if route.startswith("404") else ""
    social = BASE_URL + "assets/social.png"
    full_title = f"{title} — Veille Marque & Communication · TBS Education" if title else "Veille Marque & Communication · TBS Education"
    return f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{t(full_title)}</title>
<meta name="description" content="{a(description)}">
<link rel="canonical" href="{a(canonical)}">{robots}
<meta name="theme-color" content="#f3f2f7" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#09080c" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="website"><meta property="og:site_name" content="Veille Marque &amp; Communication"><meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{a(full_title)}"><meta property="og:description" content="{a(description)}"><meta property="og:url" content="{a(canonical)}"><meta property="og:image" content="{a(social)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{a(social)}">
<link rel="icon" type="image/svg+xml" href="{p}assets/favicon.svg?v={asset_version("favicon.svg")}">
<script>{THEME_INIT}</script>
<link rel="preload" href="{p}assets/fonts/manrope.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{p}assets/styles.css?v={asset_version("styles.css")}">
<script src="{p}assets/app.js?v={asset_version("app.js")}" defer></script>
</head>
<body>
<a class="skip" href="#main">Aller au contenu</a>
{nav_html(ctx, active)}
<main id="main" class="wrap">
{body(ctx)}
</main>
{footer_html(ctx)}
</body>
</html>
'''


def write(route, content):
    folder = DIST / route
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(content, encoding="utf-8")


def build_site():
    validate()
    (ASSETS / "favicon.svg").write_text(favicon_svg(), encoding="utf-8")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(ASSETS, DIST / "assets")
    desc = SITE["description"]
    pages = [
        ("", "", desc, lambda c: edition_body(LATEST, c), "veille"),
        ("axes/", "Les axes", "Huit axes calés sur les missions du pôle Communication & Marque de TBS Education, et leurs frontières.", axes_body, "axes"),
        ("methode/", "La méthode", "Collecte, qualification, criticité, agenda à 90 jours et limites de la veille.", method_body, "methode"),
        ("sources/", "Sources", "Références de l’édition courante et corpus de surveillance hebdomadaire.", sources_body, "sources"),
        ("archives/", "Archives", "Les éditions de la veille, avec leurs sources, leurs limites et leurs suites.", archives_body, "archives"),
    ]
    for route, title, d, body, active in pages:
        depth = len([x for x in route.split("/") if x])
        write(route, shell(route, title, d, body, active, depth))
    for ed in EDITIONS:
        route = f'editions/{ed["id"]}/'
        write(route, shell(route, f'Édition du {ed["dateLabel"]}', ed["title"], lambda c, e=ed: edition_body(e, c), "veille", 2))
    write("404/", shell("404/", "Page introuvable", "Cette page n’existe pas.", notfound_body, "", 1))
    (DIST / "404.html").write_text(shell("404/", "Page introuvable", "Cette page n’existe pas.", notfound_body, "", 0, absolute=True), encoding="utf-8")
    routes = [r for r, *_ in pages] + [f'editions/{e["id"]}/' for e in EDITIONS]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "\n".join(f"<url><loc>{a(BASE_URL + r)}</loc><lastmod>{LATEST['date']}</lastmod></url>" for r in routes)
    (DIST / "sitemap.xml").write_text(sitemap + "\n</urlset>\n", encoding="utf-8")
    (DIST / ".htaccess").write_text(f"DirectoryIndex index.html\nErrorDocument 404 {BASE_PATH}404.html\nOptions -Indexes\n", encoding="utf-8")
    print(f"Site généré dans {DIST} : {len(routes) + 2} pages · {len(LATEST['signals'])} signaux · {len(LATEST['actions'])} suites · {len(LATEST['agenda'])} échéances.")


def build_preview(path):
    """Aperçu en page unique pour un artifact Claude : vues par ancre, polices Google Fonts, CSS et JS en ligne."""
    validate()
    (ASSETS / "favicon.svg").write_text(favicon_svg(), encoding="utf-8")
    ctx = Ctx("preview")
    css = re.sub(r"/\* @font-face:start \*/.*?/\* @font-face:end \*/", "", (ASSETS / "styles.css").read_text(encoding="utf-8"), flags=re.S)
    js = (ASSETS / "app.js").read_text(encoding="utf-8")
    views = [("veille", lambda c: edition_body(LATEST, c)), ("axes", axes_body), ("methode", method_body), ("sources", sources_body), ("archives", archives_body)]
    body = "".join(f'<div data-view id="{v}"{" hidden" if i else ""}>{fn(ctx)}</div>' for i, (v, fn) in enumerate(views))
    out = (
        "<title>Veille Marque & Communication</title>\n"
        f'<meta name="description" content="{a(SITE["description"])}">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Oswald:wght@700&family=Playfair+Display:ital,wght@1,800&display=swap">\n'
        f"<style>{css}</style>\n<script>{THEME_INIT}</script>\n"
        f'<a class="skip" href="#main">Aller au contenu</a>{nav_html(ctx, "veille")}<main id="main" class="wrap">{body}</main>{footer_html(ctx)}\n<script>{js}</script>\n'
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(out, encoding="utf-8")
    print(f"Aperçu généré : {path} ({len(out) // 1024} Ko)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", metavar="FICHIER", help="générer un aperçu en page unique")
    args = parser.parse_args()
    if args.preview:
        build_preview(args.preview)
    else:
        build_site()
