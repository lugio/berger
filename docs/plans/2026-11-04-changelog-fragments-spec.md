# Journal des changements en fragments : une branche, un fichier — spec courte (04/11/2026)

Spec seule : aucun code avant le go du propriétaire. Elle touche le courtier (`courtier/outils/_portes.py`,
`courtier/outils/equipe_chef.py`) : c'est le cœur de l'installation, qui demande un go explicite.

## Constat

- Chaque branche ajoute sa ligne sous `## [Unreleased]` de `CHANGELOG.md`. Toutes les demandes touchent donc ce fichier.
- `fusionner` refuse toute mise à jour automatique dès qu'un fichier est modifié des deux côtés depuis la base
  commune, même sans conflit git (`equipe_chef.py`, `communs()` / `controler()`). Exemples : les n° 144 et 146,
  validées puis en échec de fusion. Chaque fois, il a fallu renvoyer, fusionner main, rejouer la porte tests
  (environ 10 min) et redemander.
- Deux demandes ouvertes en même temps ne peuvent donc pas passer l'une après l'autre sans un tour de plus.

## Comportement

1. **Un fragment par branche** : `changelog.d/<sujet>.md`, où `<sujet>` est le nom de la branche sans le préfixe
   `berger/`. Le contenu suit Keep a Changelog : des titres `### Added|Changed|Deprecated|Removed|Fixed|Security`,
   suivis de puces, en anglais comme aujourd'hui. Aucun titre `##`. Le nom étant propre à la branche, deux demandes
   n'ont plus de fichier commun et la mise à jour automatique existante s'applique.
2. **`CHANGELOG.md` n'est plus touché par une branche ordinaire.** `## [Unreleased]` reste vide sur main.
3. **Regroupement à la version** : la branche de finition de version (la mienne, comme `berger/version-0-3-1`)
   lance `python3 -I tests/changelog.py regrouper <x.y.z> <AAAA-MM-JJ>`. Le script :
   - écrit `## [x.y.z] - date` sous `[Unreleased]` ;
   - fusionne les fragments section par section, dans l'ordre de Keep a Changelog, puis par nom de fichier ;
   - supprime les fragments.
   Ce commit seul passe par une demande, validée par le propriétaire. `etiqueter` reste inchangé : il lit toujours
   `CHANGELOG.md`.
4. **`etiqueter` refuse** une version si un fragment reste dans `changelog.d/` sur main, avec le message
   « fragments non regroupés : <liste> ». Une ligne oubliée ne part donc pas hors version.
5. **Porte courte** (portes allégées) : `changelog.d/*.md` (mode 100644, un seul niveau) compte comme
   documentation, comme `CHANGELOG.md` aujourd'hui (`_portes.py`, liste fermée). Sans cela, une branche de
   documentation seule perdrait la porte courte.
6. **Transition** : les demandes en cours (admission-auto, ci-tableau) finissent à l'ancienne. Toute nouvelle
   mission porte la consigne du fragment. [Unreleased] est vide depuis la 0.3.1 : rien à migrer.

## Refus (contrôlés par `tests/changelog.py verifier`, joué dans `tests/suites.sh`)

- un fragment qui contient un titre `##`, une section inconnue, ou qui est vide ;
- un fragment dont le nom n'est pas en minuscules et tirets (`[a-z0-9-]+\.md`), ou qui est rangé dans un sous-dossier ;
- un lien symbolique ou un fichier exécutable dans `changelog.d/` ;
- une ligne sous `## [Unreleased]` dans `CHANGELOG.md` ;
- une branche qui modifie un fragment déjà présent sur main : c'est déjà un fichier commun, la fusion le refuse.

## Ce qui ne change pas

- `etiqueter` (lecture de `CHANGELOG.md`, conditions « sans validation »), SemVer, une étiquette jamais déplacée ;
- `pret.sh` (la documentation reste README, docs/ ou commun/) ;
- la détection des fichiers communs : le code devient plus fluide sans qu'elle s'affaiblisse.

## Limite connue (hors périmètre)

D'autres fichiers sont souvent communs : `docs/manuel.md`, ainsi que son empreinte dans `tests/vitrine.py`, qui
change dès qu'une ligne du manuel change. C'est la cause suivante des renvois. Une parade possible, pour plus tard :
calculer l'empreinte à la demande au lieu de la figer dans un test.

## Tests

- `tests/changelog.py` : `verifier`, avec un cas rouge par refus ci-dessus ; `regrouper`, à partir de 3 fragments
  qui se recouvrent (Added et Fixed dans deux fichiers), avec la sortie attendue figée et des fragments supprimés.
- `tests/moins-validations.py` : `etiqueter` refusé tant qu'un fragment reste, accepté après le regroupement.
- `tests/portes-allegees.py` : `changelog.d/x.md` donne la porte courte ; `changelog.d/a/x.md`, `changelog.d/x.sh` et
  un lien ne la donnent pas.
- `tests/processus-dev.py` : deux demandes, chacune avec son fragment, main qui avance entre les deux → la seconde
  passe par la mise à jour automatique (avant : refus pour fichier commun).

## Documentation

CONTRIBUTING (en et fr), `docs/manuel.md` (circuit, étape « version ») avec son empreinte, et le texte de mission
des développeurs : « ta ligne de journal va dans `changelog.d/<sujet>.md` ».
