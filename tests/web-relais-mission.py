#!/usr/bin/env python3
"""Deux attributions concurrentes ne peuvent pas écraser une mission ; aucun Herdr."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import datetime
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
ROOT=Path(__file__).resolve().parents[1]
class Attribution(unittest.TestCase):
    def test_creation_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            dossier=Path(tmp); (dossier/'agent.conf').touch()
            barriere=threading.Barrier(2); effets=[]; resultats=[]
            def compter(): barriere.wait(timeout=3); return []
            env=dict(dossier=lambda a:dossier,sys=sys,conf=lambda a:dict(nom='Chef',moteur='codex'),
                missions_comptees=compter,chefs=lambda:[],MISSIONS={},datetime=datetime,
                herdr_ids=lambda a:{'agents':{'codex':'panneau'}},
                journal=lambda *a:effets.append(a),echange=lambda *a:None,agents=lambda:[],
                agent_vivant=lambda a:True,time=SimpleNamespace(sleep=lambda n:None),parler=lambda *a,**kw:None)
            arbre=ast.parse((ROOT/'bin/berger').read_text())
            fn=next(n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name=='mission')
            exec(compile(ast.Module(body=[fn],type_ignores=[]),'mission','exec'),env)
            def attribuer(texte):
                try: env['mission']('chef',texte,'retro');resultats.append('ok')
                except SystemExit: resultats.append('refus')
            fils=[threading.Thread(target=attribuer,args=(texte,)) for texte in ('premiere','seconde')]
            for fil in fils:fil.start()
            for fil in fils:fil.join(4);self.assertFalse(fil.is_alive())
            self.assertCountEqual(resultats,['ok','refus']);self.assertEqual(len(effets),1)
            contenu=(dossier/'MISSION.md').read_text()
            self.assertTrue(contenu.endswith(('premiere\n','seconde\n')))
if __name__=='__main__':unittest.main()
