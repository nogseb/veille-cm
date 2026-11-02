# Veille Marque & Communication — TBS Education

Veille hebdomadaire du pôle Communication & Marque de la Direction Marketing, Communication & Développement de TBS Education. Destination : **https://nogues.app/veille-cm/**.

Elle reprend la méthode de la [Veille Concurrents & ESR](https://nogues.app/veille-esr/) et la grille de criticité de la [Veille IA & Web](https://veilleiaweb.digital/), adaptées aux sept missions du pôle.

## Périmètre

Huit axes calés sur les missions du pôle : 01 Marque & corporate, 02 Éditorial & contenus, 03 Influence, RP & social media, 04 Programmes & business communication, 05 Événements & expérience de marque, 06 International, communautés & engagement, 07 Pilotage, IA & transformation, 08 Hors champ.

Exclus : positionnement et go-to-market des programmes (pôle Marketing de l'offre) ; SEO/GEO, paid, social ads, site web, CRM, automation et data de performance (pôle Growth, Digital & Data) ; offre, admissions et marché ESR (Veille Concurrents & ESR) ; suivi des mentions de TBS Education.

## Interface

Bento « studio », clair par défaut avec mode sombre (préférence système, bascule mémorisée localement). Parenté avec les deux autres veilles : point rouge #FF3E52, titrage Oswald Bold + Playfair Display ExtraBold Italic, corps en Manrope, grammaire éditoriale commune (statuts, « Notre lecture », trois suites au plus, quatre regards). Signature propre : le logo du point qui rayonne, le radar des huit axes, la frise des 90 jours, le cas d'école, le pas de côté et le mot de la semaine.

Pages : la veille (accueil), les axes, la méthode, les sources, les archives, une page permanente par édition, une page 404. Tout le contenu est dans le HTML initial ; JavaScript ne sert qu'aux filtres, aux onglets des quatre regards et au thème. Les animations vectorielles s'arrêtent si le système demande de réduire les mouvements.

## Structure

| Fichier | Rôle |
| --- | --- |
| `content/editions.json` | Paramètres, 8 axes, frontières, KPI du pôle, éditions (signaux, agenda à 90 jours, suites, mot de la semaine) |
| `content/sources.csv` | Corpus de surveillance, par famille et niveau (N1/N2) |
| `scripts/build.py` | Contrôles éditoriaux et génération du site ; `--preview FICHIER` produit un aperçu en page unique |
| `assets/` | Styles, script, favicon, image de partage, polices locales et leurs licences (SIL OFL) |
| `scripts/social.html` | Source de l'image de partage `assets/social.png` |
| `dist/` | Site compilé, à publier tel quel sous `/veille-cm/` |
| `prompt-manus.md` | Prompt de production hebdomadaire Manus.im (moins de 4 500 caractères) |
| `prompt-enrichissement-multi-ia.md` | Prompt commun et modules de focus pour faire contribuer ChatGPT, Perplexity, Gemini, Mistral et Claude, avec la grille de consolidation |

## Ajouter une édition

1. Ajouter un objet dans le tableau `editions` de `content/editions.json`, sur le modèle de l'édition S45. La plus récente devient l'accueil ; les précédentes passent en archives avec leur page permanente.
2. Lancer `python3 scripts/build.py`.
3. Relire, puis committer `content/` et `dist/` ensemble.

Le script refuse une fenêtre de plus de 7 jours, une actualité (`week`) hors fenêtre ou un contexte (`context`) daté dans la fenêtre, plus de 12 signaux ou de 3 suites, une édition sans regard hors champ, un renvoi vers un signal inconnu, une échéance hors de l'horizon de 90 jours ou sans statut Confirmé / Indicatif, et toute source non HTTPS. Le workflow `Contrôle éditorial` rejoue ces contrôles à chaque push.

## Publication sur nogues.app

nogues.app est servi par Apache sur OVHcloud, pas par GitHub Pages. Le dépôt `nogseb/nogues.app` publie son dossier `site/` en SFTP via son workflow existant.

1. Copier le contenu de `dist/` (fichiers cachés compris : `.htaccess`) dans `site/veille-cm/` du dépôt `nogseb/nogues.app`.
2. Pousser sur la branche de publication de ce dépôt ; son workflow transfère les fichiers.
3. Vérifier https://nogues.app/veille-cm/, une page secondaire et une adresse inexistante (404).

Un push dans `nogseb/veille-cm` seul ne met pas le site en ligne. Ne jamais copier `.git`, les sources ou des secrets dans le dossier publié.

## Principes éditoriaux

Publier peu, sourcer tout, distinguer le fait, notre lecture et la suite possible. Aucune performance, aucun budget ni aucun résultat n'est déduit d'un dispositif observé. Les textes réglementaires sont résumés pour la communication et se valident avec le juridique. Les suites sont des propositions à arbitrer par la responsable du pôle. Le site ne dépose aucun cookie de suivi et ne charge aucun outil de mesure d'audience ni aucune ressource tierce.
