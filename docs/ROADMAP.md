# Feuille de route de Berger

Ce qui est prévu, et l'état du chantier modulaire. Chaque point passe par le circuit habituel (spec, go du propriétaire si la règle de go
le demande, une demande de fusion par étape).

## Chantier modulaire — où il en est

Spec : `docs/plans/2026-10-27-modulaire-spec.md`. Le code de `bin/berger` est découpé en un noyau à API explicite
(`bin/noyau/`), des moteurs (`bin/moteurs/`), des commandes en familles (`bin/commandes/`) et des vues (`bin/vues/`).
- **Lots 1 à 3 bis : faits** (noyau et API, moteurs, commandes sans risque ; `bin/berger` passe de 6 089 à 4 242 lignes).
- **Lot 4 : en attente du go inscrit du propriétaire** (validation n° 58). Il touche le courtier, le mur, les identifiants et le
  coffre, donc la règle de go : rien n'y est codé, même en local, sans ce go. Il vide `bin/commandes/transition.py` (les verbes
  encore au cœur) et ramène `bin/berger` sous 250 lignes.

## Passage progressif de Python à Rust — APRÈS le lot 4 du chantier modulaire, pas avant

- **Pourquoi après** : un seul gros chantier à la fois ; le découpage en noyau / commandes / moteurs / vues à API explicite
  (`docs/plans/2026-10-27-modulaire-spec.md`) est ce qui rend possible un portage module par module.
- **Méthode** : une spec Rust d'abord (go du propriétaire) ; un module à la fois, chacun une demande de fusion ; les tests
  boîte noire existants (`bin/berger` lancé en sous-processus) prouvent l'équivalence, inchangés.
- **Ordre pressenti** : le courtier et le transport privé d'abord (sûreté, binaire unique, typage) ; le reste seulement si un
  gain réel est montré (Berger attend surtout les agents : la vitesse n'est pas le besoin).
- **À trancher dans la spec** : la liste des crates permises (aujourd'hui aucune dépendance hors de la bibliothèque standard),
  la chaîne Rust sur chaque installation (portable, serveurs), le coût des agents qui écrivent du Rust.
