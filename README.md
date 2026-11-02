# Veille Marque & Communication — TBS Education

Veille hebdomadaire du pôle Communication & Marque de la Direction Marketing, Communication & Développement de TBS Education. Elle reprend la méthode de la [Veille Concurrents & ESR](https://nogues.app/veille-esr/) et la grille de criticité de la [Veille IA & Web](https://veilleiaweb.digital/), adaptées aux sept missions du pôle.

Destination proposée : **https://nogues.app/veille-cm/**.

## Périmètre

Huit axes calés sur les missions du pôle : 01 Marque & corporate, 02 Éditorial & contenus, 03 Influence, RP & social media, 04 Programmes & business communication, 05 Événements & expérience de marque, 06 International, communautés & engagement, 07 Pilotage, IA & transformation, 08 Hors champ.

Exclus : positionnement et go-to-market des programmes (pôle Marketing de l'offre) ; SEO/GEO, paid, social ads, site web, CRM, automation et data de performance (pôle Growth, Digital & Data) ; offre, admissions et marché ESR (Veille Concurrents & ESR) ; suivi des mentions de TBS Education.

## Structure

| Fichier | Rôle |
| --- | --- |
| `content/editions.json` | Paramètres, 8 axes, frontières, KPI du pôle, éditions (signaux, agenda à 90 jours, suites proposées) |
| `content/sources.csv` | Corpus de surveillance, par famille et niveau (N1/N2) |
| `scripts/render.py` | Contrôles éditoriaux et génération de la page |
| `dist/index.html` | Page autonome à publier sous `/veille-cm/` |
| `dist/artifact.html` | Même page, sans squelette HTML, pour la version partagée dans Claude |
| `prompt-manus.md` | Prompt de production hebdomadaire Manus.im (moins de 4 500 caractères) |

## Ajouter une édition

1. Ajouter un objet dans le tableau `editions` de `content/editions.json`, sur le modèle de l'édition pilote S45. La plus récente devient l'édition affichée.
2. Lancer `python3 scripts/render.py`.
3. Relire, puis committer `content/` et `dist/` ensemble.

Le script refuse :

- une fenêtre de collecte de plus de 7 jours ;
- une actualité (`week`) publiée hors fenêtre, ou un contexte (`context`) daté dans la fenêtre ;
- plus de 12 signaux ou plus de 3 suites ;
- une édition sans regard hors champ ;
- une suite ou un regard qui pointe vers un signal inconnu ;
- une échéance d'agenda hors de l'horizon de 90 jours, ou sans statut Confirmé / Indicatif ;
- une source qui n'est pas en HTTPS.

Le workflow `Contrôle éditorial` rejoue ces contrôles à chaque push et vérifie que `dist/` correspond aux données.

## Publication sur nogues.app

Même circuit que la Veille Concurrents & ESR : nogues.app est servi par OVHcloud, pas par GitHub Pages. Après validation, copier le contenu de `dist/index.html` dans `site/veille-cm/index.html` du dépôt `nogseb/nogues.app`, dont le workflow existant publie en SFTP. Un push dans ce dépôt seul ne met pas à jour le site.

## Principes éditoriaux

Publier peu, sourcer tout, distinguer le fait, notre lecture et la suite possible. Aucune performance, aucun budget ni aucun résultat n'est déduit d'un dispositif observé. Les textes réglementaires sont résumés pour la communication et se valident avec le juridique. Les suites sont des propositions à arbitrer par la responsable du pôle.

La page ne dépose aucun cookie de suivi et ne charge aucun outil de mesure d'audience. Polices : Manrope, Oswald et Playfair Display (Google Fonts, SIL Open Font License).
