#!/usr/bin/env python3
"""Le clone frais de la CI trouve son verrou de suites quand sa source est un checkout GitHub NON NU (sans réseau)."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + texte)


def git(dossier, *args, **kw):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_AUTHOR_NAME='essai', GIT_AUTHOR_EMAIL='essai@exemple.invalid',
               GIT_COMMITTER_NAME='essai', GIT_COMMITTER_EMAIL='essai@exemple.invalid')
    return subprocess.run(['git', '-C', str(dossier), *args], capture_output=True, text=True, env=env, **kw)


def cles_visibles(env):
    return {k: v for k, v in env.items() if k not in ('BERGER_SUITES_VERROU', 'BERGER_SUITES_VERROU_TENU')}


# Checkout comme celui de actions/checkout : dépôt NON nu, origine = URL https (injoignable ici), arbre propre, HEAD détaché.
# Les étapes lourdes de la preuve sont remplacées DANS CE COMMIT d'essai : verify ne fait que chercher le verrou avec les vraies
# fonctions de suites.sh (copiées en _verrou_reel.sh), suites devient vide. tests/clone-frais.sh reste celui du dépôt, inchangé.
with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR') or None) as t:
    racine = Path(t)
    sim = racine / 'checkout'
    rc = git(racine, 'clone', '--quiet', '--no-hardlinks', str(SRC), str(sim))
    dire(rc.returncode == 0, 'simulation : checkout non nu créé depuis le dépôt courant')
    git(sim, 'remote', 'set-url', 'origin', 'https://github.com/exemple/berger.git')
    # le dépôt courant peut avoir des changements non commités (développement) : on prend leur état, pas seulement HEAD
    for f in git(SRC, 'ls-files', '-m', '-o', '--exclude-standard').stdout.split():
        if (SRC / f).is_file():
            (sim / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SRC / f, sim / f)
    # Seules les fonctions de verrou de suites.sh (copiées telles quelles) : la sourcer en entier jouerait toute la liste des suites.
    lignes = (SRC / 'tests/suites.sh').read_text().splitlines()
    debut = next(i for i, l in enumerate(lignes) if l.startswith('_verrou_depot_nu()'))
    fin = next(i for i, l in enumerate(lignes) if i > debut and l.startswith('_verrou_global()'))
    fin = next(i for i in range(fin, len(lignes)) if lignes[i] == '}')
    fermer = next(l for l in lignes if l.startswith('_fermer_verrou()'))
    (sim / 'tests/_verrou_reel.sh').write_text('\n'.join([fermer, *lignes[debut:fin + 1]]) + '\n')
    (sim / 'tests/syntaxe.sh').write_text(
        '#!/usr/bin/env bash\nB=$(cd "$(dirname "$0")/.." && pwd)\nsource "$B/tests/_verrou_reel.sh"\n'
        '_verrou_global || { echo "VERROU INTROUVABLE"; exit 1; }\necho "VERROU TROUVE"\n')
    (sim / 'tests/suites.sh').write_text('#!/usr/bin/env bash\necho "suites remplacées par l\'essai"\n')
    git(sim, 'add', '-A')
    git(sim, 'commit', '--quiet', '-m', 'essai', '--no-verify')
    dire(git(sim, 'status', '--porcelain').stdout == '', 'simulation : arbre propre, origine https (comme sur GitHub Actions)')
    dire(git(sim, 'config', '--get', 'remote.origin.url').stdout.strip().startswith('https://'), 'simulation : origine = URL https, aucun réseau')
    env = cles_visibles(os.environ)
    r = subprocess.run(['bash', str(sim / 'tests/clone-frais.sh')], capture_output=True, text=True, env=env, timeout=300)
    dire(r.returncode == 0 and 'VERROU TROUVE' in r.stdout,
         'clone frais d\'un checkout non nu : verrou de suites résolu, preuve menée jusqu\'au bout')
    if r.returncode != 0:
        print((r.stdout + r.stderr)[-1500:])
print(f'==== {ko} échec(s)')
raise SystemExit(1 if ko else 0)
