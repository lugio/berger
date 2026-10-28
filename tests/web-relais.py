#!/usr/bin/env python3
"""Relais de rapports : données jetables, missions simulées, aucun service."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import datetime
import json
import types
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'courtier'))
import _web_relais
from _web_relais import Relais
ROOT=Path(__file__).resolve().parents[1]

class Rapports(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.agents=self.base/'agents'
        self.source=self.agents/'retro/analyses/site/rapport.md';self.source.parent.mkdir(parents=True);self.source.write_text('# Rapport\nObservation.\n')
        (self.agents/'chef').mkdir();(self.agents/'chef/agent.conf').write_text('nom = Chef')
        self.racine=self.base/'bibliotheque';self.dest=self.racine/'equipes/demo/projets/cabinet';self.dest.mkdir(parents=True)
        self.reg=self.base/'equipes/demo/projets.json';self.reg.parent.mkdir(parents=True);self.reg.write_text(json.dumps({'cabinet':{'membres':['chef']}}))
        self.equipes={'demo':{'chef_projet':'chef'}};self.missions=[]
        self.relais=Relais(self.base,self.racine,self.equipes,lambda t:'temoin' in t,lambda *a:self.missions.append(a))
    def apercu(self):
        args=['cabinet','analyses/site/rapport.md'];texte=self.relais.apercu('retro',args);return args,texte
    def test_validation_avant_depot_et_succes(self):
        args,texte=self.apercu();self.assertIn('demo/cabinet',texte);self.assertIn('chef',texte)
        self.assertEqual(len(args),3);self.assertEqual(list(self.dest.iterdir()),[]);self.assertEqual(self.missions,[])
        resultat=self.relais.executer('retro',args)
        self.assertEqual(len(list(self.dest.iterdir())),1);self.assertEqual(next(self.dest.iterdir()).read_bytes(),self.source.read_bytes())
        self.assertEqual(self.missions[0][0],'chef');self.assertEqual(self.missions[0][2],'retro')
        self.assertIn(str(next(self.dest.iterdir())),self.missions[0][1]);self.assertIn('remis',resultat)
        self.assertEqual(self.relais.executer('retro',args),resultat);self.assertEqual(len(self.missions),1)
        self.assertEqual(json.loads(self.reg.read_text())['cabinet']['membres'],['chef'])
    def test_pas_de_hash_manuel(self):
        with self.assertRaises(ValueError):self.relais.apercu('retro',['cabinet','site/rapport.md','0'*64])
        with self.assertRaises(ValueError):self.relais.executer('retro',['cabinet','site/rapport.md'])
    def test_source_scope_liens_et_fifo(self):
        for path in ('../rapport.md','analyses/../rapport.md','/etc/passwd','site//rapport.md','./rapport.md'):
            with self.assertRaises((ValueError,PermissionError)):self.relais.apercu('retro',['cabinet',path])
        self.source.unlink();self.source.symlink_to(self.reg)
        with self.assertRaises(PermissionError):self.apercu()
        self.source.unlink();os.mkfifo(self.source)
        with self.assertRaises(PermissionError):self.apercu()
        self.source.unlink();self.source.parent.rename(self.source.parent.with_name('ailleurs'));self.source.parent.symlink_to(self.source.parent.with_name('ailleurs'))
        with self.assertRaises(PermissionError):self.apercu()
    def test_secret_avant_apercu_et_execution(self):
        self.source.write_text('temoin')
        with self.assertRaises(PermissionError):self.apercu()
        self.assertFalse((self.base/'courtier/validations/web-remises').exists())
        self.source.write_text('propre');args,_=self.apercu();self.relais.filtre=lambda t:True
        with self.assertRaises(PermissionError):self.relais.executer('retro',args)
        self.assertEqual(list(self.dest.iterdir()),[])
    def test_modification_et_identite(self):
        args,_=self.apercu();self.source.write_text('autre')
        with self.assertRaises(ValueError):self.relais.executer('retro',args)
        with self.assertRaises(ValueError):self.relais.executer('autre',args)
        self.assertEqual(self.missions,[]);self.assertEqual(list(self.dest.iterdir()),[])
    def test_projet_et_chef(self):
        with self.assertRaises(ValueError):self.relais.apercu('retro',['absent','site/rapport.md'])
        other=self.base/'equipes/autre/projets.json';other.parent.mkdir(parents=True);other.write_text(self.reg.read_text());self.equipes['autre']={'chef_projet':'chef'}
        with self.assertRaises(ValueError):self.apercu()
        args=['demo/cabinet','site/rapport.md'];self.relais.apercu('retro',args)
        self.equipes['demo']['chef_projet']='inconnu'
        with self.assertRaises(ValueError):self.relais.executer('retro',args)
        self.assertEqual(self.missions,[])
    def test_chef_occupe_et_mission_echec_non_rejouee(self):
        args,_=self.apercu();mission=self.agents/'chef/MISSION.md';mission.write_text('occupé')
        with self.assertRaises(RuntimeError):self.relais.executer('retro',args)
        self.assertEqual(list(self.dest.iterdir()),[]);mission.unlink()
        def echec(*args):self.missions.append(args);raise RuntimeError('temoin')
        self.relais.mission=echec
        with self.assertRaisesRegex(RuntimeError,'mission'):self.relais.executer('retro',args)
        with self.assertRaisesRegex(RuntimeError,'mission'):self.relais.executer('retro',args)
        self.assertEqual(len(self.missions),1);self.assertEqual(len(list(self.dest.iterdir())),1)
    def test_bornes_utf8_et_vide(self):
        for brut in (b'',b'  \n',b'\xff',b'x'*(_web_relais.MAX_RAPPORT+1)):
            self.source.write_bytes(brut)
            with self.assertRaises(ValueError):self.apercu()
        self.assertEqual(self.missions,[])
    def test_snapshot_et_arguments_forges(self):
        args,_=self.apercu();temoin=args[-1]
        for faux in ([args[0],args[1],'0'*32],[args[0],'analyses/autre.md',temoin],['autre/projet',args[1],temoin]):
            with self.assertRaises((ValueError,FileNotFoundError)):self.relais.executer('retro',faux)
        self.assertEqual(self.missions,[]);self.assertEqual(list(self.dest.iterdir()),[])
    def test_depot_exclusif(self):
        args,_=self.apercu();d=json.loads((self.relais.snapshots/(args[-1]+'.json')).read_text())
        cible=self.dest/d['destination'];cible.symlink_to(self.source)
        with self.assertRaises(RuntimeError):self.relais.executer('retro',args)
        self.assertEqual(self.source.read_text(),'# Rapport\nObservation.\n');self.assertEqual(self.missions,[])
    def test_outil_integration_validation(self):
        arbre=ast.parse((ROOT/'courtier/courtier').read_text())
        noms={'OutilWeb','demander_validation','mission_rapport_web'}
        extrait=ast.Module(body=[n for n in arbre.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in noms],type_ignores=[])
        class Contexte:
            @staticmethod
            def ContexteDeLAppel(defaut):return defaut
        env=dict(_contexte=Contexte,CONFIG={},Path=Path,os=os,BERGER=self.base,EQUIPES=self.equipes,
                 contient_secret=self.relais.filtre,_web_relais=_web_relais,datetime=datetime,json=json,
                 VALIDATIONS=self.base/'courtier/validations',echange=lambda *a:None,notifier_proprietaire=lambda *a:None)
        exec(compile(extrait,'courtier extrait','exec'),env)
        o=env['OutilWeb']();o.relais.mission=self.relais.mission
        env['ECRITURES']={'web':o.ecritures};env['OBJETS']={'web':o}
        env['contexte']=lambda outil,agent:setattr(o,'contexte',{'agent':agent})
        self.assertNotIn('remettre',o.verbes)
        n,_=env['demander_validation']('retro','web','remettre',['cabinet','site/rapport.md'])
        demande=json.loads((env['VALIDATIONS']/f'{n}.json').read_text())
        self.assertIsNone(demande['valideur']);self.assertEqual(len(demande['args']),3)
        self.assertEqual(list(self.dest.iterdir()),[]);self.assertEqual(self.missions,[])
        args=list(demande['args'])
        with self.assertRaises(ValueError):o.ajuster('remettre',args,{'duree':'8h'})
        self.assertEqual(args,demande['args'])
        calls=[]
        env['_transport']=types.SimpleNamespace(executer=lambda programme,args,**kw:(calls.append((programme,args,kw)) or types.SimpleNamespace(returncode=0)))
        env['mission_rapport_web']('chef','rapport','retro')
        self.assertTrue(calls[0][:2]==(str(self.base/'bin/berger'),['mission','chef','rapport','--par','retro']),'commande métier altérée')
        self.assertTrue(calls[0][2]['capture_output'])
        env['CONFIG']={'bibliotheque':{'racine':str(self.base/'personnalisee')}}
        self.assertEqual(env['OutilWeb']().relais.racine,self.base/'personnalisee')
    def test_destination_lien(self):
        args,_=self.apercu();self.dest.rmdir();self.dest.symlink_to(self.source.parent)
        with self.assertRaises(PermissionError):self.relais.executer('retro',args)
        self.assertEqual(self.missions,[])

if __name__=='__main__':unittest.main()
