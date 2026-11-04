# Refonte de l'espace Berger : ce qui attend le propriétaire, d'abord et seulement lui (spec)

Hors règle de go : vues seulement (`bin/vues/`, leurs lectures dans `bin/noyau/lectures.py`, l'ordre des onglets). Aucun
changement du courtier, du mur, des secrets ni des validations. Demande du propriétaire, 30/10 (« tout de suite »).

## Constat (rendu des panneaux, 30/10 20:12)

1. Accueil et Décisions annoncent « À TOI DE DÉCIDER (39) » alors qu'AUCUNE validation n'attend le propriétaire : on y
   compte 26 lectures (la plupart déjà « réglées » dans À lire), 7 propositions, et les « go attendus » d'un développeur, qui
   attendent son chef de projet — tout avec le même triangle.
2. Accueil : le bloc des agents est sous la ligne de flottaison (« lignes 1–26 sur 42 ») ; l'Accueil est affiché deux fois dans
   son onglet.
3. États périmés : un « bloqué : fusion n° 101 » reste affiché après la décision sur la n° 101.
4. Lignes trop longues, chemins de fichiers (`a-lire/2026-…md`), jargon (porte pret, go n° …).
5. Checklists vide (onglet inutile) ; Documents répète À lire.
6. À GARDER : le Tableau en 5 colonnes avec ses cartes colorées ; À lire qui se coche seul « réglé » ; bandeaux et palette sobres.

## Comportement prévu

**Ce qui attend le propriétaire** (une seule définition, dans `lectures.py`, partagée par Accueil et Décisions) :
- les validations EN ATTENTE du courtier (chacune : son numéro, une phrase simple tirée de l'aperçu, et les deux commandes
  prêtes à copier `berger valider <n°>` / `berger refuser <n°>`) ;
- les lignes `❓ Question :` et `⚠ Go attendu :` écrites par un agent qui rend compte AU PROPRIÉTAIRE (coordinateur, agent
  hors équipe). Celles d'un développeur attendent son chef de projet : « attend un agent ».
- Une ligne qui cite une validation déjà décidée (« n° 101 » validée ou refusée) n'est plus affichée (état périmé).
- Les propositions (`pending/`) : un bloc à part, replié, sous le reste. Les lectures : seulement dans À lire, jamais comptées
  comme décisions ; une lecture réglée n'apparaît plus.

**Accueil** (un seul par onglet), sans défilement à 42 lignes :
1. en haut, en gros : « ✅ Rien à faire, tout avance » OU chaque élément qui attend le propriétaire (ci-dessus) ;
2. le Tableau, en version compacte (mêmes 5 colonnes) ;
3. les agents, une ligne chacun.

**Décisions** : « T'attend » (ce qui attend le propriétaire, ci-dessus), puis « Propositions » (replié), puis « Attend un
agent ».

**Documents et À lire** fusionnés en un seul onglet « À lire » (les documents non liés à une demande en bas, repliés).
**Checklists** : l'onglet n'est pas créé quand il n'y a aucune checklist ouverte.

**Phrases pour un patron** : pas de chemin de fichier, pas de jargon (« porte », « pret », « go n° »…) dans Accueil et
Décisions ; une ligne au plus par élément, coupée proprement ; le détail reste dans À lire.

## Tests (rouges d'abord)

- `tests/vues.py` (contrat des vues) gardé vert ; nouveaux cas : aucune validation en attente → « Rien à faire » ;
  une validation → ses deux commandes ; un « go attendu » d'un développeur → « attend un agent », pas « t'attend » ; une ligne
  qui cite une validation décidée → masquée ; lectures réglées absentes ; rendu de l'Accueil ≤ 42 lignes avec 7 agents ;
  aucun chemin `a-lire/` ni `.md` dans Accueil et Décisions ; onglet Checklists absent sans checklist ; un seul Accueil.
- Captures avant/après jointes à la demande (rendu texte des panneaux).

## Après l'installation

`berger refaire-espace berger` (validation du propriétaire).
