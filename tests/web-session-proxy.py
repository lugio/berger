#!/usr/bin/env python3
"""Session prêtée : flux simulés seulement, aucun socket."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import gzip
import json
import os
import re
import sys
import time
import threading
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('web', Path(__file__).resolve().parents[1] / 'courtier/_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
class Flux:
    def __init__(self): self.sortie = b''; self.entree = b'HTTP/1.1 200 OK\r\nSet-Cookie: nouveau=temoin\r\nContent-Length: 0\r\n\r\n'
    def sendall(self, x): self.sortie += x
    def settimeout(self, x): pass
    def recv(self, n): x, self.entree = self.entree[:n], self.entree[n:]; return x
    def do_handshake(self): pass
class Tests(unittest.TestCase):
    def proxy(self, fournisseur=lambda h, p: 'sid=factice'):
        with patch.object(W, 'certificat_ephemere', return_value=(b'', '', {})):
            p = W.Proxy(['site.test'], lambda *x: None, session_pretee=True, fournisseur_cookie=fournisseur)
        p.fournisseur_valeurs = lambda h: {'factice'}
        p._verifier = lambda h, port: (h, ['8.8.8.8'])
        self.amont = Flux(); self.connexions = []
        p._connecter = lambda *x: (self.connexions.append(1) or self.amont)
        p.tls_amont = type('TLS', (), {'wrap_socket': lambda s, b, **k: b})()
        return p
    def verifier_encodage_session(self, encoder, verifier_base64=False):
        # Valeur connue de stockage local : lettres Unicode minuscules, cookie HTTP ASCII.
        temoin = 'temoinfictif\u00ff\u00fe\u00fea' if verifier_base64 else 'temoinfictifabcdefghj'
        if verifier_base64:
            brut = temoin.encode()
            standard = W.base64.b64encode(brut)
            urlsafe = W.base64.urlsafe_b64encode(brut)
            self.assertTrue(temoin.isalpha() and temoin.islower())
            self.assertTrue(all(c in standard for c in (b'+', b'/', b'=')))
            self.assertTrue(len({standard, standard.rstrip(b'='), urlsafe, urlsafe.rstrip(b'=')}) == 4)
        reflet = encoder(temoin.encode())
        p = self.proxy(lambda *a: 'temoin=factice')
        p.fournisseur_valeurs = lambda h: {temoin}
        corps = b'avant-'+reflet+b'-apres'
        milieu = len(corps)//2
        morceaux = (corps[:milieu], corps[milieu:])
        self.amont.entree = (b'HTTP/1.1 200 OK\r\nX-Echo: '+reflet+
            b'\r\nTransfer-Encoding: chunked\r\n\r\n'+
            b''.join(format(len(m), 'x').encode()+b'\r\n'+m+b'\r\n' for m in morceaux)+b'0\r\n\r\n')
        recv = self.amont.recv
        self.amont.recv = lambda n: recv(min(n, 2))
        c = Flux()
        p._http(c, 'GET', 'https://site.test/', b'', [('Host','site.test')], {'tls':True,'fin':99999999999})
        tete, corps = c.sortie.split(b'\r\n\r\n', 1)
        self.assertTrue(b'X-Echo: \r\n' in tete+b'\r\n')
        self.assertTrue(corps == b'avant--apres')
        self.assertTrue(b'Content-Length: '+str(len(corps)).encode() in tete)

    def test_fixture_base64_distinctive(self):
        self.verifier_encodage_session(W.base64.b64encode, verifier_base64=True)

    def test_session_hexadecimal_casse_mixte(self):
        def encoder(v):
            code = v.hex().encode()
            lettres = 0
            mixte = bytearray()
            for c in code:
                if 97 <= c <= 102:
                    lettres += 1
                    if lettres % 2: c -= 32
                mixte.append(c)
            resultat = bytes(mixte)
            self.assertTrue(resultat != code and resultat != code.upper())
            return resultat
        self.verifier_encodage_session(encoder)

    def test_session_base64_standard(self):
        self.verifier_encodage_session(W.base64.b64encode, verifier_base64=True)

    def test_session_base64_standard_sans_remplissage(self):
        self.verifier_encodage_session(lambda v: W.base64.b64encode(v).rstrip(b'='), verifier_base64=True)

    def test_session_base64_urlsafe(self):
        self.verifier_encodage_session(W.base64.urlsafe_b64encode, verifier_base64=True)

    def test_session_base64_urlsafe_sans_remplissage(self):
        self.verifier_encodage_session(lambda v: W.base64.urlsafe_b64encode(v).rstrip(b'='), verifier_base64=True)

    def test_session_pourcentage_majuscule(self):
        self.verifier_encodage_session(lambda v: ''.join('%%%02X' % x for x in v).encode())

    def test_session_pourcentage_minuscule(self):
        self.verifier_encodage_session(lambda v: ''.join('%%%02x' % x for x in v).encode())

    def test_session_hexadecimal_minuscule(self):
        self.verifier_encodage_session(lambda v: v.hex().encode())

    def test_session_hexadecimal_majuscule(self):
        self.verifier_encodage_session(lambda v: v.hex().upper().encode())

    def test_cookie_et_reponse(self):
        for methode in ('GET', 'HEAD'):
            appels = []; p = self.proxy(lambda h, path: (appels.append((h, path)) or 'sid=factice'))
            c = Flux(); p._http(c, methode, 'https://site.test/zone?x=y', b'', [('Host','site.test'), ('Cookie','client=mal')], {'tls':True,'fin':99999999999})
            self.assertIn(b'Cookie: sid=factice', self.amont.sortie); self.assertNotIn(b'client=mal', self.amont.sortie)
            self.assertNotIn(b'Set-Cookie', c.sortie); self.assertEqual(appels, [('site.test', '/zone')])
    def test_refus_fermes(self):
        for methode, tls in [('POST',True),('DELETE',True),('GET',False)]:
            p = self.proxy()
            with patch.object(W, 'METHODES', ('GET','HEAD','POST','DELETE')):
                with self.assertRaises(W.Refus): p._http(Flux(), methode, ('https' if tls else 'http')+'://site.test/', b'', [('Host','site.test')], {'tls':tls})
            self.assertFalse(self.connexions)
        p = self.proxy(lambda *x: (_ for _ in ()).throw(RuntimeError('temoin')))
        with self.assertRaises(W.Refus) as e: p._http(Flux(),'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True})
        self.assertNotIn('temoin',str(e.exception)); self.assertFalse(self.connexions)
    def test_reflexion_entetes_corps_fragmente_et_longueur(self):
        p=self.proxy(lambda *a:'sid=abc');p.fournisseur_valeurs=lambda h:{'abc','localfactice'}
        self.amont.entree=b'HTTP/1.1 200 OK\r\nX-Session: abc\r\nContent-Length: 29\r\n\r\navant-abc-et-localfactice-fin!'
        corps=b'avant-abc-et-localfactice-fin!'
        self.amont.entree=self.amont.entree.replace(b'29',str(len(corps)).encode(),1)
        recv=self.amont.recv;self.amont.recv=lambda n:recv(min(n,2))
        c=Flux();p._http(c,'GET','https://site.test/',b'',[('Host','site.test'),('Accept-Encoding','gzip, br')],{'tls':True,'fin':99999999999})
        self.assertNotIn(b'abc',c.sortie);self.assertNotIn(b'localfactice',c.sortie)
        tete,body=c.sortie.split(b'\r\n\r\n',1)
        self.assertIn(b'Content-Length: '+str(len(body)).encode(),tete)
        self.assertIn(b'Accept-Encoding: identity',self.amont.sortie);self.assertNotIn(b'gzip',self.amont.sortie)
    def test_chunked_reflexion_a_cheval_des_chunks(self):
        p=self.proxy(lambda *a:'sid=abc');p.fournisseur_valeurs=lambda h:{'abc'}
        self.amont.entree=b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n-a\r\n3\r\nbc-\r\n0\r\n\r\n'
        c=Flux();p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
        self.assertNotIn(b'abc',c.sortie);self.assertNotIn(b'Transfer-Encoding',c.sortie)
        tete,body=c.sortie.split(b'\r\n\r\n',1);self.assertEqual(body,b'--');self.assertIn(b'Content-Length: 2',tete)
    def test_compression_fournisseur_en_panne_et_reponse_incomplete_sans_publication(self):
        for reponse in (b'HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\nContent-Length: 3\r\n\r\nabc',
                         b'HTTP/1.1 200 OK\r\nContent-Length: 9\r\n\r\nabc',
                         b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Length: 3\r\n\r\nabc'):
            p=self.proxy();p.fournisseur_valeurs=lambda h:{'factice'};self.amont.entree=reponse;c=Flux()
            with self.assertRaises(W.Refus):p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
            self.assertEqual(c.sortie,b'')
        p=self.proxy();p.fournisseur_valeurs=lambda h:(_ for _ in ()).throw(RuntimeError('temoin'));c=Flux()
        with self.assertRaises(W.Refus):p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
        self.assertEqual(c.sortie,b'');self.assertEqual(self.connexions,[])
    def test_valeur_courte_et_variantes_standard(self):
        cas=[('z',b'azb',b'ab'),('a<b',b'a&lt;b',b''),('a/b',b'a%2Fb',b''),('a"b',b'a\\"b',b'')]
        for temoin,corps,attendu in cas:
            with self.subTest(temoin=temoin):
                p=self.proxy(lambda *a:'sid='+temoin);p.fournisseur_valeurs=lambda h:{temoin}
                self.amont.entree=b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(corps)).encode()+b'\r\n\r\n'+corps
                c=Flux();p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
                tete,body=c.sortie.split(b'\r\n\r\n',1);self.assertEqual(body,attendu);self.assertTrue(tete.startswith(b'HTTP/1.1 200 OK'))
    def test_eof_fragmente_et_refus_cadrages_bornes_trailers_gzip(self):
        p=self.proxy(lambda *a:'sid=abc');p.fournisseur_valeurs=lambda h:{'abc'}
        self.amont.entree=b'HTTP/1.1 200 OK\r\n\r\n-abc-';recv=self.amont.recv;self.amont.recv=lambda n:recv(min(n,1))
        c=Flux();p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
        self.assertEqual(c.sortie.split(b'\r\n\r\n',1)[1],b'--')
        zippe=gzip.compress(b'abc')
        mauvaises=[b'Content-Length: 2097153\r\n\r\n',b'Content-Length: 3\r\nContent-Length: 3\r\n\r\nabc',
                    b'Transfer-Encoding: chunked\r\n\r\n0\r\nX-Session: abc\r\n\r\n',
                    b'Transfer-Encoding: chunked\r\n\r\n3\r\nabcXX0\r\n\r\n',
                    b'Content-Encoding: gzip\r\nContent-Length: '+str(len(zippe)).encode()+b'\r\n\r\n'+zippe]
        for cadrage in mauvaises:
            p=self.proxy();self.amont.entree=b'HTTP/1.1 200 OK\r\n'+cadrage;c=Flux()
            with self.assertRaises(W.Refus):p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
            self.assertEqual(c.sortie,b'')
    def test_fournisseur_panne_apres_collecte_et_redirection_ne_reflete_pas(self):
        p=self.proxy();appels=[]
        def valeurs(h):
            appels.append(1)
            if len(appels)>1:raise RuntimeError('temoin')
            return {'factice'}
        p.fournisseur_valeurs=valeurs;c=Flux()
        with self.assertRaises(W.Refus):p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
        self.assertEqual(c.sortie,b'');self.assertEqual(len(self.connexions),1)
        p=self.proxy();self.amont.entree=b'HTTP/1.1 302 Found\r\nLocation: https://factice.other.test/\r\nContent-Length: 0\r\n\r\n';c=Flux()
        with self.assertRaises(W.Refus) as e:p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
        self.assertNotIn('factice',str(e.exception));self.assertEqual(c.sortie,b'')
    def test_reason_location_et_range_sont_traités_hors_cadrage(self):
        p=self.proxy(lambda *a:'sid=abc');p.fournisseur_valeurs=lambda h:{'abc'}
        self.amont.entree=b'HTTP/1.1 302 abc\r\nLocation: https://site.test/?sid=abc\r\nContent-Length: 0\r\n\r\n';c=Flux()
        p._http(c,'GET','https://site.test/',b'',[('Host','site.test'),('Range','bytes=0-2'),('If-Range','abc')],{'tls':True,'fin':99999999999})
        self.assertNotIn(b'abc',c.sortie);self.assertIn(b'Location: https://site.test/?sid=',c.sortie)
        self.assertNotIn(b'Range:',self.amont.sortie)
        p=self.proxy();self.amont.entree=b'HTTP/1.1 200 OK\r\n\r\n12345';c=Flux()
        with patch.object(W,'REPONSE_SESSION_MAX',4):
            with self.assertRaises(W.Refus):p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
        self.assertEqual(c.sortie,b'')
    def test_refus_charset_bom_et_reflexions_echappees_mixtes(self):
        cas=[(b'Content-Type: text/html; charset=utf-16\r\n','abc'.encode('utf-16')),
             (b'', 'abc'.encode('utf-16')),(b'',b'a&#98;c'),(b'',b'a\\u0062c')]
        for entetes,corps in cas:
            p=self.proxy(lambda *a:'sid=abc');p.fournisseur_valeurs=lambda h:{'abc'};c=Flux()
            self.amont.entree=b'HTTP/1.1 200 OK\r\n'+entetes+b'Content-Length: '+str(len(corps)).encode()+b'\r\n\r\n'+corps
            with self.assertRaises(W.Refus):p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
            self.assertEqual(c.sortie,b'')
    def test_reflexion_javascript_octale_legacy_refusee(self):
        cas = [('temoinfictif', br'"\164\145\155\157\151\156\146\151\143\164\151\146"'),
               ('abc', br'"\141b\143"'), ('abc', br'"a\142\u0063"'),
               ('az', br'"\141\172"')]
        for temoin, corps in cas:
            with self.subTest(corps=corps):
                p = self.proxy(lambda *a: 'sid='+temoin)
                p.fournisseur_valeurs = lambda h: {temoin}
                c = Flux()
                self.amont.entree = (b'HTTP/1.1 200 OK\r\nContent-Type: application/javascript\r\nContent-Length: '
                                    + str(len(corps)).encode() + b'\r\n\r\n' + corps)
                with self.assertRaises(W.Refus):
                    p._http(c, 'GET', 'https://site.test/', b'', [('Host','site.test')], {'tls':True,'fin':99999999999})
                self.assertEqual(c.sortie, b'')

    def test_xml_utf16_sans_bom_et_declaration_non_admise_refuses(self):
        for corps in ('<?xml version="1.0" encoding="UTF-16LE"?><r>abc</r>'.encode('utf-16-le'),
                      b'<?xml version="1.0" encoding="UTF-7"?><r>abc</r>'):
            with self.subTest(corps=corps[:16]):
                p=self.proxy(lambda *a:'sid=abc');p.fournisseur_valeurs=lambda h:{'abc'};c=Flux()
                self.amont.entree=b'HTTP/1.1 200 OK\r\nContent-Type: application/xml\r\nContent-Length: '+str(len(corps)).encode()+b'\r\n\r\n'+corps
                with self.assertRaises(W.Refus):p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
                self.assertEqual(c.sortie,b'')
    def test_reflexions_binaires_utf16_utf32_masquees(self):
        for encodage in ('utf-16-le','utf-16-be','utf-32-le','utf-32-be'):
            p=self.proxy(lambda *a:'sid=abc');p.fournisseur_valeurs=lambda h:{'abc'};c=Flux()
            corps='-abc-'.encode(encodage)
            self.amont.entree=b'HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: '+str(len(corps)).encode()+b'\r\n\r\n'+corps
            p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
            body=c.sortie.split(b'\r\n\r\n',1)[1]
            self.assertNotIn('abc'.encode(encodage),body)
    def test_refus_location_serialise_par_servir_sans_donnee_amont(self):
        p=self.proxy(lambda *a:'sid=canarireflechi');p.fournisseur_valeurs=lambda h:{'canarireflechi'}
        self.amont.entree=b'HTTP/1.1 302 Found\r\nLocation: https://canarireflechi.ailleurs.test/\r\nContent-Length: 0\r\n\r\n'
        self.amont.close=lambda:None
        class Client(Flux):
            def close(self):pass
            def unwrap(self):return self
        c=Client();c.entree=b'CONNECT site.test:443 HTTP/1.1\r\nHost: site.test:443\r\n\r\n'
        def tunnel(client,cible,reste,ctx):
            ctx.update(tls=True,client=client,m='GET')
            p._http(client,'GET','https://site.test/',b'',[('Host','site.test')],ctx)
        p._tunnel=tunnel
        p.servir(c)
        self.assertTrue(c.sortie.startswith(b'HTTP/1.1 403'))
        self.assertNotIn(b'canarireflechi',c.sortie);self.assertNotIn(b'ailleurs.test',c.sortie)
    def test_reflexion_javascript_hexadecimal_standard_refusee(self):
        for temoin,reflet in [('temoinfictif',r'\x74\x65\x6d\x6f\x69\x6e\x66\x69\x63\x74\x69\x66'),
                              ('temoinfictif',r'tem\x6finfictif'),('abc',r'a\u{62}c'),("a'b",r"a\'b")]:
            with self.subTest(reflet=reflet):
                p=self.proxy();p.fournisseur_valeurs=lambda h:{temoin};c=Flux()
                corps=("<html><body><script>document.body.textContent='"+reflet+"';</script></body></html>").encode()
                self.amont.entree=b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: '+str(len(corps)).encode()+b'\r\n\r\n'+corps
                with self.assertRaises(W.Refus):p._http(c,'GET','https://site.test/',b'',[('Host','site.test')],{'tls':True,'fin':99999999999})
                self.assertEqual(c.sortie,b'')
    def test_arguments(self):
        self.assertEqual(W.demande(['site.test','motif','--session','1h']), (['site.test'],3600,True))
        for fin in (['--session','--session'],['--inconnu'],['1h','2h']):
            with self.assertRaises(ValueError): W.demande(['site.test','motif']+fin)
        with self.assertRaises(ValueError): W.demande(['site.test,app.site.test','motif','--session'])
class Cycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.notes = []; self.backups = []
        spec = importlib.util.spec_from_file_location('sessions', Path(__file__).resolve().parents[1] / 'courtier/_web_session.py')
        S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
        self.coffre = self.base / 'coffre.json'; self.coffre.write_text('{}')
        self.sessions = S.SessionCoffre(self.coffre, lambda: self.backups.append(1))
        self.sessions.enregistrer('site.test','alice', {'cookies':[dict(name='sid',value='abc',domain='site.test',path='/zone',secure=True,expires=-1)]}, time.time()+3600)
        class Faux:
            empreinte = 'publique'
            def __init__(self, *args): self.stop = False
            def ecouter(self, chemin): Path(chemin).touch()
            def arreter(self): self.stop = True
        self.fabrique = Faux
        self.a = self.acces()
    def acces(self):
        return W.Acces(self.base/'sockets',self.base/'etats',lambda *x: None,lambda *x: self.notes.append(x),self.fabrique,sessions=self.sessions)
    def test_identite_et_etat(self):
        self.a.ouvrir('alice',['site.test'],60,session=True)
        proxy = self.a.ouvert('alice')['proxy']
        self.assertEqual(proxy.fournisseur_cookie('site.test','/zone/page'),'sid=abc')
        self.assertEqual(proxy.fournisseur_cookie('site.test','/autre'),'')
        with self.assertRaises(RuntimeError): self.a.ouvrir('bob',['site.test'],60,session=True)
        for f in self.base.rglob('*'):
            if f.is_file() and f != self.coffre: self.assertNotIn('abc',f.read_text())
        self.a.fermer('alice','test')
        self.a.ouvrir('bob',['site.test'],60,session=True)
        self.assertEqual(self.a.ouvert('bob')['proxy'].fournisseur_cookie('site.test','/zone'),'')
    def fermeture(self, mode):
        self.a.ouvrir('alice',['site.test'],60,session=True)
        proxy = self.a.ouvert('alice')['proxy']
        if mode == 'fermer': self.a.fermer('alice','test')
        elif mode == 'echeance': self.a.ouvert('alice')['fin_ts']=0; self.a.tour()
        else: self.a = self.acces(); self.a.nettoyer()
        self.assertIsNone(self.sessions.lire('site.test','alice'))
        self.assertFalse(self.a.chemin('alice').exists())
        self.assertFalse((self.base/'sockets/alice-web/spki').exists())
        self.assertTrue(any('déconnecte-toi' in str(n) for n in self.notes))
        if mode != 'redemarrer': self.assertTrue(proxy.stop)
    def test_fermeture(self): self.fermeture('fermer')
    def test_echeance(self): self.fermeture('echeance')
    def test_redemarrage(self): self.fermeture('redemarrer')
    def test_nettoyage_refuse_retry(self):
        self.a.ouvrir('alice',['site.test'],60,session=True)
        proxy = self.a.ouvert('alice')['proxy']; effacer = self.sessions.effacer
        self.sessions.effacer = lambda *x: (_ for _ in ()).throw(RuntimeError('temoin'))
        self.a.fermer('alice','test'); self.assertTrue(proxy.stop)
        self.assertFalse(self.a.chemin('alice').exists())
        marque = self.base/'etats/nettoyage/site.test.json'; self.assertTrue(marque.exists())
        self.assertNotIn('abc',marque.read_text())
        with self.assertRaises(RuntimeError): self.a.ouvrir('bob',['site.test'],60,session=True)
        self.sessions.effacer = effacer; self.a.tour(); self.assertFalse(marque.exists())
        self.assertIsNone(self.sessions.lire('site.test','alice'))

    def test_nettoyage_redemarre_et_filtre_avant_suppression(self):
        self.a.ouvrir('alice',['site.test'],60,session=True)
        effacer = self.sessions.effacer
        self.sessions.effacer = lambda *x: (_ for _ in ()).throw(RuntimeError())
        self.a.fermer('alice','test')
        self.sessions.effacer = effacer
        reprise = self.acces(); vus = []
        reprise.avant_effacer = lambda: vus.append(self.sessions.lire('site.test','alice'))
        reprise.nettoyer()
        self.assertEqual(vus[0]['agent'], 'alice')
        self.assertFalse((self.base/'etats/nettoyage/site.test.json').exists())
    def test_redemarrage_marque_refusee_reserve_et_reessaie(self):
        self.a.ouvrir('alice',['site.test'],60,session=True)
        reprise = self.acces()
        with patch.object(reprise, '_marquer', side_effect=OSError('refus factice')):
            reprise.nettoyer()
        self.assertTrue((self.base/'etats/alice.json').exists())
        self.assertFalse(reprise.chemin('alice').exists())
        self.assertFalse((self.base/'sockets/alice-web/spki').exists())
        with self.assertRaises(RuntimeError): reprise.ouvrir('bob',['site.test'],60,session=True)
        for session in (False, True):
            with self.assertRaises(RuntimeError): reprise.ouvrir('alice',['autre.test'],60,session=session)
        self.assertEqual(json.loads((self.base/'etats/alice.json').read_text())['noms'], ['site.test'])
        reprise.tour()
        self.assertIsNone(self.sessions.lire('site.test','alice'))
        self.assertFalse((self.base/'etats/alice.json').exists())
        self.assertFalse(reprise.chemin('alice').exists())
        self.assertFalse((self.base/'sockets/alice-web/spki').exists())
        reprise.ouvrir('bob',['site.test'],60,session=True)
        self.assertTrue(reprise.ouvert('bob')['session'])

    def test_reprise_residuelle_preserve_fermeture_active(self):
        self.a.ouvrir('alice',['site.test'],60,session=True)
        (self.base/'etats/alice.fermer').write_text('propriétaire')
        self.a.nettoyer()
        self.assertTrue((self.base/'etats/alice.fermer').exists())
        self.a.tour()
        self.assertIsNone(self.a.ouvert('alice'))
        self.assertIsNone(self.sessions.lire('site.test','alice'))

    def test_timer_prolonge_ignore_ancien_callback(self):
        timers=[]
        class Timer:
            def __init__(self,delai,fn,args):self.fn,self.args,self.annule=fn,args,False;timers.append(self)
            def start(self):pass
            def cancel(self):self.annule=True
        with patch.object(W.threading,'Timer',Timer):
            self.a.ouvrir('alice',['site.test'],60,session=True);ancien=timers[-1]
            self.a.prolonger('alice','site.test',60);courant=timers[-1]
            self.assertIsNot(ancien,courant);self.assertTrue(ancien.annule)
            self.a.ouvert('alice')['fin_ts']=time.time()-1
            ancien.fn(*ancien.args);self.assertIsNotNone(self.a.ouvert('alice'))
            courant.fn(*courant.args);self.assertIsNone(self.a.ouvert('alice'))
    def test_timer_ancien_ne_ferme_pas_acces_rouvert(self):
        timers=[]
        class Timer:
            def __init__(self,delai,fn,args):self.fn,self.args=fn,args;timers.append(self)
            def start(self):pass
            def cancel(self):pass
        with patch.object(W.threading,'Timer',Timer):
            self.a.ouvrir('alice',['site.test'],60);ancien=timers[-1]
            self.a.fermer('alice','test');self.a.ouvrir('alice',['autre.test'],60);courant=timers[-1]
            self.a.ouvert('alice')['fin_ts']=time.time()-1
            ancien.fn(*ancien.args);self.assertIsNotNone(self.a.ouvert('alice'))
            courant.fn(*courant.args);self.assertIsNone(self.a.ouvert('alice'))
    def test_nettoyage_bloque_reserve_domaine_sans_bloquer_autre_ouverture(self):
        self.a.ouvrir('alice',['site.test'],60,session=True)
        entre,libere,fini=threading.Event(),threading.Event(),threading.Event();resultats=[];effacer=self.sessions.effacer
        def bloque(dom):entre.set();libere.wait(2);return effacer(dom)
        self.sessions.effacer=bloque
        def ouvrir():
            try:self.a.ouvrir('charlie',['site.test'],60,session=True);resultats.append('autorise')
            except RuntimeError:resultats.append('reserve')
            self.a.ouvrir('bob',['autre.test'],60);fini.set()
        nettoyage=threading.Thread(target=lambda:self.a.fermer('alice','test'),daemon=True);nouveau=threading.Thread(target=ouvrir,daemon=True)
        nettoyage.start()
        try:
            self.assertTrue(entre.wait(1));nouveau.start();self.assertTrue(fini.wait(0.5),'ouverture bloquée par le nettoyage')
            self.assertEqual(resultats,['reserve']);self.assertIsNotNone(self.a.ouvert('bob'))
        finally:
            libere.set();nettoyage.join(3)
            if nouveau.ident is not None:nouveau.join(3)
            self.a.fermer('bob','fin du test');self.a.fermer('charlie','fin du test')

    def test_nettoyages_concurrents_transaction_unique(self):
        self.a._marquer('alice', 'site.test')
        premier, liberer, rejoue = threading.Event(), threading.Event(), threading.Event()
        appels, erreurs = [], []
        effacer = self.sessions.effacer
        def effacer_bloque(domaine):
            appels.append(domaine)
            if len(appels) == 1:
                premier.set()
                if not liberer.wait(2): raise AssertionError('premier nettoyage non libéré')
            else: rejoue.set()
            effacer(domaine)
        self.sessions.effacer = effacer_bloque
        def nettoyer():
            try: self.a._nettoyages()
            except BaseException as erreur: erreurs.append(erreur)
        t1 = threading.Thread(target=nettoyer); t2 = threading.Thread(target=nettoyer)
        t1.start()
        try:
            self.assertTrue(premier.wait(2))
            t2.start()
            self.assertFalse(rejoue.wait(0.1), 'le second nettoyage entre dans effacer avant la fin du premier')
        finally:
            liberer.set(); t1.join(2)
            if t2.ident is not None: t2.join(2)
        self.assertFalse(t1.is_alive()); self.assertFalse(t2.is_alive()); self.assertEqual(erreurs, [])
        self.assertEqual(appels, ['site.test'])
        self.sessions.enregistrer('site.test', 'bob', {'cookies': []}, time.time()+60)
        self.a.ouvrir('bob', ['site.test'], 60, session=True)
        self.a._nettoyages()
        self.assertEqual(self.sessions.lire('site.test','bob')['agent'], 'bob')

    def test_absence_store_et_mauvaise_identite(self):
        self.assertEqual(self.sessions.cookie('site.test','/zone',secure=True,agent='bob'),'')
        self.a.sessions = None
        with self.assertRaises(RuntimeError): self.a.ouvrir('alice',['site.test'],60,session=True)

class EnveloppeWeb(unittest.TestCase):
    def test_shlvl_absent_du_serveur_mcp(self):
        import subprocess
        arbre = ast.parse((Path(__file__).resolve().parents[1]/'bin/berger').read_text())
        affectation = next(n for n in arbre.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'SOCAT_WEB' for t in n.targets))
        contexte = {'PORT_WEB': W.PORT_ENVELOPPE}
        exec(compile(ast.Module(body=[affectation], type_ignores=[]), 'enveloppe', 'exec'), contexte)
        resultat = subprocess.run(['/bin/sh', '-c', contexte['SOCAT_WEB'], '/socket-factice', '/bin/true',
            sys.executable, '-c', 'import os; print("SHLVL" not in os.environ)'],
            env={'PATH': '/usr/bin:/bin', 'SHLVL': '7'}, capture_output=True, text=True, timeout=5)
        self.assertTrue(resultat.returncode == 0)
        self.assertTrue(resultat.stdout.strip() == 'True')

class CourtierFonctions(unittest.TestCase):
    def test_backup_commande_et_erreurs_statiques(self):
        import subprocess
        arbre = ast.parse((Path(__file__).resolve().parents[1]/'courtier/courtier').read_text())
        fonction = next(x for x in arbre.body if isinstance(x,ast.FunctionDef) and x.name=='sauvegarder_session_web')
        spec_transport=importlib.util.spec_from_file_location('transport_backup',Path(__file__).resolve().parents[1]/'courtier/outils/_transport.py')
        transport=importlib.util.module_from_spec(spec_transport);spec_transport.loader.exec_module(transport)
        g = dict(subprocess=subprocess, BERGER=Path('/installation-factice'), _transport=transport)
        exec(compile(ast.Module(body=[fonction],type_ignores=[]),'backup','exec'),g)
        with patch.object(subprocess,'run',return_value=type('Resultat',(),{'returncode':0})()) as run:
            g['sauvegarder_session_web']()
            self.assertTrue(run.call_args.args[0]==['python3','-c',transport.LANCEUR],'lanceur non constant')
            charge=json.loads(run.call_args.kwargs['input'])
            self.assertTrue(charge['programme']=='/installation-factice/bin/berger' and charge['arguments']==['coffre','sauvegarder','avant-session-web'],'commande métier altérée')
            self.assertTrue(run.call_args.kwargs['capture_output'])
        with patch.object(subprocess,'run',side_effect=OSError('temoin')):
            with self.assertRaises(RuntimeError) as erreur: g['sauvegarder_session_web']()
            self.assertNotIn('temoin',str(erreur.exception))
        with patch.object(subprocess,'run',return_value=type('Resultat',(),{'returncode':1})()):
            with self.assertRaises(RuntimeError): g['sauvegarder_session_web']()

    def test_filtre_et_arguments(self):
        # Fonctions réelles extraites par AST : aucune initialisation de l'installation ni réseau.
        arbre = ast.parse((Path(__file__).resolve().parents[1]/'courtier/courtier').read_text())
        fonctions = [x for x in arbre.body if isinstance(x,ast.FunctionDef) and x.name=='valeurs_du_coffre']
        outil = next(x for x in arbre.body if isinstance(x,ast.ClassDef) and x.name=='OutilWeb')
        fonctions += [x for x in outil.body if isinstance(x,ast.FunctionDef) and x.name in ('ajuster','apercu_demander')]
        with tempfile.TemporaryDirectory() as t:
            f = Path(t)/'coffre.json'
            f.write_text(json.dumps({'web-session:site.test':{'agent':'alice','fin_ts':123,'etat':{'cookies':[{'value':'abcdefgh'}],'origins':[{'localStorage':[{'value':'letterslong'}]}]}}}))
            g = dict(os=os,json=json,re=re,sys=sys,COFFRE=f,_COFFRE_LU=(None,set()),_SESSIONS_RETENUES=set(),_web=W)
            exec(compile(ast.Module(body=fonctions,type_ignores=[]),'fonctions','exec'),g)
            self.assertEqual(g['valeurs_du_coffre'](), {'abcdefgh','letterslong'})
            with patch.object(json,'load',side_effect=AssertionError('relecture')): self.assertEqual(g['valeurs_du_coffre'](),{'abcdefgh','letterslong'})
            f.write_text('{}'); self.assertEqual(g['valeurs_du_coffre'](),{'abcdefgh','letterslong'})
            self.assertEqual(g['ajuster'](None,'demander',['site.test','motif','--session','1h'],{'duree':'2h'}),['site.test','motif','2h','--session'])
            g.update(contient_secret=lambda x:False,WEB=type('Web',(),{'ouvert':lambda s,a:None})())
            obj = type('O',(),{'agent':lambda s:'alice','en_attente':lambda *x:None})()
            texte = g['apercu_demander'](obj,['site.test','motif','--session'])
            for attendu in ('prêter ta session','lecture seule','CGU','berger web connecter site.test'): self.assertIn(attendu,texte)

if __name__ == '__main__': unittest.main()
