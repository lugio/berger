# Installer le Master, pas à pas (spec courte)

Date : 2026-10-15 · Sujet : `installer-master` · Règle de go : aucune (documentation et test seulement, ni code de `bin/`,
ni droits, ni production).

## Constat
Le README décrit ce qu'est le Master (« Master : le gardien de Berger ») mais pas comment le mettre en place sur une
installation neuve. Le propriétaire débutant doit deviner l'ordre des gestes, et surtout qu'un agent ne règle jamais ses
propres murs : `agent.conf` de Master est réglé à la main par le propriétaire.

## Comportement
Une sous-section du README « Installer le Master, pas à pas », en six étapes, commandes à copier-coller :
1. forge locale `~/projets/berger.git` (`git clone --bare`, refspec `forge/*`) et clone du chef `~/projets/berger` ;
2. blocs `[equipes.berger]` et `[outils.berger-admin]` de `config.exemple.toml` recopiés dans `config.toml` (à la main) ;
3. `berger nouveau master "Master"` (SOUL tiré de `commun/modeles/SOUL-master.md`) ;
4. `agents/master/agent.conf` réglé à la main : `moteur = claude`, mur strict (défaut), `superviseur = oui`,
   `skills = berger`, `outils = berger-admin` ;
5. `berger regenerer` puis `berger espace master` ;
6. vérifications : `berger-outil berger-admin etat` répond depuis Master ; `.claude/skills/berger` pointe vers
   `commun/skills/berger` ; aucune ligne `⚠` de `regenerer` pour master.
`config.exemple.toml` : les blocs commentés portent exactement ce que la section cite, et la commande d'extraction du
README les rend lisibles en TOML.

## Refus
Rien de nouveau : la section répète les refus existants (le Master ne se règle pas lui-même, jamais de `mur = ouvert`).

## Tests (`tests/installer-master.py`, dans `tests/suites.sh`)
- la commande d'extraction citée par la section, jouée sur `config.exemple.toml`, donne du TOML qui se lit ;
- il porte `chef_projet`, `coordinateur`, `fusion_par`, `installer_outil`, `verify`, `tests`, `pret`, et chaque verbe
  (lecture et actions) de `berger-admin` cité par la section ; `installer_outil` désigne une action déclarée ;
- chaque `berger <commande>` cité dans la section existe dans `bin/berger` ; chaque `berger-outil berger-admin <verbe>`
  cité est un verbe déclaré ;
- les réglages d'`agent.conf` cités sont des clés connues de `bin/berger`.
