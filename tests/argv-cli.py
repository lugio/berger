#!/usr/bin/env python3
"""Entrée CLI complète : configuration réelle jetable et moteurs simulés, sans remplacer les fonctions Berger."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SRC=Path(__file__).resolve().parents[1]

class CLI(unittest.TestCase):
    def preparer(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup)
        home=Path(td.name);installation=home/'installation';a=installation/'agents/essai'
        a.mkdir(parents=True);(a/'memory').mkdir()
        (installation/'config.toml').write_text('proprietaire = "essai"\nmasques = []\n')
        (a/'agent.conf').write_text('nom = essai\nmur = ouvert\nmoteur = codex\nconsigne_fichier = systeme.md\n')
        (a/'systeme.md').write_text('consignesystemeprivee')
        b=home/'.local/bin';b.mkdir(parents=True)
        moteur=r"""#!/usr/bin/env python3
import json,os,sys,tomllib
from pathlib import Path
moteur=Path(sys.argv[0]).name
if moteur=='codex':
 nom=sys.argv[sys.argv.index('-p')+1]
 f=Path(os.environ['CODEX_HOME'])/(nom+'.config.toml')
 configuration={}
 base=Path(os.environ['CODEX_HOME'])/'config.toml'
 if base.exists():configuration.update(tomllib.loads(base.read_text()))
 configuration.update(tomllib.loads(f.read_text()))
 instructions=configuration.get('developer_instructions','')
else:
 f=Path(sys.argv[sys.argv.index('--append-system-prompt-file')+1])
 instructions=f.read_text()
d=dict(argv=Path('/proc/self/cmdline').read_bytes().decode().split(chr(0)),texte=sys.stdin.read(),instructions=instructions,
       prive=(f.stat().st_mode&0o777==0o600 and f.parent.stat().st_mode&0o777==0o700))
Path(os.environ['TRACE']).write_text(json.dumps(d))
if '-o' in sys.argv:Path(sys.argv[sys.argv.index('-o')+1]).write_text('reponse')
else:print('reponse')
"""
        for nom in ('codex','claude'):
            f=b/nom;f.write_text(moteur);f.chmod(0o700)
        env=dict(os.environ,HOME=str(home),BERGER_DIR=str(installation),BERGER_HERDR='/bin/false',
                 BERGER_NOTIFY_SEND='/bin/false',TRACE=str(home/'trace'))
        env.pop('AGENT_PANNE',None)
        return home,env

    def verifier(self,moteur):
        home,env=self.preparer();temoin='contenupriveessai';instructions='consignesystemeprivee'
        r=subprocess.run(['python3',str(SRC/'bin/berger'),'demander','essai','--stdin','--moteur',moteur],
                         input=temoin,env=env,capture_output=True,text=True,timeout=30)
        self.assertTrue(r.returncode==0 and r.stdout.strip()=='reponse','CLI sans réponse')
        d=json.loads((home/'trace').read_text())
        self.assertTrue(d['texte']==temoin and d['instructions']==instructions,'contenu perdu sur le parcours complet')
        self.assertTrue(temoin not in str(d['argv']) and instructions not in str(d['argv']),'argv exposé sur le parcours complet')
        self.assertTrue(d['prive'],'configuration système non privée')
        self.assertTrue(temoin not in r.stdout+r.stderr and instructions not in r.stdout+r.stderr,'contenu affiché')

    def registre(self,env):
        """Le VRAI paquet bin/commandes/ (contrat, DROITS de la famille de transition), avec le seul verbe message-deposer inscrit."""
        import importlib.util,sys
        sys.path.insert(0,str(SRC/'bin'))
        spec=importlib.util.spec_from_file_location('commandes_essai',SRC/'bin/commandes/__init__.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
        ns={'VERBES_COEUR':{'message-deposer':env['verbe_message_deposer']}}
        exec(compile((SRC/'bin/commandes/transition.py').read_text(),'transition','exec'),ns)
        c.VERBES.update(ns['VERBES']);c.DROITS.update(ns['DROITS']);c.FAMILLE_DE.update({v:'transition' for v in ns['VERBES']})
        return c

    def test_commande_json(self):
        import ast,io,sys
        appels=[];temoin='contenupriveessai'
        env=dict(sys=type('Entree',(),{'exit':staticmethod(sys.exit),'stdin':io.TextIOWrapper(io.BytesIO(json.dumps(['message-deposer','origine','cible',temoin]).encode()))})(),
                 json=json,message_deposer=lambda *a:appels.append(a),print=lambda *a:None)
        fonctions=[n for f in ('bin/berger','bin/noyau/transport.py') for n in ast.parse((SRC/f).read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ('main','entree_privee','verbe_message_deposer')]
        exec(compile(ast.Module(body=fonctions,type_ignores=[]),'bin/berger','exec'),env)
        env['commandes']=self.registre(env)    # forme d'accès seule (lot 3) : main() cherche le verbe dans le registre des commandes
        env['main'](['--stdin'])
        self.assertTrue(appels==[('origine','cible',temoin)],'commande JSON perdue')

    def test_commande_positionnelle_refusee(self):
        import ast,sys
        appels=[];temoin='contenupriveessai'
        env=dict(sys=sys,message_deposer=lambda *a:appels.append(a),print=lambda *a:None)
        arbre=ast.parse((SRC/'bin/berger').read_text());n=next(n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        n2=next(n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name=='verbe_message_deposer')
        exec(compile(ast.Module(body=[n,n2],type_ignores=[]),'bin/berger','exec'),env)
        env['commandes']=self.registre(env)    # forme d'accès seule (lot 3) : main() cherche le verbe dans le registre des commandes
        with self.assertRaises(SystemExit):env['main'](['message-deposer','origine','cible',temoin])
        self.assertTrue(not appels,'ancien transport encore exécuté')

    def test_codex_instructions_heritees(self):
        home,env=self.preparer();temoin='contenupriveessai';instructions='consignebaseprivee'
        installation=Path(env['BERGER_DIR'])
        (installation/'agents/essai/agent.conf').write_text('nom = essai\nmur = ouvert\nmoteur = codex\n')
        profil=installation/'.codex';profil.mkdir(mode=0o700)
        (profil/'config.toml').write_text('developer_instructions = '+json.dumps(instructions)+'\n')
        r=subprocess.run(['python3',str(SRC/'bin/berger'),'demander','essai','--stdin','--moteur','codex'],
                         input=temoin,env=env,capture_output=True,text=True,timeout=30)
        self.assertTrue(r.returncode==0,'CLI sans réponse')
        d=json.loads((home/'trace').read_text())
        self.assertTrue(d['instructions']==instructions,'instructions de base effacées')
        self.assertTrue(instructions not in str(d['argv']),'instructions héritées exposées')

    def test_codex(self):self.verifier('codex')
    def test_claude(self):self.verifier('claude')
    def test_usage_reel(self):
        home,env=self.preparer()
        r=subprocess.run(['python3',str(SRC/'bin/berger'),'demander'],env=env,capture_output=True,text=True,timeout=30)
        self.assertTrue(r.returncode!=0 and 'usage :' in r.stderr and 'Traceback' not in r.stderr,'usage incorrect')

if __name__=='__main__':unittest.main()
