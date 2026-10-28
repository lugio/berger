# Branche de finition du chef de projet, et en-tête de journal avec un titre

Spec, 13/10/2026 (mission de master, lot 6 ; deux trous du processus de dév générique signalés le 13/10 par l'agent
sécurité). Complète `docs/plans/2026-10-12-processus-dev-generique-spec.md`.

## 1. Le chef de projet publie SA branche de finition

> **Corrigé le 13/10/2026** (`docs/plans/2026-10-13-chef-copie-spec.md`) : la branche n'est pas dans le dépôt du chef (en
> lecture seule pour lui) mais dans SA copie de travail ; le courtier l'importe dans le dépôt en avance rapide seule.

**Constat.** Le chef de projet finit parfois lui-même un sujet (exemple : un chef sur une branche de finition,
dans son dépôt). Son outil (`<projet>-chef`, type `equipe_chef`) n'avait aucun verbe pour pousser une branche : bloqué.

**Comportement.** Deux verbes de LECTURE (comme chez le développeur : « les portes décident ») dans `<projet>-chef`,
réservés au chef de projet déclaré (`chef_projet` de `[equipes.<projet>]`, comparé à l'agent de l'APPEL —
`ContexteDeLAppel`, jamais un attribut partagé) :
- `pousser <branche>` : `git push origin refs/heads/<b>:refs/heads/<b>` depuis le dépôt du chef — jamais de force (pas de
  `+`, pas de `--force` : un historique réécrit est refusé par git), hooks et fsmonitor désactivés (`ENV_GIT`, comme le
  `pousser` des développeurs et la fusion).
- `demander-fusion <branche> "<résumé>"` : les MÊMES contrôles que le développeur (`_portes.controler_demande`, partagé :
  pas de mécanisme parallèle) — résumé lisible, commits à fusionner, branche poussée telle quelle, à jour avec la branche
  principale, porte `pret` déclarée, règle du correctif ; dépôt propre si la branche y est extraite ; puis les 4 portes
  rejouées dans une copie JETABLE du courtier (`jouer_portes`, comme `rejouer`) ; demande inscrite par
  `_portes.inscrire_demande` (même fichier `demandes/<sujet>.json`, même panneau Échanges), avec l'agent appelant et
  `finition: true`. Sujet = la branche sans le préfixe de l'équipe.
- Ensuite le chemin habituel : `demandes`, `relire`, `rejouer`, `fusionner` (validée), `etiqueter`.

**Qui valide la fusion.** Le chef a écrit ET relu sa branche : personne d'autre ne l'a relue. Sa fusion est donc validée
par le **propriétaire seul** (`valideur` de l'outil → personne), quel que soit `fusion_par`. Plus largement, l'auteur
d'une demande n'en valide jamais la fusion (s'il est `valide_par`, le propriétaire décide).

**Refus.** Appelant autre que le chef de projet (un développeur, un autre agent) ; branche principale ; branche hors du
préfixe de l'équipe (`prefixe`, `equipe/` par défaut) ; nom hors motif `<prefixe>[A-Za-z0-9][A-Za-z0-9_-]{0,63}` (donc
pas de `..`, de tiret initial, d'espace, de `+`, d'option) ; arguments en trop ; branche absente du dépôt ; sujet déjà
pris par la demande d'une autre branche.

## 2. `entree_journal` : un titre après la date

**Constat.** `_portes.entree_journal` exigeait `## [x.y.z] - AAAA-MM-JJ` seul sur la ligne ; un projet écrit un titre après
la date (`## [3.480.2] - 2026-10-05 — *Titre*`) → `etiqueter` aurait refusé les versions de ce projet.

**Comportement.** Accepté : l'en-tête seul, ou suivi d'un espace puis d'un texte quelconque. Refusé : un texte AVANT
`##`, une date invalide (`2026-13-45`, `2026-10-5`), une version voisine (`[3.480.20]` ne vaut pas pour `3.480.2`), une
date collée à un texte (`2026-10-05x`).

## Tests

`tests/chef-finition.py` (branché dans `tests/suites.sh`) : le chef pousse et demande → la demande apparaît dans
`demandes` au nom du chef, portes vertes inscrites, `rejouer` conforme, fusion soumise au propriétaire seul (et
fusionnée une fois validée) ; refus listés ci-dessus ; push non en avance rapide refusé ; hook `pre-push` piégé (dans
`.git/hooks` et par `core.hooksPath`) jamais exécuté ; un développeur n'a pas ce verbe et l'outil du chef le refuse ;
`entree_journal` : les cas du § 2.
