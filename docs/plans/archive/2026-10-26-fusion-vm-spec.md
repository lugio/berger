# Fusion de la ligne de l'installation avec la ligne de développement (spec)

Règle de go : cas 1 (courtier, gardes, droits, règles de validation). Go du propriétaire à inscrire sur CE fichier avant l'ouverture.
Rien de propre à un moteur.

## Constat

Deux lignes partent du même commit `d6eb28e` (14/10) :
- **ligne de développement** (`dev/main`, a195814) : 153 commits après d6eb28e. On y trouve le transport privé des arguments (`--stdin`,
  socket, aucun texte dans la ligne de commande), MCP, accès web, espace auto, modèles de SOUL, neutralité du dépôt (verifier-depot,
  contrôle sans-marques) et la CI. Son arbre est identique au dépôt public.
- **ligne de l'installation** (`vm/2026-10-16`, db14325) : 54 commits après d6eb28e, en service depuis le 16/10. On y trouve
  l'anti-boucle, la règle de go (`equipe go`, `go_mots`, hors-go), les textes du courtier refusés au lieu d'être coupés, le redémarrage
  du courtier avec fermeture, `besoin`, l'annonce d'un changement d'outil, la vue Documents, « À lire » qui se vide, le temps réel
  et le verbe `prod` générique.

Ni la publication ni la synchronisation ne passent : aucune des deux lignes ne contient l'autre.

**Cause racine.** Les deux lignes ont avancé en même temps, chacune dans son propre dépôt, et aucune n'a été reportée dans l'autre.

## Comportement

- Branche `berger/fusion-vm` = **une vraie fusion** (`git merge`) de `dev/main` et de db14325 (plus cette spec). Pas de rebase, pas de
  cherry-pick, aucune réécriture : les deux historiques sont gardés.
- Dans les conflits, il faut garder **les deux comportements**. Quand ils se contredisent, on garde :
  1. le transport privé de la ligne de développement : aucun texte d'agent dans les arguments d'un processus. Les verbes venus de
     l'installation (`equipe go`, `besoin`, `prod`…) passent par ce transport ;
  2. la neutralité : `verifier-depot` et le contrôle sans-marques restent verts (aucun nom de projet, de personne ni d'éditeur réel) ;
  3. la CI de la ligne de développement, qui reste verte ;
  4. sinon, le comportement le plus prudent, avec le choix écrit.
- La coupure silencieuse d'un texte du courtier à 2 000 caractères doit avoir **disparu** de `courtier/courtier` : un texte trop long
  est refusé, jamais amputé.
- Ce qui est propre à une installation (notice d'un serveur donné, adresses, noms d'hôtes) reste hors du dépôt.

## Refus

Toute réécriture d'une des deux lignes. Tout comportement perdu sans être écrit. Tout test retiré pour faire passer la fusion.

## Tests

Les suites des **deux** lignes passent sur le commit de fusion :
- `tests/tout.sh` et la CI ;
- `courtier-textes`, `redemarrage-courtier`, `regle-go`, `anti-boucle`, `besoin`, `verbe-prod`, `alire-se-vide`, `annonce-outil`,
  `temps-reel`, adaptés au transport `--stdin` si besoin ;
- un contrôle que `courtier/courtier` ne coupe plus aucun texte.

Une suite qui ne peut pas tourner (moteur absent) est dite « non mesurée », jamais « verte ».

## Livrable

La liste des conflits (fichier, ce que chaque ligne apportait, la résolution choisie). Elle sert à la description de la demande de
fusion sur la ligne de développement.
