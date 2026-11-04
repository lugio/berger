#!/usr/bin/env python3
"""Chemins d'effacement en POST validé (lot 1 b, docs/plans/2026-10-29-acces-web-envoi-spec.md) — HTTPS réel par paires de
sockets, aucun port, DNS ou coffre réel. `delete` : refusé en GET et HEAD, permis en POST validé (post_autorise), refusé en
POST non validé et en session prêtée ; `logout`, `export`, `settings`, `payment` refusés dans tous les cas, même mêlés à
`delete`, y compris encodés. Chaque refus arrive avant toute connexion au site et figure au journal du proxy.
Renvoi n° 98 : l'autorisation POST de CONNEXION (navigateur prêté au propriétaire, `berger web connecter`) ne permet jamais
l'effacement — seule celle des ACTIONS d'un agent (`effacement_autorise`) le permet ; les refus du navigateur de connexion
sont journalisés ; PARCOURS complet par le vrai courtier (installation jetable) : demande `--post` → aperçu « POST permis :
effacement » → validation du propriétaire → l'accès ouvert transmet l'autorisation au proxy de CET agent → POST accepté ;
validation sans cette mention → 405 ; un secret (valeur du coffre, forme de clé) dans le corps ou l'URL d'un POST validé →
403, absent du journal, notifié en urgence (détecteur du courtier, contient_secret). Renvoi n° 99 : le corps est décodé selon
son type et son jeu de caractères (JSON en UTF-8/16/32 avec ses échappements, formulaire, multipart et ses parties base64,
texte) et CHAQUE forme passe au détecteur ; un corps qu'on ne sait pas décoder, d'un autre type ou compressé est refusé ; le
« + » d'un CHEMIN reste un « + » (les deux formes contrôlées) ; le journal de connexion masque une forme de clé.
Lot 1 bis : chaque en-tête envoyé (nom et valeur, décodés) passe au détecteur ; Content-Type, Content-Encoding ou
Transfer-Encoding répété ou ambigu refusé ; chaque partie multipart analysée selon SON type (même fonction que le corps) ;
toute partie avec un nom de fichier refusée ; aucun motif de refus ne recopie la requête (réponse et journal).
Renvoi n° 102 (changement de méthode) : un POST --post n'est accepté que dans une LISTE FERMÉE de formats — un Content-Type
parmi quatre, charset utf-8 seul, en-têtes nommés et uniques (principal et parties), parties « form-data; name » seul, JSON
sans clé répétée à toute profondeur, ni multipart imbriqué, ni nom de fichier, ni Content-Encoding/Transfer-Encoding ; puis
le détecteur. Renvoi n° 103 : la même liste fermée pour TOUTES les méthodes (GET, HEAD, POST, CONNECT), en HTTP clair ET dans
le tunnel, par une seule fonction (controler_envoi) ; décodage d'URL jusqu'au point fixe, sinon refusé ; méthode fixe partout.
Renvoi n° 105 : un seul décodage au point fixe, fait par la fonction commune AVANT toute décision (chemins interdits compris) ;
l'hôte n'est écrit au journal que s'il est permis, sinon « hôte non permis » ; formats aussi en HTTP clair ; espion des refus précoces. Messages et journal : textes fixes (méthode hors liste, hôte de redirection, port, type jamais recopiés).
Usage : python3 tests/web-effacement.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.machinery, importlib.util, json, os, shutil, socket, ssl, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('web_effacement', ROOT / 'courtier/_web.py')
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

EFFACEMENT = ('/privacy/delete-request', '/compte/DELETE', '/api/%64elete', '/x?action=delete')
TOUJOURS = ('/logout', '/export', '/settings', '/payment', '/%65xport', '/privacy/delete-request/settings',
            '/delete/logout', '/payment?then=delete')


class Effacement(unittest.TestCase):
    """Le même proxy qu'en vrai (W.Proxy, liste par défaut), un faux site TLS local ; `post` = la validation permet le POST."""

    def proxy(self, post=False, session=False, effacement=None):
        """`post` = la validation permet le POST ; `effacement` (par défaut : comme `post`) = autorisation des ACTIONS d'un agent."""
        self.vus, self.journal, self.fils = [], [], []
        p = W.Proxy(['permis.test'], lambda *a: self.journal.append(a), resoudre=lambda h, port: ['93.184.215.14'],
                    ouvrir=self.amont, delai=2, post_autorise=post, effacement_autorise=post if effacement is None else effacement)
        if session:
            p.session_pretee = True; p.fournisseur_cookie = lambda h, c: ''; p.fournisseur_valeurs = lambda h: set()
        self.origine = W.Proxy(['permis.test'], lambda *a: None, delai=2)
        p.tls_amont = ssl.create_default_context(cadata=self.origine.certificat_pem.decode())
        self.addCleanup(self.origine.arreter); self.addCleanup(p.arreter)
        self.p = p
        return p

    def tearDown(self):
        for t in getattr(self, 'fils', []): t.join(3)

    def amont(self, adresse):
        self.vus.append(adresse)
        a, b = socket.socketpair()
        def site():
            try:
                with self.origine.contextes_tls['permis.test'].wrap_socket(b, server_side=True) as s:
                    tete, _ = W.lire_entete(s, W.ENTETE_MAX, 'requête', time.time() + 2)
                    self.vus.append(tete)
                    s.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 7\r\nConnection: close\r\n\r\nTEMOIN!')
            except OSError: pass
        t = threading.Thread(target=site); t.start(); self.fils.append(t)
        return a

    def requete(self, methode, chemin, corps=b''):
        a, b = socket.socketpair(); self.addCleanup(a.close); a.settimeout(3)
        t = threading.Thread(target=self.p.servir, args=(b,)); t.start(); self.fils.append(t)
        a.sendall(b'CONNECT permis.test:443 HTTP/1.1\r\nHost: permis.test:443\r\n\r\n')
        tete = b''
        while not tete.endswith(b'\r\n\r\n'): tete += a.recv(1)
        self.assertIn(b' 200 ', tete)
        ctx = ssl.create_default_context(cadata=self.p.certificat_pem.decode())
        brut = (f'{methode} {chemin} HTTP/1.1\r\nHost: permis.test\r\nContent-Type: application/x-www-form-urlencoded\r\n'
                f'Content-Length: {len(corps)}\r\n\r\n').encode() + corps
        with ctx.wrap_socket(a, server_hostname='permis.test', suppress_ragged_eofs=False) as s:
            s.sendall(brut); out = b''
            while True:
                x = s.recv(65536)
                if not x: return out
                out += x

    def refuse(self, r, code):
        self.assertIn(code, r.split(b'\r\n', 1)[0]); self.assertEqual(self.vus, [], "aucune connexion au site")
        self.assertTrue(any(j[2] is False for j in self.journal), f"refus journalisé ({self.journal})")

    def test_liste_par_defaut_inchangee(self):
        self.assertEqual(set(W.CHEMINS_BLOQUES), {'logout', 'delete', 'export', 'settings', 'payment'})
        self.assertFalse(self.proxy().post_autorise, "POST non validé par défaut")

    def test_delete_refuse_en_get_et_head(self):
        for post in (False, True):
            for methode in ('GET', 'HEAD'):
                for chemin in EFFACEMENT:
                    with self.subTest(post=post, methode=methode, chemin=chemin):
                        self.proxy(post=post); self.refuse(self.requete(methode, chemin), b'403')

    def test_delete_permis_en_post_valide(self):
        for chemin in EFFACEMENT:
            with self.subTest(chemin=chemin):
                self.proxy(post=True); r = self.requete('POST', chemin, b'motif=art17')
                self.assertIn(b'200 OK', r); self.assertTrue(r.endswith(b'TEMOIN!'))
                self.assertEqual(self.vus[0], ('93.184.215.14', 443))
                self.assertTrue(self.vus[1].startswith(f'POST {chemin} HTTP/1.1'.encode()))
                self.assertTrue(any(j[0] == 'POST' and j[2] is True for j in self.journal), f"POST permis journalisé ({self.journal})")

    def test_delete_refuse_en_post_non_valide(self):
        for chemin in EFFACEMENT:
            with self.subTest(chemin=chemin):
                self.proxy(post=False); self.refuse(self.requete('POST', chemin, b'motif=art17'), b'405')

    def test_delete_refuse_en_session_pretee(self):
        self.proxy(post=True, session=True); self.refuse(self.requete('POST', EFFACEMENT[0], b'motif=art17'), b'405')

    def test_autres_chemins_toujours_refuses(self):
        for post in (False, True):
            for methode in ('GET', 'HEAD', 'POST'):
                for chemin in TOUJOURS:
                    with self.subTest(post=post, methode=methode, chemin=chemin):
                        self.proxy(post=post); r = self.requete(methode, chemin, b'x=1' if methode == 'POST' else b'')
                        self.refuse(r, b'403' if post or methode != 'POST' else b'405')

    def test_connexion_du_proprietaire_sans_effacement(self):
        """Le navigateur de connexion a le POST (se connecter) mais jamais l'effacement : refusé et journalisé."""
        for chemin in EFFACEMENT:
            with self.subTest(chemin=chemin):
                self.proxy(post=True, effacement=False); self.refuse(self.requete('POST', chemin, b'motif=art17'), b'403')
        self.proxy(post=True, effacement=False); r = self.requete('POST', '/login', b'identifiant=x')
        self.assertIn(b'200 OK', r, "la connexion elle-même passe toujours")

    def test_post_valide_ne_se_change_pas_en_delete(self):
        """Le POST d'effacement reste un POST : surcharge de méthode refusée, comme partout."""
        self.proxy(post=True)
        self.refuse(self.requete('POST', '/privacy/delete-request?_method=DELETE', b''), b'403')
        self.proxy(post=True)
        self.refuse(self.requete('POST', '/privacy/delete-request', b'_method=DELETE'), b'403')
        self.proxy(post=True)
        self.refuse(self.requete('DELETE', '/privacy/delete-request'), b'405')


class JournalConnexion(unittest.TestCase):
    """`berger web connecter` : le proxy reçoit un vrai journal (plus une fonction vide) ; ses refus vont à courtier/appels.log."""

    def test_refus_du_navigateur_de_connexion_journalises(self):
        sys.path.insert(0, str(ROOT / 'courtier'))
        import _web_connexion as C
        from _web_session import SessionCoffre
        with tempfile.TemporaryDirectory() as t:
            base = Path(t); etats = base / 'web'; etats.mkdir()
            (etats / 'alice.json').write_text(json.dumps(dict(agent='alice', noms=['site.test'], session=True, fin_ts=200, socket='/x')))
            store = SessionCoffre(base / 'coffre.json', lambda: None, horloge=lambda: 100); store.coffre.write_text('{}')
            vus = []
            class Faux:
                empreinte = 'SPKI'
                def __init__(self, noms, journal, **kw): vus.append((journal, kw))
                def ecouter_local(self): return 12345
                def arreter(self): pass
            def capture(*a, **k):
                vus[0][0]('POST', 'site.test', False, 'chemin bloqué'); vus[0][0]('GET', 'site.test', True, '200, 3 octets')
                return {'cookies': [], 'origins': []}
            C.connecter('site.test', etats, base / 'profils', store, {'node': '/n', 'playwright_module': '/p', 'navigateur': '/c'},
                        ROOT / 'bin/berger-web-connecter.mjs', fabrique=Faux, capture=capture, horloge=lambda: 100)
            self.assertNotIn('effacement_autorise', vus[0][1], "la connexion ne reçoit jamais l'autorisation d'effacement")
            log = (base / 'appels.log').read_text() if (base / 'appels.log').exists() else ''
            self.assertIn('web-connexion:site.test', log); self.assertIn('POST', log); self.assertIn('REFUSÉ', log)
            self.assertIn('chemin bloqué', log); self.assertNotIn('200, 3 octets', log)

    def test_forme_de_cle_masquee_au_journal_de_connexion(self):
        """Renvoi n° 99, point 3 : hôte et détail passent par le masquage du courtier avant d'être écrits."""
        sys.path.insert(0, str(ROOT / 'courtier'))
        import _web_connexion as C
        cle = 'sk-' + 'x' * 24; valeur = 'Temoin' + 'Coffre' + 'Journal'
        with tempfile.TemporaryDirectory() as t:
            etats = Path(t) / 'web'; etats.mkdir()
            noter = C.journal_refus(etats, 'site.test', lambda x: valeur in x)
            noter('CONNECT', cle + '.test', False, 'autre nom'); noter('POST', 'site.test', False, 'motif ' + valeur)
            log = (Path(t) / 'appels.log').read_text()
            self.assertNotIn(cle, log); self.assertNotIn(valeur, log); self.assertEqual(log.count('[masqué : la ligne contenait un secret]'), 2)
            self.assertEqual(log.count('REFUSÉ'), 2)


class Parcours(unittest.TestCase):
    reponse_site = None                                    # réponse du faux site (par défaut : 200 TEMOIN!)
    recus = []                                             # (en-tête, corps) de chaque requête reçue par le faux site
    """Vrai courtier, installation jetable : demande → validation du PROPRIÉTAIRE (berger valider) → accès ouvert → proxy de
    CET agent. Le proxy est le vrai (W.Proxy du courtier) ; seuls la résolution, le site et l'écoute sont remplacés."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); m = Path(cls.tmp.name); i = m / 'berger'; cls.i = i
        _produit.copier(ROOT, i, ('bin', 'courtier', 'commun'))
        (i / 'config.toml').write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
        cls.temoin = 'Temoin' + 'Coffre' + 'Envoi'                 # valeurs secrètes factices, construites à l'exécution
        cls.temoin_plus = 'Temoin' + '+' + 'Coffre' + 'Envoi'
        (m / 'coffre-essai.json').write_text(json.dumps({'service': {'jeton': cls.temoin}, 'autre': {'jeton': cls.temoin_plus}}))
        d = i / 'agents/effaceur'; (d / 'memory').mkdir(parents=True)
        (d / 'agent.conf').write_text('nom = effaceur\nmoteur = claude\npanneaux = claude\nheures = aucune\nmur = strict\noutils = web\n')
        cls.env = {**os.environ, 'HOME': str(m), 'BERGER_DIR': str(i), 'BERGER_HERDR': '/bin/false', 'BERGER_NOTIFY_SEND': '/bin/true'}
        cls.ancien = {k: os.environ.get(k) for k in ('HOME', 'BERGER_DIR', 'BERGER_HERDR', 'BERGER_NOTIFY_SEND')}
        os.environ.update({k: cls.env[k] for k in cls.ancien})
        chargeur = importlib.machinery.SourceFileLoader('courtier_effacement', str(i / 'courtier/courtier'))   # fichier sans .py
        cls.C = importlib.util.module_from_spec(importlib.util.spec_from_loader('courtier_effacement', chargeur)); chargeur.exec_module(cls.C)
        WC = cls.C._web
        cls.origine = WC.Proxy(['permis.test'], lambda *a: None, delai=2)
        cls.vus = []
        class SansEcoute(WC.Proxy):                       # le vrai proxy, servi par paires de sockets (aucun AF_UNIX)
            def ecouter(self, chemin): Path(chemin).write_text('')
        def fabrique(noms, journal):
            p = SansEcoute(noms, journal, resoudre=lambda h, port: ['93.184.215.14'], ouvrir=cls.amont, delai=2)
            p.tls_amont = ssl.create_default_context(cadata=cls.origine.certificat_pem.decode()); return p
        cls.C.WEB.fabrique = fabrique

    @classmethod
    def tearDownClass(cls):
        for a in list(cls.C.WEB.ouverts): cls.C.WEB.fermer(a, 'fin du test')
        cls.origine.arreter(); cls.tmp.cleanup()
        for k, v in cls.ancien.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    @classmethod
    def amont(cls, adresse):
        """Le faux site : TLS sur 443, en clair sur 80 ; il garde chaque requête reçue, corps compris (cls.recus)."""
        cls.vus.append(adresse); a, b = socket.socketpair()
        def site():
            try:
                s = cls.origine.contextes_tls['permis.test'].wrap_socket(b, server_side=True) if adresse[1] == 443 else b
                with s:
                    tete, reste = W.lire_entete(s, W.ENTETE_MAX, 'requête', time.time() + 2)
                    lg = int(next((l.split(b':', 1)[1] for l in tete.split(b'\r\n') if l.lower().startswith(b'content-length:')), b'0'))
                    while len(reste) < lg:
                        x = s.recv(65536)
                        if not x: break
                        reste += x
                    cls.recus.append((tete, reste[:lg]))
                    s.sendall(cls.reponse_site or b'HTTP/1.1 200 OK\r\nContent-Length: 7\r\nConnection: close\r\n\r\nTEMOIN!')
            except OSError: pass
        threading.Thread(target=site, daemon=True).start(); return a

    def outil(self, verbe, *args):
        d = self.i / 'agents/effaceur/courrier'; (d / 'encours').mkdir(parents=True, exist_ok=True)
        f = d / 'encours' / f'{time.time_ns()}.json'; f.write_text(json.dumps({'outil': 'web', 'verbe': verbe, 'args': list(args)}))
        self.C.traiter('effaceur', f, {}); return json.loads((d / 'reponses' / f.name).read_text())

    def decider(self, n, *plus):
        p = subprocess.Popen([sys.executable, str(self.i / 'bin/berger'), 'valider', str(n), *plus], env=self.env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while p.poll() is None: self.C.traiter_decisions(); time.sleep(0.1)
        return p.returncode, p.stdout.read()

    def poster(self, chemin, corps='motif=art17', type_='application/x-www-form-urlencoded', entetes=''):
        """POST de l'agent par le proxy de SON accès ouvert (CONNECT + TLS, comme son navigateur) ; `corps` texte ou octets."""
        p = self.C.WEB.ouvert('effaceur')['proxy']
        a, b = socket.socketpair(); a.settimeout(3)
        threading.Thread(target=p.servir, args=(b,), daemon=True).start()
        a.sendall(b'CONNECT permis.test:443 HTTP/1.1\r\nHost: permis.test:443\r\n\r\n'); tete = b''
        while not tete.endswith(b'\r\n\r\n'): tete += a.recv(1)
        ctx = ssl.create_default_context(cadata=p.certificat_pem.decode())
        with ctx.wrap_socket(a, server_hostname='permis.test') as s:
            b = corps if isinstance(corps, bytes) else corps.encode()
            s.sendall(f'POST {chemin} HTTP/1.1\r\nHost: permis.test\r\nContent-Type: {type_}\r\n{entetes}Content-Length: {len(b)}\r\n\r\n'.encode() + b)
            out = b''
            while (x := s.recv(65536)): out += x
        return out

    def ouvrir(self, motif, *options, duree=()):
        """Un accès ouvert pour CE test : motif rendu unique (le garde-fou anti-boucle du courtier refuse le même appel répété
        plus de 6 fois par heure) ; un accès laissé ouvert par un test en échec est d'abord fermé."""
        if self.C.WEB.ouvert('effaceur'): self.fermer()
        Parcours.n_ouvertures = getattr(Parcours, 'n_ouvertures', 0) + 1
        r = self.outil('demander', 'permis.test', f'{motif} (essai n° {Parcours.n_ouvertures})', *options); self.assertTrue(r['ok'], r)
        n = r['en_attente']; apercu = json.loads((self.i / f'courtier/validations/{n}.json').read_text())['apercu']
        rc, o = self.decider(n, *duree); self.assertEqual(rc, 0, o); self.assertIsNotNone(self.C.WEB.ouvert('effaceur'), o)
        return apercu

    def fermer(self): self.C.WEB.fermer('effaceur', 'fin du test')        # directement : web fermer répété buterait sur l'anti-boucle

    def test_validation_avec_post_puis_post_de_l_agent_accepte(self):
        apercu = self.ouvrir('demande d’effacement art. 17', '--post')
        try:
            self.assertIn('permis.test', apercu); self.assertIn('2 h', apercu); self.assertIn('POST permis : effacement', apercu)
            r = self.poster('/privacy/delete-request')
            self.assertIn(b'200 OK', r); self.assertTrue(r.endswith(b'TEMOIN!'))
            self.assertIn('POST', self.outil('etat')['donnees']['methodes'])
        finally: self.fermer()

    def test_duree_du_proprietaire_garde_le_post(self):
        self.ouvrir('effacement', '--post', duree=('--duree', '1h'))
        try:
            self.assertLess(self.C.WEB.ouvert('effaceur')['fin_ts'] - time.time(), 3700)
            self.assertIn(b'200 OK', self.poster('/privacy/delete-request'))
        finally: self.fermer()

    def test_validation_sans_post_alors_405(self):
        apercu = self.ouvrir('lecture seule')
        try:
            self.assertNotIn('POST permis', apercu)
            self.assertIn(b' 405 ', self.poster('/privacy/delete-request').split(b'\r\n', 1)[0] + b' ')
            self.assertNotIn('POST', self.outil('etat')['donnees']['methodes'])
        finally: self.fermer()

    def test_secret_dans_un_envoi_valide_refuse_journalise_sans_valeur_et_notifie(self):
        notes = []; ancien = self.C.notifier_proprietaire
        self.C.notifier_proprietaire = lambda titre, texte, urgent=False: notes.append((titre, texte, urgent))
        self.ouvrir('effacement', '--post')
        try:
            cle = 'sk-' + 'x' * 24
            envois = (('/privacy/delete-request', 'motif=art17&jeton=' + self.temoin),                       # corps
                      ('/privacy/delete-request', 'motif=' + self.temoin.replace('Coffre', '%43offre')),       # corps encodé
                      ('/privacy/delete-request?ref=' + self.temoin, 'motif=art17'),                          # URL
                      ('/contact', 'texte=' + cle))                                                           # forme de clé
            for chemin, corps in envois:
                with self.subTest(chemin=chemin, corps=corps[:20]):
                    k = len(self.vus); r = self.poster(chemin, corps)
                    self.assertIn(b' 403 ', r.split(b'\r\n', 1)[0] + b' '); self.assertEqual(len(self.vus), k, "rien n'est parti au site")
            log = (self.i / 'courtier/appels.log').read_text()
            self.assertIn('secret', log); self.assertNotIn(self.temoin, log); self.assertNotIn(cle, log)
            alertes = [n for n in notes if 'secret' in n[0]]               # la demande de validation notifie aussi (non urgente)
            self.assertEqual(len(alertes), len(envois)); self.assertTrue(all(u for _, _, u in alertes), "notifié en urgence")
            self.assertFalse(any(self.temoin in x or cle in x for n in notes for x in n[:2]))
            self.assertIn(b'200 OK', self.poster('/privacy/delete-request'), "un envoi propre passe toujours")
        finally:
            self.C.notifier_proprietaire = ancien; self.fermer()

    def refuse_sans_envoi(self, r, quoi):
        k = len(self.vus); self.assertNotIn(b'200 OK', r.split(b'\r\n', 1)[0], quoi)
        self.assertEqual(r.split(b' ', 2)[1][:1], b'4', f"{quoi} : refus 4xx ({r[:40]})")

    def test_secrets_dans_toutes_les_formes_du_corps(self):
        """Renvoi n° 99, point 1 : chaque forme décodée passe au détecteur ; ce qu'on ne sait pas décoder est refusé."""
        notes = []; ancien = self.C.notifier_proprietaire
        self.C.notifier_proprietaire = lambda titre, texte, urgent=False: notes.append((titre, texte, urgent))
        self.ouvrir('effacement', '--post')
        T = self.temoin; frontiere = 'frontiereEssai'
        def multipart(contenu, entete=''):
            return (f'--{frontiere}\r\nContent-Disposition: form-data; name="texte"\r\n{entete}\r\n{contenu}\r\n--{frontiere}--\r\n').encode()
        import base64
        try:
            secrets = (('JSON UTF-8', json.dumps({'texte': T}).encode(), 'application/json'),
                       ('JSON clé', json.dumps({T: 'x'}).encode(), 'application/json'),
                       ('JSON échappé', ('{"texte": "' + ''.join(f'\\u{ord(x):04x}' for x in T) + '"}').encode(), 'application/json'),
                       ('multipart', multipart(T), f'multipart/form-data; boundary={frontiere}'),
                       ('formulaire', ('texte=' + T.replace('E', '%45')).encode(), 'application/x-www-form-urlencoded'))
            for quoi, corps, type_ in secrets:
                with self.subTest(quoi=quoi):
                    k = len(self.vus); r = self.poster('/contact', corps, type_)
                    self.assertIn(b' 403 ', r.split(b'\r\n', 1)[0] + b' ', quoi); self.assertEqual(len(self.vus), k, f"{quoi} : rien parti au site")
            illisibles = (('octets inconnus', b'\xff\xfe\xfd\x00\x80', 'application/octet-stream', ''),
                          ('JSON UTF-16 BOM (hors format)', json.dumps({'texte': T}).encode('utf-16'), 'application/json', ''),
                          ('JSON UTF-16 LE (hors format)', json.dumps({'texte': T}).encode('utf-16-le'), 'application/json', ''),
                          ('JSON UTF-32 (hors format)', json.dumps({'texte': T}).encode('utf-32'), 'application/json', ''),
                          ('texte UTF-16 déclaré (hors format)', T.encode('utf-16-be'), 'text/plain; charset=utf-16-be', ''),
                          ('partie base64 (hors format)', multipart(base64.b64encode(T.encode()).decode(), 'Content-Transfer-Encoding: base64\r\n'),
                           f'multipart/form-data; boundary={frontiere}', ''),
                          ('UTF-8 invalide', b'texte=\xff\xfe\x80', 'text/plain', ''),
                          ('charset inconnu', b'texte propre', 'text/plain; charset=inconnu-x', ''),
                          ('JSON illisible', b'{"texte": ', 'application/json', ''),
                          ('compressé', __import__('gzip').compress(T.encode()), 'text/plain', 'Content-Encoding: gzip\r\n'))
            for quoi, corps, type_, ent in illisibles:
                with self.subTest(quoi=quoi):
                    k = len(self.vus); r = self.poster('/contact', corps, type_, ent)
                    self.assertTrue(r.split(b'\r\n', 1)[0].split(b' ')[1].startswith(b'4'), f"{quoi} : refusé ({r[:60]})")
                    self.assertEqual(len(self.vus), k, f"{quoi} : jamais transmis sans contrôle")
            log = (self.i / 'courtier/appels.log').read_text(); self.assertNotIn(T, log)
            self.assertEqual(len([n for n in notes if 'secret' in n[0]]), len(secrets))
            for quoi, corps, type_ in (('JSON propre', json.dumps({'texte': 'demande art. 17'}).encode(), 'application/json; charset=utf-8'),
                                       ('multipart propre', multipart('demande art. 17'), f'multipart/form-data; boundary={frontiere}')):
                with self.subTest(quoi=quoi): self.assertIn(b'200 OK', self.poster('/contact', corps, type_), quoi)
        finally:
            self.C.notifier_proprietaire = ancien; self.fermer()

    def test_plus_du_chemin_reste_un_plus(self):
        """Renvoi n° 99, point 2 : « + » du chemin = « + » ; requête et formulaire : les deux formes."""
        notes = []; ancien = self.C.notifier_proprietaire
        self.C.notifier_proprietaire = lambda titre, texte, urgent=False: notes.append((titre, texte, urgent))
        self.ouvrir('effacement', '--post')
        try:
            for chemin, corps in (('/Temoin+Coffre%45nvoi', 'motif=art17'), ('/x?q=Temoin%2BCoffre%45nvoi', 'motif=art17'),
                                  ('/x?q=Temoin+CoffreEnvoi', 'motif=art17'), ('/contact', 'q=Temoin%2BCoffreEnvoi')):
                with self.subTest(chemin=chemin, corps=corps):
                    k = len(self.vus); r = self.poster(chemin, corps)
                    self.assertIn(b' 403 ', r.split(b'\r\n', 1)[0] + b' '); self.assertEqual(len(self.vus), k)
            self.assertNotIn(self.temoin_plus, (self.i / 'courtier/appels.log').read_text())
        finally:
            self.C.notifier_proprietaire = ancien; self.fermer()

    def test_formes_de_cle_identiques_octet_pour_octet(self):
        """MOTIFS_CLES déplacé (renvoi n° 99, accord du chef de projet) : le même motif qu'avant, octet pour octet, et le MÊME
        objet pour le courtier et pour journal_refus. Référence : empreinte du motif tel qu'il était défini dans courtier/courtier
        sur main (4f69605), calculée avant le déplacement."""
        import hashlib, importlib.machinery, re
        sys.path.insert(0, str(ROOT / 'courtier'))
        import _secrets, _web_connexion
        self.assertEqual(hashlib.sha256(_secrets.MOTIFS_CLES.pattern.encode()).hexdigest(),
                         '8fc3102d18622508b502e40fdc8f0d40e3fd85fa024d7354c9c4fd75fcb8bf5d')
        self.assertEqual(_secrets.MOTIFS_CLES.flags, re.UNICODE)
        self.assertIs(_web_connexion.MOTIFS_CLES, _secrets.MOTIFS_CLES, "journal_refus lit la définition partagée")
        source = (ROOT / 'courtier/courtier').read_text()
        self.assertEqual(source.count('MOTIFS_CLES = '), 1); self.assertIn('MOTIFS_CLES = _secrets.MOTIFS_CLES', source)
        self.assertNotIn('re.compile(r"sk-', source, "aucune copie du motif dans le courtier")
        self.assertEqual(self.C.MOTIFS_CLES.pattern, _secrets.MOTIFS_CLES.pattern, "le courtier chargé détecte les mêmes formes")

    def test_lot_1_bis(self):
        """Lot 1 bis (n° 100 validée par erreur) : en-têtes, types ambigus, parties multipart, pièces jointes, motifs statiques."""
        notes = []; ancien = self.C.notifier_proprietaire
        self.C.notifier_proprietaire = lambda titre, texte, urgent=False: notes.append((titre, texte, urgent))
        self.ouvrir('effacement', '--post')
        T = self.temoin; fr = 'frontiereEssai'; echappe = ''.join(f'\\u{ord(x):04x}' for x in T)
        def multipart(contenu, entetes_partie, nom='name="texte"'):
            return (f'--{fr}\r\nContent-Disposition: form-data; {nom}\r\n{entetes_partie}\r\n{contenu}\r\n--{fr}--\r\n').encode()
        mp = f'multipart/form-data; boundary={fr}'
        try:
            cas = (  # (quoi, chemin, corps, type, en-têtes en plus, code attendu)
                ('en-tête secret', '/contact', 'motif=art17', 'application/x-www-form-urlencoded', f'X-Token: {T}\r\n', b'400'),
                ('en-tête secret encodé', '/contact', 'motif=art17', 'application/x-www-form-urlencoded', f'X-Token: {T.replace("C", "%43")}\r\n', b'400'),
                ('nom d\'en-tête secret', '/contact', 'motif=art17', 'application/x-www-form-urlencoded', f'X-{T}: 1\r\n', b'400'),
                ('en-tête permis secret', '/contact', 'motif=art17', 'application/x-www-form-urlencoded', f'Referer: https://permis.test/{T}\r\n', b'403'),
                ('deux Content-Type', '/contact', '{"texte": "' + echappe + '"}', 'text/plain', 'Content-Type: application/json\r\n', b'400'),
                ('Content-Type ambigu', '/contact', '{"texte": "' + echappe + '"}', 'text/plain, application/json', '', b'415'),
                ('deux Content-Encoding', '/contact', 'motif=art17', 'application/x-www-form-urlencoded',
                 'Content-Encoding: identity\r\nContent-Encoding: identity\r\n', b'400'),
                ('partie JSON échappée', '/contact', multipart('{"texte": "' + echappe + '"}', 'Content-Type: application/json\r\n'), mp, '', b'403'),
                ('partie formulaire encodée', '/contact', multipart('texte=' + T.replace('E', '%45'), 'Content-Type: application/x-www-form-urlencoded\r\n'), mp, '', b'403'),
                ('pièce jointe texte', '/contact', multipart('demande art. 17', 'Content-Type: text/plain\r\n', 'name="preuve"; filename="preuve.txt"'), mp, '', b'415'),
                ('pièce jointe filename*', '/contact', multipart('demande art. 17', '', "name=\"preuve\"; filename*=UTF-8''preuve.txt"), mp, '', b'415'),
                ('type secret recopié', '/contact', 'x', f'application/{T}', '', b'415'),
                ('type inconnu recopié', '/contact', 'x', f'application/{T.lower()}x', '', b'415'),
            )
            for quoi, chemin, corps, type_, ent, code in cas:
                with self.subTest(quoi=quoi):
                    k = len(self.vus); r = self.poster(chemin, corps, type_, ent)
                    self.assertEqual(r.split(b'\r\n', 1)[0].split(b' ')[1], code, f"{quoi} : {r[:80]}")
                    self.assertEqual(len(self.vus), k, f"{quoi} : rien parti au site")
                    self.assertNotIn(T.encode(), r); self.assertNotIn(T.lower().encode(), r)
            log = (self.i / 'courtier/appels.log').read_text(); self.assertNotIn(T, log); self.assertNotIn(T.lower(), log)
            self.assertIn(b'200 OK', self.poster('/contact', multipart('{"texte": "demande"}', 'Content-Type: application/json\r\n'), mp))
            self.assertIn(b'200 OK', self.poster('/contact', 'motif=art17', 'application/x-www-form-urlencoded', 'X-Requested-With: fetch\r\n'))
        finally:
            self.C.notifier_proprietaire = ancien; self.fermer()

    def test_liste_fermee_des_formats(self):
        """Renvoi n° 102 : un POST --post n'entre que dans les formats prévus ; un test par contournement signalé."""
        notes = []; ancien = self.C.notifier_proprietaire
        self.C.notifier_proprietaire = lambda titre, texte, urgent=False: notes.append((titre, texte, urgent))
        self.ouvrir('effacement', '--post')
        T = self.temoin; fr = 'frontiereEssai'; esc = ''.join(f'\\u{ord(x):04x}' for x in T); mp = f'multipart/form-data; boundary={fr}'
        def partie(entetes, contenu): return f'--{fr}\r\n{entetes}\r\n{contenu}\r\n'
        def mpart(*parties, avant=''): return (avant + ''.join(parties) + f'--{fr}--\r\n').encode()
        cd = 'Content-Disposition: form-data; name="texte"\r\n'
        try:
            refus = (  # (quoi, corps, type, en-têtes en plus)
                # bloquant 1 : en-têtes répétés dans une partie
                ('partie : deux Content-Type', mpart(partie(cd + 'Content-Type: text/plain\r\nContent-Type: application/json\r\n', '{"t": "' + esc + '"}')), mp, ''),
                ('partie : second Content-Disposition filename*', mpart(partie(cd + "Content-Disposition: form-data; name=\"p\"; filename*=UTF-8''preuve.txt\r\n", 'propre')), mp, ''),
                # bloquant 2 : JSON à clé répétée
                ('JSON clé répétée', ('{"x": "' + esc + '", "x": "propre"}').encode(), 'application/json', ''),
                ('JSON clé répétée en profondeur', ('{"a": [{"x": "' + esc + '", "x": "propre"}]}').encode(), 'application/json', ''),
                ('partie JSON clé répétée', mpart(partie(cd + 'Content-Type: application/json\r\n', '{"x": "' + esc + '", "x": "p"}')), mp, ''),
                # liste fermée : type, charset, en-têtes, parties
                ('type hors liste', b'<p>propre</p>', 'text/html', ''),
                ('charset hors liste', b'propre', 'text/plain; charset=iso-8859-1', ''),
                ('paramètre de type en plus', b'propre', 'text/plain; charset=utf-8; x=y', ''),
                ('sans Content-Type', b'propre', '', ''),
                ('en-tête inconnu', b'motif=art17', 'application/x-www-form-urlencoded', 'X-Autre: propre\r\n'),
                ('en-tête permis répété', b'motif=art17', 'application/x-www-form-urlencoded', 'Accept: */*\r\nAccept: */*\r\n'),
                ('Transfer-Encoding', b'motif=art17', 'application/x-www-form-urlencoded', 'Transfer-Encoding: identity\r\n'),
                ('partie : en-tête inconnu', mpart(partie(cd + 'X-Partie: 1\r\n', 'propre')), mp, ''),
                ('partie : Content-Transfer-Encoding', mpart(partie(cd + 'Content-Transfer-Encoding: 8bit\r\n', 'propre')), mp, ''),
                ('partie : paramètre en plus', mpart(partie('Content-Disposition: form-data; name="texte"; x="y"\r\n', 'propre')), mp, ''),
                ('partie : sans Content-Disposition', mpart(partie('Content-Type: text/plain\r\n', 'propre')), mp, ''),
                ('partie : type hors liste', mpart(partie(cd + 'Content-Type: text/html\r\n', 'propre')), mp, ''),
                ('partie : multipart imbriqué', mpart(partie(cd + 'Content-Type: multipart/form-data; boundary=dedans\r\n', '--dedans--')), mp, ''),
                ('multipart : préambule', mpart(partie(cd, 'propre'), avant='texte caché\r\n'), mp, ''),
            )
            for quoi, corps, type_, ent in refus:
                with self.subTest(quoi=quoi):
                    k = len(self.vus); r = self.poster('/contact', corps, type_, ent) if type_ else self.poster_sans_type('/contact', corps)
                    self.assertTrue(r.split(b'\r\n', 1)[0].split(b' ')[1].startswith(b'4'), f"{quoi} : refusé ({r[:70]})")
                    self.assertEqual(len(self.vus), k, f"{quoi} : rien parti au site"); self.assertNotIn(T.encode(), r)
            self.assertNotIn(T, (self.i / 'courtier/appels.log').read_text())
            permis = (('navigateur', b'motif=art17', 'application/x-www-form-urlencoded',
                       'User-Agent: Mozilla/5.0\r\nAccept: text/html\r\nAccept-Language: fr\r\nOrigin: https://permis.test\r\n'
                       'Referer: https://permis.test/contact\r\nSec-Fetch-Mode: navigate\r\nCookie: s=propre\r\n'),
                      ('JSON utf-8 déclaré', b'{"texte": "demande", "n": [1, {"a": "b"}]}', 'application/json; charset=utf-8', ''),
                      ('texte', 'demande art. 17 — effacement'.encode(), 'text/plain;charset=UTF-8', ''),
                      ('multipart deux parties', mpart(partie(cd, 'demande'), partie('Content-Disposition: form-data; name="j"\r\nContent-Type: application/json\r\n', '{"a": 1}')), mp, ''))
            for quoi, corps, type_, ent in permis:
                with self.subTest(quoi=quoi): self.assertIn(b'200 OK', self.poster('/contact', corps, type_, ent), quoi)
        finally:
            self.C.notifier_proprietaire = ancien; self.fermer()

    def poster_sans_type(self, chemin, corps):
        p = self.C.WEB.ouvert('effaceur')['proxy']
        a, b = socket.socketpair(); a.settimeout(3)
        threading.Thread(target=p.servir, args=(b,), daemon=True).start()
        a.sendall(b'CONNECT permis.test:443 HTTP/1.1\r\nHost: permis.test:443\r\n\r\n'); tete = b''
        while not tete.endswith(b'\r\n\r\n'): tete += a.recv(1)
        with ssl.create_default_context(cadata=p.certificat_pem.decode()).wrap_socket(a, server_hostname='permis.test') as s:
            s.sendall(f'POST {chemin} HTTP/1.1\r\nHost: permis.test\r\nContent-Length: {len(corps)}\r\n\r\n'.encode() + corps); out = b''
            while (x := s.recv(65536)): out += x
        return out

    def test_messages_et_journal_fixes(self):
        """Renvoi n° 102, bloquant 3 : un hôte de redirection secret n'est pas recopié dans la réponse ; une méthode hors liste
        n'est jamais écrite telle quelle ; le journal du courtier masque aussi le verbe d'une ligne qui contient un secret."""
        T = self.temoin
        self.ouvrir('effacement', '--post')
        try:
            Parcours.reponse_site = f'HTTP/1.1 302 Found\r\nLocation: https://{T.lower()}x.{T}.test/x\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'.encode()
            r = self.poster('/contact')
            self.assertIn(b' 403 ', r.split(b'\r\n', 1)[0] + b' '); self.assertNotIn(T.encode(), r); self.assertNotIn(T.lower().encode(), r)
        finally:
            Parcours.reponse_site = None; self.fermer()
        self.C.journal('effaceur', 'web:permis.test', T, ['permis.test'], False, 'essai')
        log = (self.i / 'courtier/appels.log').read_text(); self.assertNotIn(T, log); self.assertNotIn(T.lower(), log)
        vus = []
        p = W.Proxy(['permis.test'], lambda *a: vus.append(a), resoudre=lambda h, port: ['93.184.215.14'], ouvrir=lambda a: None, delai=2)
        self.addCleanup(p.arreter)
        a, b = socket.socketpair(); a.settimeout(3)
        threading.Thread(target=p.servir, args=(b,), daemon=True).start()
        a.sendall(b'TEMOINXYZ http://permis.test/ HTTP/1.1\r\nHost: permis.test\r\n\r\n'); r = b''
        while (x := a.recv(65536)): r += x
        a.close()
        self.assertTrue(vus and all(j[0] in ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'CONNECT', 'TRACE', '?') for j in vus), vus)
        self.assertNotIn(b'TEMOINXYZ', r)

    def brut(self, requete, https=True):
        """Une requête brute de l'agent par le proxy de SON accès : dans le tunnel (HTTPS, CONNECT puis TLS) ou en clair."""
        p = self.C.WEB.ouvert('effaceur')['proxy']
        a, b = socket.socketpair(); a.settimeout(3)
        threading.Thread(target=p.servir, args=(b,), daemon=True).start()
        if not https:
            a.sendall(requete); out = b''
            while (x := a.recv(65536)): out += x
            a.close(); return out
        a.sendall(b'CONNECT permis.test:443 HTTP/1.1\r\nHost: permis.test:443\r\n\r\n'); tete = b''
        while not tete.endswith(b'\r\n\r\n'): tete += a.recv(1)
        with ssl.create_default_context(cadata=p.certificat_pem.decode()).wrap_socket(a, server_hostname='permis.test') as s:
            s.sendall(requete); out = b''
            while (x := s.recv(65536)): out += x
        return out

    @staticmethod
    def code(r): return r.split(b'\r\n', 1)[0].split(b' ')[1]

    def test_liste_fermee_pour_toutes_les_methodes_http_et_https(self):
        """Renvoi n° 103 : GET, HEAD, POST, en HTTP clair ET dans le tunnel, par la même liste fermée."""
        self.ouvrir('effacement', '--post')
        T = self.temoin
        try:
            for https in (False, True):
                cible = '/page' if https else 'http://permis.test/page'
                for methode in ('GET', 'HEAD', 'POST'):
                    for quoi, ent in (('en-tête inconnu', 'X-Token: propre\r\n'), ('doublon', 'Accept: */*\r\nAccept: */*\r\n'),
                                      ('type inconnu', 'Content-Type: application/x-inconnu\r\n'), ('Transfer-Encoding', 'Transfer-Encoding: identity\r\n')):
                        with self.subTest(https=https, methode=methode, quoi=quoi):
                            k = len(self.vus)
                            r = self.brut(f'{methode} {cible} HTTP/1.1\r\nHost: permis.test\r\n{ent}Content-Length: 0\r\n\r\n'.encode(), https)
                            self.assertTrue(self.code(r).startswith(b'4'), f"{r[:60]}"); self.assertEqual(len(self.vus), k)
                    with self.subTest(https=https, methode=methode, quoi='encodé au-delà du point fixe'):
                        valeur = T
                        for _ in range(12): valeur = valeur.replace('%', '%25').replace('C', '%43')
                        k = len(self.vus)
                        r = self.brut(f'{methode} {cible}?q={valeur} HTTP/1.1\r\nHost: permis.test\r\nContent-Length: 0\r\n\r\n'.encode(), https)
                        self.assertTrue(self.code(r).startswith(b'4'), f"{r[:60]}"); self.assertEqual(len(self.vus), k)
                    with self.subTest(https=https, methode=methode, quoi='propre'):
                        n = len(self.recus)
                        r = self.brut(f'{methode} {cible} HTTP/1.1\r\nHost: permis.test\r\nAccept: */*\r\nContent-Length: 0\r\n\r\n'.encode(), https)
                        self.assertEqual(self.code(r), b'200', r[:80]); self.assertEqual(self.recus[n][1], b'', "corps reçu par le site : vide")
            self.assertNotIn(T, (self.i / 'courtier/appels.log').read_text())
        finally: self.fermer()

    def test_post_vide_sans_type_et_corps_recu(self):
        """POST vide sans Content-Type : permis, et le site reçoit un corps vide ; sur les succès, le corps reçu est celui envoyé."""
        self.ouvrir('effacement', '--post')
        try:
            for https in (False, True):
                cible = '/privacy/delete-request' if https else 'http://permis.test/privacy/delete-request'
                with self.subTest(https=https, quoi='POST vide'):
                    n = len(self.recus)
                    r = self.brut(f'POST {cible} HTTP/1.1\r\nHost: permis.test\r\nContent-Length: 0\r\n\r\n'.encode(), https)
                    self.assertEqual(self.code(r), b'200', r[:80]); self.assertEqual(self.recus[n][1], b'')
                for type_, corps in (('application/x-www-form-urlencoded', b'motif=art17&nom=Dupont'), ('application/json', b'{"motif": "art. 17"}'),
                                     ('text/plain; charset=utf-8', 'demande d’effacement'.encode())):
                    with self.subTest(https=https, type_=type_):
                        n = len(self.recus)
                        r = self.brut(f'POST {cible} HTTP/1.1\r\nHost: permis.test\r\nContent-Type: {type_}\r\nContent-Length: {len(corps)}\r\n\r\n'.encode() + corps, https)
                        self.assertEqual(self.code(r), b'200', r[:80]); self.assertEqual(self.recus[n][1], corps, "le site reçoit exactement le corps envoyé")
        finally: self.fermer()

    def test_methode_jamais_recopiee_en_http_et_https(self):
        """Renvoi n° 103 : une méthode inconnue n'est jamais écrite au journal, ni en clair ni dans le tunnel (texte fixe « ? »)."""
        self.ouvrir('effacement', '--post')
        try:
            debut = (self.i / 'courtier/appels.log').read_text()
            for https in (False, True):
                with self.subTest(https=https):
                    r = self.brut(f'TEMOINXYZQW {"/x" if https else "http://permis.test/x"} HTTP/1.1\r\nHost: permis.test\r\n\r\n'.encode(), https)
                    self.assertTrue(self.code(r).startswith(b'4')); self.assertNotIn(b'TEMOIN', r)
            nouveau = (self.i / 'courtier/appels.log').read_text()[len(debut):]
            self.assertNotIn('TEMOIN', nouveau); self.assertIn('\t?\t', nouveau)
        finally: self.fermer()

    def test_chaque_chemin_passe_par_la_fonction_commune(self):
        """Renvoi n° 103 : HTTP clair, tunnel HTTPS (CONNECT compris), GET, HEAD, POST appellent controler_envoi."""
        WC = self.C._web; vrai = WC.controler_envoi; appels = []
        def espion(*a, **k): appels.append(k.get('methode', a[3] if len(a) > 3 else None)); return vrai(*a, **k)
        WC.controler_envoi = espion
        self.ouvrir('effacement', '--post')
        try:
            for https in (False, True):
                cible = '/x' if https else 'http://permis.test/x'
                for methode in ('GET', 'HEAD', 'POST'):
                    with self.subTest(https=https, methode=methode):
                        k = len(appels)
                        self.brut(f'{methode} {cible} HTTP/1.1\r\nHost: permis.test\r\nContent-Length: 0\r\n\r\n'.encode(), https)
                        self.assertIn(methode, appels[k:], f"{methode} {'HTTPS' if https else 'HTTP'} passe par controler_envoi")
                        if https: self.assertIn('CONNECT', appels[k:], "le CONNECT du tunnel aussi")
        finally:
            WC.controler_envoi = vrai; self.fermer()

    def test_decodage_unique_avant_toute_decision(self):
        """Renvoi n° 105, point 1 : un chemin interdit encodé au-delà de 8 tours est refusé (un seul décodage au point fixe,
        avant les chemins interdits ET les secrets), en HTTP clair et dans le tunnel."""
        self.ouvrir('effacement', '--post')
        try:
            for https in (False, True):
                for n in (9, 12):
                    chemin = 'settings'
                    for _ in range(n): chemin = chemin.replace('%', '%25').replace('s', '%73')
                    cible = f'/{chemin}' if https else f'http://permis.test/{chemin}'
                    with self.subTest(https=https, tours=n):
                        k = len(self.vus)
                        r = self.brut(f'POST {cible} HTTP/1.1\r\nHost: permis.test\r\nContent-Type: text/plain\r\nContent-Length: 6\r\n\r\npropre'.encode(), https)
                        self.assertTrue(self.code(r).startswith(b'4'), r[:70]); self.assertEqual(len(self.vus), k, "rien parti au site")
        finally: self.fermer()

    def test_hote_non_permis_jamais_au_journal(self):
        """Renvoi n° 105, point 2 : l'hôte n'est écrit au journal que s'il est permis ; sinon « hôte non permis » (HTTP et CONNECT)."""
        self.ouvrir('effacement', '--post')
        T = self.temoin.lower()
        try:
            debut = (self.i / 'courtier/appels.log').read_text()
            p = self.C.WEB.ouvert('effaceur')['proxy']
            for requete in (f'GET http://{T}.test/ HTTP/1.1\r\nHost: {T}.test\r\n\r\n'.encode(),
                            f'CONNECT {T}.test:443 HTTP/1.1\r\nHost: {T}.test:443\r\n\r\n'.encode()):
                with self.subTest(requete=requete[:8]):
                    a, b = socket.socketpair(); a.settimeout(3)
                    threading.Thread(target=p.servir, args=(b,), daemon=True).start()
                    a.sendall(requete); r = b''
                    while (x := a.recv(65536)): r += x
                    a.close(); self.assertNotIn(T.encode(), r)
            nouveau = (self.i / 'courtier/appels.log').read_text()[len(debut):]
            self.assertNotIn(T, nouveau); self.assertEqual(nouveau.count('hôte non permis'), 2, nouveau)
            self.brut(b'GET /page HTTP/1.1\r\nHost: permis.test\r\n\r\n')
            self.assertIn('\tpermis.test\t', (self.i / 'courtier/appels.log').read_text(), "un hôte permis reste au journal")
        finally: self.fermer()

    def test_multipart_et_json_aussi_en_http_clair(self):
        """Renvoi n° 105, point 3 : les formats et le détecteur valent aussi en HTTP clair (multipart, JSON)."""
        self.ouvrir('effacement', '--post')
        T = self.temoin; fr = 'frontiereEssai'; esc = ''.join(f'\\u{ord(x):04x}' for x in T)
        def envoi(type_, corps): return (f'POST http://permis.test/contact HTTP/1.1\r\nHost: permis.test\r\nContent-Type: {type_}\r\n'
                                         f'Content-Length: {len(corps)}\r\n\r\n').encode() + corps
        mp = f'multipart/form-data; boundary={fr}'
        def mpart(entetes, contenu): return f'--{fr}\r\n{entetes}\r\n{contenu}\r\n--{fr}--\r\n'.encode()
        cd = 'Content-Disposition: form-data; name="texte"\r\n'
        try:
            for quoi, type_, corps in (('JSON échappé', 'application/json', ('{"t": "' + esc + '"}').encode()),
                                       ('JSON clé répétée', 'application/json', ('{"x": "' + esc + '", "x": "p"}').encode()),
                                       ('multipart secret', mp, mpart(cd, T)),
                                       ('partie JSON échappée', mp, mpart(cd + 'Content-Type: application/json\r\n', '{"t": "' + esc + '"}')),
                                       ('pièce jointe', mp, mpart('Content-Disposition: form-data; name="p"; filename="preuve.txt"\r\n', 'propre'))):
                with self.subTest(quoi=quoi):
                    k = len(self.vus); r = self.brut(envoi(type_, corps), https=False)
                    self.assertTrue(self.code(r).startswith(b'4'), r[:70]); self.assertEqual(len(self.vus), k)
            for quoi, type_, corps in (('JSON propre', 'application/json', b'{"motif": "art. 17"}'), ('multipart propre', mp, mpart(cd, 'demande'))):
                with self.subTest(quoi=quoi):
                    n = len(self.recus); r = self.brut(envoi(type_, corps), https=False)
                    self.assertEqual(self.code(r), b'200', r[:70]); self.assertEqual(self.recus[n][1], corps)
        finally: self.fermer()

    def test_espion_aussi_sur_les_refus_precoces(self):
        """Renvoi n° 105, point 3 : le contrôle commun passe AVANT les refus précoces (hôte non permis, port, chemin interdit,
        méthode refusée), en HTTP clair et dans le tunnel."""
        WC = self.C._web; vrai = WC.controler_envoi; appels = []
        def espion(*a, **k): appels.append(k.get('methode', a[3] if len(a) > 3 else None)); return vrai(*a, **k)
        WC.controler_envoi = espion
        self.ouvrir('effacement', '--post')
        p = self.C.WEB.ouvert('effaceur')['proxy']
        def clair(requete):
            a, b = socket.socketpair(); a.settimeout(3)
            threading.Thread(target=p.servir, args=(b,), daemon=True).start()
            a.sendall(requete); r = b''
            while (x := a.recv(65536)): r += x
            a.close(); return r
        try:
            cas = (('hôte non permis (HTTP)', lambda: clair(b'GET http://autre.test/ HTTP/1.1\r\nHost: autre.test\r\n\r\n'), 'GET'),
                   ('hôte non permis (CONNECT)', lambda: clair(b'CONNECT autre.test:443 HTTP/1.1\r\nHost: autre.test:443\r\n\r\n'), 'CONNECT'),
                   ('port refusé', lambda: clair(b'GET http://permis.test:8080/ HTTP/1.1\r\nHost: permis.test:8080\r\n\r\n'), 'GET'),
                   ('chemin interdit (HTTP)', lambda: clair(b'GET http://permis.test/settings HTTP/1.1\r\nHost: permis.test\r\n\r\n'), 'GET'),
                   ('chemin interdit (HTTPS)', lambda: self.brut(b'GET /logout HTTP/1.1\r\nHost: permis.test\r\n\r\n'), 'GET'),
                   ('méthode refusée (HTTPS)', lambda: self.brut(b'PUT /x HTTP/1.1\r\nHost: permis.test\r\nContent-Length: 0\r\n\r\n'), 'PUT'))
            for quoi, faire, methode in cas:
                with self.subTest(quoi=quoi):
                    k = len(appels); r = faire()
                    self.assertTrue(self.code(r).startswith(b'4'), r[:60]); self.assertIn(methode, appels[k:], f"{quoi} : contrôle commun appelé avant le refus")
        finally:
            WC.controler_envoi = vrai; self.fermer()

    def test_post_refuse_en_session_pretee_et_option_inconnue(self):
        for args in (('effacement', '--post', '--session'), ('effacement', '--post', '--post'), ('effacement', '--effacer')):
            with self.subTest(args=args):
                r = self.outil('demander', 'permis.test', *args)
                self.assertFalse(r['ok'], r); self.assertIsNone(self.C.WEB.ouvert('effaceur'))


if __name__ == '__main__':
    unittest.main(verbosity=1)
