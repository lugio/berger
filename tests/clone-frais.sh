#!/usr/bin/env bash
# Preuve reproductible, uniquement locale : verify et tests du commit courant,
# clone neuf et HOME vide. Ne lance ni tests/tout.sh ni les moteurs réels.
set -euo pipefail
source_dir=$(cd "$(dirname "$0")/.." && pwd)
if [ -n "$(git -C "$source_dir" status --porcelain)" ]; then
  echo 'ÉCHEC clone frais : commiter les changements avant cette preuve' >&2
  exit 1
fi
revision=$(git -C "$source_dir" rev-parse HEAD)
# Berger lance ses aides avec le python3 trouvé d'abord dans /usr/local/bin:/usr/bin:/bin (PATH_MISE de bin/berger) :
# il doit être en 3.11 ou plus (tomllib), sinon des dizaines de contrôles échouent loin de la cause.
if ! PATH=/usr/local/bin:/usr/bin:/bin python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
  echo "ÉCHEC clone frais : le python3 du système ($(PATH=/usr/local/bin:/usr/bin:/bin python3 --version 2>&1)) doit être en 3.11 ou plus" >&2
  exit 1
fi
python_real=$(python3 -c 'import os, sys; print(os.path.realpath(sys.executable))')
workspace=$(mktemp -d /tmp/bcfXXXXXX)
trap 'rm -rf -- "$workspace"' EXIT
mkdir -p "$workspace/home" "$workspace/tools" "$workspace/tmp"
ln -s "$python_real" "$workspace/tools/python3"
cat > "$workspace/tools/interdit" <<'SH'
#!/bin/sh
echo 'ÉCHEC clone frais : appel interdit à un programme réel' >&2
exit 97
SH
chmod +x "$workspace/tools/interdit"
for program in herdr codex claude notify-send; do
  ln -s interdit "$workspace/tools/$program"
done
# L'environnement ne transporte ni BERGER_DIR ni profil utilisateur ni jeton.
# Les tests qui ont besoin d'un moteur/Herdr doivent poser leur propre double.
env -i HOME="$workspace/home" TMPDIR="$workspace/tmp" \
  PATH="$workspace/tools:/usr/local/bin:/usr/bin:/bin" \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null BERGER_CLONE_FRAIS=1 \
  BERGER_HERDR="$workspace/tools/herdr" BERGER_NOTIFY_SEND="$workspace/tools/notify-send" \
  bash -s -- "$source_dir" "$workspace/clone" "$revision" <<'SH'
set -euo pipefail
git -c core.hooksPath=/dev/null clone --quiet --local --no-hardlinks --no-checkout "$1" "$2"
git -C "$2" -c core.hooksPath=/dev/null checkout --quiet --detach "$3"
cd "$2"
test "$(git rev-parse HEAD)" = "$3"
test ! -e config.toml
test ! -e agents
test ! -e "$HOME/.config/berger/coffre.json"
echo "ok clone frais : commit $3, aucune configuration personnelle"
bash tests/syntaxe.sh
bash tests/suites.sh
SH
