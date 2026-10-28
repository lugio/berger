# -*- coding: utf-8 -*-
"""Appels internes : corps et chemins privés sur stdin, code de lancement constant."""
import json
import subprocess

MAXIMUM = 1024 * 1024
LANCEUR = """import io, json, runpy, sys
brut = sys.stdin.buffer.read(1048577)
if len(brut) > 1048576: raise SystemExit('entrée interne trop grande')
d = json.loads(brut.decode('utf-8'))
if not isinstance(d, dict) or set(d) != {'programme', 'arguments', 'entree'}: raise SystemExit('entrée interne invalide')
if not isinstance(d['programme'], str) or not isinstance(d['entree'], str): raise SystemExit('entrée interne invalide')
if not isinstance(d['arguments'], list) or not all(isinstance(a, str) for a in d['arguments']): raise SystemExit('entrée interne invalide')
sys.stdin = io.TextIOWrapper(io.BytesIO(d['entree'].encode('utf-8')))
sys.argv = ['berger', *d['arguments']]
g = runpy.run_path(d['programme'], run_name='appel_interne')
g['main'](d['arguments'], prive=True)
"""


def charge(programme, arguments, entree=''):
    if isinstance(entree, bytes): entree = entree.decode('utf-8')
    if not isinstance(entree, str) or not all(isinstance(a, str) for a in arguments):
        raise ValueError('entrée interne invalide')
    brut = json.dumps({'programme': str(programme), 'arguments': list(arguments), 'entree': entree},
                      ensure_ascii=False).encode('utf-8')
    if len(brut) > MAXIMUM: raise ValueError('entrée interne trop grande')
    return brut


def executer(programme, arguments, **options):
    entree = charge(programme, arguments, options.pop('input', ''))
    if options.get('text') or options.get('encoding') or options.get('universal_newlines'):
        entree = entree.decode('utf-8')
    return subprocess.run(['python3', '-c', LANCEUR], input=entree, **options)


def lancer(programme, arguments, **options):
    entree = charge(programme, arguments, options.pop('input', ''))
    if options.get('text') or options.get('encoding') or options.get('universal_newlines'):
        entree = entree.decode('utf-8')
    processus = subprocess.Popen(['python3', '-c', LANCEUR], stdin=subprocess.PIPE, **options)
    try:
        processus.stdin.write(entree)
        processus.stdin.close()
        processus.stdin = None
    except BaseException:
        processus.stdin.close()
        processus.terminate()
        processus.wait()
        raise
    import threading
    threading.Thread(target=processus.wait, daemon=True).start()
    return processus


def executer_shell(commande, construire=None, **options):
    """Script anonyme 600, créé dans un dossier 700 puis détaché du système de fichiers.

    stdin reste disponible pour les données du crochet. Le descripteur est fermé
    par le noyau même si le processus est interrompu ; aucun nom de transport ne reste.
    `construire` reçoit une commande sans contenu et la place dans le bac existant.
    """
    import os
    import tempfile
    repertoire = tempfile.mkdtemp(prefix='script-')
    try:
        with tempfile.TemporaryFile(mode='w+b', dir=repertoire) as flux:
            os.rmdir(repertoire)
            repertoire = None
            brut = commande.encode('utf-8')
            if len(brut) > MAXIMUM: raise ValueError('script trop grand')
            flux.write(brut); flux.seek(0)
            numero = flux.fileno()
            if construire is None:
                argv = ['bash', '/dev/fd/' + str(numero)]
            else:
                argv = construire(['bash', '/dev/commande'])
                if not argv or argv[0] != 'bwrap': raise ValueError('bac attendu')
                position = argv.index('--chdir')
                argv[position:position] = ['--perms', '0400', '--ro-bind-data', str(numero), '/dev/commande']
            transmis = tuple(options.pop('pass_fds', ())) + (numero,)
            return subprocess.run(argv, pass_fds=transmis, **options)
    finally:
        if repertoire is not None: os.rmdir(repertoire)


def ecrire_configuration(repertoire, nom, texte):
    """Configuration générée persistante : dossier 700, remplacement exclusif 600 sans lien."""
    import os
    import re
    import stat
    import uuid
    from pathlib import Path
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,128}', nom) or nom in ('.', '..'):
        raise ValueError('nom de configuration invalide')
    repertoire = Path(repertoire)
    repertoire.mkdir(mode=0o700, exist_ok=True)
    dossier = os.open(repertoire, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporaire = '.' + uuid.uuid4().hex + '.tmp'
    cree = False
    try:
        if os.fstat(dossier).st_uid != os.getuid(): raise ValueError('dossier de configuration non conforme')
        os.fchmod(dossier, 0o700)
        try:
            meta = os.stat(nom, dir_fd=dossier, follow_symlinks=False)
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_nlink != 1:
                raise ValueError('configuration non conforme')
        except FileNotFoundError: pass
        fd = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dossier)
        cree = True
        with os.fdopen(fd, 'w', encoding='utf-8') as flux: flux.write(texte)
        os.replace(temporaire, nom, src_dir_fd=dossier, dst_dir_fd=dossier)
    finally:
        try:
            if cree:
                try: os.unlink(temporaire, dir_fd=dossier)
                except FileNotFoundError: pass
        finally: os.close(dossier)
    return repertoire / nom
