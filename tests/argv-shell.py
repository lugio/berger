#!/usr/bin/env python3
"""Scripts littéraux : absence dans cmdline, stdin indépendant et fermeture des fichiers."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

SRC=Path(__file__).resolve().parents[1]
CODE="import json,os;from pathlib import Path;print(json.dumps(Path('/proc/'+str(os.getppid())+'/cmdline').read_bytes().decode().split(chr(0))))"
TEMOIN='contenupriveessai'
COMMANDE='python3 -c '+shlex.quote(CODE)+'; : #contenupriveessai'

def module(nom):
    spec=importlib.util.spec_from_file_location(nom,SRC/'courtier/outils'/(nom+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

class Shell(unittest.TestCase):
    def verifier(self, nom):
        with tempfile.TemporaryDirectory() as td:
            mod=module(nom)
            o=mod.Outil({'dossier':td},None,None)
            if nom=='copie':
                o.hors_bac={'essai'};o.valeurs=lambda:{'copie':td,'branche':'branche','sujet':'sujet','port':'port'}
            r=o.executer(COMMANDE,'essai')
            self.assertTrue(r.returncode==0,'script non exécuté')
            self.assertTrue(TEMOIN not in str(json.loads(r.stdout)),'script dans argv bash')
    def test_commandes(self): self.verifier('commandes')
    def test_copie(self): self.verifier('copie')
    def test_pile(self):
        with tempfile.TemporaryDirectory() as td:
            appels=[]
            def run(argv,**kw):
                r=subprocess.run(argv,**kw);appels.append(r);return r
            env=dict(subprocess=SimpleNamespace(run=run),shlex=shlex)
            if (SRC/'courtier/outils/_transport.py').exists(): env['_transport']=module('_transport')
            arbre=ast.parse((SRC/'bin/berger').read_text());n=next(n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name=='_pile')
            exec(compile(ast.Module(body=[n],type_ignores=[]),'bin/berger','exec'),env)
            # Le transport utilise le même module subprocess ; capturer son résultat sans afficher son contenu.
            if '_transport' in env:
                vrai=env['_transport'].executer_shell
                def executer(*a,**kw):
                    r=vrai(*a,**kw);appels.append(r);return r
                env['_transport']=SimpleNamespace(executer_shell=executer)
            env['_pile']({'pile_creer':COMMANDE},'creer',{'copie':td})
            self.assertTrue(appels and TEMOIN not in str(json.loads(appels[0].stdout)),'script pile dans argv')
    def test_crochet(self):
        with tempfile.TemporaryDirectory() as td:
            sorties=[]
            env=dict(subprocess=subprocess,shlex=shlex,Path=Path,json=json,os=os,
                     developpeur=lambda a:'projet',EQUIPES={'projet':{'depot':td,'crochet_ecriture':COMMANDE}},
                     conf=lambda a:{'copie':td},sys=SimpleNamespace(stdin=io.StringIO('{}')),
                     print=lambda texte:sorties.append(texte))
            if (SRC/'courtier/outils/_transport.py').exists(): env['_transport']=module('_transport')
            arbre=ast.parse((SRC/'bin/berger').read_text());n=next(n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name=='lancer_crochet_equipe')
            exec(compile(ast.Module(body=[n],type_ignores=[]),'bin/berger','exec'),env)
            env['lancer_crochet_equipe']('essai')
            temoin='contenupriveessai'
            self.assertTrue(sorties and temoin not in str(json.loads(sorties[0])),'script crochet dans argv')

    def test_bac_refuse_script_litteral(self):
        base=module('_commandes')
        with self.assertRaises(ValueError):base.bac_a_sable(COMMANDE,None,[])

    def test_stdin_et_nettoyage(self):
        transport=module('_transport')
        repertoires=[]; fds=[]
        vrai=subprocess.run
        def run(argv,**kw):
            fd=kw['pass_fds'][-1];fds.append(fd)
            self.assertTrue(os.fstat(fd).st_mode&0o777==0o600,'droits script')
            self.assertTrue('(deleted)' in os.readlink('/proc/self/fd/'+str(fd)),'fichier nommé restant')
            return vrai(argv,**kw)
        from unittest.mock import patch
        with patch.object(transport.subprocess,'run',run):
            r=transport.executer_shell('read -r ligne; test "$ligne" = contenuessai',input='contenuessai\n',text=True,capture_output=True)
        self.assertTrue(r.returncode==0,'stdin consommé par le script')
        for fd in fds:
            with self.assertRaises(OSError): os.fstat(fd)

if __name__=='__main__': unittest.main()
