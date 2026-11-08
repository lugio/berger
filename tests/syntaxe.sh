#!/usr/bin/env bash
# Porte « verify » du projet berger (rapide, quelques secondes) : chaque fichier Python et shell suivi par git se relit
# sans erreur de syntaxe. La suite complète est la porte « tests » (tests/suites.sh), la finition la porte « pret »
# (tests/pret.sh) — circuit : docs/plans/2026-10-12-processus-dev-generique-spec.md.
# Usage : bash tests/syntaxe.sh   (code de retour = nombre de fichiers en erreur)
cd "$(dirname "$0")/.." || exit 1
# python3 hors des raccourcis de mise (06/11/2026) : depuis omarchy-settings 4.5.0, le raccourci …/mise/shims/python3 écrit dans
# ~/.local/share/mise à chaque appel et meurt dans un bac à sable (« mise ERROR Read-only file system ») : la porte mourait avant
# de démarrer. Seul l'appel à python3 ci-dessous prend le PATH sans les raccourcis (le python3 suivant : celui du système ; en CI,
# le 3.11 de /usr/local/bin) ; le reste du script garde son PATH (renvoi n° 173). Contrôlé par tests/portes-python.py.
_sans_mise=$(tr ':' '\n' <<<"$PATH" | grep -v '/mise/shims/*$' | paste -sd:)
ko=0; py=(); sh=()
while IFS= read -r f; do
  [ -f "$f" ] || continue
  case "$f" in
    *.py) py+=("$f") ;;
    *.sh) sh+=("$f") ;;
    *) case "$(head -c 64 "$f" 2>/dev/null | head -n 1)" in
         '#!'*python*) py+=("$f") ;;
         '#!'*bash*|'#!'*/sh*) sh+=("$f") ;;
       esac ;;
  esac
done < <(git ls-files)
# ast.parse : aucun __pycache__ écrit dans la copie
PATH=$_sans_mise python3 - "${py[@]}" <<'PY' || ko=$((ko + $?))
import ast, sys
ko = 0
for f in sys.argv[1:]:
    try: ast.parse(open(f, encoding="utf-8").read(), f)
    except (SyntaxError, UnicodeDecodeError) as e: ko += 1; print(f"ÉCHEC {f} : {e}")
sys.exit(ko)
PY
for f in "${sh[@]}"; do bash -n "$f" || { echo "ÉCHEC $f : syntaxe shell"; ko=$((ko + 1)); }; done
[ $ko = 0 ] && echo "ok syntaxe : ${#py[@]} fichiers Python, ${#sh[@]} scripts shell"
exit $ko
