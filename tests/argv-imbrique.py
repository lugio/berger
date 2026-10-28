#!/usr/bin/env python3
"""Les appels internes à Berger gardent corps et chemins hors des argv du noyau."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1]

class Imbrique(unittest.TestCase):
    def preparer(self):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        root = Path(td.name) / 'cheminpriveessai'; (root / 'bin').mkdir(parents=True)
        f = root / 'bin/berger'
        f.write_text("#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\n"
                     "def main(args, prive=False):\n d={'argv':Path('/proc/self/cmdline').read_bytes().decode().split(chr(0)), 'args':args, 'entree':sys.stdin.read()}\n with open(os.environ['TRACE'], 'a') as f: f.write(json.dumps(d)+'\\n')\n print('{}')\n"
                     "if __name__ == '__main__': main(sys.argv[1:])\n")
        f.chmod(0o700)
        trace = root / 'trace'
        return root, trace

    def module(self, chemin):
        spec = importlib.util.spec_from_file_location('essai', SRC / chemin)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod

    def test_transport_direct(self):
        root, trace=self.preparer(); temoin='contenupriveessai'
        transport=self.module('courtier/outils/_transport.py')
        with patch.dict(os.environ,TRACE=str(trace)):
            r=transport.executer(root/'bin/berger',['essai',temoin],input=temoin,text=True,capture_output=True)
        self.assertTrue(r.returncode==0,'lancement privé en échec')
        d=json.loads(trace.read_text())
        self.assertTrue(d['args']==['essai',temoin] and d['entree']==temoin,'charge privée altérée')
        self.assertTrue(temoin not in str(d['argv']) and 'cheminpriveessai' not in str(d['argv']),'argv privé exposé')

    def test_transport_asynchrone(self):
        root, trace=self.preparer(); temoin='contenupriveessai'
        transport=self.module('courtier/outils/_transport.py')
        with patch.dict(os.environ,TRACE=str(trace)):
            p=transport.lancer(root/'bin/berger',['essai',temoin],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.assertTrue(p.wait(timeout=5)==0,'lancement asynchrone en échec')
        d=json.loads(trace.read_text())
        self.assertTrue(d['args']==['essai',temoin] and temoin not in str(d['argv']),'transport asynchrone altéré')

    def test_transport_borne(self):
        transport=self.module('courtier/outils/_transport.py')
        with self.assertRaises(ValueError): transport.charge('berger',['a'*(1024*1024)])
        with self.assertRaises(ValueError): transport.charge('berger',[{}])

    def appels(self, nom):
        root, trace = self.preparer(); temoin = 'contenupriveessai'
        env = dict(BERGER=root, subprocess=subprocess, json=json, echange=lambda *a: None, EN_DELEGATION=set(), suivre_delegation=lambda *a:None)
        env['reglage'] = lambda a, cle: 'strict' if cle == 'mur' else ''
        transport = SRC / 'courtier/outils/_transport.py'
        if transport.exists(): env['_transport'] = self.module('courtier/outils/_transport.py')
        arbre = ast.parse((SRC / 'courtier/courtier').read_text())
        f = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == nom)
        exec(compile(ast.Module(body=[f], type_ignores=[]), 'courtier/courtier', 'exec'),env)
        rep=[]
        with patch.dict(os.environ, TRACE=str(trace)):
            if nom == 'notifier_proprietaire': env[nom](temoin,temoin)
            elif nom == 'deleguer': env[nom]('origine','cible',temoin,lambda *a:rep.append(a))
            elif nom == 'ecrire': env[nom]('origine','cible',temoin,lambda *a:rep.append(a))
            elif nom == 'missionner': env[nom]('origine','confier','cible',[temoin],lambda *a:rep.append(a))
            else: env[nom]('origine','ouvrir',['projet','sujet',temoin],lambda *a:rep.append(a))
        self.assertTrue(trace.exists(), 'sous-processus non joué')
        d=json.loads(trace.read_text())
        self.assertTrue(temoin in d['args'] or temoin in d['entree'], 'contenu interne perdu')
        self.assertTrue(temoin not in str(d['argv']), 'contenu dans argv imbriqué')
        self.assertTrue('cheminpriveessai' not in str(d['argv']), 'chemin privé dans argv imbriqué')
        if nom!='notifier_proprietaire': self.assertTrue(rep and rep[0][0].get('ok') is True, 'réponse interne perdue')

    def test_notification(self): self.appels('notifier_proprietaire')
    def test_delegation(self): self.appels('deleguer')
    def test_message(self): self.appels('ecrire')
    def test_mission(self): self.appels('missionner')
    def test_equipe(self): self.appels('equipe_commande')

    def test_renvoi(self):
        root, trace = self.preparer(); temoin = 'contenupriveessai'
        mod=self.module('courtier/outils/equipe_chef.py')
        mod.__file__=str(root / 'courtier/outils/equipe_chef.py')
        o=mod.Outil.__new__(mod.Outil); o.contexte={'agent':'chef'}
        f=root / 'demande.json'; d={'agent':'cible','sujet':'sujet'}
        o.demande=lambda sujet:(f,d)
        with patch.dict(os.environ, TRACE=str(trace)):
            o.renvoyer(['sujet',temoin])
            fin=time.monotonic()+5
            while not trace.exists() and time.monotonic()<fin: time.sleep(.02)
        self.assertTrue(trace.exists(), 'renvoi non joué')
        t=json.loads(trace.read_text())
        self.assertTrue(t['entree']==temoin or temoin in t['entree'], 'motif de renvoi perdu sur stdin')
        self.assertTrue('--stdin' in t['args'], 'syntaxe de parler non migrée')
        self.assertTrue(temoin not in str(t['argv']), 'motif dans argv de renvoi')
        self.assertTrue('cheminpriveessai' not in str(t['argv']), 'chemin dans argv de renvoi')

if __name__=='__main__': unittest.main()
