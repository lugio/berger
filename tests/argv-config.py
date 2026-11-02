#!/usr/bin/env python3
"""Profils privés : dossiers préexistants, liens et nettoyage en échec."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

SRC=Path(__file__).resolve().parents[1]
TEMOIN="contenuessai"

class Configuration(unittest.TestCase):
    def fonction(self,racine):
        spec=importlib.util.spec_from_file_location('transport',SRC/'courtier/outils/_transport.py')
        transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)
        env=dict(os=os,Path=Path,re=re,json=json,CODEX_HOME=racine,transport=transport)   # forme d'accès : la fonction vit dans bin/moteurs/codex.py (nom `transport`)
        arbre=ast.parse((SRC/'bin/moteurs/codex.py').read_text())
        n=next(n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name=='ecrire_profil_ouvert')
        exec(compile(ast.Module(body=[n],type_ignores=[]),'bin/moteurs/codex.py','exec'),env)
        return env['ecrire_profil_ouvert'],transport

    def test_dossier_preexistant(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'profil';root.mkdir();root.chmod(0o755)
            fonction,_=self.fonction(root)
            nom=fonction('essai',TEMOIN)
            self.assertTrue(root.stat().st_mode&0o777==0o700,'dossier non privé')
            self.assertTrue((root/(nom+'.config.toml')).stat().st_mode&0o777==0o600,'profil non privé')

    def test_dossier_lie(self):
        with tempfile.TemporaryDirectory() as td:
            autre=Path(td)/'autre';autre.mkdir()
            root=Path(td)/'profil';root.symlink_to(autre,target_is_directory=True)
            fonction,_=self.fonction(root)
            with self.assertRaises((OSError,ValueError)):fonction('essai',TEMOIN)
            self.assertTrue(not list(autre.iterdir()),'écriture à travers un lien')

    def test_profil_lie(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'profil';root.mkdir(mode=0o700)
            cible=Path(td)/'autre';cible.write_text('ancien')
            (root/'ouvert-essai.config.toml').symlink_to(cible)
            fonction,_=self.fonction(root)
            with self.assertRaises((OSError,ValueError)):fonction('essai',TEMOIN)
            self.assertTrue(cible.read_text()=='ancien','cible modifiée')

    def test_nettoyage_echec(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);_,transport=self.fonction(root)
            (root/'systeme.md').write_text('ancien')
            with patch('os.replace',side_effect=OSError('échec simulé')):
                with self.assertRaises(OSError):transport.ecrire_configuration(root,'systeme.md',TEMOIN)
            self.assertTrue(sorted(p.name for p in root.iterdir())==['systeme.md'],'fichier temporaire restant')
            self.assertTrue((root/'systeme.md').read_text()=='ancien','configuration précédente perdue')

if __name__=='__main__':unittest.main()
