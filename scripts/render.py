#!/usr/bin/env python3
"""Render the Marque & Communication watch into one self-contained page (artifact body)."""
import csv
import html
import json
import re
import sys
from collections import OrderedDict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "content/editions.json").read_text(encoding="utf-8"))
SITE, POLICY = DATA["site"], DATA["editorialPolicy"]
AXES = OrderedDict((a["id"], a) for a in DATA["axes"])
EDITIONS = sorted(DATA["editions"], key=lambda e: e["date"], reverse=True)
ED = EDITIONS[0]
SIGNALS = ED["signals"]
SIG = {s["id"]: s for s in SIGNALS}
TIMING = {"week": "Actualité de la fenêtre", "context": "Actu hors période", "observation": "Dispositif observé"}
PRIORITY = {"Critique": "p-critique", "Important": "p-important", "À surveiller": "p-surveiller"}
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def a(value):
    """Escape for attributes and URLs."""
    return html.escape(str(value), quote=True)


def t(value):
    """Escape display text and apply French typographic non-breaking spaces."""
    s = html.escape(str(value), quote=False)
    s = re.sub(r" ([:])", " \\1", s)
    s = re.sub(r" ([;?!])", " \\1", s)
    s = s.replace("« ", "« ").replace(" »", " »").replace(" %", " %").replace(" M€", " M€")
    return s


def ext(url, label, css=""):
    if not url.startswith("https://"):
        raise ValueError(f"Invalid URL {url}")
    return f'<a class="{a(css)}" href="{a(url)}" target="_blank" rel="noopener noreferrer">{t(label)}<svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M6 18 18 6M8 6h10v10" stroke="currentColor" stroke-width="1.8"/></svg><span class="sr-only"> (nouvel onglet)</span></a>'


def validate():
    start, end = date.fromisoformat(ED["periodStart"]), date.fromisoformat(ED["periodEnd"])
    assert (end - start).days <= 6 and end <= date.fromisoformat(ED["date"]), "Fenêtre invalide"
    assert len(SIGNALS) <= POLICY["maxSignals"] and len(ED["actions"]) <= POLICY["maxActions"], "Plafonds dépassés"
    assert any(s["axis"] == "horschamp" for s in SIGNALS), "Un regard hors champ est requis"
    assert ED["featuredSignal"] in SIG, "Signal mis en avant inconnu"
    for s in SIGNALS:
        assert s["axis"] in AXES and s["sources"], f"Axe ou source manquant : {s['id']}"
        assert s["priority"] in PRIORITY, f"Criticité inconnue : {s['id']}"
        pub = date.fromisoformat(s["publicationDate"])
        if s["timing"] == "week":
            assert start <= pub <= end, f"Date hors fenêtre pour une actualité : {s['id']}"
        if s["timing"] == "context":
            assert pub < start, f"Un contexte doit précéder la fenêtre : {s['id']}"
        for src in s["sources"]:
            assert src["url"].startswith("https://"), src["url"]
    for act in ED["actions"]:
        assert act["signal"] in SIG, act["title"]
    for p in ED["perspectives"]:
        assert all(k in SIG for k in p["signals"]), p["id"]
    assert [p["id"] for p in ED["perspectives"]] == ["panorama", "fil-rouge", "tensions", "concurrence"]
    horizon = date.fromisoformat(ED["date"]) + timedelta(days=POLICY["agendaHorizonDays"])
    for item in ED["agenda"]:
        d = date.fromisoformat(item["date"])
        assert date.fromisoformat(ED["date"]) <= d <= horizon, f"Échéance hors horizon : {item['title']}"
        assert item["axis"] in AXES and item["status"] in ("Confirmé", "Indicatif")


def reading_minutes():
    words = len((ED["intro"] + " " + ED["stake"]).split())
    for s in SIGNALS:
        words += len((s["title"] + " " + s["fact"] + " " + s["implication"]).split())
    return max(1, round(words / 210))


def axis_label(axis_id):
    ax = AXES[axis_id]
    return f'{ax["number"]} — {ax["name"]}'


def card(s):
    ax = AXES[s["axis"]]
    outside = s["axis"] == "horschamp"
    classes = "signal-card" + (" outside-card" if outside else "") + (" case-card" if s.get("caseStudy") else "")
    timing = "" if s["timing"] == "week" else f'<span class="timing-badge">{t(TIMING[s["timing"]])}</span>'
    flag = ""
    if outside:
        flag = '<span class="card-flag flag-outside">Regard hors ESR</span>'
    elif s.get("caseStudy"):
        flag = '<span class="card-flag flag-case">Cas d’école</span>'
    first = s["sources"][0]
    analysis = ""
    if s.get("analysis"):
        parts = "".join(f'<section><h4>{t(x["title"])}</h4><p>{t(x["text"])}</p></section>' for x in s["analysis"])
        analysis = f'<details class="card-details case-details"><summary>Lire le cas d’école<span aria-hidden="true" class="plus">+</span></summary><div class="details-body"><p class="details-note">Appréciation éditoriale. Elle ne mesure pas les résultats de l’établissement.</p>{parts}</div></details>'
    sources = "".join(f'<li>{ext(x["url"], x["publisher"] + " — " + x["name"])}<span>{t(x["type"])} · {t(x["date"])}</span></li>' for x in s["sources"])
    return f'''<article class="{classes}" data-axis="{a(s["axis"])}" id="signal-{a(s["id"])}">
<div class="card-top"><span class="axis-label">{t(axis_label(s["axis"]))}</span><span class="chips"><span class="chip {PRIORITY[s["priority"]]}">{t(s["priority"])}</span><span class="chip chip-intent">{t(s["label"])}</span></span></div>
{flag}<h3>{t(s["title"])}</h3>
<div class="timing-line">{timing}<span>{t(s["dateLabel"])}</span></div>
<p class="signal-fact">{t(s["fact"])}</p>
<p class="verdict"><strong>Notre lecture</strong> {t(s["verdict"])}</p>
<div class="implication"><span>Pour le pôle Communication &amp; Marque</span><p>{t(s["implication"])}</p></div>
<div class="card-bottom"><span class="roadmap">Feuille de route · {t(s["roadmap"])}</span>{ext(first["url"], first["publisher"], "source-link")}</div>
{analysis}
<details class="card-details"><summary>Dates, sources et limites<span aria-hidden="true" class="plus">+</span></summary><div class="details-body"><p class="details-date">{t(s["status"])} · {t(s["dateLabel"])}</p><p>{t(s["limits"])}</p><ul class="source-list">{sources}</ul></div></details>
</article>'''


def filter_bar(scope_items, key, label):
    counts = {}
    for item in scope_items:
        counts[item[key]] = counts.get(item[key], 0) + 1
    buttons = f'<button type="button" class="filter-button is-active" data-filter="all" aria-pressed="true">Tous <span>{len(scope_items)}</span></button>'
    for ax in AXES.values():
        n = counts.get(ax["id"], 0)
        dis = " is-empty" if n == 0 else ""
        buttons += f'<button type="button" class="filter-button{dis}" data-filter="{a(ax["id"])}" aria-pressed="false">{t(ax["short"])} <span>{n}</span></button>'
    return f'<div class="filter-bar" role="group" aria-label="{a(label)}">{buttons}</div>'


def sig_links(ids):
    return "".join(f'<a href="#signal-{a(k)}">{t(SIG[k]["actor"])}</a>' for k in ids)


def view_veille(minutes, sources_count):
    feat = SIG[ED["featuredSignal"]]
    fsrc = feat["sources"][0]
    week = sum(s["timing"] == "week" for s in SIGNALS)
    ctx = sum(s["timing"] == "context" for s in SIGNALS)
    obs = sum(s["timing"] == "observation" for s in SIGNALS)
    quals = [f"{week} actualités de la fenêtre"]
    if ctx:
        quals.append(f"{ctx} contextes hors période")
    if obs:
        quals.append(f"{obs} dispositifs observés")
    ordered = [s for s in SIGNALS if s["axis"] != "horschamp"] + [s for s in SIGNALS if s["axis"] == "horschamp"]
    cards = "".join(card(s) for s in ordered)

    kpi_tiles = ""
    for k in DATA["kpis"]:
        links = sig_links(ED["kpiLinks"].get(k["id"], []))
        if k["id"] == "anticipation":
            links += '<a href="#agenda">Agenda à 90 jours</a>'
        kpi_tiles += f'<article class="kpi-tile"><p class="kpi-value">{t(k["value"])}</p><h3>{t(k["name"])}</h3><p>{t(k["text"])}</p><div class="kpi-links"><span>Signaux utiles</span>{links}</div></article>'

    facets = ""
    for i, p in enumerate(ED["perspectives"], 1):
        text = ED["intro"] if p["id"] == "panorama" else p["text"]
        facets += f'<article class="facet"><p class="facet-kicker"><span>{t(p["name"])}</span><span>0{i}</span></p><h3>{t(p["question"])}</h3><p>{t(text)}</p><div class="facet-links"><span>Revenir aux signaux</span>{sig_links(p["signals"])}</div></article>'

    months = OrderedDict()
    for item in sorted(ED["agenda"], key=lambda x: x["date"]):
        d = date.fromisoformat(item["date"])
        months.setdefault(f"{MONTHS[d.month - 1]} {d.year}", []).append(item)
    agenda = ""
    for month, items in months.items():
        rows = ""
        for it in items:
            st = "st-confirmed" if it["status"] == "Confirmé" else "st-indicative"
            note = f'<p class="agenda-note">{t(it["note"])}</p>' if it.get("note") else ""
            rows += f'''<li class="agenda-item"><p class="agenda-date">{t(it["dateLabel"])}</p><div class="agenda-body"><h4>{t(it["title"])}</h4><p>{t(it["why"])}</p>{note}</div><div class="agenda-meta"><span class="chip {st}">{t(it["status"])}</span><span class="agenda-axis">{t(AXES[it["axis"]]["number"] + " " + AXES[it["axis"]]["short"])}</span>{ext(it["source"]["url"], it["source"]["publisher"], "source-link")}</div></li>'''
        agenda += f'<div class="agenda-month"><h3>{t(month.capitalize())}</h3><ol>{rows}</ol></div>'

    actions = ""
    for i, act in enumerate(ED["actions"], 1):
        actions += f'<article class="action-card"><span class="action-number">0{i}</span><div><p class="action-horizon">{t(act["horizon"])} · À arbitrer</p><h3>{t(act["title"])}</h3><p class="action-owner">{t(act["owner"])}</p><p><strong>Livrable attendu</strong> {t(act["result"])}</p><a class="action-link" href="#signal-{a(act["signal"])}">Signal d’origine : {t(SIG[act["signal"]]["actor"])}</a></div></article>'
    heading = {0: "Aucune suite à engager.", 1: "Une piste. Pas un engagement.", 2: "Deux pistes. Pas deux engagements.", 3: "Trois pistes. Pas trois engagements."}[len(ED["actions"])]
    coverage = "".join(f'<li><strong>{t(AXES[k]["number"] + " " + AXES[k]["name"])}</strong><span>{t(v)}</span></li>' for k, v in ED["coverage"].items())

    return f'''<section class="view" id="veille" aria-labelledby="hero-title">
<div class="hero container">
<div class="hero-rings" aria-hidden="true"><span></span><span></span><span></span></div>
<p class="edition-meta"><span class="live-dot" aria-hidden="true"></span><span>{t(ED["status"])} · {t(ED["dateLabel"])}</span><span class="meta-period">Fenêtre du {t(ED["period"])}</span></p>
<div class="hero-grid">
<div class="hero-title"><p class="eyebrow">TBS Education / radar hebdomadaire du pôle Communication &amp; Marque</p><h1 id="hero-title">Marque.<br>Récits.<br><span>Rayonnement.</span></h1><p class="hero-subtitle">Ce qui change dans la façon dont les marques se racontent, se diffusent et se prouvent. Et ce que le pôle peut en faire.</p></div>
<aside class="featured" aria-label="Le signal à retenir"><p class="featured-kicker">Le signal à retenir · cas d’école</p><p class="featured-fact">{t(ED["featuredFact"])}</p><h2>{t(ED["featuredTitle"])}</h2><p class="featured-note">{t(ED["featuredNote"])}</p><div class="featured-bottom"><span>{t(ED["featuredLabel"])}</span><a href="#signal-{a(feat["id"])}">Lire le signal</a>{ext(fsrc["url"], fsrc["publisher"], "featured-source")}</div></aside>
</div>
<div class="edition-strip"><div><strong>{len(SIGNALS):02d}</strong><span>signaux sélectionnés</span></div><div><strong>{len(ED["actions"]):02d}</strong><span>suites proposées</span></div><div><strong>{len(ED["agenda"]):02d}</strong><span>échéances à 90 jours</span></div><div><strong>{minutes:02d}<small> min</small></strong><span>pour lire l’essentiel</span></div></div>
</div>
<section class="summary-box container" aria-labelledby="summary-title"><div class="summary-head"><p class="eyebrow">Le point de départ</p><h2 id="summary-title">L’essentiel en 30 secondes.</h2></div><div class="summary-content"><div><p class="summary-label">Résumé de la semaine</p><p class="summary-lead">{t(ED["intro"])}</p></div><div class="summary-stake"><p class="summary-label">Enjeux pour le pôle</p><p>{t(ED["stake"])}</p></div></div></section>
<section class="kpi-section container" aria-labelledby="kpi-title"><div class="section-head"><div><p class="eyebrow">Aligné sur la feuille de route du pôle</p><h2 id="kpi-title">Ce que sert cette édition.</h2></div></div><div class="kpi-grid">{kpi_tiles}</div></section>
<section class="signals-section container" data-filter-scope aria-labelledby="signals-title"><div class="section-head"><div><p class="eyebrow">Une sélection, pas une revue de presse</p><h2 id="signals-title">Ce qui mérite votre attention.</h2></div><span class="section-counter" data-count aria-live="polite">{len(SIGNALS)} signaux</span></div><p class="timing-summary">{t(" · ".join(quals))}. Les contextes ne sont pas présentés comme des nouveautés de la semaine.</p>{filter_bar(SIGNALS, "axis", "Filtrer les signaux par axe")}<div class="signals-grid">{cards}</div><div class="empty-state" hidden><h3>Aucun signal retenu sur cet axe cette semaine.</h3><p>La sélection est volontairement courte : ce n’est pas une preuve d’absence d’actualité.</p><a href="#axes">Voir le périmètre des huit axes</a></div></section>
<section class="facets-section container" aria-labelledby="facets-title"><div class="section-head"><div><p class="eyebrow">Prendre du recul</p><h2 id="facets-title">Une édition. <em>Quatre regards.</em></h2></div></div><div class="facets-grid">{facets}</div></section>
<section class="agenda-section container" id="agenda" aria-labelledby="agenda-title"><div class="section-head"><div><p class="eyebrow">Anticiper plutôt que subir</p><h2 id="agenda-title">À anticiper dans les 90 jours.</h2></div><span class="section-tag">Confirmé ou indicatif, toujours sourcé</span></div><p class="section-description">Salons, calendrier post-bac, échéances réglementaires et publications attendues qui touchent le pôle d’ici fin janvier 2027. Une date indicative est à confirmer avant d’engager des moyens.</p><div class="agenda">{agenda}</div></section>
<section class="actions-section container" aria-labelledby="actions-title"><div class="section-head"><div><p class="eyebrow">De la veille à la suite utile</p><h2 id="actions-title">{heading}</h2></div><span class="section-tag">Propositions à arbitrer</span></div><div class="actions-grid">{actions}</div><p class="fine-print">Pilotes, moyens et calendrier à confirmer par la responsable du pôle. Ces pistes ne constituent pas des engagements des équipes.</p></section>
<section class="coverage-box container"><details><summary><span>Ce que couvre, et ne couvre pas, cette édition</span><span aria-hidden="true" class="plus">+</span></summary><p>{t(ED["notice"])}</p><ul>{coverage}</ul></details></section>
<p class="edition-foot container">Édition publiée le {t(ED["dateLabel"])} · Europe/Paris · {sources_count} sources consultables · Archives : aucune édition antérieure, il s’agit de l’édition pilote.</p>
</section>'''


def view_axes():
    cards = ""
    for ax in AXES.values():
        last = " axis-outside" if ax["id"] == "horschamp" else ""
        cards += f'<article class="axis-card{last}"><span class="axis-number">{t(ax["number"])}</span><h2>{t(ax["name"])}</h2><p class="axis-mission">{t(ax["mission"])}</p><p>{t(ax["description"])}</p><p class="axis-question">{t(ax["question"])}</p></article>'
    bounds = "".join(f'<div><h3>{t(b["title"])}</h3><p>{t(b["text"])}</p></div>' for b in DATA["boundaries"])
    return f'''<section class="view" id="axes" hidden aria-labelledby="axes-title">
<div class="page-intro container"><p class="eyebrow">Le périmètre</p><h1 id="axes-title">Sept missions.<br><span>Un pas de côté.</span></h1><p>Les axes suivent les sept missions du pôle Communication &amp; Marque, plus un regard hors champ. Ils structurent la collecte : ce ne sont pas huit rubriques à remplir. Un sujet garde un axe principal ; les autres dimensions restent des liens.</p></div>
<div class="container axes-grid">{cards}</div>
<section class="container editorial-note"><h2>Des frontières claires.</h2><p class="section-description">La Direction Marketing, Communication &amp; Développement compte trois pôles. Cette veille ne couvre que le pôle Communication &amp; Marque.</p><div class="boundary-grid">{bounds}</div></section>
</section>'''


def view_method():
    steps = [
        ("01 / Collecter", "Partir des sources.", "Chaque semaine, trois recherches par axe et lecture des publications les plus récentes. Priorité aux sources de niveau N1 (officielles, plateformes, établissements, réseaux de l’enseignement supérieur) et N2 (presse spécialisée communication, création et enseignement supérieur). Les contenus promotionnels non sourcés et les articles réservés non lus sont écartés."),
        ("02 / Qualifier", "Garder les bonnes dates.", "Publication, événement, période des données et consultation ne sont pas interchangeables. Trois statuts restent visibles : actualité de la fenêtre, contexte hors période, dispositif observé. Une page non datée est une observation, pas une nouveauté."),
        ("03 / Évaluer", "Quatre critères.", "Impact pour le pôle, urgence d’action, fiabilité de la source, convergence avec d’autres signaux. Chaque signal est rattaché à un objectif ou à un enjeu de la feuille de route du pôle."),
        ("04 / Sélectionner", "Publier peu.", f"De {POLICY['targetMinSignals']} à {POLICY['maxSignals']} signaux, plafond de {POLICY['maxSignals']}, dont au moins un regard hors enseignement supérieur et un cas d’école décrypté. Aucun remplissage : un sujet sans preuve suffisante n’est pas ajouté. L’essentiel se lit en 30 secondes, les décryptages restent repliés."),
        ("05 / Anticiper", "Voir 90 jours devant.", "Un agenda des salons, temps forts, calendriers officiels, échéances réglementaires et publications attendues, distinguant le confirmé de l’indicatif. Il sert directement l’objectif d’anticipation du pôle."),
        ("06 / Proposer", "Une suite bornée.", f"Zéro à {POLICY['maxActions']} suites : vérifier, comparer, tester, préparer ou surveiller. Chacune indique la mission pilote proposée, le livrable attendu et un horizon indicatif. Rien n’engage automatiquement les équipes."),
    ]
    cards = "".join(f'<article class="method-card"><span>{t(k)}</span><h2>{t(h)}</h2><p>{t(p)}</p></article>' for k, h, p in steps)
    levels = [("p-critique", "Critique", "Impact à moins de 30 jours, ou obligation déjà applicable. Vérification et décision sans délai."), ("p-important", "Important", "Impact entre un et six mois. Planification et approfondissement recommandés."), ("p-surveiller", "À surveiller", "Signal émergent ou horizon plus lointain. Pas d’action immédiate, suivi éditorial.")]
    lv = "".join(f'<div class="level"><span class="chip {c}">{t(n)}</span><p>{t(d)}</p></div>' for c, n, d in levels)
    return f'''<section class="view" id="methode" hidden aria-labelledby="method-title">
<div class="page-intro container"><p class="eyebrow">La méthode</p><h1 id="method-title">Moins de bruit.<br><span>Plus de discernement.</span></h1><p>Une veille utile distingue le fait, notre lecture et la suite possible. Elle reprend la méthode de la Veille Concurrents &amp; ESR et la grille de criticité de la Veille IA &amp; Web, adaptées aux missions du pôle.</p></div>
<div class="container method-grid">{cards}</div>
<section class="container editorial-note"><h2>Trois niveaux de criticité.</h2><div class="levels">{lv}</div></section>
<section class="container editorial-note"><h2>Ce que cette veille ne promet pas.</h2><div class="boundary-grid"><div><h3>Pas d’exhaustivité</h3><p>L’absence d’un signal ne signifie pas l’absence d’activité. Les limites de couverture restent explicites dans chaque édition.</p></div><div><h3>Pas de performance inventée</h3><p>Une campagne visible ne dit rien de son coût ni de son effet sur la considération. Aucun résultat n’est déduit d’un dispositif observé.</p></div><div><h3>Pas d’avis juridique</h3><p>Les textes réglementaires sont résumés pour éclairer la communication. Leur application à TBS Education se valide avec le juridique.</p></div><div><h3>Pas de social listening</h3><p>La veille observe l’environnement. Le suivi des mentions de TBS Education reste une mission outillée du pôle.</p></div></div></section>
<section class="container method-bottom"><h2>Rythme et format.</h2><p>Publication chaque lundi, sur la fenêtre du lundi au dimanche précédents. L’essentiel se lit en cinq à dix minutes ; les cas d’école et les limites se déplient à la demande. Production assistée par IA (Manus.im), relecture humaine avant publication.</p><h2>Une publication de veille, pas une position officielle.</h2><p>Les analyses et suites sont des propositions de travail à arbitrer par la responsable du pôle. Elles ne remplacent ni les décisions des équipes, ni la validation juridique, ni les positions institutionnelles de TBS Education.</p><h2>Vie privée.</h2><p>Cette page ne dépose aucun cookie de suivi, ne charge aucun outil de mesure d’audience et ne collecte aucune donnée. Les liens de sources ouvrent des sites tiers, soumis à leurs propres règles.</p></section>
</section>'''


def view_sources():
    rows = list(csv.DictReader((ROOT / "content/sources.csv").open(encoding="utf-8", newline=""), delimiter=";"))
    families = list(OrderedDict.fromkeys(r["famille"] for r in rows))
    refs = OrderedDict()
    for s in SIGNALS:
        for src in s["sources"]:
            refs.setdefault(src["url"], src)
    for item in ED["agenda"]:
        refs.setdefault(item["source"]["url"], {"url": item["source"]["url"], "publisher": item["source"]["publisher"], "name": "Agenda — " + item["title"], "type": "Échéance", "date": item["dateLabel"]})
    primary = "".join(f'<li>{ext(r["url"], r["publisher"] + " — " + r["name"])}<span>{t(r["type"])} · {t(r["date"])}</span></li>' for r in refs.values())
    buttons = f'<button type="button" class="filter-button is-active" data-filter="all" aria-pressed="true">Toutes <span>{len(rows)}</span></button>'
    fam_ids = {}
    for i, f in enumerate(families):
        fam_ids[f] = f"fam{i}"
        n = sum(r["famille"] == f for r in rows)
        buttons += f'<button type="button" class="filter-button" data-filter="fam{i}" aria-pressed="false">{t(f)} <span>{n}</span></button>'
    cards = ""
    for r in rows:
        axes = " · ".join(AXES[x]["short"] for x in r["axes"].split(","))
        cards += f'<article class="source-card" data-axis="{fam_ids[r["famille"]]}"><div class="source-top"><span>{t(r["famille"])}</span><span class="chip chip-level">{t(r["niveau"])}</span></div><h3>{t(r["source"])}</h3><p>{t(r["role"])}</p><p class="source-limit"><strong>Limite</strong> {t(r["limite"])}</p><p class="source-axes">Axes · {t(axes)}</p>{ext(r["url"], "Consulter la source", "source-visit")}</article>'
    return f'''<section class="view" id="sources" hidden aria-labelledby="sources-title">
<div class="page-intro container"><p class="eyebrow">La traçabilité</p><h1 id="sources-title">Des sources.<br><span>Pas des suppositions.</span></h1><p>Les références de l’édition courante, puis le corpus de surveillance hebdomadaire, classé par famille et par niveau de fiabilité.</p></div>
<section class="container primary-sources"><h2>Les {len(refs)} références de l’édition.</h2><ul class="source-list">{primary}</ul></section>
<section class="container sources-section" data-filter-scope><div class="section-head"><div><p class="eyebrow">Corpus de surveillance</p><h2>Où regarder chaque semaine.</h2></div><span class="section-counter" data-count aria-live="polite">{len(rows)} sources</span></div><p class="section-description">N1 : sources officielles, plateformes, établissements et réseaux de l’enseignement supérieur. N2 : presse spécialisée, à recouper avec la source primaire. Les relais d’annonces ne valent pas confirmation.</p><div class="filter-bar" role="group" aria-label="Filtrer le corpus par famille">{buttons}</div><div class="source-grid">{cards}</div><div class="empty-state" hidden><h3>Aucune source dans cette sélection.</h3></div></section>
</section>'''


CSS = r"""
/* Radar éditorial : colonne de lecture large, cartes Bento à bords francs, agenda en frise. Famille visuelle des veilles nogues.app, teintée violet pour le pôle Communication & Marque. */
:root{
  --paper:#121019;--surface:#1b1825;--soft:#221d2e;--line:#352f45;--ink:#f3f1f7;--muted:#aea7bc;
  --red:#ff3e52;--red-text:#ff8a97;--red-bg:#3b1e29;--violet:#b9a4ff;--violet-bg:#2a2245;
  --feature-bg:#1f1a2d;--feature-ink:#f6f4fa;--feature-muted:#bdb5cb;--feature-line:#40385a;
  --outside-bg:#1f1931;--outside-line:#463a72;--header-bg:color-mix(in srgb,var(--paper) 94%,transparent);
  --display:Oswald,"Arial Narrow",Arial,sans-serif;--serif:"Playfair Display",Georgia,serif;--font:Manrope,"Segoe UI",Arial,sans-serif;
  --radius:18px;color-scheme:dark
}
@media (prefers-color-scheme:light){:root:not([data-theme="dark"]){
  --paper:#f6f4f9;--surface:#ffffff;--soft:#eee6ff;--line:#dcd6e6;--ink:#17141f;--muted:#5d5769;
  --red-text:#bf1e32;--red-bg:#ffd8d6;--violet:#4000bf;--violet-bg:#eee6ff;
  --feature-bg:#17141f;--feature-ink:#ffffff;--feature-muted:#cbc4d6;--feature-line:#3a3447;
  --outside-bg:#f2edff;--outside-line:#cdbff4;color-scheme:light}}
:root[data-theme="light"]{
  --paper:#f6f4f9;--surface:#ffffff;--soft:#eee6ff;--line:#dcd6e6;--ink:#17141f;--muted:#5d5769;
  --red-text:#bf1e32;--red-bg:#ffd8d6;--violet:#4000bf;--violet-bg:#eee6ff;
  --feature-bg:#17141f;--feature-ink:#ffffff;--feature-muted:#cbc4d6;--feature-line:#3a3447;
  --outside-bg:#f2edff;--outside-line:#cdbff4;color-scheme:light}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:96px}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--font);font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit}
p,h1,h2,h3,h4{margin:0}
h1,h2,h3,h4{text-wrap:balance}
h2{font-size:clamp(25px,3vw,34px);font-weight:800;letter-spacing:-.04em;line-height:1.14}
h3{font-size:21px;font-weight:800;letter-spacing:-.03em;line-height:1.2}
h1{font-family:var(--display);font-weight:700;text-transform:uppercase;letter-spacing:-.01em;line-height:1.04}
h1 span,h2 em{font-family:var(--serif);font-style:italic;font-weight:800;color:var(--red);text-transform:none;letter-spacing:-.02em}
svg{width:15px;height:15px;flex:none}
button{font:inherit;color:inherit;cursor:pointer}
:focus-visible{outline:3px solid var(--red);outline-offset:4px;border-radius:4px}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
.container{width:100%;max-width:1248px;margin-inline:auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
@media (min-width:900px){.container{padding-left:max(24px,env(safe-area-inset-left,0px));padding-right:max(24px,env(safe-area-inset-right,0px))}}
.eyebrow{font-size:11px;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);margin-bottom:12px}
.site-header{position:sticky;top:env(safe-area-inset-top,0px);z-index:20;background:var(--header-bg);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:21;background:var(--paper)}
.header-inner{display:flex;align-items:center;gap:28px;min-height:76px;flex-wrap:wrap}
.wordmark{display:flex;align-items:center;gap:11px;text-decoration:none;font-weight:800;font-size:20px;letter-spacing:-.04em;line-height:1.1}
.wordmark small{display:block;font-size:10.5px;letter-spacing:.12em;font-weight:800;margin-top:4px}
.brand-dot{width:30px;height:30px;border-radius:50%;background:var(--red);flex:none}
.site-nav{display:flex;gap:6px;margin-inline:auto;overflow-x:auto;scrollbar-width:none}
.site-nav a{font-size:14px;font-weight:700;text-decoration:none;padding:10px 12px;border-radius:9px;white-space:nowrap;color:var(--muted)}
.site-nav a:hover{color:var(--ink)}
.site-nav a[aria-current="page"]{color:var(--ink);box-shadow:inset 0 -2px 0 var(--red);border-radius:0}
.org{font-size:13px;font-weight:800;padding-left:18px;border-left:1px solid var(--line);white-space:nowrap}
@media (max-width:860px){.header-inner{gap:6px 14px;padding-block:12px}.site-nav{order:3;width:100%;margin:0 -12px}.org{margin-left:auto}}
.hero{position:relative;overflow:hidden;padding-top:34px}
.hero-rings{position:absolute;inset:0;pointer-events:none;z-index:0}
.hero-rings span{position:absolute;left:36%;top:30%;width:340px;height:340px;margin:-170px;border:1px solid var(--red);border-radius:50%;opacity:.0;animation:ring 9s cubic-bezier(.2,.7,.2,1) infinite}
.hero-rings span:nth-child(2){animation-delay:-3s}.hero-rings span:nth-child(3){animation-delay:-6s}
@keyframes ring{0%{transform:scale(.1);opacity:0}15%{opacity:.22}80%{opacity:.04}100%{transform:scale(1.15);opacity:0}}
@media (prefers-reduced-motion:reduce){.hero-rings span{animation:none;opacity:0}html{scroll-behavior:auto}}
.edition-meta{position:relative;z-index:1;display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.live-dot{width:8px;height:8px;border-radius:50%;background:var(--red)}
.meta-period{color:var(--muted);padding-left:14px;border-left:1px solid var(--line);text-transform:none;letter-spacing:.02em}
.hero-grid{position:relative;z-index:1;display:grid;grid-template-columns:1.1fr 1fr;gap:56px;padding:34px 0 40px}
.hero-grid>*{min-width:0}
.hero h1{font-size:clamp(46px,7vw,92px);margin-bottom:22px}
.hero-subtitle{font-size:18px;color:var(--muted);max-width:30em}
.featured{background:var(--feature-bg);color:var(--feature-ink);border:1px solid var(--feature-line);border-radius:var(--radius);padding:28px 30px 24px;display:flex;flex-direction:column;gap:14px;position:relative;overflow:hidden}
.featured::after{content:"";position:absolute;width:240px;height:240px;right:-150px;top:70px;border:1px solid var(--feature-line);border-radius:50%}
.featured-kicker{font-size:11px;font-weight:800;letter-spacing:.15em;text-transform:uppercase;color:var(--feature-muted)}
.featured-fact{font-family:var(--display);font-weight:700;text-transform:uppercase;color:var(--red);font-size:clamp(34px,4vw,52px);line-height:1;letter-spacing:-.01em;max-width:10em}
.featured h2{font-size:23px;letter-spacing:-.03em;max-width:22em}
.featured-note{font-size:14.5px;color:var(--feature-muted);line-height:1.65;max-width:34em}
.featured-bottom{margin-top:auto;padding-top:16px;border-top:1px solid var(--feature-line);display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--feature-muted)}
.featured-bottom span{flex:1 1 100%}
.featured-bottom a{font-size:13px;letter-spacing:0;text-transform:none;color:var(--feature-ink);font-weight:700;display:inline-flex;gap:7px;align-items:center;text-underline-offset:4px}
.featured-bottom a:hover{color:var(--red)}
.edition-strip{position:relative;z-index:1;display:grid;grid-template-columns:repeat(4,1fr);border-block:1px solid var(--line);padding-block:20px}
.edition-strip>div{display:flex;align-items:center;gap:12px;padding:0 20px;border-right:1px solid var(--line);min-width:0}
.edition-strip>div:first-child{padding-left:0}.edition-strip>div:last-child{border-right:0}
.edition-strip strong{font-size:30px;font-weight:800;letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.edition-strip small{font-size:15px}
.edition-strip span{font-size:13px;color:var(--muted);line-height:1.35;max-width:8em}
.summary-box{margin-top:40px}
.summary-box>.summary-head,.summary-box>.summary-content{min-width:0}
.summary-box{display:grid;grid-template-columns:.7fr 1.6fr;gap:44px}
[hidden]{display:none!important}
.edition-strip strong{white-space:nowrap}
.summary-head h2{font-size:28px}
.summary-content{display:grid;gap:22px;background:var(--soft);border-radius:var(--radius);padding:30px 34px}
.summary-label{font-size:10.5px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--red-text);margin-bottom:8px}
.summary-lead{font-size:18px;line-height:1.65;letter-spacing:-.015em}
.summary-stake{border-top:1px solid var(--line);padding-top:18px}
.summary-stake p:last-child{font-size:15px;color:var(--muted);line-height:1.75}
section.kpi-section,section.signals-section,section.facets-section,section.agenda-section,section.actions-section{padding-top:64px}
.section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px 24px;flex-wrap:wrap;margin-bottom:22px}
.section-head>div{min-width:0}
.section-counter,.section-tag{font-size:12.5px;color:var(--muted);font-weight:700;padding-bottom:4px}
.section-tag{text-transform:uppercase;letter-spacing:.08em;font-size:11px;color:var(--violet)}
.section-description{color:var(--muted);max-width:62em;margin-bottom:22px;font-size:15px}
.kpi-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.kpi-tile{border:1px solid var(--line);border-radius:var(--radius);padding:22px 24px;display:flex;flex-direction:column;gap:8px;background:var(--surface);min-width:0}
.kpi-value{font-family:var(--display);font-weight:700;font-size:40px;line-height:1;color:var(--violet);font-variant-numeric:tabular-nums}
.kpi-tile h3{font-size:18px}
.kpi-tile>p:not(.kpi-value){font-size:14px;color:var(--muted)}
.kpi-links{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto;padding-top:12px;border-top:1px solid var(--line)}
.kpi-links span,.facet-links span{flex-basis:100%;font-size:10.5px;font-weight:800;letter-spacing:.11em;text-transform:uppercase;color:var(--muted)}
.kpi-links a,.facet-links a{font-size:12.5px;font-weight:700;text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:4px 10px}
.kpi-links a:hover,.facet-links a:hover{border-color:var(--red);color:var(--red-text)}
.timing-summary{font-size:13.5px;color:var(--muted);margin:-8px 0 14px}
.filter-bar{display:flex;gap:6px;overflow-x:auto;padding-bottom:16px;scrollbar-width:thin}
.filter-button{border:1px solid var(--line);background:transparent;color:var(--muted);border-radius:9px;font-size:12.5px;font-weight:700;padding:9px 13px;white-space:nowrap}
.filter-button span{font-variant-numeric:tabular-nums;opacity:.7;margin-left:3px}
.filter-button:hover{border-color:var(--muted);color:var(--ink)}
.filter-button.is-active{background:var(--ink);border-color:var(--ink);color:var(--paper)}
.filter-button.is-empty{opacity:.55}
.signals-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
.signal-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:24px 26px 0;display:flex;flex-direction:column;gap:14px;min-width:0;scroll-margin-top:100px}
.signal-card:target{border-color:var(--red)}
.card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap}
.axis-label{font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{display:inline-flex;align-items:center;font-size:11px;font-weight:800;letter-spacing:.04em;padding:4px 9px;border-radius:6px;white-space:nowrap;border:1px solid transparent}
.p-critique{background:var(--red);color:#fff}
.p-important{background:var(--violet-bg);color:var(--violet);border-color:var(--violet)}
.p-surveiller{border-color:var(--line);color:var(--muted)}
.chip-intent{background:var(--red-bg);color:var(--red-text)}
.chip-level{border-color:var(--line);color:var(--ink)}
.st-confirmed{background:var(--violet-bg);color:var(--violet)}
.st-indicative{border-color:var(--line);color:var(--muted);border-style:dashed}
.card-flag{align-self:flex-start;font-size:10.5px;font-weight:800;letter-spacing:.13em;text-transform:uppercase;padding:3px 0;border-bottom:2px solid currentColor}
.flag-case{color:var(--red-text)}.flag-outside{color:var(--violet)}
.signal-card h3{font-size:22px}
.timing-line{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font-size:12.5px;color:var(--muted)}
.timing-badge{font-size:10.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;padding:3px 8px;border-radius:5px;background:var(--soft);color:var(--ink)}
.signal-fact{font-size:15px;line-height:1.7}
.verdict{font-size:14.5px;line-height:1.7;color:var(--muted)}
.verdict strong{color:var(--ink);margin-right:6px}
.implication{background:var(--soft);border-radius:12px;padding:14px 16px}
.implication span{display:block;font-size:10.5px;font-weight:800;letter-spacing:.11em;text-transform:uppercase;color:var(--red-text);margin-bottom:6px}
.implication p{font-size:14.5px;line-height:1.7}
.card-bottom{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px 14px;padding-top:4px}
.roadmap{font-size:12px;font-weight:700;color:var(--violet)}
.source-link{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:700;text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:4px}
.source-link:hover{color:var(--red-text);text-decoration-color:currentColor}
.card-details{border-top:1px solid var(--line);margin:0 -26px;padding:0 26px}
.card-details summary{list-style:none;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:14px 0;font-size:13px;font-weight:800;cursor:pointer}
.card-details summary::-webkit-details-marker{display:none}
.plus{font-size:18px;line-height:1;transition:transform .2s}
details[open]>summary .plus{transform:rotate(45deg)}
.details-body{display:grid;gap:12px;padding-bottom:20px;font-size:14px;line-height:1.75}
.details-body h4{font-size:14.5px;margin-bottom:4px}
.details-note,.details-date{font-size:12.5px;color:var(--muted)}
.case-details summary{color:var(--red-text)}
.source-list{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.source-list li{display:grid;gap:2px;min-width:0}
.source-list a{font-weight:700;text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px;overflow-wrap:anywhere;display:inline}
.source-list a svg{margin-left:5px;vertical-align:-2px}
.source-list li>span{font-size:12.5px;color:var(--muted)}
.outside-card{background:var(--outside-bg);border-color:var(--outside-line)}
.outside-card .implication{background:color-mix(in srgb,var(--violet-bg) 70%,transparent)}
.outside-card .card-details{border-color:var(--outside-line)}
.case-card{border-color:color-mix(in srgb,var(--red) 45%,var(--line))}
.empty-state{border:1px dashed var(--line);border-radius:var(--radius);padding:36px;text-align:center;display:grid;gap:8px;justify-items:center}
.empty-state p{color:var(--muted)}
.facets-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.facet{border:1px solid var(--line);border-radius:var(--radius);padding:24px 26px;display:flex;flex-direction:column;gap:12px;min-width:0}
.facet:first-child{background:var(--feature-bg);color:var(--feature-ink);border-color:var(--feature-line)}
.facet:first-child .facet-kicker,.facet:first-child .facet-links span{color:var(--feature-muted)}
.facet:first-child .facet-links a{border-color:var(--feature-line)}
.facet-kicker{display:flex;justify-content:space-between;font-size:11px;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}
.facet-kicker span:last-child{color:var(--red)}
.facet>p:not(.facet-kicker){font-size:15px;line-height:1.75}
.facet-links{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto;padding-top:10px}
.agenda{display:grid;gap:26px}
.agenda-month h3{font-family:var(--display);text-transform:uppercase;font-weight:700;font-size:22px;letter-spacing:.01em;color:var(--violet);margin-bottom:8px}
.agenda-month ol{list-style:none;margin:0;padding:0;border-left:2px solid var(--line);display:grid}
.agenda-item{display:grid;grid-template-columns:150px minmax(0,1fr) auto;gap:6px 22px;padding:16px 0 16px 22px;border-bottom:1px solid var(--line);position:relative}
.agenda-item::before{content:"";position:absolute;left:-7px;top:22px;width:12px;height:12px;border-radius:50%;background:var(--paper);border:2px solid var(--red)}
.agenda-date{font-weight:800;font-size:15px;font-variant-numeric:tabular-nums}
.agenda-body h4{font-size:16.5px;letter-spacing:-.02em;margin-bottom:4px}
.agenda-body p{font-size:14.5px;color:var(--muted);line-height:1.65}
.agenda-body .agenda-note{font-size:12.5px;font-style:italic;margin-top:4px}
.agenda-meta{display:flex;flex-direction:column;align-items:flex-end;gap:6px;min-width:0}
.agenda-axis{font-size:11.5px;font-weight:700;color:var(--muted);white-space:nowrap}
.actions-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.action-card{display:flex;gap:16px;border:1px solid var(--line);border-radius:var(--radius);padding:24px;background:var(--surface);min-width:0}
.action-card>div{display:grid;gap:9px;min-width:0;align-content:start}
.action-number{font-family:var(--display);font-size:34px;font-weight:700;line-height:1;color:var(--red)}
.action-horizon{font-size:10.5px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--red-text)}
.action-card h3{font-size:19px}
.action-owner{font-size:13px;font-weight:700;color:var(--violet)}
.action-card p{font-size:14px;line-height:1.65}
.action-card strong{display:block;font-size:12px;letter-spacing:.04em;margin-bottom:2px}
.action-link{font-size:12.5px;font-weight:700;color:var(--muted);text-underline-offset:3px}
.fine-print{font-size:12.5px;color:var(--muted);margin-top:14px}
.coverage-box{margin-top:44px}
.coverage-box details{border-block:1px solid var(--line)}
.coverage-box summary{list-style:none;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:18px 0;font-weight:800;cursor:pointer}
.coverage-box summary::-webkit-details-marker{display:none}
.coverage-box details>p{color:var(--muted);font-size:14.5px;max-width:62em;margin-bottom:14px}
.coverage-box ul{list-style:none;margin:0 0 20px;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:10px 26px}
.coverage-box li{display:grid;gap:2px;font-size:14px;min-width:0}
.coverage-box li span{color:var(--muted)}
.edition-foot{font-size:12.5px;color:var(--muted);padding-block:22px 64px}
.page-intro{padding-block:52px 34px;max-width:1248px}
.page-intro h1{font-size:clamp(42px,6vw,76px);margin-bottom:20px}
.page-intro p:last-child{font-size:17px;color:var(--muted);max-width:44em}
.axes-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.axis-card{border:1px solid var(--line);border-radius:var(--radius);padding:22px;background:var(--surface);display:flex;flex-direction:column;gap:10px;min-width:0}
.axis-number{font-family:var(--display);font-weight:700;font-size:30px;color:var(--violet);line-height:1}
.axis-card h2{font-size:19px;letter-spacing:-.02em}
.axis-mission{font-size:12px;font-weight:800;color:var(--red-text)}
.axis-card>p{font-size:14px;line-height:1.65;color:var(--muted)}
.axis-card .axis-question{margin-top:auto;padding-top:12px;border-top:1px solid var(--line);color:var(--ink);font-weight:700;font-size:14px}
.axis-outside{background:var(--outside-bg);border-color:var(--outside-line)}
.editorial-note{padding-top:56px}
.editorial-note>h2{margin-bottom:18px}
.boundary-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.boundary-grid>div{border-top:2px solid var(--red);padding:16px 4px 4px;min-width:0}
.boundary-grid h3{font-size:18px;margin-bottom:6px}
.boundary-grid p{font-size:14.5px;color:var(--muted);line-height:1.7}
.method-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.method-card{border:1px solid var(--line);border-radius:var(--radius);padding:24px;background:var(--surface);display:grid;gap:10px;align-content:start;min-width:0}
.method-card>span{font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--red-text)}
.method-card h2{font-size:22px}
.method-card p{font-size:14.5px;color:var(--muted);line-height:1.7}
.levels{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.level{display:grid;gap:10px;align-content:start;border:1px solid var(--line);border-radius:14px;padding:18px}
.level .chip{justify-self:start}
.level p{font-size:14.5px;color:var(--muted)}
.method-bottom{padding-block:56px 64px;display:grid;gap:10px;max-width:900px;margin-left:0}
.method-bottom h2{font-size:22px;margin-top:14px}
.method-bottom p{color:var(--muted);font-size:15px}
.primary-sources{margin-top:4px}
.primary-sources>h2{margin-bottom:16px}
.primary-sources .source-list{border:1px solid var(--line);border-radius:var(--radius);padding:22px 24px;background:var(--surface)}
.sources-section{padding-block:56px 64px}
.source-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.source-card{border:1px solid var(--line);border-radius:var(--radius);padding:20px 22px;background:var(--surface);display:flex;flex-direction:column;gap:8px;min-width:0}
.source-top{display:flex;justify-content:space-between;gap:10px;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.source-card h3{font-size:18px}
.source-card p{font-size:14px;line-height:1.6}
.source-limit,.source-axes{color:var(--muted)}
.source-limit strong{color:var(--ink);margin-right:5px}
.source-visit{margin-top:auto;padding-top:8px;display:inline-flex;gap:6px;align-items:center;font-size:13px;font-weight:800;text-decoration:none;color:var(--red-text)}
.site-footer{border-top:1px solid var(--line);background:var(--soft);margin-top:24px}
.footer-inner{display:flex;flex-wrap:wrap;justify-content:space-between;gap:20px;padding-block:34px}
.footer-brand{font-weight:800;letter-spacing:.06em;font-size:14px}
.footer-inner p{color:var(--muted);font-size:14px;margin-top:4px}
.footer-links{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center}
.footer-links a{font-size:13.5px;font-weight:700;display:inline-flex;gap:6px;align-items:center;text-underline-offset:4px}
.footer-bottom{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 20px;padding-block:14px 26px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
@media (max-width:1080px){.axes-grid{grid-template-columns:repeat(2,1fr)}.actions-grid,.method-grid,.source-grid{grid-template-columns:repeat(2,1fr)}}
@media (max-width:860px){.hero-grid,.summary-box,.signals-grid,.facets-grid,.kpi-grid,.boundary-grid,.levels,.coverage-box ul{grid-template-columns:1fr}.hero-grid{gap:30px}.summary-box{gap:16px}.edition-strip{grid-template-columns:1fr 1fr;row-gap:16px}.edition-strip>div:nth-child(2){border-right:0}.edition-strip>div:nth-child(3){padding-left:0}.agenda-item{grid-template-columns:1fr}.agenda-meta{flex-direction:row;flex-wrap:wrap;align-items:center}}
@media (max-width:620px){.axes-grid,.actions-grid,.method-grid,.source-grid{grid-template-columns:1fr}.signal-card{padding:20px 18px 0}.card-details{margin:0 -18px;padding:0 18px}.summary-content{padding:22px 20px}.featured{padding:22px 20px}.edition-strip strong{font-size:26px}.org{display:none}.site-nav a{padding:10px 8px;font-size:13.5px}}
"""

JS = r"""
(function(){
  var views=['veille','axes','methode','sources'];
  function show(id){
    var target=document.getElementById(id);
    var view=views.indexOf(id)>-1?id:(target&&target.closest('.view')?target.closest('.view').id:'veille');
    views.forEach(function(v){var el=document.getElementById(v);if(el){el.hidden=(v!==view);}});
    document.querySelectorAll('.site-nav a').forEach(function(a){
      if(a.getAttribute('href')==='#'+view){a.setAttribute('aria-current','page');}else{a.removeAttribute('aria-current');}
    });
    if(target&&views.indexOf(id)===-1){
      var d=target.querySelector('details');
      requestAnimationFrame(function(){target.scrollIntoView({block:'start'});});
    }else{window.scrollTo(0,0);}
  }
  function route(){var h=(location.hash||'').replace('#','');show(h||'veille');}
  window.addEventListener('hashchange',route);
  route();
  document.querySelectorAll('[data-filter-scope]').forEach(function(scope){
    var buttons=scope.querySelectorAll('.filter-button');
    var items=scope.querySelectorAll('[data-axis]');
    var counter=scope.querySelector('[data-count]');
    var empty=scope.querySelector('.empty-state');
    var noun=scope.classList.contains('sources-section')?['source','sources']:['signal','signaux'];
    buttons.forEach(function(btn){
      btn.addEventListener('click',function(){
        var f=btn.getAttribute('data-filter');var n=0;
        buttons.forEach(function(b){var on=b===btn;b.classList.toggle('is-active',on);b.setAttribute('aria-pressed',on?'true':'false');});
        items.forEach(function(it){var ok=f==='all'||it.getAttribute('data-axis')===f;it.hidden=!ok;if(ok){n++;}});
        if(counter){counter.textContent=n+' '+(n>1?noun[1]:noun[0]);}
        if(empty){empty.hidden=n!==0;}
      });
    });
  });
})();
"""


def page():
    validate()
    minutes = reading_minutes()
    urls = {src["url"] for s in SIGNALS for src in s["sources"]} | {i["source"]["url"] for i in ED["agenda"]}
    nav = "".join(f'<a href="#{v}">{t(l)}</a>' for v, l in [("veille", "La veille"), ("axes", "Les 8 axes"), ("methode", "La méthode"), ("sources", "Sources")])
    header = f'''<header class="site-header"><div class="container header-inner"><a class="wordmark" href="#veille" aria-label="Veille Marque et Communication, édition courante"><span class="brand-dot" aria-hidden="true"></span><span>VEILLE<small>MARQUE &amp; COMMUNICATION</small></span></a><nav class="site-nav" aria-label="Navigation principale">{nav}</nav><span class="org">TBS Education</span></div></header>'''
    footer = f'''<footer class="site-footer"><div class="container"><div class="footer-inner"><div><p class="footer-brand">VEILLE MARQUE &amp; COMMUNICATION</p><p>{t(SITE["baseline"])}</p></div><div class="footer-links"><a href="#methode">Méthode et limites</a>{ext("https://nogues.app/veille-esr/", "La Veille Concurrents & ESR")}{ext("https://veilleiaweb.digital/", "La Veille IA & Web")}</div></div><div class="footer-bottom"><span>TBS Education · {t(SITE["team"])} · Prototype éditorial sourcé</span><span>Sans cookies de suivi · Sans mesure d’audience</span></div></div></footer>'''
    body = header + "<main>" + view_veille(minutes, len(urls)) + view_axes() + view_method() + view_sources() + "</main>" + footer
    head = (
        '<title>Veille Marque & Communication</title>\n'
        f'<meta name="description" content="{a(SITE["description"])}">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Oswald:wght@600;700&family=Playfair+Display:ital,wght@1,800&display=swap">\n'
        f'<style>{CSS}</style>\n'
    )
    return head + body + f"\n<script>{JS}</script>\n", minutes, len(urls)


if __name__ == "__main__":
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    content, minutes, nsources = page()
    # Version Claude (artifact) : contenu seul, le squelette HTML est ajouté à la publication.
    (out_dir / "artifact.html").write_text(content, encoding="utf-8")
    # Version nogues.app : document HTML complet, prêt à être servi sous /veille-cm/.
    full = (
        '<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        f'<link rel="canonical" href="{a(SITE["url"])}">\n'
        + content
    )
    head_end = full.index("<header class=\"site-header\">")
    full = full[:head_end] + "</head>\n<body>\n" + full[head_end:] + "</body>\n</html>\n"
    (out_dir / "index.html").write_text(full, encoding="utf-8")
    print(f"OK {out_dir} · {len(SIGNALS)} signaux · {len(ED['actions'])} suites · {len(ED['agenda'])} échéances · {nsources} sources · {minutes} min · {len(content)//1024} Ko")
