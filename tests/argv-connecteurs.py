#!/usr/bin/env python3
"""Corps et URL privés des connecteurs : capture réelle de /proc, valeurs jamais affichées."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1]

class Connecteurs(unittest.TestCase):
    def verifier(self, nom):
        spec = importlib.util.spec_from_file_location(nom, SRC / 'courtier/outils' / (nom + '.py'))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        temoin = 'contenupriveessai'
        corps = {'texte': temoin, 'lignes': 'citation " puis \n et é', 'chemin': 'a\\b'}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); trace = root / 'trace'
            faux = root / 'curl'
            faux.write_text('#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\n'
                            "d = {'argv': Path('/proc/self/cmdline').read_bytes().decode().split(chr(0)), 'config': sys.stdin.read()}\n"
                            "with open(os.environ['TRACE'], 'a') as f: f.write(json.dumps(d) + '\\n')\n"
                            "sys.stdout.write('{}\\n200')\n")
            faux.chmod(0o700)
            hotes = []
            reglages = {'cle': 'temoin', 'hote': 'exemple.invalid', 'ip_secours': 'secours', 'depots': ['exemple/depot']}
            o = mod.Outil(reglages, lambda cle: temoin, lambda cle, url: hotes.append(url))
            with patch.dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'], TRACE=str(trace)):
                resultat = o.appel(temoin, 'POST', corps)
            traces = [json.loads(l) for l in trace.read_text().splitlines()]
            self.assertTrue(resultat == {}, 'réponse perdue')
            self.assertTrue(all(temoin not in str(t['argv']) for t in traces), 'contenu dans argv curl')
            self.assertTrue(len(hotes) == 1 and temoin in hotes[0], 'contrôle hôte perdu')
            for t in traces:
                config = {}
                for ligne in t['config'].splitlines():
                    k, v = ligne.split('=', 1)
                    config.setdefault(k.strip(), []).append(json.loads(v.strip()))
                self.assertTrue(json.loads(config['data-binary'][0]) == corps, 'corps altéré')
                self.assertTrue(config['url'][0] == hotes[0], 'URL altérée')
                self.assertTrue(config['request'] == ['POST'], 'méthode altérée')

    def test_github(self): self.verifier('github')
    def test_dolibarr(self): self.verifier('dolibarr')

if __name__ == '__main__': unittest.main()
