"""Connexion du propriétaire. Aucune entrée MCP ; sorties et erreurs statiques."""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time

from _web import Proxy
from _web_session import domaine_exact, nombre, ETAT_MAX


class ConnexionRefusee(Exception):
    pass


def runtime_config(config):
    c = config.get('web', {})
    resultat = {k: c.get(k) for k in ('node', 'playwright_module', 'navigateur')}
    if not all(isinstance(v, str) and Path(v).is_absolute() for v in resultat.values()):
        raise ConnexionRefusee('configuration [web] nécessaire : chemins absolus node, playwright_module, navigateur')
    if (not all(Path(v).is_file() for v in resultat.values())
            or not all(os.access(resultat[k], os.X_OK) for k in ('node', 'navigateur'))):
        raise ConnexionRefusee('runtime [web] indisponible ; configuration nécessaire')
    return resultat


def _lease(etats, domaine, maintenant):
    """Un état moderne, unique et sans fermeture/nettoyage en cours."""
    if (etats/'nettoyage'/f'{domaine}.json').exists(): raise ConnexionRefusee('accès session indisponible')
    candidats = []
    for f in etats.glob('*.json'):
        if f.is_symlink(): raise ConnexionRefusee('accès session indisponible')
        try:
            brut = f.read_bytes()
            if len(brut) > 16384: raise ValueError()
            d = json.loads(brut)
            if not isinstance(d, dict): raise ValueError()
        except (OSError, ValueError): raise ConnexionRefusee('accès session indisponible') from None
        if domaine not in d.get('noms', []): continue
        agent = d.get('agent')
        if (not isinstance(agent, str) or not re.fullmatch(r'[\w.-]{1,60}', agent)
                or f.name != agent+'.json' or d.get('session') is not True
                or d.get('noms') != [domaine] or not nombre(d.get('fin_ts'))
                or d['fin_ts'] <= maintenant or not isinstance(d.get('socket'), str)
                or not d['socket'] or (etats/(agent+'.fermer')).exists()):
            raise ConnexionRefusee('accès session indisponible')
        st = f.stat()
        candidats.append((d, (f.name, st.st_ino, st.st_mtime_ns, brut)))
    if len(candidats) != 1: raise ConnexionRefusee('un accès session validé unique est requis')
    return candidats[0]


def _arreter_processus(p):
    if p.poll() is None:
        p.terminate()
        try: p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill(); p.communicate()


def capturer(runtime, helper, domaine, proxy, spki, profil, valide):
    env = dict(os.environ, TMPDIR=str(profil), TMP=str(profil), TEMP=str(profil))
    p = subprocess.Popen([runtime['node'], str(helper), runtime['playwright_module'], runtime['navigateur'],
                          domaine, proxy, spki], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        while True:
            if not valide(): raise ConnexionRefusee('accès session fermé ou expiré')
            try: sortie, _ = p.communicate(timeout=0.2); break
            except subprocess.TimeoutExpired: continue
        if p.returncode != 0 or len(sortie) > ETAT_MAX: raise ConnexionRefusee('connexion interrompue')
        return json.loads(sortie)
    finally:
        _arreter_processus(p)


def connecter(domaine, etats, profils, sessions, runtime, helper, *, fabrique=Proxy, capture=capturer, horloge=time.time, chemins_bloques=None):
    proxy = None
    profil = None
    try:
        domaine_exact(domaine)
        etats, profils = Path(etats), Path(profils)
        initial, identite = _lease(etats, domaine, horloge())
        coffre = sessions.coffre
        parent = coffre.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o077
                or not stat.S_ISREG(coffre.lstat().st_mode) or coffre.is_symlink()):
            raise ConnexionRefusee('coffre privé indisponible')
        def valide():
            try: permis = _lease(etats, domaine, horloge())[1] == identite
            except (ConnexionRefusee, OSError, ValueError, TypeError): permis = False
            if not permis and proxy is not None: proxy.arreter()
            return permis
        profils.mkdir(mode=0o700, parents=True, exist_ok=True)
        if profils.is_symlink(): raise ConnexionRefusee('dossier de profils indisponible')
        os.chmod(profils, 0o700)
        profil = Path(tempfile.mkdtemp(prefix='connexion-', dir=profils)); os.chmod(profil, 0o700)
        options = {'post_autorise': True}
        if chemins_bloques is not None: options['chemins_bloques'] = chemins_bloques
        proxy = fabrique([domaine], lambda *args: None, **options)
        port = proxy.ecouter_local()
        etat = capture(runtime, helper, domaine, f'http://127.0.0.1:{port}', proxy.empreinte, profil, valide)
        if not valide(): raise ConnexionRefusee('accès session fermé ou expiré')
        sessions.enregistrer(domaine, initial['agent'], etat, initial['fin_ts'], autoriser=valide)
    except KeyboardInterrupt:
        raise
    except ConnexionRefusee:
        raise
    except Exception:
        raise ConnexionRefusee('connexion impossible ; aucune session publiée') from None
    finally:
        try:
            if proxy is not None: proxy.arreter()
        finally:
            if profil is not None:
                try:
                    shutil.rmtree(profil)
                    if profil.exists(): raise OSError()
                except OSError:
                    raise ConnexionRefusee('nettoyage du profil impossible') from None
