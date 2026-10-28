"""Rapport web validé : lecture sûre, snapshot lié au go, dépôt et mission au chef."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

MAX_RAPPORT = 256 * 1024
IDENTIFIANT = re.compile(r'[a-z0-9][a-z0-9_.-]{0,59}')
SANS_LIEN = os.O_NOFOLLOW | os.O_CLOEXEC


def _identifiant(texte):
    if not isinstance(texte, str) or not IDENTIFIANT.fullmatch(texte) or texte in ('.', '..'):
        raise ValueError('identifiant invalide')
    return texte


def _source(rapport):
    if not isinstance(rapport, str): raise ValueError('rapport relatif requis')
    parties = rapport.split('/')
    if parties and parties[0] == 'analyses': parties = parties[1:]
    if (not parties or any(not p or p in ('.', '..') or any(ord(c) < 32 or ord(c) == 127 for c in p) for p in parties)
            or not parties[-1].endswith('.md')):
        raise ValueError('rapport .md relatif sous analyses requis')
    return parties


def _dossier(racine, parties):
    fd = os.open(racine, os.O_RDONLY | os.O_DIRECTORY | SANS_LIEN)
    try:
        for partie in parties:
            suivant = os.open(partie, os.O_RDONLY | os.O_DIRECTORY | SANS_LIEN, dir_fd=fd)
            os.close(fd); fd = suivant
        return fd
    except BaseException:
        os.close(fd); raise


class Relais:
    def __init__(self, berger, racine, equipes, filtre, mission):
        self.berger, self.racine = Path(berger), Path(racine)
        self.equipes, self.filtre, self.mission = equipes, filtre, mission
        self.snapshots = self.berger/'courtier/validations/web-remises'

    def _projet(self, cible):
        parties = cible.split('/') if isinstance(cible, str) else []
        if len(parties) not in (1, 2): raise ValueError('projet inconnu ou ambigu')
        for p in parties: _identifiant(p)
        candidats = []
        for eq, config in self.equipes.items():
            _identifiant(eq)
            if len(parties) == 2 and parties[0] != eq: continue
            try: registre = json.loads((self.berger/'equipes'/eq/'projets.json').read_text())
            except (OSError, ValueError): continue
            projet = parties[-1]
            if isinstance(registre, dict) and isinstance(registre.get(projet), dict):
                chef = config.get('chef_projet', '')
                _identifiant(chef)
                dd = None
                try:
                    dd = _dossier(self.berger/'agents', [chef])
                    fd = os.open('agent.conf', os.O_RDONLY | os.O_NONBLOCK | SANS_LIEN, dir_fd=dd)
                    try:
                        if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('chef de projet invalide')
                    finally: os.close(fd)
                except OSError: raise ValueError('chef de projet invalide') from None
                finally:
                    if dd is not None: os.close(dd)
                candidats.append((eq, projet, chef))
        if len(candidats) != 1: raise ValueError('projet inconnu ou ambigu')
        return candidats[0]

    def _lire(self, agent, parties):
        fd = None
        try:
            fd = _dossier(self.berger/'agents', [agent, 'analyses', *parties[:-1]])
            source = os.open(parties[-1], os.O_RDONLY | os.O_NONBLOCK | SANS_LIEN, dir_fd=fd)
            with os.fdopen(source, 'rb') as flux:
                st = os.fstat(flux.fileno())
                if not stat.S_ISREG(st.st_mode): raise PermissionError('rapport ordinaire requis')
                if st.st_size > MAX_RAPPORT: raise ValueError('rapport trop grand')
                brut = flux.read(MAX_RAPPORT + 1)
        except OSError: raise PermissionError('rapport absent ou lien refusé sous analyses') from None
        finally:
            if fd is not None: os.close(fd)
        if len(brut) > MAX_RAPPORT: raise ValueError('rapport trop grand')
        try: texte = brut.decode('utf-8')
        except UnicodeError: raise ValueError('rapport UTF-8 requis') from None
        if not texte.strip(): raise ValueError('rapport vide')
        if self.filtre(texte): raise PermissionError('rapport refusé : secret détecté')
        return brut, texte

    def _destination(self, eq, projet):
        try: return _dossier(self.racine, ['equipes', eq, 'projets', projet])
        except OSError: raise PermissionError('destination du projet absente ou lien refusé') from None

    def _preflight(self, chef):
        dd = _dossier(self.berger/'agents', [chef])
        try:
            try: os.stat('MISSION.md', dir_fd=dd, follow_symlinks=False)
            except FileNotFoundError: return
            raise RuntimeError('chef occupé : aucune mission confiée')
        finally: os.close(dd)

    def _ecrire_snapshot(self, token, d, nouveau=False):
        nom = token + '.json'
        if nouveau:
            fd = os.open(self.snapshots/nom, os.O_WRONLY | os.O_CREAT | os.O_EXCL | SANS_LIEN, 0o600)
            with os.fdopen(fd, 'w') as flux:
                json.dump(d, flux, ensure_ascii=False); flux.flush(); os.fsync(flux.fileno())
        else:
            tmp = self.snapshots/('.'+token+'.tmp')
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | SANS_LIEN, 0o600)
            try:
                with os.fdopen(fd, 'w') as flux:
                    json.dump(d, flux, ensure_ascii=False); flux.flush(); os.fsync(flux.fileno())
                os.replace(tmp, self.snapshots/nom)
            finally: tmp.unlink(missing_ok=True)
        dd = os.open(self.snapshots, os.O_RDONLY | os.O_DIRECTORY | SANS_LIEN)
        try: os.fsync(dd)
        finally: os.close(dd)

    @contextmanager
    def _verrou(self):
        fd = os.open(self.snapshots/'.lock', os.O_RDWR | os.O_CREAT | SANS_LIEN, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX); yield
        finally: os.close(fd)

    def apercu(self, agent, args):
        if len(args) != 2: raise ValueError('web remettre <projet> <rapport.md>')
        _identifiant(agent)
        if self.filtre(' '.join(args)): raise PermissionError('arguments refusés : secret détecté')
        parties = _source(args[1]); eq, projet, chef = self._projet(args[0])
        brut, texte = self._lire(agent, parties)
        self._preflight(chef)
        fd = self._destination(eq, projet); os.close(fd)
        token = uuid.uuid4().hex
        nom = f'rapport-web-{agent}-{token}.md'
        d = dict(agent=agent, source='/'.join(parties), equipe=eq, projet=projet, chef=chef,
                 sha256=hashlib.sha256(brut).hexdigest(), destination=nom, etat='pret')
        destination = self.racine/'equipes'/eq/'projets'/projet/nom
        apercu = (f'Remettre le rapport de {agent} au projet {eq}/{projet} ; destination : {destination} ; '
                  f'mission au chef {chef} ; SHA256 {d["sha256"]}. Aperçu du contenu :\n{texte[:1200]}')
        if self.filtre(apercu): raise PermissionError('aperçu refusé : secret détecté')
        self.snapshots.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self.snapshots.is_symlink(): raise PermissionError('snapshot indisponible')
        os.chmod(self.snapshots, 0o700)
        self._ecrire_snapshot(token, d, nouveau=True)
        args[:] = [eq+'/'+projet, 'analyses/'+'/'.join(parties), token]
        return apercu

    def executer(self, agent, args):
        if len(args) != 3 or not re.fullmatch(r'[0-9a-f]{32}', args[2]): raise ValueError('snapshot de validation requis')
        _identifiant(agent)
        with self._verrou():
            try:
                fd = os.open(self.snapshots/(args[2]+'.json'), os.O_RDONLY | os.O_NONBLOCK | SANS_LIEN)
                with os.fdopen(fd, 'rb') as flux:
                    if not stat.S_ISREG(os.fstat(flux.fileno()).st_mode): raise ValueError()
                    d = json.loads(flux.read(32768))
            except (OSError, ValueError): raise ValueError('snapshot de validation invalide') from None
            eq, projet, chef = self._projet(args[0]); parties = _source(args[1])
            if (d.get('agent'), d.get('equipe'), d.get('projet'), d.get('chef'), d.get('source')) != (agent, eq, projet, chef, '/'.join(parties)):
                raise ValueError('snapshot ne correspond plus à la demande')
            brut, _ = self._lire(agent, parties)
            if hashlib.sha256(brut).hexdigest() != d.get('sha256'): raise ValueError('rapport modifié depuis son aperçu ; nouvelle validation requise')
            destination = self.racine/'equipes'/eq/'projets'/projet/d['destination']
            if d['etat'] == 'termine': return f'rapport remis à {eq}/{projet} ; mission confiée à {chef}'
            if d['etat'] != 'pret': raise RuntimeError('rapport déposé ; mission non confirmée : contrôle propriétaire requis, aucun rejeu')
            self._preflight(chef)
            dd = self._destination(eq, projet)
            try:
                fd = os.open(d['destination'], os.O_WRONLY | os.O_CREAT | os.O_EXCL | SANS_LIEN, 0o640, dir_fd=dd)
                with os.fdopen(fd, 'wb') as flux:
                    flux.write(brut); flux.flush(); os.fsync(flux.fileno())
                os.fsync(dd)
            except OSError: raise RuntimeError('dépôt exclusif impossible ; aucune mission confiée') from None
            finally: os.close(dd)
            # Avant tout effet extérieur : une coupure ne rejoue jamais la mission.
            d['etat'] = 'mission-en-cours'; self._ecrire_snapshot(args[2], d)
            texte = (f'Rapport web validé pour {eq}/{projet} : {destination}. '
                     f'Lis ce rapport, précise le travail à réaliser et ouvre toi-même le développeur selon la chaîne habituelle. '
                     f'Référence de remise : {args[2]}.')
            try: self.mission(chef, texte, agent)
            except Exception:
                d['etat'] = 'mission-non-confirmee'; self._ecrire_snapshot(args[2], d)
                raise RuntimeError('rapport déposé ; mission non confirmée : contrôle propriétaire requis, aucun rejeu') from None
            d['etat'] = 'termine'; self._ecrire_snapshot(args[2], d)
            return f'rapport remis à {eq}/{projet} ; mission confiée à {chef}'
