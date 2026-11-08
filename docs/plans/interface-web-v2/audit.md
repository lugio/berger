# Interface web de Berger — audit visuel (03/11/2026)

Lancée en local (`berger interface servir`, 127.0.0.1:8765), regardée en 1440×900 et 390×844 (Playwright).
La maquette `maquette-accueil.html` (même dossier) fait foi : icônes SVG, menu repliable, 1440/820/390,
fenêtres de détail, aucune bordure colorée à gauche, aucun émoji. Les noms d'agents y sont fictifs.

## Ce qui marche
- Mêmes onglets que Herdr (Accueil, Décisions, Tableau, À lire, Coulisses) + Documents + une page par agent.
- Rapide : Accueil en ~2 s, changement d'onglet ~0,35 s ; temps réel (« mis à jour il y a 0 s »).
- Barre d'onglets en bas sur mobile, pastilles de compteurs.

## Défauts
1. « null » affiché en haut de l'Accueil (bug d'affichage).
2. Bordure colorée à GAUCHE sur les alertes (règle du propriétaire : jamais) ; cartes chiffres avec liseré coloré en haut.
3. Accueil beaucoup trop long : 5 500 px (28 « À lire » + tableaux de jetons en entier) → pas simple.
4. Textes bruts techniques partout (SHA de 40 caractères, phrases de 300 caractères copiées des validations).
5. Tableau : une carte de validation déborde de sa colonne (texte coupé).
6. Agents : état « ? » pour les agents fermés (moteur non connu quand l'agent est fermé) ; double icône (silhouette + émoji) ; noms coupés (« admission-a… »).
7. Mobile : la barre du bas coupe « Documents » ; cartes chiffres en 2 colonnes OK.
8. Poids : ~1 Mo transféré au 1er chargement (vue courtier 48 Ko demandée 2 fois).
9. Aucune action possible (lecture seule) : il faut toujours taper `berger valider N` ailleurs (lot 2).
