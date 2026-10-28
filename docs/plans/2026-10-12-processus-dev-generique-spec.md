# Processus de développement générique — un seul circuit pour toutes les équipes

Spec, 13/10/2026 (mission de master). Vaut pour TOUT projet déclaré dans `[equipes.<projet>]` : rien n'est codé pour un
projet nommé ; ce qui change d'un projet à l'autre est un réglage (portes, coordinateur, `fusion_par`).

## Le circuit

```
(règle de go : spec + go du propriétaire avant le code dans 5 cas) spec → tests → code → doc → porte verify → porte tests → (porte gate) → finition → porte pret
     → demande de fusion (les 4 portes jouées, chaque résultat inscrit)
     → relecture du chef de projet (rejoue les portes, RECOMPTE l'annonce)
     → fusion validée (pret rejoué ; main avancée : mise à jour automatique sûre, portes rejouées)
     → étiquette de version + entrée de journal (versions publiées)
     → installation (recette : go du valideur ; production : go du propriétaire)
```

## Règles et sources

| Étape | Règle | Source exacte |
|---|---|---|
| Exigences | Le circuit, ses portes, la règle de go et qui valide quoi sont écrits une fois (ce document, puis `commun/modeles/equipe-processus.md`) et tenus à jour | NIST SP 800-218 (SSDF) 1.1, **PO.1** (PO.1.1 : documenter les exigences du processus de développement et les maintenir) |
| Spec | Chaque sujet commence par une spec courte (`docs/plans/AAAA-MM-JJ-<sujet>-spec.md`) : constat, comportement, refus, tests — décisions de conception gardées | SSDF **PW.1.2** (suivre et conserver les exigences, risques et décisions de conception) |
| Spec relue | La spec est relue par quelqu'un qui ne l'a pas écrite (le chef de projet à la relecture, ou la sécurité avant le code) | SSDF **PW.2** (PW.2.1 : revue de conception par une personne non impliquée ou un outil) |
| Environnements séparés | Un développeur = SA copie, SA branche, SA pile ; tout code du développeur que le courtier lance tourne dans un bac à sable ; jamais la recette ni la production | SSDF **PO.5.1** (séparer et protéger chaque environnement de développement) |
| Critères de contrôle | Quatre portes nommées, déclarées par projet : `verify` (rapide), `tests` (suite complète), `gate` (facultative : qualité, couverture…), `pret` (finition du projet, « Definition of Done ») ; chaque résultat est inscrit : vert, rouge, ou **« non mesuré »** quand la porte n'est pas déclarée — jamais « vert » par défaut | SSDF **PO.4.1** (définir les critères des contrôles et les suivre tout au long du cycle ; exemple : les ajouter à la « Definition of Done ») ; GitHub, « About protected branches » › *Require status checks to pass before merging* |
| `pret` obligatoire | Sans porte `pret` déclarée, pas de demande ni de fusion | SSDF PO.4.1 (critère de fin explicite) |
| Tests avant le code | Les tests qui prouvent le comportement sont écrits avant ou avec le code, dans la même branche | DORA, « Continuous integration » (tests automatisés à chaque modification) ; Google Engineering Practices, « What to look for in a code review » › *Tests* |
| Correctif de bug | Toute branche qui contient un commit `fix…` ajoute ou modifie un **test qui reproduit le bug**, et chaque commit `fix…` écrit sa **cause racine** (`Cause racine : …`) — refus sinon | SSDF **PW.8.2**, exemple 3 (ajouter à la suite de tests les tests des vulnérabilités déjà signalées, pour qu'elles ne reviennent pas) ; SSDF **RV.3** (RV.3.1 : analyser la cause racine) |
| Intégration fréquente | Branches courtes, mises à jour depuis `main` souvent (`mettre-a-jour`) ; une branche est saine quand ses portes sont vertes | DORA, « Continuous integration » (branches de courte durée, intégrées au tronc au moins chaque jour ; réparer vite un build cassé) ; GitHub flow |
| À jour avant fusion | La demande est refusée si la branche ne contient pas `main` ; à la fusion, si `main` a avancé : mise à jour automatique SEULEMENT sans fichier commun ni conflit, portes rejouées sur le résultat ; sinon refus clair | GitHub, « About protected branches » › *Require branches to be up to date before merging* |
| Relecture par un autre | La fusion est demandée par le chef de projet, validée par un autre (coordinateur ou propriétaire) ; un agent ne valide jamais sa propre demande (le courtier renvoie au propriétaire) | GitHub, « About protected branches » › *Require pull request reviews before merging* ; SSDF **PS.1.1**, exemple 4 (le propriétaire du code relit et approuve toute modification faite par d'autres) |
| Relecture du code | Le chef relit le code (mission remplie, conventions, rien de cassé ailleurs, tests présents) et approuve ce qui améliore l'état général du code ; il **rejoue les portes** lui-même et **recompte** ce que le développeur a annoncé | SSDF **PW.7.2** (relecture/analyse du code selon les règles de l'organisation, constats consignés) ; Google Engineering Practices, « The Standard of Code Review » et « What to look for in a code review » |
| Tests rejouables | Le relecteur rejoue les 4 portes sur le commit demandé, dans une copie du courtier, et compare au résultat inscrit (état et bilan) | SSDF **PW.8.2** (documenter les résultats des tests) ; SSDF PW.7.2 |
| Fusion | Avance rapide seule, jamais de push forcé, branche du développeur supprimée | GitHub, « About protected branches » (*force pushes* bloqués) ; GitHub flow (supprimer la branche après fusion) |
| Version publiée | Une ÉTIQUETTE git annotée `v<MAJEUR.MINEUR.CORRECTIF>` par version publiée, jamais déplacée, et une **entrée de journal** `## [x.y.z] - AAAA-MM-JJ` dans `CHANGELOG.md` (message de l'étiquette) ; refus si la version n'est pas SemVer, n'est pas plus grande que la dernière, ou n'a pas d'entrée | SSDF **PS.3** (PS.3.1 : archiver chaque version publiée et ses données d'intégrité) ; SemVer 2.0.0 (§2 forme X.Y.Z, §3 une version publiée ne change plus, §11 précédence ; FAQ : préfixe « v » courant) ; Keep a Changelog 1.1.0 (une entrée par version, la plus récente en haut, date ISO 8601) |
| Installation | Recette : go du valideur des fusions ; production : go du propriétaire, à chaque fois | USER.md (« Ce qui passe TOUJOURS par lui ») ; SSDF PO.5.1 |

## Règle de go (validée par le propriétaire le 12/10/2026, reprise telle quelle)

On remonte au propriétaire AVANT le code (spec courte + go) seulement si le travail touche :
1. un **secret visible**, ou un changement de **droits, d'authentification ou de gestion des secrets** ;
2. une **écriture dans un logiciel métier** ;
3. la **production** ;
4. le **pare-feu** ;
5. **plus d'appels vers un service extérieur** (guichet, registre, logiciel métier).

Hors de ces cas, le coordinateur décide seul. La fusion et la mise en production restent validées comme aujourd'hui
(`fusion_par`).

## Qui valide quoi (inchangé, rappel)

| Geste | Qui valide |
|---|---|
| Travail dans SA copie : commits, portes, pousser SA branche, demander la fusion | personne : les portes décident |
| Fusion dans la branche principale (et la mise à jour automatique qui la précède), étiquette de version, installation hors production | le coordinateur (`valide_par`) — ou le propriétaire seul si `fusion_par = "proprietaire"` ; jamais le demandeur |
| Production (installer, publier en ligne, toute modification d'un service) | le propriétaire seul, à chaque fois |

## Réglages `[equipes.<projet>]` (même forme pour les quatre portes)

`verify` / `verify_outil` (existe), `tests` / `tests_outil`, `gate` / `gate_outil` (facultatif), `pret` / `pret_outil`.
`<porte>` = commande lancée dans la copie, en bac à sable ; `<porte>_outil = "<outil> <verbe>"` = verbe de LECTURE d'un
outil du courtier, qui reçoit la branche poussée (jamais un argument de l'agent). Exemple pour Berger : `verify = "bash tests/syntaxe.sh"`, `tests = "bash tests/suites.sh"`,
`pret = "bash tests/pret.sh"`.

## Comportement

**Développeur** (`equipe_dev.py`) : un verbe par porte déclarée (`verify`, `tests`, `gate`, `pret`). `demander-fusion` :
copie propre, poussée, à jour avec `main` ; règle du correctif (commit `fix…` → test touché + `Cause racine :`) ; `pret`
déclarée ; puis les 4 portes jouées dans l'ordre, chacune inscrite (`vert` / `rouge` / `non mesuré`, code, bilan = dernière
ligne de la sortie, commit). Une porte rouge = pas de demande (le message donne les 4 résultats).

**Chef de projet** (`equipe_chef.py`) :
- `relire <sujet>` montre aussi les portes annoncées ; `rejouer <sujet>` (lecture) : les 4 portes sur le commit demandé,
  dans une copie jetable du courtier, comparées à l'annonce (`identique` ou l'écart).
- `fusionner <sujet>` (écriture validée) : la branche n'a pas bougé depuis la demande ; `pret` est rejouée et doit être
  verte, sinon REFUS.
  - `main` n'a pas avancé : avance rapide + push (comme avant).
  - `main` a avancé : refus si un fichier est modifié des deux côtés depuis la base commune (**fichier commun**, même sans
    conflit git : risque de sens) ou en cas de conflit. Sinon le commit de mise à jour est calculé DANS le dépôt du chef
    (`git merge-tree --write-tree` + `git commit-tree`, sans copie de travail), les 4 portes sont rejouées dans une copie
    jetable (portes `_outil` : sur une branche `integration/<sujet>` poussée puis effacée), puis ce commit est poussé sur
    `main` en avance rapide. Jamais de push depuis la copie où les portes ont tourné (son `.git` a pu être modifié par le
    code testé). Push refusé (main a encore bougé) : refus, rien de forcé.
- `etiqueter <version>` (écriture, même valideur que la fusion) : SemVer 2.0.0, plus grande que la dernière étiquette
  `v…`, absente de la forge, entrée `## [<version>] - AAAA-MM-JJ` dans le `CHANGELOG.md` de `main` → étiquette annotée
  sur `origin/main` (message = l'entrée), poussée sans force, tracée dans Échanges. Un titre après la date est toléré
  (`## [3.480.2] - 2026-10-05 — *Titre*`), rien avant `##`, date réelle exigée.
- SA branche de finition (`pousser <branche>`, `demander-fusion <branche> "<résumé>"`, fusion au propriétaire seul) :
  `docs/plans/2026-10-13-chef-finition-spec.md` ; écrite dans SA copie de travail, importée en avance rapide :
  `docs/plans/2026-10-13-chef-copie-spec.md`.

**Documentation** : le circuit est écrit UNE fois dans `commun/modeles/equipe-processus.md`, ajouté aux consignes de
chaque membre d'équipe ; README, REGLES (règle de go et qui valide quoi, pour tous), skill berger et `modeles/equipe-*.md` y renvoient.

## Tests (`tests/suites.sh`)

`tests/processus-dev.py` : portes absentes (« non mesuré ») / vertes / rouges ; `pret` absente → refus ; `gate` absente →
« non mesuré » ; correctif sans test ou sans cause racine → refus ; `rejouer` recompte ; `pret` rouge à la fusion → refus ;
`main` avancée sans fichier commun → mise à jour automatique, portes rejouées, avance rapide ; avec fichier commun → refus,
rien poussé ; portes rouges après mise à jour → refus, rien poussé ; étiquette (SemVer, plus grande, journal, jamais
déplacée) ; aucun nom de projet dans le code des outils d'équipe. `tests/equipe.py` et `tests/equipe-verif.py` adaptés
(`pret` désormais déclarée).
