#!/usr/bin/env python3
"""Les futurs profils sont masqués avant leur création, sans vrai coffre."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def charger(fichier, nom, env):
    arbre = ast.parse((ROOT/fichier).read_text())
    fn = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == nom)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), fichier, 'exec'), env)
    return env[nom]
class Masques(unittest.TestCase):
    def test_agents_et_courtier_parent_effectif_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); home=base/'home'; home.mkdir()
            for externe in (False, True):
                parent=(base/'externe' if externe else home/'.config/berger')
                env=dict(Path=Path, HOME=home, COFFRE=parent/'coffre.json', RESULTATS=base/'resultats',
                    SOCKETS_MCP=base/'sockets', MASQUES_DOSSIERS=[], MASQUES_OPTIONNELS=[],
                    superviseur=lambda a:True, cloisons=lambda a:[])
                masques=charger('bin/berger','masques',env)('alice')
                self.assertIn(str(parent), [str(home/m) for m in masques])
                self.assertTrue(parent.is_dir()); self.assertEqual(parent.stat().st_mode & 0o777,0o700)
                env=dict(Path=Path, CONFIG={}, COFFRE=parent/'coffre.json', BERGER=base/'produit', AGENTS=base/'agents')
                self.assertIn(str(parent),charger('courtier/courtier','masques_courtier',env)())
    def test_parent_deja_declare_une_seule_fois(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp); parent=home/'.secret'; parent.mkdir()
            env=dict(Path=Path,HOME=home,COFFRE=parent/'coffre.json',RESULTATS=home/'resultats',
                SOCKETS_MCP=home/'sockets',MASQUES_DOSSIERS=['.secret'],MASQUES_OPTIONNELS=[],
                superviseur=lambda a:True,cloisons=lambda a:[])
            masques=charger('bin/berger','masques',env)('alice')
            self.assertEqual([str(home/m) for m in masques],[str(parent)])
    def test_claude_chemin_absolu(self):
        arbre=ast.parse((ROOT/'bin/berger').read_text())
        fn=next(n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name=='reglages_claude')
        env=dict(Path=Path,HOME=Path('/home/faux'),masques=lambda a:['.secret','/externe/prive'],a='alice',MASQUE_FICHIER='jeton')
        exec(compile(ast.Module(body=[fn.body[0]],type_ignores=[]),'reglages','exec'),env)
        self.assertIn('Read(//externe/prive/**)',env['deny'])
        self.assertIn('Read(~/.secret/**)',env['deny'])
if __name__=='__main__':unittest.main()
