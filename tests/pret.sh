#!/usr/bin/env bash
# Porte « pret » du projet berger (finition, « Definition of Done » — SSDF PO.4.1) : ce que la relecture ne doit pas
# avoir à rappeler. Sur les changements de la branche par rapport à origin/main :
#  1. ni espace en fin de ligne ni marqueur de conflit (git diff --check) ;
#  2. code modifié (bin/, courtier/, crochets/) → un test modifié ou ajouté (tests/) : « corriger sans le test qui le
#     prouve » est interdit (skill berger) ;
#  3. code modifié → la documentation suit dans la même branche (README.md, docs/ ou commun/) ;
#  4. chaque suite tests/*.py est jouée par tests/suites.sh ou tests/tout.sh (une suite oubliée ne protège rien).
# Circuit : docs/plans/2026-10-12-processus-dev-generique-spec.md. Usage : bash tests/pret.sh (0 = prêt)
cd "$(dirname "$0")/.." || exit 1
ko=0; echec() { echo "ÉCHEC $*"; ko=$((ko + 1)); }
base=$(git merge-base origin/main HEAD 2>/dev/null) || { echo "ÉCHEC pas de origin/main : lance « mettre-a-jour »"; exit 1; }
changes=$(git diff --name-only "$base" HEAD)
git diff --check "$base" HEAD >/dev/null || { git diff --check "$base" HEAD | head -n 20; echec "espaces en fin de ligne ou marqueurs de conflit (ci-dessus)"; }
if grep -qE '^(bin|courtier|crochets)/' <<<"$changes"; then
  grep -qE '^tests/' <<<"$changes" || echec "code modifié sans test (tests/) : ajoute le test qui prouve le changement"
  grep -qE '^(README\.md|docs/|commun/)' <<<"$changes" || echec "code modifié sans documentation (README.md, docs/ ou commun/)"
fi
for f in tests/*.py; do
  n=$(basename "$f"); case "$n" in _*|sonde-*) continue ;; esac
  grep -q "$n" tests/suites.sh tests/tout.sh || echec "$f n'est jouée ni par tests/suites.sh ni par tests/tout.sh"
done
[ $ko = 0 ] && echo "ok pret : $(grep -c . <<<"$changes") fichier(s) changé(s), finition du projet berger"
exit $ko
