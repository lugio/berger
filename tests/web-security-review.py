#!/usr/bin/env python3
"""Régressions de la revue propriétaire : flux factices, aucun service ni vrai coffre."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('web_revue',ROOT/'courtier/_web.py')
W=importlib.util.module_from_spec(spec);spec.loader.exec_module(W)
def fonctions(fichier,noms,env):
    if '_transport' not in env and 'subprocess' in env:
        env['_transport']=types.SimpleNamespace(
            executer=lambda programme,args,**kw:env['subprocess'].run([programme,*args],**kw),
            lancer=lambda programme,args,**kw:env['subprocess'].Popen([programme,*args],**kw))
    arbre=ast.parse((ROOT/fichier).read_text())
    corps=[n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name in noms]
    exec(compile(ast.Module(body=corps,type_ignores=[]),fichier,'exec'),env)
    return env

class Methodes(unittest.TestCase):
    def test_surcharges_refusees_avant_cookie_et_amont(self):
        cas=[('https://site.test/',[(nom,'DELETE')],b'') for nom in
             ('X-HTTP-Method-Override','x-http-method','X-Method-Override')]
        cas += [('https://site.test/',[('Content-Type','application/json')],json.dumps({'_method':'DELETE'}).encode('utf-16')),
                ('https://site.test/?_method=DELETE',[],b''),
                ('https://site.test/?%5fMeThOd=GET',[],b''),
                ('https://site.test/?action=delete',[],b''),
                ('https://site.test/',[('Content-Type','application/x-www-form-urlencoded')],b'_method=DELETE'),
                ('https://site.test/',[('Content-Type','multipart/form-data; boundary=essai')],
                 b'--essai\r\nContent-Disposition: form-data; name=_method\r\n\r\nDELETE\r\n--essai--\r\n')]
        for url,entetes,corps in cas:
            with self.subTest(url=url,entetes=entetes):
                p=W.Proxy.__new__(W.Proxy);p.post_autorise=False;p.session_pretee=True;p.chemins_bloques=W.CHEMINS_BLOQUES
                p._verifier=lambda *a:('site.test',['8.8.8.8']);acces=[]
                p.fournisseur_cookie=lambda *a:(acces.append('cookie') or 'sid=valeurfactice')
                p.fournisseur_valeurs=lambda *a:{'valeurfactice'}
                def connecter(*a):acces.append('amont');raise LookupError('amont factice')
                p._connecter=connecter
                verdict='accepte'
                try:p._http(None,'GET',url,corps,[('Host','site.test'),('Content-Length',str(len(corps))),*entetes],{'tls':True,'fin':99999999999})
                except W.Refus:verdict='refuse'
                except LookupError:pass
                self.assertEqual((verdict,acces),('refuse',[]))

class Echeances(unittest.TestCase):
    def test_sauvegarde_bloquee_ne_retarde_pas_un_autre_acces(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);entre=threading.Event();libere=threading.Event();ferme=threading.Event()
            class Sessions:
                def cookie(self,*a,**kw):return ''
                def effacer(self,*a):entre.set();libere.wait(3)
            class Proxy:
                empreinte='publique'
                def __init__(self,noms,journal):self.noms=noms;self.stop=False
                def ecouter(self,chemin):Path(chemin).touch()
                def arreter(self):
                    self.stop=True
            def journal(agent,outil,verbe,*args):
                if agent=='bob' and verbe=='fermer':ferme.set()
            a=W.Acces(base/'sockets',base/'etats',journal,lambda *a:None,Proxy,sessions=Sessions())
            a.ouvrir('alice',['site.test'],60,session=True)
            a.ouvrir('bob',['autre.test'],0.2)
            proxy_bob=a.ouvert('bob')['proxy']
            fil=threading.Thread(target=lambda:a.fermer('alice','test'),daemon=True)
            fil.start()
            try:
                self.assertTrue(entre.wait(1),'nettoyage non atteint')
                self.assertTrue(ferme.wait(1),'autre proxy expiré encore ouvert derrière la sauvegarde')
                self.assertTrue(proxy_bob.stop)
                self.assertFalse(a.chemin('bob').exists())
            finally:
                libere.set();fil.join(3)
                a.fermer('bob','fin du test')

class ApercuPrive(unittest.TestCase):
    def test_aucun_argv_prive_jusqu_aux_notifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);(b/'courtier').mkdir();v=b/'courtier/validations';argv=[]
            canari='contenupriveessai'
            env_bin=dict(Path=Path,json=json,datetime=datetime,ECHANGES=b/'courtier/echanges.jsonl',BERGER=b,
                shutil=types.SimpleNamespace(which=lambda x:True),NOTIFY_SEND='notify-factice',HERDR='herdr-factice')
            def run(args,**kw):
                argv.append(list(args))
                if args[0]==str(b/'bin/berger'):
                    if args[1]=='echange':
                        texte=kw.get('input','') if args[5:]==['--stdin'] else ' '.join(args[5:])
                        env_bin['echange'](*args[2:5],texte)
                    elif args[1]=='notifier':
                        assert args[2]=='--stdin'
                        titre,texte=json.loads(kw['input'])
                        env_bin['notifier'](titre,texte,urgent='--urgent' in args[3:])
                return types.SimpleNamespace(returncode=0)
            env_bin['subprocess']=types.SimpleNamespace(run=run,TimeoutExpired=subprocess.TimeoutExpired)
            fonctions('bin/berger',{'echange'},env_bin); fonctions('bin/noyau/bandeaux.py',{'notifier'},env_bin)   # notifier : dans le noyau depuis le lot 3 bis
            env=dict(BERGER=b,VALIDATIONS=v,datetime=datetime,json=json,os=os,
                ECRITURES={'web':{'remettre':(lambda args:canari,lambda args:None)}},
                contexte=lambda *a:None,OBJETS={'web':types.SimpleNamespace(valideur=lambda *a:None)},
                CONFIG={'proprietaire':'proprietaire-factice'},contient_secret=lambda t:False,
                subprocess=types.SimpleNamespace(run=run,Popen=lambda args,**kw:argv.append(list(args))))
            fonctions('courtier/courtier',{'demander_validation','echange','notifier_proprietaire'},env)
            n,_=env['demander_validation']('retro','web','remettre',['projet','rapport.md'])
            self.assertEqual(json.loads((v/f'{n}.json').read_text())['apercu'],canari)
            self.assertEqual((v/f'{n}.json').stat().st_mode & 0o777,0o600)
            self.assertFalse(any(canari in str(a) for a in argv),'aperçu privé présent dans un argv')

    def test_decision_ne_retransmet_pas_apercu_en_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            v=Path(tmp);canari='contenupriveessai';argv=[]
            d=dict(n=1,agent='essai',outil='web',verbe='remettre',args=[],apercu=canari)
            (v/'1.json').write_text(json.dumps(d));(v/'1.decision').write_text('refuser')
            env=dict(VALIDATIONS=v,BERGER=v,CONFIG={},json=json,datetime=datetime,os=os,
                decisions_en_ordre=lambda:[v/'1.decision'],file_tenue=lambda:False,fermeture_active=lambda:False,
                journal_agent=lambda *a:None,journal=lambda *a:None,echange=lambda *a:None,
                subprocess=types.SimpleNamespace(Popen=lambda args,**kw:argv.append(args),DEVNULL=-3))
            fonctions('courtier/courtier',{'traiter_decisions'},env);env['traiter_decisions']()
            self.assertFalse(any(canari in str(a) for a in argv))
            self.assertEqual((v/'1.fait.json').stat().st_mode & 0o777,0o600)

class ValeursCourtes(unittest.TestCase):
    def test_une_valeur_courte_ne_bloque_pas_une_reponse_innocente(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'coffre-factice.json'
            f.write_text(json.dumps({'web-session:site.test':{'etat':{'cookies':[{'value':'z'},{'value':'abcdefg'},{'value':'abcdefgh'}],
                'origins':[{'localStorage':[{'value':'ok'},{'value':'temoinfictif'}]}]}}}))
            env=dict(os=os,json=json,re=re,sys=sys,COFFRE=f,_COFFRE_LU=(None,set()),_SESSIONS_RETENUES=set(),MOTIFS_CLES=re.compile(r'(?!)'))
            fonctions('courtier/courtier',{'valeurs_du_coffre','contient_secret'},env)
            self.assertFalse(env['contient_secret']('réponse innocente : 1 élément ok'))
            self.assertEqual(env['valeurs_du_coffre'](),{'abcdefgh','temoinfictif'})
            f.write_text('{}')
            self.assertTrue(env['contient_secret']('abcdefgh'))
            self.assertFalse(env['contient_secret']('1 élément ok'))
if __name__=='__main__':unittest.main()
