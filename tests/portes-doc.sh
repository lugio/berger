#!/usr/bin/env bash
# Porte courte « doc » du projet berger (spec 2026-10-28-portes-allegees-spec.md) : jouée à la place de « tests » quand le courtier
# lit, dans le diff de la demande, que des fichiers de documentation changent. Elle contrôle : la syntaxe (tests/syntaxe.sh), les
# marques et la neutralité du dépôt (tests/marques-produit.py, tests/vitrine.py : verifier-depot en dépôt jetable), l'empreinte du
# manuel et les liens locaux (tests/vitrine.py). Usage : bash tests/portes-doc.sh   (code de retour = nombre de contrôles en échec)
cd "$(dirname "$0")/.." || exit 1
ko=0
for c in "bash tests/syntaxe.sh" "python3 tests/marques-produit.py" "python3 tests/vitrine.py"; do
  out=$($c 2>&1); rc=$?
  if [ $rc = 0 ]; then echo "ok $c : $(tail -n 1 <<<"$out")"; else echo "ÉCHEC $c"; tail -n 20 <<<"$out"; ko=$((ko + 1)); fi
done
[ $ko = 0 ] && echo "ok porte doc : syntaxe, marques, empreinte du manuel et liens"
exit $ko
