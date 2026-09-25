# parispartners.com — refonte 2026

Refonte complète du site Paris Partners Softwares. HTML/CSS/JS statique, sans
framework, sans dépendance à installer sur le serveur.

## Mise en ligne

Copiez à la racine du serveur web :

```
*.html   contact.php   assets/   robots.txt   sitemap.xml
```

Aucune base de données, aucun build côté serveur. Le seul composant dynamique
est `contact.php` (traitement du formulaire), qui tourne sur le PHP déjà présent
sur l'hébergement OVH. Les dossiers `_src-v3/` et `tools/` sont des sources de
travail — **ne les déployez pas**.

## Structure

```
index.html                            Accueil
offres.html                           Offres & services (5 offres, ancres #progiciel, #tma, …)
cas-clients.html                      Références filtrables
a-propos.html                         Société, méthodologie, modèle de delivery
blog.html                             Index de la veille IT
article-assistants-de-code.html       Article — sert de gabarit
contact.html                          Coordonnées, carte, formulaire
mentions-legales.html                 Légal + confidentialité + cookies
plan-du-site.html                     Plan du site

assets/css/style.css                  Feuille de style unique (design system complet)
assets/js/main.js                     Comportements (nav, filtre, formulaire)
assets/img/                           Logos clients, photos, marque

_src-v3/layout.html                   Gabarit commun : en-tête, pied de page, <head>
_src-v3/pages/*.html                  Contenu de chaque page
tools/build.py                        Assemble _src-v3/ → HTML à la racine
tools/check.py                        Vérifie liens, ancres, assets, accessibilité
```

## Modifier le site

**Contenu d'une page** → éditez `_src-v3/pages/<page>.html`, puis :

```bash
python tools/build.py
python tools/check.py
```

**En-tête, pied de page, navigation, balises `<head>`** → éditez
`_src-v3/layout.html` une seule fois, puis rebuild. C'est tout l'intérêt du
générateur : la navigation n'existe qu'en un seul endroit.

Pour ajouter une entrée au menu, éditez aussi `NAV_ITEMS` dans
`tools/build.py`.

Vous pouvez tout à fait éditer directement les `.html` de la racine — mais le
prochain `build.py` les écrasera.

`check.py` sort en code d'erreur non nul s'il trouve un problème : il peut être
branché sur une CI. Il vérifie les liens, les ancres, les assets, le texte
alternatif des images, l'association label/champ, la couverture du sitemap — et
signale toute **classe CSS utilisée dans le HTML sans règle correspondante**
dans `style.css`, un défaut qui passe autrement inaperçu (le navigateur ignore
la classe en silence).

## Formulaire de contact

`contact.php` reçoit le formulaire et l'envoie par e-mail à `CONTACT_TO`. Aucun
service tiers, aucun compte, aucune donnée qui sort du serveur.

À vérifier au déploiement, en haut du fichier :

| Constante | Valeur | Remarque |
| --- | --- | --- |
| `CONTACT_TO` | `contact@parispartners.com` | destinataire des demandes |
| `CONTACT_FROM` | `site@parispartners.com` | **doit exister ou être autorisée** sur le domaine, sinon OVH refuse l'envoi |
| `THROTTLE_SECONDS` | `30` | délai minimum entre deux envois par IP |

Comportement vérifié en local (PHP 8.3, serveur intégré) :

- `GET` → 405 ; corps vide ou JSON invalide → 400 ; champs manquants → 422 avec
  la liste des champs, que `main.js` re-signale dans le formulaire.
- Pot de miel rempli → 200 sans envoi, pour ne rien apprendre au robot.
- Le compteur anti-flood ne démarre qu'après un envoi **réussi** : un visiteur
  qui se trompe d'adresse puis corrige n'est pas bloqué 30 secondes.
- Injection d'en-tête : les `CRLF` sont neutralisés et le nom d'affichage est
  encodé en RFC 2047, donc un `Bcc:` glissé dans le champ « nom » ne produit
  aucun en-tête supplémentaire.
- JavaScript désactivé : le `<form action="contact.php">` fonctionne quand même
  et renvoie une page de confirmation HTML.

## Audit de contraste

`tools/audit-contrast.py` teste le contraste texte/fond sur chaque page
construite, **dans le navigateur** :

```bash
python tools/audit-contrast.py
python tools/audit-contrast.py --theme dark
```

Pourquoi le navigateur et pas la feuille de style : le fond réel d'un texte est
celui du premier ancêtre peint, après composition alpha. Une valeur qui passe
isolément échoue une fois posée sur un bandeau dont la couleur vient de trois
niveaux plus haut. Le script injecte un auditeur, laisse Chrome résoudre la
cascade, puis rapporte ce qui échoue réellement. Seuils WCAG 2.1 AA appliqués
par élément : 3:1 pour le grand texte (≥ 24 px, ou ≥ 18,66 px en gras), 4,5:1
sinon.

Le texte posé sur un dégradé ou une image n'a pas de couleur de fond unique :
ces éléments sont listés à part comme « à vérifier au pixel » plutôt que devinés.
Les dégradés du projet ont été vérifiés par calcul sur chacune de leurs bornes —
le pire cas pour du blanc opaque est **4,68:1** (l'extrémité rouge), qui passe.

État actuel : **0 échec** sur les deux thèmes, 963 éléments mesurés par thème.

### Ce que l'audit a trouvé

| Cause | Avant | Après |
| --- | --- | --- |
| `--ink-3` sur `--paper-2` — 16 occurrences (`.facts dt`) | 4,45:1 | **4,73:1** |
| `.brand__tag` blanc à 80 % sur le dégradé | 3,46:1 | **4,68:1** |
| `.nav__link` à `opacity: .82` sur le dégradé | 3,57:1 | **4,68:1** |
| `.ribbon dt` et `.ribbon dd small` blanc à 82 % | 3,57:1 | **4,68:1** |
| `.cta p` blanc à 90 % | 4,04:1 | **4,68:1** |
| `.tile--grad p` blanc à 92 % | 4,16:1 | **4,68:1** |
| bordure `.icon-btn` à 55 % (WCAG 1.4.11, 3:1) | 2,30:1 | **3,46:1** |

Deux enseignements :

- **Le blanc translucide sur un dégradé est un piège.** Six règles utilisaient
  `rgba(255,255,255,.8)` à `.92` : élégant sur l'indigo, insuffisant sur
  l'extrémité rouge. Tous ces textes sont désormais en blanc opaque, et le
  survol de la navigation est signalé par un soulignement plutôt que par
  l'opacité.
- **`.tile--plate` n'avait aucune couleur de fond de repli.** Son image est un
  `<img>` enfant et son voile un `::after` : si la planche ne se charge pas, il
  restait du texte blanc sur la couleur du bandeau. Elle retombe maintenant sur
  l'indigo profond. Même famille de défaut que le contour des cartes.

## Audit non textuel (SC 1.4.11)

`tools/audit-hover.py` mesure le contraste des **surfaces interactives** contre
le fond qui se trouve derrière elles — ce que l'audit de texte ne voit pas.

```bash
python tools/audit-hover.py
python tools/audit-hover.py --theme dark
```

C'est ainsi qu'un survol rouge sur un dégradé rouge→indigo a pu obtenir
**1,00:1** sans être détecté : l'étiquette blanche à l'intérieur du bouton
passait, elle, très confortablement.

Deux approches ont été écartées avant d'arriver à celle-ci. Une analyse
statique de la feuille de style ne sait pas sur quel fond un contrôle se pose
réellement : elle compare chaque remplissage à toutes les surfaces peintes du
fichier et produit 21 faux positifs. Et `:hover` ne peut pas être déclenché
dans un `--dump-dom`. Le script lit donc les règles `:hover` dans
`document.styleSheets`, les apparie aux éléments avec `el.matches()`, et résout
le vrai fond du parent — dégradés développés stop par stop, car c'est là que se
cachait le défaut.

### Ce que l'audit a corrigé

| Surface | Avant | Après |
| --- | --- | --- |
| `.btn--on-dark:hover` — remplissage rouge sur le dégradé du bloc d'appel | **1,00:1** | **3,91:1** (libellé 13,74:1) |
| `.tile--dark` sur `band--dark` — le même jeton que le bandeau, sur 7 tuiles | **1,00:1** | **1,63:1** (contour) + lavis de marque |
| `.tile--tint` — remplissage pâle sans arête, 4 tuiles | 1,10:1 | arête dégradée 4 px + filet 1 px |

Sur le survol du bloc d'appel, aucun remplissage sombre ne fonctionnait non
plus : l'indigo profond n'atteint que **1,82:1** contre l'extrémité indigo du
dégradé. Ce bandeau ne tolère que des remplissages clairs.

Trois traitements ont été essayés avant celui qui est en place :

| Traitement | Frontière | Libellé | Verdict |
| --- | --- | --- | --- |
| Remplissage rouge | 1,00:1 | 4,68:1 | échec — plus aucune frontière |
| Remplissage indigo profond | 1,82:1 | 16,45:1 | échec — collision avec l'indigo du dégradé |
| Blanc + libellé et anneau rouges | 4,68:1 | 4,68:1 | conforme, mais se lit comme une erreur de saisie |
| **Fond bleuté `--tint`, libellé `--ground`** | **3,91:1** | **13,74:1** | retenu |

Le troisième passait la mesure mais pas le regard : un anneau rouge autour d'un
bouton blanc ressemble à un champ invalide. Le survol retenu fait simplement
varier la surface — signal conventionnel d'un bouton — sans introduire de
couleur absente de la palette, et multiplie par trois le contraste du libellé.

Vérification finale : plus aucun survol n'introduit de rouge.

### Ce qui reste signalé, et pourquoi ce n'est pas un échec

Un élément reste listé : les pastilles d'ancrage du hero de `offres.html`
(`.pillnav a`, 1,42:1). Il porte **leur propre libellé visible ou leur propre glyphe**, et ce libellé ou
ce glyphe respecte les seuils de contraste. Le critère 1.4.11 porte sur
« l'information visuelle nécessaire à l'identification » du composant : quand
c'est le texte qui identifie le contrôle, sa bordure est décorative. Leurs
bordures ont été renforcées d'un cran par souci de finition, sans chercher les
3:1 qui alourdiraient inutilement des designs volontairement fins.

`.chip` et `.tag` ont été retirés du périmètre de l'outil : ce sont des textes
décorés, pas des composants d'interface.

## Points à traiter avant mise en ligne

1. **Mentions légales — deux décisions.** La page a été pré-remplie depuis
   l'annuaire des entreprises de l'État (SIREN 452925118) et le DNS, **pas**
   depuis un document officiel. Un commentaire dans
   `_src-v3/pages/mentions-legales.html` détaille chaque source. Deux points
   demandent votre arbitrage :

   - L'annuaire donne la dénomination sociale **« PARIS PARTNERS »** (nom
     commercial « Paris Partners Software »), pas « Paris Partners Softwares
     SAS ». Les mentions légales doivent porter la dénomination du Kbis.
   - L'annuaire situe le **siège social au 10 rue de Penthièvre, 75008 Paris**
     depuis le 27/09/2019, pas à Courbevoie. Les mentions légales doivent
     indiquer le siège ; Courbevoie reste l'adresse des bureaux sur la page
     Contact. À confirmer.

   Restent à compléter, introuvables en source ouverte : **capital social** et
   **directeur de la publication**.

   Le n° de TVA `FR45452925118` est *calculé* depuis le SIREN
   (clé = (12 + 3 × (SIREN mod 97)) mod 97) : valable seulement si la société
   est assujettie. L'hébergeur (OVH SAS) est *déduit* du DNS —
   `parispartners.com` → `213.186.33.16` / `cluster005.ovh.net`.

2. **Chiffres.** CA 4,2 M€ (2024), 50 collaborateurs, 32 projets, 19 clients :
   repris de l'ancien site. L'annuaire confirme la tranche d'effectif 50–99
   salariés. À rafraîchir si les chiffres 2025 sont disponibles.

3. **Google Fonts / Google Maps.** Ce sont les deux seules requêtes externes du
   site. Si vous préférez zéro dépendance tierce (et une page cookies encore
   plus simple), les polices peuvent être auto-hébergées et la carte remplacée
   par un lien.

4. **Provenance des logos clients — à valider.** Les cinq logos manquants ont
   été récupérés sur les sites officiels des clients concernés :

   | Client | Fichier | Source |
   | --- | --- | --- |
   | Cegid | `cegid.png` (500×204) | `cegid.com` — `cegid-logo-blue-rgb.png` |
   | Tessi | `tessi.svg` (306×92) | `tessi.eu` — SVG inline, variante `logo-tessi-blue` |
   | Sixaxe | `sixaxe.svg` (181×47) | `sixaxe.com` — `Logo_sixaxe_RVB.svg` |
   | Family Partners | `family-partners.png` (459×129) | `family-partners.fr` — logo bleu, version non recadrée |
   | Klassroom | `klassroom.svg` (154×15) | `klassroom.fr` — `klassroom-logow.svg`, **recoloré** |

   Deux réserves :

   - **Klassroom ne publie que la version blanche** de son logo institutionnel
     (utilisée sur pied de page sombre) : invisible sur nos tuiles claires. Les
     tracés officiels ont été conservés tels quels et seule la couleur d'encre a
     été passée en gris ardoise, ce qui reproduit exactement le rendu de la
     maquette. À remplacer si Klassroom fournit un fichier sombre natif.
   - **Family Partners** : l'identification repose sur le nom seul. Le logo
     retenu est celui du multi-family office parisien `family-partners.fr`
     (SIREN 911 366 326) et correspond au visuel de la maquette (bloc angulaire
     bleu marine + « FAMILY PARTNERS » sur deux lignes). À confirmer qu'il
     s'agit bien de ce client.

   D'une manière générale, l'affichage de logos clients suppose leur accord.
   Vérifiez que les autorisations couvrent bien ces cinq nouveaux.

5. **Photos des bureaux — à fournir.** Les deux photos de l'ancien site
   (`office.jpg`, `home.jpg`) montraient les anciens locaux du 130 rue de
   Normandie — la plaque « 130/132 Normandie » était même lisible sur l'une
   d'elles. Elles ont été **supprimées**. Les deux emplacements ont été
   remplacés par du contenu conçu pour l'occasion, qui se tient sans
   photographie :

   - page À propos, section « Qui nous sommes » → panneau *Carte d'identité* ;
   - section « Modèle de delivery » → schéma France ↔ Cambodge.

   Si vous souhaitez remettre des photos, il faut des vues du **56 boulevard de
   la Mission Marchande**. Ne pas réimporter les fichiers de l'ancien site :
   ils y sont toujours en ligne.

   L'image du hero (`hero-bg.jpg`) est conservée : c'est une vue générale du
   quartier de La Défense, mitoyen de Courbevoie, et non un cliché de vos
   locaux. Elle sert aussi d'`og:image` pour les aperçus de lien.

6. **Position du parcours en 4 étapes.** Le bloc « À votre service » (conseil →
   digitalisation → pilotage → tests & maintenance) est placé juste après le
   hero, comme sur la maquette. La méthodologie détaillée en six étapes reste
   sur la page À propos, vers laquelle le bloc renvoie.

## Une seule version

Le dépôt a porté trois designs complets en parallèle (v1 à la racine, v2 et
v3 dans leurs sous-dossiers). v3 a été retenu : c'est désormais le seul, et il
occupe la racine. v1 et v2 restent récupérables dans l'historique git, au
commit `4e11caf` :

```bash
git checkout 4e11caf -- v2 _src-v2     # récupérer v2
git show 4e11caf:index.html            # consulter un fichier de v1
```

Les sections qui suivent gardent le préfixe « v3 » : c'est le nom du parti
pris visuel, pas celui d'un dossier.

### v3 — imagerie générée

PPS ne dispose d'aucune photographie : les seules images de l'ancien site
montraient des locaux quittés depuis. Plutôt que d'acheter des banques d'images
ou de fabriquer un bureau, v3 utilise **six planches SVG générées** —
graphe de nœuds, traces de télémétrie, grille en perspective, flux, champ de
densité, et une composition large pour le hero — dessinées dans le dégradé de
marque sur fond indigo profond :

```bash
python tools/make-plates.py     # -> v3/assets/img/plates/*.svg
```

Le rendu est déterministe (générateur pseudo-aléatoire à graine fixe) : relancer
le script produit des fichiers identiques. Chaque planche pèse quelques kilo-octets
et se redimensionne sans perte.

Si de vraies photographies arrivent, la classe `.duotone` de
`v3/assets/css/style.css` applique le même traitement rouge/indigo, pour que
l'imagerie reste une famille visuelle unique. Les planches peuvent alors être
remplacées une à une.

### v3 — palette : trois rôles distincts

Le premier jet faisait du rouge de marque la couleur de travail : boutons,
étiquettes, liens, bords de cartes. Deux problèmes, mesurés :

1. **Collision sémantique.** 27 règles utilisaient `--red`, dont *à la fois*
   tout le mobilier de marque *et* les deux états d'erreur du formulaire. Un
   champ invalide avait exactement la couleur d'un bouton : le rouge ne voulait
   plus rien dire.
2. **Contresens.** Le rouge saturé signale l'alerte et la panne. C'est un choix
   contre-intuitif pour une société dont l'argument est précisément que vos
   applications ne tombent pas.

Corrigé en séparant trois rôles :

| Rôle | Valeur | Emploi | Contraste sur blanc |
| --- | --- | --- | --- |
| `--accent` | `#2f3f9e` indigo | boutons, étiquettes, liens, bords de cartes | **9,03:1** |
| `--emph` | `#dc2f2a` rouge de marque | emphase des titres, une tuile, le motif de carrés | 4,68:1 |
| `--danger` | `#c0231e` | erreurs de formulaire, et rien d'autre | 6,00:1 |

L'indigo est tout aussi présent dans le logo que le rouge, il porte la stabilité
plutôt que l'alerte, et il double le contraste (9,03:1 contre 4,68:1). Le rouge
reste dans le dégradé de la barre de navigation, du bandeau de chiffres et du
bloc d'appel — il n'a donc pas disparu, il a cessé d'être partout.

Exception assumée : sur les fonds indigo profond (hero, en-têtes de page), les
étiquettes restent en rouge clair `#ff8a80`. Un indigo clair y serait illisible.

### v3 — accent sur fond sombre : un vestige corrigé

Sur les bandeaux clairs, l'accent de travail était bien passé à l'indigo lors du
basculement de palette. Sur les bandeaux **sombres**, il était resté en rouge
clair `#ff8a80` — la même carte affichait donc un filet indigo sur fond clair et
un filet rouge sur fond sombre. C'était un vestige : `--accent` a changé, les
règles `.band--dark` non.

Six règles concernées : `.eyebrow--on-dark`, `.phero .eyebrow`,
`.tile--dark .tile__label`, `.band--dark .steps__n`, et les arêtes colorées de
`.ref` / `.post` / `.steps > li` / `.panel` sur fond sombre.

Toutes basculées vers un nouveau jeton `--accent-light: #9daaf3`. L'indigo de
travail lui-même est inutilisable là : `#2f3f9e` ne donne que **1,82:1** sur
`#141a4a`. `#9daaf3` donne **7,43:1** — et c'est déjà la borne indigo de
`--grad-light`, donc ce jeton nomme une couleur existante, il n'en ajoute pas.

`#ff8a80` ne subsiste qu'à trois endroits, tous liés à l'emphase : la première
borne de `--grad-light`, et les deux couleurs de repli du texte en dégradé.

Au passage, la grille de la procédure est passée de `minmax(15rem)` à
`minmax(19rem)` : avec six étapes, quatre colonnes laissaient un 4+2 et deux
cellules vides. À trois colonnes elle tombe en 3+3, puis 2+2+2, puis 6 — chaque
palier équilibré.

### v3 — emphase des titres : du rouge plat au dégradé

Les mots mis en emphase dans les titres portent désormais le dégradé de marque
au lieu d'un rouge plat. C'était la dernière grande surface de rouge plat de la
page, et un dégradé se lit comme une marque là où un aplat rouge se lit comme
une alerte — même raisonnement que pour la tuile et le survol du bloc d'appel.

**Uniquement sur les grands caractères.** Un dégradé étalé sur dix caractères de
11 px en capitales ne se lit pas comme un dégradé : il fait une bouillie. Les
petites étiquettes (`.eyebrow`, `.tile__label`, `.steps__n`) gardent donc leur
rouge clair plat, et le texte d'erreur garde `--danger` plat — c'est tout
l'intérêt de ce rôle.

**Deux dégradés, pas un.** Le dégradé de marque est inutilisable sur les fonds
indigo profond : mesuré sur `#141a4a`, son extrémité violette donne **2,30:1**
et son extrémité indigo **1,82:1** — les mots s'y noieraient. Un `--grad-light`
a donc été ajouté pour ces fonds (rouge clair → mauve → indigo clair), dont
chaque borne dépasse 7:1.

| | Bornes | Pire point |
| --- | --- | --- |
| Fonds clairs — `--grad` | 4,68 · 7,15 · 9,03 | **4,68:1** (identique au rouge plat qu'il remplace) |
| Fonds sombres — `--grad-light` | 7,21 · 7,73 · 7,43 | **7,21:1** |

**Garde-fou.** `color: transparent` sans `background-clip: text` fait purement
disparaître le texte. La règle est donc sous `@supports`, la couleur plate
restant la déclaration de base — c'est exactement le défaut « compter sur autre
chose pour produire le résultat visible » qui avait déjà touché les cartes, les
tuiles à planche et les libellés translucides.

À noter : un auditeur automatique ne voit ici que `transparent`. Les contrastes
ci-dessus ont donc été calculés borne par borne, pas mesurés sur le rendu.

### v3 — sens du dégradé : conservé, et harmonisé

Question posée : faut-il inverser le dégradé de la barre de navigation ?
**Non**, pour deux raisons non esthétiques.

D'abord la mesure. Le bouton blanc « Prendre rendez-vous » est à l'extrémité
**droite** de la barre. Sur l'indigo il obtient une frontière de **9,03:1** ;
sur le rouge, **4,68:1**. Inverser diviserait par deux la séparation du contrôle
le plus important de la page, et placerait la couleur la plus forte derrière
lui. L'arbitrage inverse — le logo passerait de 4,68:1 à 9,03:1 — ne compense
pas : le logo est identifié par sa forme et sa position, pas par sa frontière.

Ensuite la marque. Le symbole PPS est un **triangle rouge en haut à gauche** et
un **triangle indigo en bas à droite**. L'ordre rouge → indigo est donc celui du
logo lui-même ; l'inverser mettrait la barre en contradiction avec la marque.

En revanche la question a révélé une **incohérence** : `.tile--grad` tournait
dans l'autre sens (indigo d'abord), orientation choisie pour que sa petite
étiquette tombe sur l'indigo. Cette raison a disparu quand tous ses textes sont
passés en blanc opaque (≥ 4,68:1 sur n'importe quelle borne). La tuile a donc
été remise dans le sens commun — rouge d'abord — en gardant un angle diagonal,
puisqu'il s'agit d'une carte et non d'un bandeau horizontal.

Toutes les surfaces de marque commencent désormais par le rouge.

### v3 — blocs décoratifs : le procédé abandonné

Le décor emprunté à Inetum comportait cinq aplats débordant des bords du
bandeau — trois en bleu pâle en haut à gauche des sections, deux en rouge sur le
bord droit. **Tous ont été supprimés**, en deux temps.

Les rouges d'abord : mesuré sur le rendu, l'aplat de la section Technologies
faisait 112 px de haut et venait mourir contre le bord droit du viewport, dans
une marge basse généreuse — environ **80 % du bloc tombait dans du vide** et il
ne faisait qu'effleurer l'angle du panneau.

J'ai alors conservé les trois bleu pâle en affirmant qu'ils « s'imbriquaient
avec la limite de section ». **C'était faux** : ils souffraient exactement du
même défaut, en plus discret. Ils ont été retirés à leur tour, ainsi que toute
la mécanique `.deco`.

Ce qui distingue ce procédé quand il fonctionne : chez Inetum les aplats sont
larges et **recouvrent franchement du contenu**, ils se lisent donc comme une
strate d'une composition. Posés en absolu dans la marge d'une section, sans rien
derrière ni par-dessus, ce ne sont que des rectangles égarés.

Le motif de petits carrés (`.squares`) est conservé, et la différence est
instructive : il ne se pose **jamais** dans du blanc. Il n'apparaît que sur la
planche du hero ou sur le dégradé du bloc d'appel, donc il a toujours un fond
réel et se lit comme un motif, pas comme une forme flottante.

### v3 — la tuile pleine : du rouge plat au dégradé

La mosaïque a besoin d'une tuile claire pour casser le rythme des tuiles
sombres — c'est le rôle que jouent les aplats jaunes chez Inetum. La version
initiale utilisait un aplat de rouge de marque. Deux défauts mesurés :

- l'étiquette de catégorie (11 px, capitales) donnait **3,79:1** sur le rouge
  plat : **échec AA** ;
- une fois le rouge ramené au rôle d'emphase, une carte entière en rouge
  redevenait la surface la plus forte de la page, et se lisait comme un panneau
  d'alerte plutôt que comme un accent de marque.

`.tile--red` est devenue `.tile--grad`, remplie du dégradé de marque **orienté
à 165°** pour que l'indigo se trouve derrière la petite étiquette (9:1) et le
rouge derrière le grand titre (4,68:1, largement suffisant à cette taille) :

```css
.tile--grad {
  background: linear-gradient(165deg, var(--indigo) 0%, var(--purple) 52%, var(--emph) 100%);
}
```

La tuile rejoint ainsi la famille de dégradés déjà portée par la barre de
navigation, le bandeau de chiffres et le bloc d'appel, au lieu d'introduire une
quatrième signification. Le contrôle des classes orphelines de `check.py` a
validé le renommage sur les quatre pages concernées.

### v3 — correctif de contour des cartes

`.ref`, `.post`, `.steps > li` et `.panel` sont des cartes blanches placées
tantôt sur blanc, tantôt sur gris, tantôt sur indigo. Comme elles ne comptaient
que sur le fond du bandeau parent pour se détacher, sur un bandeau blanc leur
corps disparaissait et il ne restait que l'arête colorée de 4 px — qui se lisait
comme une barre flottante, pas comme une carte. Dix-huit composants étaient
touchés sur trois pages. Elles portent désormais un contour de 1 px en plus de
l'arête, ce qui fonctionne sur les trois fonds.

### v3 — ce qui est repris d'Inetum, et ce qui ne l'est pas

Repris : barre de navigation en dégradé saturé, capitales, hero en pleine
largeur, mosaïque de tuiles inégales mêlant aplats de couleur et imagerie,
étiquette de catégorie en capitales au-dessus de chaque titre, blocs pleins
débordant des bords, motif de petits carrés, et le motif de lien
« EN SAVOIR PLUS → ».

**Non repris**, volontairement :

- Inetum place son `<h1>` **sous** une image pleine hauteur : au premier écran,
  la page ne dit rien. Ici la proposition est sur le hero.
- Inetum publie quatre `<h1>` et zéro `<section>`. v3 respecte un seul `<h1>`
  par page et des repères sémantiques réels.
- Inetum affiche du magenta sur jaune à 3,61:1. Chaque paire de v3 a été mesurée.
- Inetum n'a pas de balise `description` et son `<title>` est « French | Inetum ».

Les builds de prévisualisation s'obtiennent avec `--out _preview --noindex` ;
le build du site, lui, est indexable.

## Ce qui a changé par rapport à l'ancien site

- Suppression de jQuery, Bootstrap 3, wow.js, isotope, owl.carousel,
  smoothscroll, mousescroll et Font Awesome — remplacés par un CSS et un JS
  écrits pour le site (~2 requêtes au lieu de ~10).
- Suppression du script de tracking tiers `link-page.info`, chargé en `http://`
  depuis une page en HTTPS.
- Logo refait en SVG : net à toute taille, fonctionne sur fond clair et sombre
  (l'ancien était un PNG de 220 px avec un reflet incrusté).
- Thème clair/sombre, avec respect de la préférence système et bascule
  manuelle mémorisée.
- Respect de `prefers-reduced-motion` sur toutes les animations.
- Navigation clavier complète, lien d'évitement, landmarks ARIA, `aria-current`
  sur la page active, filtre accessible via `aria-pressed`.
- Contenu technique dépoussiéré : Symfony 2 → Symfony, AngularJS → React/Vue,
  ajout de TypeScript, Docker, Playwright ; corrections de « SQ Server » →
  SQL Server, « PostreSQL » → PostgreSQL, balise `<abb>` → `<abbr>`.
- Correction du filtre des références : l'entrée NEOFI portait la classe
  `conception` au lieu de `concept` et n'apparaissait donc dans aucun filtre.
- Suppression du `<div style="height:750px">` vide en haut de la page Contact.
- Le pied de page affichait `©2026PPS` ; l'année est maintenant calculée.
