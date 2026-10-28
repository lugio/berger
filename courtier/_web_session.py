# -*- coding: utf-8 -*-
"""Sessions prêtées, uniquement côté courtier ; aucun accès réseau ni journal de secrets.
Le callback sans argument sauvegarder() doit réaliser une sauvegarde chiffrée vérifiée
et lever une exception en cas d'échec. Les lecteurs retournent des données internes :
ne jamais les exposer au MCP. Le contexte appelant gère l'arrêt du proxy à échéance.
"""
import copy
import fcntl
import ipaddress
import json
import math
import os
import re
import stat
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

ETAT_MAX = 256 * 1024
COFFRE_MAX = 16 * 1024 * 1024
COOKIE_MAX = 8192
DOMAINE = re.compile(r'(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')
NOM_COOKIE = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
VALEUR_COOKIE = re.compile(r'[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*')


def domaine_exact(domaine):
    if not isinstance(domaine, str) or not DOMAINE.fullmatch(domaine) or domaine.endswith('.localhost'):
        raise ValueError('domaine exact invalide')
    try: ipaddress.ip_address(domaine)
    except ValueError: return domaine
    raise ValueError('adresse IP refusée')


def nombre(valeur):
    return type(valeur) in (int, float) and math.isfinite(valeur)


def nettoyer(domaine, etat, maintenant):
    try: brut = json.dumps(etat, ensure_ascii=True, allow_nan=False).encode()
    except (TypeError, ValueError): raise ValueError('état invalide') from None
    if len(brut) > ETAT_MAX or not isinstance(etat, dict): raise ValueError('état trop grand ou invalide')
    cookies, origins = etat.get('cookies', []), etat.get('origins', [])
    if not isinstance(cookies, list) or not isinstance(origins, list): raise ValueError('état invalide')
    propres = []
    for c in cookies:
        if not isinstance(c, dict): continue
        nom, valeur, hote, chemin = (c.get(k) for k in ('name', 'value', 'domain', 'path'))
        if not all(isinstance(x, str) for x in (nom, valeur, hote, chemin)): continue
        if not NOM_COOKIE.fullmatch(nom) or not VALEUR_COOKIE.fullmatch(valeur): continue
        if len(nom) + len(valeur) + 1 > COOKIE_MAX: continue
        # Sans point initial : cookie host-only. Avec point : suffixe parent applicable.
        parent = hote[1:] if hote.startswith('.') else hote
        if not DOMAINE.fullmatch(parent): continue
        if hote.startswith('.'):
            if domaine != parent and not domaine.endswith('.' + parent): continue
        elif domaine != parent: continue
        if not chemin.startswith('/') or any(ord(x) < 32 or ord(x) == 127 for x in chemin): continue
        expire = c.get('expires', -1)
        if not nombre(expire) or (expire != -1 and expire <= maintenant): continue
        if type(c.get('secure', False)) is not bool: continue
        propre = {k: c[k] for k in ('name', 'value', 'domain', 'path', 'secure', 'expires', 'httpOnly', 'sameSite') if k in c}
        propres.append(propre)
    locales = []
    for o in origins:
        if not isinstance(o, dict) or o.get('origin') != 'https://' + domaine: continue
        stockage = o.get('localStorage', [])
        if not isinstance(stockage, list): continue
        items = [{'name': x['name'], 'value': x['value']} for x in stockage
                 if isinstance(x, dict) and isinstance(x.get('name'), str) and isinstance(x.get('value'), str)]
        locales.append({'origin': o['origin'], 'localStorage': items})
    return {'cookies': propres, 'origins': locales}


class SessionCoffre:
    def __init__(self, coffre: Path, sauvegarder, horloge=time.time):
        if not callable(sauvegarder): raise TypeError('sauvegarde requise')
        self.coffre, self.sauvegarder, self.horloge = Path(coffre), sauvegarder, horloge
        self._connues = set()
        self._connues_session = {}
        self._mutex = threading.RLock()

    @contextmanager
    def _verrou(self):
        with self._mutex:
            fd = os.open(str(self.coffre) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('verrou invalide')
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally: os.close(fd)

    def _charger(self):
        try: fd = os.open(self.coffre, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except FileNotFoundError: return {}
        with os.fdopen(fd, 'rb') as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode): raise ValueError('coffre invalide')
            brut = f.read(COFFRE_MAX + 1)
        if len(brut) > COFFRE_MAX: raise ValueError('coffre trop grand')
        try: contenu = json.loads(brut)
        except (ValueError, UnicodeError): raise ValueError('coffre invalide') from None
        if not isinstance(contenu, dict): raise ValueError('coffre invalide')
        return contenu

    def _retenir(self, entree, domaine=None):
        valeurs = set()
        if not isinstance(entree, dict): return
        etat = entree.get('etat', {})
        if not isinstance(etat, dict): return
        for c in etat.get('cookies', []):
            if isinstance(c, dict) and isinstance(c.get('value'), str) and c['value']: valeurs.add(c['value'])
        for o in etat.get('origins', []):
            if not isinstance(o, dict): continue
            for x in o.get('localStorage', []):
                if isinstance(x, dict) and isinstance(x.get('value'), str) and x['value']: valeurs.add(x['value'])

        self._connues.update(valeurs)
        if domaine is not None and isinstance(entree.get('agent'), str):
            self._connues_session.setdefault((domaine, entree['agent']), set()).update(valeurs)

    def _ecrire(self, contenu):
        brut = json.dumps(contenu, ensure_ascii=True, allow_nan=False).encode()
        if len(brut) > COFFRE_MAX: raise ValueError('coffre trop grand')
        # Aucun fichier temporaire avant la sauvegarde chiffrée vérifiée.
        self.sauvegarder()
        fd, nom = tempfile.mkstemp(prefix='.' + self.coffre.name + '-', dir=self.coffre.parent)
        try:
            with os.fdopen(fd, 'wb') as f:
                os.fchmod(f.fileno(), 0o600)
                f.write(brut); f.flush(); os.fsync(f.fileno())
            if self.coffre.is_symlink(): raise ValueError('lien coffre refusé')
            os.replace(nom, self.coffre)
            dfd = os.open(self.coffre.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
        finally:
            try: os.unlink(nom)
            except FileNotFoundError: pass

    def enregistrer(self, domaine, agent, etat, fin_ts, autoriser=None):
        domaine_exact(domaine)
        if not isinstance(agent, str) or not agent or not nombre(fin_ts) or fin_ts <= self.horloge():
            raise ValueError('agent ou échéance invalide')
        entree = {'agent': agent, 'fin_ts': fin_ts, 'etat': nettoyer(domaine, etat, self.horloge())}
        with self._verrou():
            if fin_ts <= self.horloge() or (autoriser is not None and not autoriser()):
                raise ValueError('autorisation expirée ou fermée')
            contenu = self._charger(); cle = 'web-session:' + domaine
            ancien = contenu.get(cle)
            self._retenir(ancien, domaine)
            if ancien != entree:
                contenu[cle] = entree
                self._ecrire(contenu)
            self._retenir(entree, domaine)

    def lire(self, domaine, agent=None):
        domaine_exact(domaine)
        with self._verrou():
            entree = self._charger().get('web-session:' + domaine)
            self._retenir(entree, domaine)
            if not isinstance(entree, dict) or not nombre(entree.get('fin_ts')) or entree['fin_ts'] <= self.horloge(): return None
            if agent is not None and entree.get('agent') != agent: return None
            return copy.deepcopy(entree)

    def cookie(self, domaine, chemin='/', secure=True, agent=None):
        domaine_exact(domaine)
        if not secure: return ''
        entree = self.lire(domaine, agent=agent)
        if entree is None: return ''
        if not isinstance(chemin, str) or not chemin.startswith('/'): return ''
        cookies = nettoyer(domaine, entree.get('etat'), self.horloge())['cookies']
        morceaux, taille = [], 0
        for c in sorted(cookies, key=lambda c: -len(c['path'])):
            p = c['path']
            if chemin != p and not (chemin.startswith(p) and (p.endswith('/') or chemin[len(p):].startswith('/'))): continue
            morceau = c['name'] + '=' + c['value']
            ajout = len(morceau) + (2 if morceaux else 0)
            if taille + ajout > COOKIE_MAX: continue
            morceaux.append(morceau); taille += ajout
        return '; '.join(morceaux)

    def valeurs_session(self, domaine, agent):
        """Valeurs connues de CE prêt, retenues pour les réponses encore en vol ; aucune sortie agent."""
        domaine_exact(domaine)
        with self._verrou():
            self._retenir(self._charger().get('web-session:' + domaine), domaine)
            return set(self._connues_session.get((domaine, agent), set()))

    def valeurs(self):
        with self._verrou():
            for cle, entree in self._charger().items():
                if cle.startswith('web-session:'): self._retenir(entree, cle[len('web-session:'):])
            return set(self._connues)

    def effacer(self, domaine):
        domaine_exact(domaine)
        with self._verrou():
            contenu = self._charger(); cle = 'web-session:' + domaine
            if cle not in contenu: return False
            self._retenir(contenu.pop(cle), domaine)
            self._ecrire(contenu)
            return True
