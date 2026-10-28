#!/usr/bin/env python3
"""Connexion propriétaire, uniquement faux proxy/capture ; aucun socket."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import sys
import shutil
import subprocess
import os
from contextlib import contextmanager
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'courtier'))
import _web_connexion as C
from _web_session import SessionCoffre
import _web as W

class Connexion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.etats = self.base/'web'; self.etats.mkdir()
        self.f = self.etats/'alice.json'; self.lease = dict(agent='alice', noms=['site.test'], session=True, fin_ts=200, socket='/unused')
        self.f.write_text(json.dumps(self.lease)); self.backups=[]
        self.store = SessionCoffre(self.base/'coffre.json', lambda:self.backups.append(True), horloge=lambda:100)
        self.store.coffre.write_text('{}')
        self.proxies=[]
        outer=self
        class Proxy:
            empreinte='SPKI'
            def __init__(self,*args,**kw): self.kw=kw; self.stop=False; outer.proxies.append(self)
            def ecouter_local(self): return 12345
            def arreter(self): self.stop=True
        self.proxy=Proxy
    def run_connect(self, capture=None):
        return C.connecter('site.test', self.etats, self.base/'profils', self.store,
            {'node':'/fake/node','playwright_module':'/fake/pw.mjs','navigateur':'/fake/chromium'},
            ROOT/'bin/berger-web-connecter.mjs', fabrique=self.proxy, capture=capture or (lambda *a,**k:{'cookies':[]}), horloge=lambda:100)
    def test_succes(self):
        def capture(runtime, helper, domaine, proxy, spki, profil, valide):
            self.assertEqual((domaine,proxy,spki), ('site.test','http://127.0.0.1:12345','SPKI'))
            self.assertEqual(profil.stat().st_mode & 0o777,0o700); self.assertTrue(valide())
            return {'cookies':[], 'origins':[]}
        self.run_connect(capture)
        self.assertEqual(self.store.lire('site.test')['agent'],'alice'); self.assertEqual(self.backups,[True])
        self.assertTrue(self.proxies[0].stop); self.assertEqual(list((self.base/'profils').iterdir()),[])
    def test_refus(self):
        for change in ({'session':False},{'fin_ts':99},{'noms':['other.test']}, {'session':None}):
            self.f.write_text(json.dumps(self.lease|change))
            with self.assertRaises(C.ConnexionRefusee): self.run_connect()
        self.assertEqual(self.proxies,[])
    def test_multiple_et_nettoyage(self):
        (self.etats/'bob.json').write_text(json.dumps(self.lease|{'agent':'bob'}))
        with self.assertRaises(C.ConnexionRefusee):self.run_connect()
        (self.etats/'bob.json').unlink(); (self.etats/'nettoyage').mkdir()
        (self.etats/'nettoyage/site.test.json').write_text('{}')
        with self.assertRaises(C.ConnexionRefusee):self.run_connect()
    def test_fermeture_remplacement_et_erreur(self):
        for action in ('fermer','remplacer','erreur','annuler'):
            self.f.write_text(json.dumps(self.lease))
            def capture(*args):
                if action=='fermer': self.f.unlink()
                if action=='remplacer': self.f.write_text(json.dumps(self.lease|{'fin_ts':201}))
                if action=='erreur': raise RuntimeError('temoin')
                if action=='annuler': raise KeyboardInterrupt()
                return {'cookies':[]}
            with self.assertRaises((C.ConnexionRefusee,KeyboardInterrupt)):self.run_connect(capture)
            self.assertIsNone(self.store.lire('site.test')); self.assertEqual(list((self.base/'profils').iterdir()),[])
            self.assertTrue(self.proxies[-1].stop)
    def test_remplacement_sous_verrou(self):
        verrou=self.store._verrou
        @contextmanager
        def remplacer():
            with verrou():
                self.f.write_text(json.dumps(self.lease|{'fin_ts':201}))
                yield
        self.store._verrou=remplacer
        with self.assertRaises(C.ConnexionRefusee):self.run_connect()
        self.assertEqual(json.loads(self.store.coffre.read_text()),{}); self.assertFalse(self.backups)
    def test_coffre_prive_requis(self):
        self.base.chmod(0o755)
        try:
            with self.assertRaises(C.ConnexionRefusee):self.run_connect()
            self.assertFalse(self.proxies)
        finally:self.base.chmod(0o700)
    def test_runtime_explicite(self):
        for c in ({},{'web':{'node':'relative','navigateur':'/x','playwright_module':'/y'}}):
            with self.assertRaises(C.ConnexionRefusee):C.runtime_config(c)
    def test_autoriser_sous_verrou(self):
        vus=[]; original=self.store._charger
        verrou=self.store._verrou; actif=[]
        @contextmanager
        def surveiller():
            with verrou():
                actif.append(True)
                try:yield
                finally:actif.pop()
        self.store._verrou=surveiller
        def autoriser():
            self.assertEqual(actif,[True]); vus.append('autoriser'); return False
        self.store._charger=lambda: (vus.append('charger') or original())
        with self.assertRaises(ValueError):
            self.store.enregistrer('site.test','alice',{},200,autoriser=autoriser)
        self.assertEqual(vus,['autoriser']); self.assertFalse(self.backups)

class Methodes(unittest.TestCase):
    def test_post_proprietaire_seulement(self):
        p=W.Proxy.__new__(W.Proxy)
        p.post_autorise=True; p.session_pretee=False; p.chemins_bloques=()
        p._verifier=lambda *a:('site.test',['203.0.113.1'])
        def temoin(*args): raise LookupError('amont factice atteint')
        p._connecter=temoin
        args=(None,'POST','https://site.test/',b'', [('Host','site.test')], {'tls':True})
        with self.assertRaises(LookupError):p._http(*args)
        p.session_pretee=True
        with self.assertRaises(W.Refus):p._http(*args)
        p.session_pretee=False; p.post_autorise=False
        with self.assertRaises(W.Refus):p._http(*args)

class Helper(unittest.TestCase):
    def test_capture_env_et_annulation(self):
        class Processus:
            returncode=None
            stop=False
            def poll(self):return self.returncode
            def terminate(self):self.stop=True; self.returncode=1
            def communicate(self,timeout=None):return (b'{}',b'temoin non publie')
        p=Processus(); vu={}
        def popen(args,**kw):vu.update(kw); return p
        with patch.object(C.subprocess,'Popen',popen):
            with self.assertRaises(C.ConnexionRefusee):
                C.capturer({'node':'/fake','playwright_module':'/module','navigateur':'/browser'},'helper','site.test','proxy','spki',Path('/private/profile'),lambda:False)
        self.assertTrue(p.stop)
        for k in ('TMPDIR','TMP','TEMP'):self.assertEqual(vu['env'][k],'/private/profile')
        self.assertEqual(vu['stdout'],subprocess.PIPE); self.assertEqual(vu['stderr'],subprocess.PIPE)
    def test_module_factice(self):
        node=shutil.which('node')
        if not node: self.skipTest('node absent')
        with tempfile.TemporaryDirectory() as t:
            t=Path(t); module=t/'fake.mjs'; trace=t/'trace.json'
            module.write_text("""
import fs from 'node:fs';
const trace=[];
export const chromium={launch:async options=>{
 trace.push(options);
 if(process.env.ECHEC) throw Error('temoin');
 return {newContext:async()=>({newPage:async()=>({
 waitForEvent:async(type,opts)=>{trace.push(['close',type,opts]);},
 goto:async url=>{trace.push(url);}}),
 storageState:async()=>{trace.push('collecte');return {cookies:[
 {domain:'site.test',name:'sid',value:'temoin'}, {domain:'other.test',name:'x',value:'bad'}],
 origins:[{origin:'https://site.test',localStorage:[]},{origin:'https://other.test'}]};}}),
 close:async()=>{trace.push('browser.close');fs.writeFileSync(process.env.TRACE,JSON.stringify(trace));}};
}};
""")
            r=subprocess.run([node,str(ROOT/'bin/berger-web-connecter.mjs'),str(module),'/fake/browser','site.test','http://127.0.0.1:1234','SPKI'],capture_output=True,env=dict(os.environ,TRACE=str(trace)))
            self.assertEqual(r.returncode,0,r.stderr)
            state=json.loads(r.stdout); self.assertEqual(len(state['cookies']),1); self.assertEqual(len(state['origins']),1)
            tr=json.loads(trace.read_text()); opts=tr[0]
            self.assertIs(opts['headless'],False); self.assertIs(opts['chromiumSandbox'],True)
            self.assertEqual(opts['proxy'],{'server':'http://127.0.0.1:1234','bypass':'<-loopback>'})
            self.assertIn('--ignore-certificate-errors-spki-list=SPKI',opts['args'])
            self.assertNotIn('ignoreHTTPSErrors',opts); self.assertEqual(tr[-2:],['collecte','browser.close'])
            r=subprocess.run([node,str(ROOT/'bin/berger-web-connecter.mjs'),str(module),'/fake/browser','site.test','http://127.0.0.1:1234','SPKI'],capture_output=True,env=dict(os.environ,TRACE=str(trace),ECHEC='1'))
            self.assertEqual(r.returncode,1); self.assertEqual(r.stdout,b''); self.assertNotIn(b'temoin',r.stderr)

if __name__=='__main__':unittest.main()
