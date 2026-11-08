#!/usr/bin/env bash
# Porte courte « doc » du projet berger (spec 2026-10-28-portes-allegees-spec.md) : jouée à la place de « tests » quand le courtier
# lit, dans le diff de la demande, que des fichiers de documentation changent. Elle contrôle : la syntaxe (tests/syntaxe.sh), les
# fragments du journal (tests/changelog.py), les marques et la neutralité du dépôt (tests/marques-produit.py, tests/vitrine.py :
# verifier-depot en dépôt jetable), les empreintes du manuel par section (tests/attendus/manuel/) et les liens locaux (tests/vitrine.py).
# Usage : bash tests/portes-doc.sh   (code de retour = nombre de contrôles en échec)
cd "$(dirname "$0")/.." || exit 1
# python3 hors des raccourcis de mise (06/11/2026, tests/syntaxe.sh) : un dossier dont le SEUL python3 est le premier python3 du PATH
# qui n'est pas un raccourci mise, mis en tête ; le reste du PATH (herdr, gh… des raccourcis) est gardé tel quel (renvoi n° 173).
_py=$(PATH=$(tr ':' '\n' <<<"$PATH" | grep -v '/mise/shims/*$' | paste -sd:); command -v python3)
_pyd=$(mktemp -d 2>/dev/null) && [ -n "$_py" ] && ln -s "$_py" "$_pyd/python3" && PATH="$_pyd:$PATH" || _pyd=""
ko=0
for c in "bash tests/syntaxe.sh" "python3 -I tests/changelog.py" "python3 tests/marques-produit.py" "python3 tests/vitrine.py"; do
  out=$($c 2>&1); rc=$?
  if [ $rc = 0 ]; then echo "ok $c : $(tail -n 1 <<<"$out")"; else echo "ÉCHEC $c"; tail -n 20 <<<"$out"; ko=$((ko + 1)); fi
done
[ -n "$_pyd" ] && rm -rf "$_pyd"
[ $ko = 0 ] && echo "ok porte doc : syntaxe, journal, marques, empreinte du manuel et liens"
exit $ko
