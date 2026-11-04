#!/usr/bin/env python3
"""Régressions de la revue web : verdicts sur témoins, Host et tunnels, sans moteur ni socket local."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

T = Path(__file__).resolve().parent

def charger(n, f):
    s = importlib.util.spec_from_file_location(n, T / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

C = charger('contrat', 'contrat-moteur.py')
S = charger('sonde', 'sonde-mcp.py')

class Revue(unittest.TestCase):
    def contrat(self, panne=False):
        appels, verdicts = [], []
        class Site:
            port, n = 12345, 0
            def __init__(self, marque): pass
            def fermer(self): pass
        class Proxy:
            def __init__(self, noms, journal, **kw): self.journal = journal
            def ecouter(self, chemin): pass
            def arreter(self): pass
        class Relais:
            def __init__(self, a): pass
            def fermer(self): pass
            def web(self, **kw):
                appels.append(kw)
                # Simule un navigateur inexécutable : l'ancien contrat prenait ces octets pour un refus.
                return {'urls': {u: {'marque': False, 'pre': False, 'octets': 14, 'execute': not panne}
                                 for u in kw.get('urls', [])},
                        'direct': {'127.0.0.1:12345': 'refuse'}}
        with tempfile.TemporaryDirectory() as d, patch.object(C, 'B', Path(d)), patch.object(C, 'FauxSite', Site), \
             patch.object(C, 'Relais', Relais), patch.object(C, 'charger_web', return_value=SimpleNamespace(
                 Proxy=Proxy, preparer_dossier=lambda *a: Path(d))):
            C.conditions_web(lambda bon, msg: verdicts.append((bool(bon), msg)), 'agent',
                             {'ecriture': [d]}, SimpleNamespace(poser=lambda *a: None), Path(d) / 'absent')
        return appels, verdicts

    def test_defaut_deux_navigateur_en_panne_ne_prouve_aucun_refus(self):
        with patch.object(S.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'panne')):
            r = S.web(['file:///temoin'], navigateur=True, marque='temoin')
        self.assertIs(r['urls']['file:///temoin'].get('execute'), False)
        _, verdicts = self.contrat(panne=True)
        refus = [(ok, msg) for ok, msg in verdicts if msg.startswith(('(7)', '(9)'))]
        self.assertTrue(refus)
        self.assertFalse(any(ok for ok, _ in refus), refus)

    def test_defaut_trois_host_de_url(self):
        class Connexion:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def sendall(self, b): self.requete = b
            def recv(self, n): return b''
        c = Connexion()
        with patch.object(S.socket, 'create_connection', return_value=c):
            S.web(['http://permis.test:8080/page'])
        self.assertIn(b'\r\nHost: permis.test:8080\r\n', c.requete)

    def test_defaut_quatre_contrat_exerce_connect_et_sni(self):
        appels, verdicts = self.contrat()
        tunnels = [t for a in appels for t in a.get('tunnels', [])]
        self.assertIn({'hote': 'permis.test', 'sni': 'permis.test'}, tunnels)
        self.assertIn({'hote': 'ailleurs.test', 'sni': 'ailleurs.test'}, tunnels)
        self.assertIn({'hote': 'permis.test', 'sni': 'ailleurs.test'}, tunnels)
        self.assertTrue(any('(8)' in msg and 'SNI divergent' in msg for _, msg in verdicts))

if __name__ == '__main__': unittest.main()
