#!/usr/bin/env python3
"""Conservation du manuel et liens de la vitrine, sans réseau ni installation réelle."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, message):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + message)


def liens_invalides(fichier):
    texte = re.sub(r'```.*?```', '', fichier.read_text(), flags=re.S)
    erreurs = []
    for cible in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', texte):
        lien = urlsplit(cible)
        if lien.scheme or lien.netloc:
            continue  # Aucun accès réseau : seules les destinations locales sont contrôlées.
        chemin = fichier.parent / unquote(lien.path) if lien.path else fichier
        if not chemin.exists():
            erreurs.append(cible)
        elif lien.fragment and chemin.suffix == '.md':
            titres = re.findall(r'^#+ (.+)$', chemin.read_text(), re.M)
            ancres = [re.sub(r'[^\w\- ]', '', t.lower()).replace(' ', '-') for t in titres]
            if unquote(lien.fragment) not in ancres:
                erreurs.append(cible)
    return erreurs


def main():
    manuel = SRC / 'docs/manuel.md'
    dire(manuel.is_file(), 'manuel français présent dans docs/')
    if not manuel.is_file():
        return 1
    contenu = manuel.read_text()
    # Le sommaire est ajouté sans modifier le corps du manuel conservé en référence.
    corps = re.sub(r'^## Sommaire\n.*?(?=^## Principes\n)', '', contenu,
                   count=1, flags=re.M | re.S)
    dire(hashlib.sha256(corps.encode()).hexdigest() == '80d4530ca17b18224f14f6a7158af89cf91f2591875505bb71d1276309544de9',
         'corps du manuel conservé, hors sommaire')
    documents = (SRC / 'README.md', SRC / 'README.fr.md', manuel, SRC / 'docs/install.md')
    for fichier in documents:
        erreurs = liens_invalides(fichier)
        dire(not erreurs, f'liens locaux valides : {fichier.relative_to(SRC)} {erreurs or ""}')
    dire('docs/manuel.md' in (SRC / 'README.md').read_text(), 'README racine oriente vers le manuel')
    sommaire = re.search(r'^## Sommaire\n(.*?)(?=^## Principes\n)', contenu, re.M | re.S)
    titres = re.findall(r'^## (.+)$', corps, re.M)
    dire(bool(sommaire) and re.findall(r'^- \[([^]]+)\]', sommaire[1], re.M) == titres,
         'sommaire : toutes les sections du manuel, dans leur ordre')
    dire('docs/install.md' in (SRC / 'README.md').read_text(),
         'README anglais oriente vers installation anglaise')

    with tempfile.TemporaryDirectory() as dossier:
        t = Path(dossier)
        f = t / 'page.md'
        f.write_text('[absent](absent.md)\n[ancre](page.md#absente)\n')
        dire(len(liens_invalides(f)) == 2, 'témoin : fichier et ancre cassés détectés')
        # Exécuter la vraie commande du produit, uniquement sur des données jetables.
        (t / 'docs').mkdir(parents=True)
        for chemin in ('README.md', 'README.fr.md', 'docs/manuel.md', 'docs/install.md', '.gitignore'):
            (t / chemin).write_bytes((SRC / chemin).read_bytes())
        (t / 'config.toml').write_text('proprietaire = "Propriétaire factice"\n')
        env = {**os.environ, 'HOME': str(t / 'maison'), 'BERGER_DIR': str(t)}
        subprocess.run(['git', 'init', '-q', str(t)], check=True, env=env)
        r = subprocess.run(['git', '-C', str(t), 'add', '.'], capture_output=True, env=env)
        suivis = subprocess.check_output(['git', '-C', str(t), 'ls-files'], text=True, env=env).splitlines()
        dire(r.returncode == 0 and 'docs/manuel.md' in suivis and 'docs/install.md' in suivis,
             'liste blanche Git accepte manuel et installation anglaise')
        r = subprocess.run([sys.executable, str(SRC / 'bin/berger'), 'verifier-depot'], env=env,
                           capture_output=True, text=True)
        dire(r.returncode == 0 and 'dépôt propre' in r.stdout,
             'verifier-depot accepte ces fichiers dans une installation jetable'
             + ('' if r.returncode == 0 else ' : ' + r.stdout + r.stderr))
    print(f'==== {ko} échec(s)')
    return 1 if ko else 0


if __name__ == '__main__':
    sys.exit(main())
