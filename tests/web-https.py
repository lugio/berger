#!/usr/bin/env python3
"""HTTPS réel par paires de sockets : aucun port, DNS ou coffre réel."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import base64
import hashlib
import importlib.util
import os
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('web_https', ROOT / 'courtier/_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

class HTTPS(unittest.TestCase):
    def setUp(self):
        self.vus, self.journal, self.fils = [], [], []
        self.p = W.Proxy(['permis.test', 'sous.permis.test'], lambda *a: self.journal.append(a),
                         resoudre=lambda h, p: ['93.184.215.14'], ouvrir=self.amont, delai=2)
        # Le faux site a son propre certificat ; le proxy lui fait confiance explicitement.
        self.origine = W.Proxy(['permis.test'], lambda *a: None, delai=2)
        self.p.tls_amont = ssl.create_default_context(cadata=self.origine.certificat_pem.decode())

    def tearDown(self):
        self.p.arreter(); self.origine.arreter()
        for t in self.fils: t.join(3)

    def amont(self, adresse):
        self.vus.append(adresse)
        a, b = socket.socketpair()
        def site():
            try:
                with self.origine.contextes_tls['permis.test'].wrap_socket(b, server_side=True) as s:
                    tete, _ = W.lire_entete(s, W.ENTETE_MAX, 'requête', __import__('time').time() + 2)
                    self.vus.append(tete)
                    s.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 7\r\nConnection: close\r\n\r\nTEMOIN!')
            except OSError: pass
        t = threading.Thread(target=site); t.start(); self.fils.append(t)
        return a

    def requete(self, brut, sni='permis.test'):
        a, b = socket.socketpair(); self.addCleanup(a.close); a.settimeout(3)
        t = threading.Thread(target=self.p.servir, args=(b,)); t.start(); self.fils.append(t)
        a.sendall(b'CONNECT permis.test:443 HTTP/1.1\r\nHost: permis.test:443\r\n\r\n')
        tete = b''
        while not tete.endswith(b'\r\n\r\n'): tete += a.recv(1)
        self.assertIn(b' 200 ', tete)
        ctx = ssl.create_default_context(cadata=self.p.certificat_pem.decode())
        try:
            with ctx.wrap_socket(a, server_hostname=sni, suppress_ragged_eofs=False) as s:
                self.certificat_recu = s.getpeercert(binary_form=True)
                s.sendall(brut); out = b''
                while True:
                    x = s.recv(65536)
                    if not x: return out
                    out += x
        finally: a.close()

    def test_get_https_dechiffre_puis_tls_amont_verifie(self):
        try:
            r = self.requete(b'GET /page HTTP/1.1\r\nHost: permis.test\r\n\r\n')
        except OSError as e:
            self.fail(f"GET nominal : {type(e).__name__} ; journal proxy={self.journal!r} ; amont={self.vus!r}")
        self.assertIn(b'200 OK', r); self.assertTrue(r.endswith(b'TEMOIN!'))
        self.assertEqual(self.vus[0], ('93.184.215.14', 443))
        self.assertIn(b'GET /page HTTP/1.1', self.vus[1])
        cert = x509.load_der_x509_certificate(self.certificat_recu)
        spki = cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        self.assertEqual(self.p.empreinte, base64.b64encode(hashlib.sha256(spki).digest()).decode())

    def test_methodes_interdites_avant_connexion_amont(self):
        for methode in ('POST', 'DELETE', 'PUT', 'PATCH', 'OPTIONS'):
            with self.subTest(methode=methode):
                r = self.requete(f'{methode} / HTTP/1.1\r\nHost: permis.test\r\nContent-Length: 0\r\n\r\n'.encode())
                self.assertIn(b'405 ', r); self.assertEqual(self.vus, [])

    def test_host_distinct_meme_si_autorise_refuse(self):
        for entete in (b'Host: ailleurs.test', b'Host: sous.permis.test', b'Host: permis.test\r\nHost: ailleurs.test',
                       b'Host: permis.test:444', b'X: y'):
            with self.subTest(entete=entete):
                r = self.requete(b'GET / HTTP/1.1\r\n' + entete + b'\r\n\r\n')
                self.assertIn(b'400 ', r); self.assertEqual(self.vus, [])

    def test_sni_distinct_du_connect_refuse(self):
        with self.assertRaises(ssl.SSLError):
            self.requete(b'GET / HTTP/1.1\r\nHost: sous.permis.test\r\n\r\n', sni='sous.permis.test')
        self.assertEqual(self.vus, [])

    def test_corps_et_entetes_ambigus_refuses(self):
        for entete, code in ((b'Content-Length: 65537', b'413 '),
                             (b'Content-Length: 0\r\nContent-Length: 1', b'400 '),
                             (b'Transfer-Encoding: chunked', b'411 ')):
            with self.subTest(entete=entete):
                r = self.requete(b'GET / HTTP/1.1\r\nHost: permis.test\r\n' + entete + b'\r\n\r\n')
                self.assertIn(code, r); self.assertEqual(self.vus, [])

    def test_chemins_dangereux_refuses_y_compris_encodes(self):
        for chemin in ('/logout', '/api/delete', '/%65xport', '/settings', '/payment', '/safe/../logout'):
            with self.subTest(chemin=chemin):
                r = self.requete(f'GET {chemin} HTTP/1.1\r\nHost: permis.test\r\n\r\n'.encode())
                self.assertIn(b'403 ', r); self.assertEqual(self.vus, [])

    def test_tls_amont_non_fiable_refuse(self):
        self.p.tls_amont = ssl.create_default_context()
        r = self.requete(b'GET / HTTP/1.1\r\nHost: permis.test\r\n\r\n')
        self.assertIn(b'502 ', r)
        self.assertFalse(any(isinstance(x, bytes) for x in self.vus))

    def test_cles_distinctes_par_acces(self):
        self.assertNotEqual(self.p.empreinte, self.origine.empreinte)


class Certificats(unittest.TestCase):
    def test_certificat_borne_aux_noms_et_fichiers_prives_effaces(self):
        from unittest.mock import patch
        original, dossiers = tempfile.TemporaryDirectory, []
        def creer(*a, **kw):
            d = original(*a, **kw); dossiers.append(Path(d.name)); return d
        with patch.object(W.tempfile, 'TemporaryDirectory', side_effect=creer):
            pem, empreinte, contextes = W.certificat_ephemere(['permis.test', 'sous.permis.test'])
        cert = x509.load_pem_x509_certificate(pem)
        self.assertEqual(cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName),
                         ['permis.test', 'sous.permis.test'])
        self.assertEqual(set(contextes), {'permis.test', 'sous.permis.test'})
        self.assertTrue(dossiers); self.assertTrue(all(not d.exists() for d in dossiers))
        self.assertEqual(len(base64.b64decode(empreinte)), 32)
        self.assertNotIn(b'PRIVATE KEY', pem)

class Cadrage(unittest.TestCase):
    def test_connection_ne_retire_pas_le_cadrage_du_corps(self):
        class Flux:
            def __init__(self): self.envoye = b""; self.lu = False
            def settimeout(self, t): pass
            def sendall(self, b): self.envoye += b
            def recv(self, n):
                if self.lu: return b""
                self.lu = True
                return b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        amont, client = Flux(), Flux()
        p = W.Proxy(['permis.test'], lambda *a: None, resoudre=lambda *a: ['93.184.215.14'], ouvrir=lambda a: amont)
        corps = b'POST /delete HTTP/1.1\r\nHost: permis.test\r\nContent-Length: 0\r\n\r\n'
        ctx = {'fin': __import__('time').time() + 2, 'amont': None}
        p._http(client, 'GET', 'http://permis.test/', corps,
                [('Host', 'permis.test'), ('Content-Length', str(len(corps))), ('Connection', 'Content-Length')], ctx)
        self.assertIn(('Content-Length: ' + str(len(corps)) + '\r\n').encode(), amont.envoye)
        self.assertTrue(amont.envoye.endswith(corps))

class ReponseCadree(unittest.TestCase):
    def test_reponse_complete_ne_relit_pas_amont_ferme(self):
        class Amont:
            def __init__(self): self.lu = False
            def settimeout(self, t): pass
            def sendall(self, b): pass
            def recv(self, n):
                if self.lu: raise BrokenPipeError("amont fermé après sa réponse complète")
                self.lu = True
                return b"HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\nTEMOIN!"
        class Client:
            envoye = b""
            def settimeout(self, t): pass
            def sendall(self, b): self.envoye += b
        amont, client = Amont(), Client()
        p = W.Proxy(['permis.test'], lambda *a: None, resoudre=lambda *a: ['93.184.215.14'], ouvrir=lambda a: amont)
        ctx = {'fin': __import__('time').time() + 2, 'amont': None}
        p._http(client, 'GET', 'http://permis.test/', b'', [('Host', 'permis.test')], ctx)
        self.assertTrue(client.envoye.endswith(b'TEMOIN!'))

class Entetes(unittest.TestCase):
    def test_controles_et_noms_invalides_refuses(self):
        for ligne in ('X: valeur\nHost: ailleurs.test', 'X: valeur\x00', 'X X: valeur', ':authority: ailleurs.test'):
            with self.subTest(ligne=ligne):
                with self.assertRaises(W.Refus): W.entetes([ligne])

class Navigateur(unittest.TestCase):
    def test_empreinte_lue_au_lancement_et_options_fournies_remplacees(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); nav = d / 'navigateur'; empreinte = d / 'spki'
            nav.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n'); nav.chmod(0o700)
            empreinte.write_text(base64.b64encode(bytes(range(32))).decode() + '\n')
            env = {**os.environ, 'BERGER_NAVIGATEUR': str(nav), 'BERGER_WEB_EMPREINTE': str(empreinte)}
            r = subprocess.run([str(ROOT / 'bin/berger-navigateur-web'), '--ignore-certificate-errors=true', '--ignore-certificate-errors',
                                '--ignore-certificate-errors-spki-list=valeur-injectee', '--proxy-server=http://autre',
                                '--headless'], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            args = r.stdout.splitlines()
            self.assertIn('--ignore-certificate-errors-spki-list=' + empreinte.read_text().strip(), args)
            self.assertNotIn('--ignore-certificate-errors', args)
            self.assertNotIn('--ignore-certificate-errors=true', args)
            self.assertNotIn('--ignore-certificate-errors-spki-list=valeur-injectee', args)
            self.assertIn('--headless', args)
            self.assertIn('--proxy-server=http://127.0.0.1:3128', args)

    def test_empreinte_malformee_refusee_sans_lancer_le_navigateur(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'spki'; f.write_text('--ignore-certificate-errors')
            r = subprocess.run([str(ROOT / 'bin/berger-navigateur-web')], capture_output=True,
                               env={**os.environ, 'BERGER_NAVIGATEUR': '/usr/bin/true', 'BERGER_WEB_EMPREINTE': str(f)})
            self.assertNotEqual(r.returncode, 0)

if __name__ == '__main__': unittest.main(verbosity=2)
