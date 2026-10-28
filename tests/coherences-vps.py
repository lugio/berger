#!/usr/bin/env python3
"""Régressions VPS, sans moteur, réseau ni Herdr réel ; fonctions de production isolées."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import datetime
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent


def fonctions(fichier, noms, contexte):
    arbre = ast.parse((SRC / fichier).read_text())
    noeuds = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name in noms]
    exec(compile(ast.Module(body=noeuds, type_ignores=[]), fichier, 'exec'), contexte)
    return contexte


class Coherences(unittest.TestCase):
    def test_essai_noter_json(self):
        texte = (SRC / 'tests/tout.sh').read_text()
        helpers = texte.split('# Fonctions des contrôles VPS\n', 1)[1].split('# Fin des fonctions des contrôles VPS', 1)[0]
        bloc = texte.split('ea=""', 1)[1].split('# ── délégation :', 1)[0]
        with tempfile.TemporaryDirectory() as td:
            b = Path(td); (b / 'agents/source').mkdir(parents=True)
            (b / 'courtier/validations').mkdir(parents=True)
            (b / 'courtier/validations/1.json').write_text('{}')
            (b / 'bin').mkdir(); berger = b / 'bin/berger'
            berger.write_text('#!/bin/sh\nexit 0\n'); berger.chmod(0o700)
            faux = b / 'faux'; faux.mkdir(); moteur = faux / 'codex'
            moteur.write_text('''#!/usr/bin/env python3
import json, sys
if 'essai' not in sys.argv: sys.exit(1)  # tentative d'auto-validation refusée
assert '--stdin' in sys.argv and json.load(sys.stdin)==['test auto-validation']
print(json.dumps({'ok':True,'en_attente':'1'}))
'''); moteur.chmod(0o700)
            import os
            env = {**os.environ, 'PATH': str(faux) + ':/usr/bin:/bin', 'B': td, 'AGENTS': 'source', 'seul': ''}
            code = helpers + '''
reglage() { case "$2" in outils) echo essai;; moteur) echo codex;; mur) echo strict;; esac; }
dire() { echo "$1 $4"; }
sleep() { :; }
ea=""
''' + bloc
            r = subprocess.run(['bash', '-c', code], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("l'agent ne peut pas se valider lui-même", r.stdout)
            self.assertNotIn('ÉCHEC', r.stdout)

    def test_horaires_herdr(self):
        texte = (SRC / 'tests/tout.sh').read_text()
        self.assertIn('# Fonctions des contrôles VPS', texte)
        fonctions_shell = texte.split('# Fonctions des contrôles VPS\n', 1)[1].split('# Fin des fonctions des contrôles VPS', 1)[0]
        with tempfile.TemporaryDirectory() as td:
            b = Path(td); (b / 'agents/a').mkdir(parents=True)
            for h, heures, mission, attendu in ((5, '8-19', False, 1), (8, '8-19', False, 0),
                    (19, '8-19', False, 0), (20, '8-19', False, 1), (5, '8-19', True, 0),
                    (12, 'aucune', False, 1), (12, 'aucune', True, 0),
                    (5, '', False, 1), (12, 'malforme', False, 0)):
                with self.subTest(h=h, heures=heures, mission=mission):
                    m = b / 'agents/a/MISSION.md'
                    if mission: m.write_text('mission')
                    else: m.unlink(missing_ok=True)
                    code = fonctions_shell + '\nreglage() { echo "$HEURES"; }; herdr_attendu a "$HEURE"'
                    import os
                    r = subprocess.run(['bash', '-c', code], env={**os.environ, 'B': td, 'HEURES': heures, 'HEURE': str(h)}, capture_output=True)
                    self.assertEqual(r.returncode, attendu, r.stderr)

    def test_auto_test_delegation_json(self):
        texte = (SRC / 'tests/tout.sh').read_text()
        # Le bloc réel et de faux exécutables : aucun vrai moteur/client ne peut être atteint.
        bloc = texte.split('# ── délégation :', 1)[1].split('# ── contrat', 1)[0]
        bloc = bloc[bloc.index('\n') + 1:]
        helpers = texte.split('# Fonctions des contrôles VPS\n', 1)[-1].split('# Fin des fonctions des contrôles VPS', 1)[0] if '# Fonctions des contrôles VPS' in texte else ''
        with tempfile.TemporaryDirectory() as td:
            b = Path(td)
            for a in ('chef', 'source', 'cible', 'sans'): (b / 'agents' / a).mkdir(parents=True)
            faux = b / 'faux'; faux.mkdir()
            moteur = faux / 'codex'
            moteur.write_text('''#!/usr/bin/env python3
import json, sys
a=sys.argv
try: params=json.load(sys.stdin)
except ValueError: print(json.dumps({'ok':False,'erreur':'transport positionnel refusé'})); sys.exit(1)
agent=a[a.index('-p')+1]; cible=a[a.index('deleguer')+1]
assert '--stdin' in a and len(params)==1
if agent=='source' and cible=='cible': print(json.dumps({'ok':True}))
elif agent in ('sans','cible','source'): print(json.dumps({'ok':False,'erreur':f"{agent} n'a pas le droit de déléguer à {cible}"}))
else: print(json.dumps({'ok':False,'erreur':'mauvaise paire'}))
'''); moteur.chmod(0o700)
            reglages = '''
reglage() {
 case "$1:$2" in
 chef:moteur) echo claude;; chef:mur) echo ouvert;; chef:outils) echo deleguer:cible;;
 source:moteur|cible:moteur|sans:moteur) echo codex;;
 source:mur|cible:mur|sans:mur) echo strict;; source:outils) echo deleguer:cible;;
 esac
}
dire() { echo "$1 $4"; }
'''
            import os
            env = {**os.environ, 'PATH': str(faux) + ':/usr/bin:/bin', 'B': td,
                   'AGENTS': 'chef source cible sans', 'seul': '', 'T': 'Test : '}
            r = subprocess.run(['bash', '-c', helpers + reglages + bloc], env=env, capture_output=True, text=True)
            self.assertNotIn('ÉCHEC', r.stdout, r.stdout + r.stderr)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('réponse reçue', r.stdout)
            self.assertIn('sans droit', r.stdout)
            env['AGENTS'] = 'chef'
            r = subprocess.run(['bash', '-c', helpers + reglages + bloc], env=env, capture_output=True, text=True)
            self.assertIn('INFO', r.stdout)
            self.assertIn('non testable', r.stdout)
            self.assertNotIn('ÉCHEC', r.stdout)
            # Une erreur de transport ne devient jamais une preuve de refus de droit.
            moteur.write_text('#!/bin/sh\necho \'{"ok": false, "erreur": "transport positionnel refusé"}\'\n')
            env['AGENTS'] = 'source cible sans'
            r = subprocess.run(['bash', '-c', helpers + reglages + bloc], env=env, capture_output=True, text=True)
            self.assertIn('refus du courtier non prouvé', r.stdout)
            self.assertNotIn('refus exact du courtier', r.stdout)

    def test_consigne_delegation(self):
        for mur in ('strict', 'ouvert'):
            with self.subTest(mur=mur):
                appels = []
                def executer(*a, **k):
                    appels.append(k)
                    return types.SimpleNamespace(returncode=0, stdout='ENGAGEMENTS: aucun')
                g = fonctions('courtier/courtier', ['deleguer'], {
                    'EN_DELEGATION': set(), 'echange': lambda *a: None,
                    'reglage': lambda a, cle: mur if cle == 'mur' else '',
                    'BERGER': SRC, '_transport': types.SimpleNamespace(executer=executer),
                    'subprocess': subprocess, 'suivre_delegation': lambda *a: None})
                g['deleguer']('source', 'cible', 'Question témoin', lambda *a: None)
                texte = appels[0]['input']
                self.assertIn('tes propres accès', texte)
                self.assertIn(mur, texte)
                self.assertIn('Ne modifie aucun fichier sauf ton journal', texte)
                self.assertIn('Question témoin', texte)
                self.assertEqual(appels[0]['timeout'], 420)

    def test_regles_sans_contournement(self):
        for f in ('commun/REGLES.md', 'commun/modeles/SOUL-master.md'):
            with self.subTest(f=f):
                texte = (SRC / f).read_text()
                self.assertIn('même en lecture seule', texte)
                self.assertIn('par un fichier', texte)

    def test_fin_apres_refus(self):
        with tempfile.TemporaryDirectory() as td:
            racine = Path(td); agent = racine / 'agents/p-s'; agent.mkdir(parents=True)
            mission = agent / 'MISSION.md'; mission.write_text('# Mission\n')
            ancien = datetime.datetime.now() - datetime.timedelta(hours=1)
            import os
            os.utime(mission, (ancien.timestamp(),) * 2)
            (agent / 'CHECKLIST.md').write_text('# Travail\n- [ ] Fusion\n')
            demandes = racine / 'equipes/p/demandes'; demandes.mkdir(parents=True)
            demande = {'agent': 'p-s', 'sujet': 's', 'branche': 'p/s', 'commit': 'tete',
                       'etat': 'à relire', 'demande': ancien.isoformat(timespec='minutes')}
            (demandes / 's.json').write_text(json.dumps(demande))
            validations = racine / 'courtier/validations'; validations.mkdir(parents=True)
            fait = {'etat': 'refusé', 'par': 'Proprio', 'agent': 'chef', 'outil': 'p-chef',
                    'verbe': 'fusionner', 'args': ['s'], 'n': 1,
                    'demande': datetime.datetime.now().isoformat(timespec='minutes'),
                    'decide': datetime.datetime.now().isoformat(timespec='minutes')}
            ferme = []
            g = fonctions('bin/berger', ['refus_fusion_proprietaire', 'fin_mission'], {
                'BERGER': racine, 'PROPRIETAIRE': 'Proprio', 'EQUIPES': {'p': {'chef_projet': 'chef'}},
                'Path': Path, 'json': json, 'datetime': datetime, 'sys': sys,
                'dossier': lambda a: agent,
                'conf': lambda a: {'nom': a, 'projet': 'p', 'sujet': 's', 'branche': 'p/s', 'copie': str(racine / 'copie')},
                '_git': lambda *a, **k: types.SimpleNamespace(returncode=0, stdout='tete\n'),
                'mission_finie': lambda a: False, 'chefs': lambda: [],
                'journal': lambda *a: None, 'echange': lambda *a: None,
                'fermer_mission': lambda a: ferme.append(a)})
            # Une décision absente, étrangère, ancienne, non propriétaire ou non refusée ne suffit jamais.
            for changements in (None, {'par': 'coord'}, {'etat': 'validé mais ÉCHEC'},
                                  {'outil': 'autre-chef'}, {'agent': 'intrus'}, {'args': ['autre']},
                                  {'verbe': 'etiqueter'}, {'demande': '2000-01-01T00:00'}):
                with self.subTest(changements=changements):
                    f = validations / 'un.fait.json'
                    if changements is None: f.unlink(missing_ok=True)
                    else: f.write_text(json.dumps({**fait, **changements}))
                    with self.assertRaises(SystemExit): g['fin_mission']('p-s', 'chef')
                    self.assertTrue(mission.exists())
                    self.assertEqual(ferme, [])
            # Une nouvelle demande, une nouvelle mission ou un nouveau commit invalident l'ancien refus.
            (validations / 'un.fait.json').write_text(json.dumps(fait))
            for changements in ({'demande': '2999-01-01T00:00'}, {'commit': 'autre'}, {'agent': 'autre'},
                                  {'branche': 'autre'}, {'etat': 'fusionnée'}):
                with self.subTest(demande=changements):
                    (demandes / 's.json').write_text(json.dumps({**demande, **changements}))
                    with self.assertRaises(SystemExit): g['fin_mission']('p-s', 'chef')
            (demandes / 's.json').write_text(json.dumps(demande))
            plus_recent = validations / 'deux.fait.json'
            plus_recent.write_text(json.dumps({**fait, 'n': 2, 'etat': 'validé mais ÉCHEC'}))
            with self.assertRaises(SystemExit): g['fin_mission']('p-s', 'chef')
            plus_recent.unlink()
            attente = validations / '2.json'
            attente.write_text(json.dumps({**fait, 'n': 2, 'etat': 'en attente'}))
            with self.assertRaises(SystemExit): g['fin_mission']('p-s', 'chef')
            attente.unlink()
            # Une mission recréée dans la même minute n'hérite jamais de l'ancien refus.
            creation = datetime.datetime.fromisoformat(fait['demande']).replace(second=45).timestamp()
            trace_refus = validations / 'un.fait.json'
            os.utime(mission, (creation, creation))
            os.utime(trace_refus, (creation - 10, creation - 10))
            with self.assertRaises(SystemExit): g['fin_mission']('p-s', 'chef')
            os.utime(mission, (ancien.timestamp(),) * 2)
            maintenant = datetime.datetime.now().timestamp()
            os.utime(trace_refus, (maintenant, maintenant))
            # Le refus ne permet pas à un autre acteur de fermer la mission.
            with self.assertRaises(SystemExit): g['fin_mission']('p-s', 'coord')
            g['fin_mission']('p-s', 'chef')
            self.assertFalse(mission.exists())
            self.assertEqual(ferme, ['p-s'])
            self.assertIn('Abandonné :', (agent / 'CHECKLIST.md').read_text())


if __name__ == '__main__':
    class Resultat(unittest.TextTestResult):
        def addSuccess(self, test):
            super().addSuccess(test)
            print('ok ' + test.id())
    unittest.main(testRunner=unittest.TextTestRunner(resultclass=Resultat))
