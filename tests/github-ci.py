#!/usr/bin/env python3
"""État CI GitHub : faux curl, aucun réseau et aucun coffre."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole
import ast
import re
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SRC = Path(__file__).resolve().parent.parent

def charger(nom, fichier):
    spec = importlib.util.spec_from_file_location(nom, SRC / fichier)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

github = charger('github_ci', 'courtier/outils/github.py')
# Charger la vraie fonction pure sans initialiser une installation Berger.
arbre = ast.parse((SRC / 'bin/noyau/lectures.py').read_text())
gravite = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == 'gravite')
espace = {'re': re, 'ANSI': re.compile(r'\033\[[0-9;]*m')}
exec(compile(ast.Module(body=[gravite], type_ignores=[]), '<gravite>', 'exec'), espace)
lectures = SimpleNamespace(gravite=espace['gravite'])

class CI(unittest.TestCase):
    def setUp(self):
        self.jeton = 'jeton-factice-du-test'
        self.hotes = []
        self.outil = github.Outil({'cle': 'forge.jeton', 'depots': ['exemple/projet']},
                                  lambda cle: self.jeton, lambda cle, url: self.hotes.append((cle, url)))
        self.run = {'name': 'Model-free checks', 'head_sha': 'abcdefabcdefabcdef',
                    'updated_at': '2026-11-02T12:00:00Z', 'status': 'completed', 'conclusion': 'success'}

    def appel(self, args=None, reponse=None, brut=None):
        contenu = brut if brut is not None else json.dumps(reponse if reponse is not None else {'workflow_runs': [self.run]})
        with patch.object(github.subprocess, 'run', return_value=SimpleNamespace(stdout=contenu + '\n200', returncode=0)) as curl:
            resultat = self.outil.verbes['ci'](args or ['exemple/projet'])
        self.assertEqual(curl.call_count, 1)
        argv = curl.call_args.args[0]
        self.assertEqual(argv[0], 'curl')
        self.assertNotIn(self.jeton, ' '.join(argv))
        self.assertIn('Bearer ' + self.jeton, curl.call_args.kwargs['input'])
        self.assertNotIn(self.jeton, resultat)
        self.assertNotIn('https://', resultat)
        self.assertEqual(len(resultat.splitlines()), 1)
        return resultat, curl.call_args.kwargs['input']

    def test_succes(self):
        resultat, config = self.appel()
        self.assertEqual(resultat, '✓ CI Model-free checks verte · abcdefabcd · 2026-11-02T12:00:00Z')
        self.assertIn('/actions/runs?branch=main&per_page=1', config)
        self.assertIn('request = "GET"', config)
        self.assertEqual(self.hotes, [('forge.jeton', 'https://api.github.com/repos/exemple/projet/actions/runs?branch=main&per_page=1')])
        self.assertNotIn('ci', self.outil.ecritures)

    def test_echecs(self):
        for conclusion in ('failure', 'timed_out', 'startup_failure', 'cancelled'):
            with self.subTest(conclusion=conclusion):
                self.run['conclusion'] = conclusion
                resultat, _ = self.appel()
                self.assertIn('✗ CI Model-free checks en ÉCHEC', resultat)
                self.assertEqual(lectures.gravite(resultat, {}), 'rouge')

    def test_en_cours_et_branche(self):
        self.run.update(status='in_progress', conclusion=None)
        resultat, config = self.appel(['exemple/projet', 'feature/test-ci'])
        self.assertIn('⚠ CI Model-free checks en cours', resultat)
        self.assertEqual(lectures.gravite(resultat, {}), 'jaune')
        self.assertIn('branch=feature/test-ci&per_page=1', config)

    def test_reponses_illisibles(self):
        for valeur in ({'workflow_runs': []}, {}, None, [], {'workflow_runs': [None]},
                       {'workflow_runs': [{}]}, {'workflow_runs': 'incorrect'}):
            with self.subTest(valeur=valeur), self.assertRaisesRegex((RuntimeError, ValueError), 'GitHub CI'):
                self.appel(brut=json.dumps(valeur))
        with self.assertRaisesRegex((RuntimeError, ValueError), 'GitHub CI'):
            self.appel(brut='pas du JSON')

    def test_etat_inconnu_et_sortie_malveillante(self):
        for modification in ({'conclusion': 'neutral'}, {'conclusion': 'skipped'},
                             {'name': 'https://exemple.invalid'}, {'name': self.jeton},
                             {'name': 'workflow\nforgé'}, {'name': 'workflow\u2028forgé'},
                             {'head_sha': 'https://exemple.invalid'}, {'updated_at': 'invalide'}):
            original = self.run.copy()
            self.run.update(modification)
            with self.subTest(modification=modification), self.assertRaisesRegex(RuntimeError, 'GitHub CI'):
                self.appel()
            self.run = original
        with patch.object(github.subprocess, 'run', return_value=SimpleNamespace(stdout=self.jeton + '\n403', returncode=0)):
            with self.assertRaisesRegex(RuntimeError, '^GitHub CI : réponse illisible ou collecte en échec$'):
                self.outil.verbes['ci'](['exemple/projet'])

    def test_refus_avant_curl(self):
        for args in ([], ['autre/projet'], ['exemple/projet', ''], ['exemple/projet', 'x' * 101],
                     ['exemple/projet', 'main&per_page=100'], ['exemple/projet', 'main\n'],
                     ['exemple/projet', 'branche avec espace'], ['exemple/projet', 'main', 'extra']):
            with self.subTest(args=args), patch.object(github.subprocess, 'run') as curl:
                with self.assertRaises(ValueError):
                    self.outil.verbes['ci'](args)
                curl.assert_not_called()
        self.assertEqual(self.hotes, [])

if __name__ == '__main__':
    resultat = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(CI))
    if resultat.wasSuccessful():
        print(f'ok CI GitHub : {resultat.testsRun} tests sans réseau')
    raise SystemExit(not resultat.wasSuccessful())
