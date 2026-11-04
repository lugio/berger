#!/usr/bin/env python3
"""Frontière réelle du client de courrier ; aucun témoin affiché."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import json
import os
import runpy
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace

SRC = Path(__file__).resolve().parent.parent


class ClientPrive(unittest.TestCase):
    def reponse_courtier(self):
        env = dict(os=os, json=json, Path=Path)
        arbre = ast.parse((SRC / 'courtier/courtier').read_text())
        corps = [n for n in arbre.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('ecrire_reponse_privee', 'repondre_erreur')]
        exec(compile(ast.Module(body=corps, type_ignores=[]), 'courtier/courtier', 'exec'), env)
        return env['repondre_erreur']

    def preparer(self):
        temporaire = tempfile.TemporaryDirectory(); self.addCleanup(temporaire.cleanup)
        racine = Path(temporaire.name); client = racine / 'client'
        shutil.copy2(SRC / 'courtier/berger-outil', client)
        (racine / 'agent.conf').write_text('nom = essai\n')
        return racine, client

    def lancer(self, racine, client, arguments=('--stdin',), contenu=b'[]'):
        p = subprocess.Popen([sys.executable, str(client), 'essai', 'agir', *arguments],
                             cwd=racine, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def nettoyer():
            if p.poll() is None: p.kill(); p.wait()
            for flux in (p.stdin, p.stdout, p.stderr):
                if flux: flux.close()
        self.addCleanup(nettoyer)
        try: p.stdin.write(contenu); p.stdin.close()
        except BrokenPipeError: pass
        p.stdin = None
        return p

    def attendre(self, p, racine):
        fin = time.monotonic() + 5
        while time.monotonic() < fin:
            fichiers = list((racine / 'courrier/demandes').glob('*.json'))
            if fichiers: return fichiers[0]
            if p.poll() is not None: break
            time.sleep(0.02)
        self.fail('demande non déposée')

    def repondre(self, racine, nom, contenu):
        f = racine / 'courrier/reponses' / nom
        fd = os.open(f, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as flux: flux.write(contenu)
        return f

    def test_stdin_et_permissions(self):
        temoin = 'contenupriveessai'
        with tempfile.TemporaryDirectory() as temporaire:
            racine = Path(temporaire)
            client = racine / 'client'
            shutil.copy2(SRC / 'courtier/berger-outil', client)
            (racine / 'agent.conf').write_text('nom = essai\n')
            p = subprocess.Popen([sys.executable, str(client), 'essai', 'agir', '--stdin'],
                                 cwd=racine, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                p.stdin.write(json.dumps([temoin]).encode()); p.stdin.close(); p.stdin = None
                fin = time.monotonic() + 5
                demandes = racine / 'courrier/demandes'
                while not list(demandes.glob('*.json')) and time.monotonic() < fin:
                    time.sleep(0.02)
                fichiers = list(demandes.glob('*.json'))
                self.assertTrue(len(fichiers) == 1, 'demande non déposée')
                f = fichiers[0]
                req = json.loads(f.read_text())
                mode_fichier = f.stat().st_mode & 0o777
                mode_dossier = demandes.stat().st_mode & 0o777
                argv = Path(f'/proc/{p.pid}/cmdline').read_bytes()
                reponses = racine / 'courrier/reponses'; reponses.mkdir(exist_ok=True)
                rep = reponses / f.name
                fd = os.open(rep, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'w') as flux: flux.write(json.dumps({'ok': True, 'donnees': 'fait'}))
                f.unlink()  # consommation par le courtier factice
                sortie, erreur = p.communicate(timeout=5)
                self.assertTrue(p.returncode == 0, 'client en échec')
                with self.subTest('stdin'):
                    self.assertTrue(req.get('args') == [temoin], 'stdin non transmis')
                self.assertTrue(temoin.encode() not in argv, 'contenu dans cmdline')
                with self.subTest('permissions'):
                    self.assertTrue(mode_fichier == 0o600 and mode_dossier == 0o700, 'permissions non privées')
                self.assertTrue(not rep.exists() and not list(demandes.iterdir()), 'fichiers oubliés')
            finally:
                if p.poll() is None: p.kill(); p.wait()
                for flux in (p.stdin, p.stdout, p.stderr):
                    if flux: flux.close()

    def test_refus_positionnel_et_entrees_invalides(self):
        cas = [(('contenupriveessai',), b''), (('--stdin',), b'{}'), (('--stdin',), b'['),
               (('--stdin',), b'\xff'), (('--stdin',), json.dumps(['a'] * 6).encode()),
               (('--stdin',), b'a' * (1024 * 1024 + 1))]
        for arguments, contenu in cas:
            with self.subTest('entrée refusée'):
                racine, client = self.preparer()
                p = self.lancer(racine, client, arguments, contenu)
                sortie, erreur = p.communicate(timeout=5)
                self.assertTrue(p.returncode != 0, 'entrée invalide acceptée')
                self.assertTrue(not list(racine.glob('courrier/demandes/*.json')), 'demande invalide publiée')
                self.assertTrue(b'contenupriveessai' not in sortie + erreur, 'valeur affichée')

    def test_lien_dossier_refuse(self):
        racine, client = self.preparer()
        externe = racine / 'ailleurs'; externe.mkdir()
        (racine / 'courrier').symlink_to(externe, target_is_directory=True)
        p = self.lancer(racine, client)
        p.communicate(timeout=5)
        self.assertTrue(p.returncode != 0 and not list(externe.iterdir()), 'lien de dossier suivi')

    def fichier_entree(self, racine, contenu):
        dossier = racine / '.transport'; dossier.mkdir(mode=0o700)
        f = dossier / 'requete.json'
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as flux: flux.write(contenu)
        return f

    def test_fichier_consomme(self):
        racine, client = self.preparer(); temoin = 'contenupriveessai'
        entree = self.fichier_entree(racine, json.dumps([temoin]).encode())
        p = self.lancer(racine, client, ('--fichier', '.transport/requete.json'), b'')
        demande = self.attendre(p, racine)
        self.assertTrue(not entree.exists() and not list(entree.parent.iterdir()), 'entrée non consommée')
        self.assertTrue(json.loads(demande.read_text())['args'] == [temoin], 'fichier perdu')
        self.assertTrue(temoin.encode() not in Path(f'/proc/{p.pid}/cmdline').read_bytes(), 'fichier en argv')
        self.repondre(racine, demande.name, b'{"ok":true}')
        p.communicate(timeout=5)
        self.assertTrue(p.returncode == 0, 'parcours fichier en échec')

    def test_fichier_invalide_consomme(self):
        racine, client = self.preparer()
        entree = self.fichier_entree(racine, b'[')
        p = self.lancer(racine, client, ('--fichier', '.transport/requete.json'), b'')
        p.communicate(timeout=5)
        self.assertTrue(p.returncode != 0 and not entree.exists() and not list(entree.parent.iterdir()),
                        'entrée invalide oubliée')

    def test_reservation_fichier_exclusive(self):
        racine, client = self.preparer()
        entree = self.fichier_entree(racine, b'[]')
        reserve = entree.parent / '.temoin.tmp'; reserve.write_text('intact'); reserve.chmod(0o600)
        g = runpy.run_path(str(client), run_name='essai')
        fonction = g['lire_fichier']
        fonction.__globals__['uuid'] = SimpleNamespace(uuid4=lambda: SimpleNamespace(hex='temoin'))
        ancien = Path.cwd(); os.chdir(racine)
        try:
            with self.assertRaises(FileExistsError): fonction('.transport/requete.json')
        finally: os.chdir(ancien)
        self.assertTrue(reserve.read_text() == 'intact' and entree.exists(), 'réservation écrasée')

    def test_lien_reponse_refuse_et_nettoye(self):
        racine, client = self.preparer(); p = self.lancer(racine, client)
        demande = self.attendre(p, racine)
        cible = racine / 'temoin'; cible.write_text('intact')
        rep = racine / 'courrier/reponses' / demande.name
        rep.symlink_to(cible)
        p.communicate(timeout=5)
        self.assertTrue(p.returncode != 0, 'réponse liée acceptée')
        self.assertTrue(cible.read_text() == 'intact', 'cible de lien modifiée')
        self.assertTrue(not os.path.lexists(rep) and not demande.exists(), 'liens ou demandes oubliés')

    def test_reponses_bornees_et_privees(self):
        for contenu, mode in ((b'a' * (1024 * 1024 + 1), 0o600),
                              (b'{"ok":true}', 0o644), (b'{"ok":"oui"}', 0o600)):
            with self.subTest('réponse refusée'):
                racine, client = self.preparer(); p = self.lancer(racine, client)
                demande = self.attendre(p, racine)
                rep = self.repondre(racine, demande.name, contenu); rep.chmod(mode)
                p.communicate(timeout=5)
                self.assertTrue(p.returncode != 0, 'réponse non conforme acceptée')
                self.assertTrue(not demande.exists() and not rep.exists(), 'nettoyage après refus absent')

    def test_nettoyage_interruption(self):
        for numero in (signal.SIGINT, signal.SIGTERM):
            with self.subTest('interruption'):
                racine, client = self.preparer(); p = self.lancer(racine, client)
                demande = self.attendre(p, racine)
                p.send_signal(numero)
                sortie, erreur = p.communicate(timeout=5)
                self.assertTrue(not demande.exists() and not list(demande.parent.iterdir()), 'demande oubliée après interruption')
                self.assertTrue(b'Traceback' not in erreur, 'trace non maîtrisée sur interruption')

    def test_reponse_courtier_privee(self):
        racine, client = self.preparer()
        encours = racine / 'courrier/encours'; encours.mkdir(parents=True)
        demande = encours / 'temoin.json'; demande.write_text('{}')
        self.reponse_courtier()(demande, 'refus')
        rep = racine / 'courrier/reponses/temoin.json'
        self.assertTrue(rep.stat().st_mode & 0o777 == 0o600, 'réponse du courtier non privée')
        self.assertTrue(rep.parent.stat().st_mode & 0o777 == 0o700, 'dossier de réponse non privé')
        self.assertTrue(not demande.exists(), 'demande non consommée')

    def test_lien_dossier_courtier_refuse(self):
        racine, client = self.preparer()
        encours = racine / 'courrier/encours'; encours.mkdir(parents=True)
        demande = encours / 'temoin.json'; demande.write_text('{}')
        ailleurs = racine / 'ailleurs'; ailleurs.mkdir()
        (racine / 'courrier/reponses').symlink_to(ailleurs, target_is_directory=True)
        with self.assertRaises((OSError, ValueError)):
            self.reponse_courtier()(demande, 'refus')
        self.assertTrue(not list(ailleurs.iterdir()), 'le courtier a suivi un lien')

    def test_parcours_client_courtier_et_droits(self):
        temoin = 'contenupriveessai'
        for scenario in ('lecture', 'interdit', 'validation', 'lectureseule', 'filtre'):
            with self.subTest(scenario):
                racine, client = self.preparer()
                p = self.lancer(racine, client, contenu=json.dumps([temoin]).encode())
                demande = self.attendre(p, racine)
                argv = Path(f'/proc/{p.pid}/cmdline').read_bytes()
                encours = racine / 'courrier/encours' / demande.name
                demande.rename(encours)
                appels = []; validations = []; gestes = []
                def lecture(args): appels.append(args); return 'fait'
                def valider(*args):
                    validations.append(args)
                    (racine / 'validations').mkdir()
                    (racine / 'validations/1.json').write_text('{"valideur":null}')
                    return 1, 'controle'
                env = dict(os=os, json=json, Path=Path, time=time,
                           lecture_seule=lambda a: scenario == 'lectureseule',
                           droits=lambda a: [] if scenario == 'interdit' else ['essai'],
                           OUTILS={'essai': {'agir': lecture}}, OBJETS={},
                           ECRITURES={'essai': {'agir': (lambda a: 'controle', lambda a: gestes.append(a))}}
                                     if scenario in ('validation', 'lectureseule') else {},
                           contient_secret=lambda t: scenario == 'filtre', contexte=lambda *a: None,
                           demander_validation=valider, VALIDATIONS=racine / 'validations',
                           CONFIG={'proprietaire': 'proprietaire'}, journal=lambda *a: None,
                           controle_boucle=lambda *a: None)          # anti-boucle : hors sujet ici (tests/anti-boucle.py)
                arbre = ast.parse((SRC / 'courtier/courtier').read_text())
                # le vrai refus des textes trop longs (trop_long) : il est sur le chemin de chaque demande
                corps = [n for n in arbre.body if (isinstance(n, ast.FunctionDef)
                         and n.name in ('ecrire_reponse_privee', 'traiter', 'trop_long', 'mission_max'))
                         or (isinstance(n, ast.Assign) and any(isinstance(c, ast.Name) and c.id == 'TEXTES_OUTILS'
                                                                for x in n.targets for c in ast.walk(x)))]
                exec(compile(ast.Module(body=corps, type_ignores=[]), 'courtier/courtier', 'exec'), env)
                env['traiter']('essai', encours, {})
                sortie, erreur = p.communicate(timeout=5)
                rep = json.loads(sortie)
                self.assertTrue(rep['ok'] == (scenario in ('lecture', 'validation')), 'résultat ou droits modifiés')
                self.assertTrue(temoin.encode() not in argv + sortie + erreur, 'contenu affiché ou dans argv')
                self.assertTrue(not gestes, 'écriture exécutée sans validation')
                self.assertTrue(bool(validations) == (scenario == 'validation'), 'circuit de validation modifié')
                self.assertTrue(appels == ([[temoin]] if scenario in ('lecture', 'filtre') else []), 'arguments perdus ou accès interdit exécuté')
                self.assertTrue(not encours.exists(), 'demande du courtier non nettoyée')


if __name__ == '__main__':
    resultat = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ClientPrive))
    if resultat.wasSuccessful():
        for numero in range(resultat.testsRun): print('ok client privé', numero + 1)
    sys.exit(0 if resultat.wasSuccessful() else 1)
