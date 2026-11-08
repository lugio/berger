# Interface web v2 : finition de l'interface (lisibilité, composants partagés, parcours) — spec courte (05/11/2026)

Hors go : présentation seulement, aucun pouvoir nouveau ni changement de session. Les actions restent celles du lot 2
(go n° 140), avec ses garde-fous inchangés. Demande du propriétaire du 05/11, à partir de la QA au navigateur du même jour
(lots 1 et 2 installés, 5c1d242 ; rapport et 43 captures). Ce lot passe AVANT le lot 3 (dialogue avec les agents), qui
réutilisera ses composants.

## Constat (mesuré au navigateur : 1440 sombre, 1440 clair, 390)

1. Dans « Document à lire », les listes Markdown deviennent des pastilles saumon en gras de 12 px, au contraste de 2,3:1.
2. Le code en ligne est invisible en thème clair (contraste de 1,1:1).
3. Les métadonnées d'un document occupent 4 grands cadres : le texte commence à mi-hauteur, et à un écran plus bas sur mobile.
4. Sur mobile, le titre de la fenêtre se coupe au milieu d'un mot (« Docume / nt »), et le sous-titre est tronqué.
5. La fenêtre fait 680 px de large sur un écran de 1440 : c'est trop étroit pour un texte long.
6. Échap, le piège du focus et le retour du focus ne sont pas vérifiés.
7. L'Accueil a des boutons incohérents (plein, lien), et la carte d'une décision n'a ni Valider ni Refuser.
8. Dans la fiche d'agent et les Coulisses, chaque valeur simple est dans son propre grand cadre, d'où des pages très longues.
9. Des libellés techniques restent visibles : « a_decider », « Genre », « Quoi ».
10. Dans le Tableau, les cartes sont denses, tout est au même poids, et l'action attendue ne ressort pas.
11. `app.css` contient 17 couleurs en dur, hors des jetons.

## Comportement

### 1. Jetons CSS, et eux seuls

- Sur `:root`, en thème clair et en thème sombre (préférence du système, puis choix mémorisé) :
  - les couleurs : fond, surface, texte, texte doux, accent, états (fond et texte), ligne ;
  - les espacements, sur une échelle de 4 px ;
  - les tailles de texte, les rayons, les ombres et la durée des transitions.
- Aucune couleur en dur hors du bloc des jetons : c'est contrôlé par un test. L'état se montre par un fond teinté ou un
  badge, jamais par une bordure colorée à gauche.
- Contraste AA dans les deux thèmes : 4,5:1 pour le texte et le code en ligne, 3:1 pour les gros textes, les icônes et les
  bordures de champ.

### 2. Échelle de texte

- Le corps est en 15 px, un document en 16 px. Rien sous 12 px, et seuls les badges et les dates descendent à 12 px.
- Interligne de 1,5. Longueur de ligne de 75 caractères au plus en lecture.
- Les titres se coupent entre les mots (`overflow-wrap: anywhere` seulement pour les SHA et les chemins), jamais au milieu
  d'un mot.

### 3. Composants partagés (une définition, réutilisée partout)

Carte, Fenêtre, Bouton, Badge d'état, Liste clé/valeur, Tableau, Markdown, État vide, Chargement :
- **Fenêtre** : un en-tête (titre et une ligne de métadonnées « auteur · date · lu »), un corps, et un pied d'actions collé
  en bas.
  - Largeur de 820 px sur bureau, plein écran sur mobile.
  - Échap ferme la fenêtre ; le focus reste piégé dedans tant qu'elle est ouverte, puis revient à l'élément qui l'a ouverte.
- **Bouton** :
  - quatre genres (primaire, secondaire, danger, lien), et un seul primaire par zone ;
  - au moins 40 px de haut, 44 px sur mobile.
- **Markdown** :
  - des listes à puces normales, à la taille du texte ;
  - du code en ligne et en bloc lisible dans les deux thèmes ;
  - des tableaux qui défilent dans leur cadre, jamais la page.
- **Liste clé/valeur** : une grille compacte, en deux colonnes sur bureau et une sur mobile. Elle remplace les cadres d'une
  seule valeur (points 3 et 8).
- **Libellés humains** : « À décider », « Type », « Objet ». Aucune clé interne n'est affichée.

### 4. Parcours d'une décision en 2 clics au plus

- Depuis « À toi de décider », un clic ouvre la fenêtre de la décision. Cette fenêtre EST l'aperçu du lot 2 : elle montre le
  numéro, l'aperçu exact et l'empreinte, et elle porte le jeton.
- Dans le pied de la fenêtre :
  - **Valider** est le 2e clic ;
  - **Refuser** ouvre le champ du motif, puis se confirme.
- Rien ne change côté serveur : ce sont les mêmes appels `/api/action/apercu` et `/api/action`, avec le même journal et
  le même débit.
- Après l'action :
  - une confirmation courte s'affiche (« n° 160 validée ») ;
  - l'élément traité disparaît de la liste ;
  - le défilement reste au même endroit.
- Le même composant d'action sert sur toutes les cartes : Répondre, Voir et Valider sont trois Boutons, d'un genre fixe.

### 5. Fluidité

- Aucun saut de mise en page au rafraîchissement : la place est réservée, et une liste est remplacée sans être vidée d'abord.
- Les transitions durent 150 ms au plus, et rien ne bouge si le système demande `prefers-reduced-motion`.
- Un état « chargement » visible après 300 ms.
- Le rafraîchissement ne ferme jamais une fenêtre ouverte et n'efface jamais un motif en cours de saisie.

### 6. Tableau

Pour chaque carte :
- l'action attendue en premier (badge et bouton) ;
- le reste en texte doux ;
- 3 lignes au plus avant « Voir ».

### 7. À lire (EN PRIORITÉ, constat du propriétaire sur un écran de 1920 : « À lire n'est pas lisible »)

- **Mise en page** :
  - au-delà de 1280 px : deux volets, la liste à gauche (360 px) et le document ouvert à droite ;
  - en dessous : une liste pleine largeur, puis la Fenêtre ;
  - plus de colonne de 1190 px avec un vide à droite.
- **Liste** :
  - un document non lu est en gras, avec un point d'état ;
  - un document lu est en poids normal, au contraste AA, jamais en gris pâle ;
  - la date et l'agent sont sur une ligne douce.
- **Document** :
  - un en-tête d'une seule ligne (« agent · date · lu »), puis le texte ;
  - 16 px, interligne de 1,6, 75 caractères par ligne au plus ;
  - titres et listes espacés : 1,5 em avant un titre, 0,5 em entre les éléments d'une liste.
- **Convention de fond**, rendue par la page : un document qui commence par « **En bref** : … » puis « **Pour toi** : … » les
  montre en tête, dans un encadré doux sans bordure gauche. La section `## Détail` (et ce qui suit) est **repliée par défaut**
  (`<details>`), et s'ouvre d'un clic.
  - Un document sans cette forme s'affiche tel quel.
  - L'onglet signale « forme ancienne » à l'agent auteur, jamais au propriétaire.
- **Tests** :
  - à 1920, deux volets sans vide à droite de plus de 10 % de la largeur ;
  - un document lu garde un contraste de 4,5:1 ;
  - le « Détail » est replié à l'ouverture, puis ouvert au clic ;
  - « En bref » et « Pour toi » sont rendus en tête.

## Refus et limites

- Aucun pouvoir nouveau : aucune action n'est ajoutée, et Valider, Refuser et Répondre gardent leurs garde-fous.
- Aucune dépendance nouvelle (ni cadriciel ni police téléchargée), et le premier chargement reste sous 400 Kio.
- Hors de ce lot : le dialogue avec les agents (lot 3), les réglages et les nouvelles vues.

## Tests

Les tests MESURENT au navigateur réel (Playwright, `tests/_page_navigateur.js`) aux 4 largeurs (1920, 1440, 820, 390) et dans les 2
thèmes. On ne se contente pas de captures :
- **Contraste** calculé sur chaque nœud de texte visible, y compris le code en ligne, les listes, les badges et les boutons :
  4,5:1 au moins (3:1 pour les gros textes). Le pire cas est cité en cas d'échec.
- **Tailles** :
  - aucun texte calculé sous 12 px ;
  - le corps fait 15 px ou plus, un document 16 px ;
  - une cible tactile fait 44 px ou plus sur mobile.
- **Débordement** : aucune largeur de défilement horizontal sur la page ni dans une fenêtre. Un titre n'est jamais coupé au
  milieu d'un mot, ce qu'on contrôle sur le titre « Document à lire » à 390 px.
- **Clavier** :
  - Échap ferme la fenêtre ;
  - Tab reste dans la fenêtre ;
  - à la fermeture, le focus revient à la carte d'origine.
- **Parcours** : une décision d'essai se valide en 2 clics depuis l'Accueil, disparaît, et la confirmation s'affiche.
  Refuser sans motif est impossible.
- **Fluidité** :
  - un rafraîchissement forcé, fenêtre ouverte et motif saisi, ne ferme pas la fenêtre et garde le motif ;
  - aucun déplacement de la mise en page de plus de 0,1 (CLS) au rafraîchissement.
- **Sans navigateur** : un test lit `app.css` et refuse toute couleur hors du bloc des jetons, et toute bordure gauche colorée.
- **Playwright absent** : la partie navigateur est « non mesuré », jamais « vert ». Le chef de projet la joue sur la machine
  du propriétaire avant de demander la fusion, et joint le résultat chiffré.

Doc : le manuel (interface) et `changelog.d/interface-finition-ui.md`. Relecture Codex avec la demande.
