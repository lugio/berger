# Feuille de route de Berger

Ce qui est prévu, et l'état du chantier modulaire. Chaque point passe par le circuit habituel (spec, go du propriétaire si la règle de go
le demande, une demande de fusion par étape).

## Fait, engagé, intentions, sujets ouverts (état au 01/11/2026)

**Fait**
- **Chantier modulaire, lots 1 à 4c** (spec : `docs/plans/2026-10-27-modulaire-spec.md`) : noyau à API explicite (`bin/noyau/`), moteurs
  (`bin/moteurs/`), familles de commandes (`bin/commandes/` : missions, messages, besoins, équipes) et vues (`bin/vues/`).
  `bin/berger` passe de 6 089 à 4 050 lignes ; entrées, sorties, refus et droits inchangés (tests d'équivalence).
- **Moteurs** : Codex de nouveau admis à côté de Claude Code, outils web intégrés fermés pour les agents stricts, listes fermées d'outils
  par moteur et par version (`tests/outils-connus/`), sous-agents de Codex prouvés isolés (condition 13 du contrat).
- **Espace Berger** : 11 onglets regroupés en 5, chaque alerte rouge visible.
- **Accès web des agents**, lots 1 et 1 bis ; portes de fusion allégées ; modèles par niveau et type de travail ; suites de tests en parallèle ;
  publication du commit installé.

**Engagé**
- **Version 0.3.0** : documentation du dépôt public (README, contribution, installation, plans archivés) avant la publication, qui reste un
  geste séparé du propriétaire.

**Intentions** (rien n'est commencé ; chacune passe par une spec et, si la règle de go le demande, le go du propriétaire)
- **Lot 4d du chantier modulaire** : courtier, mur, secrets et dépôt ; vider `bin/commandes/transition.py` et ramener `bin/berger` sous
  250 lignes. Il touche le cœur de l'installation : go explicite avant tout code.
- **Passage progressif de Python à Rust**, après le lot 4d (voir ci-dessous).
- **Accès web des agents, lot 2** : liste validée chaque semaine (autonomie).

**Sujets ouverts**
- Listes fermées pour chaque nouvelle version de Claude Code ou de Codex : sans elles l'admission échoue (voir CONTRIBUTING).
- Captures de l'espace Berger pour les cinq onglets : le générateur de démonstration n'en rend que trois.

## Passage progressif de Python à Rust — APRÈS le lot 4 du chantier modulaire, pas avant

- **Pourquoi après** : un seul gros chantier à la fois ; le découpage en noyau / commandes / moteurs / vues à API explicite
  (`docs/plans/2026-10-27-modulaire-spec.md`) est ce qui rend possible un portage module par module.
- **Méthode** : une spec Rust d'abord (go du propriétaire) ; un module à la fois, chacun une demande de fusion ; les tests
  boîte noire existants (`bin/berger` lancé en sous-processus) prouvent l'équivalence, inchangés.
- **Ordre pressenti** : le courtier et le transport privé d'abord (sûreté, binaire unique, typage) ; le reste seulement si un
  gain réel est montré (Berger attend surtout les agents : la vitesse n'est pas le besoin).
- **À trancher dans la spec** : la liste des crates permises (aujourd'hui, hors de la bibliothèque standard, seule la bibliothèque Python `cryptography` est utilisée, par l'accès web et ses tests),
  la chaîne Rust sur chaque installation (portable, serveurs), le coût des agents qui écrivent du Rust.
