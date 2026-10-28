# -*- coding: utf-8 -*-
"""Accès web d'un agent, côté courtier (voie B de Rétro, 18/10/2026, docs/plans/2026-10-18-retro-web-spec.md §1).
Le proxy termine le TLS pour le seul nom de l'accès, contrôle SNI et Host, les méthodes et le corps,
puis ouvre un TLS vérifié vers l'adresse publique contrôlée. Une clé distincte est créée par accès
(cryptography) ; seuls le certificat public et son SPKI sont exportés. Les fichiers privés temporaires,
hors du montage web, sont effacés après chargement dans OpenSSL.
Le socket proxy.sock et le SPKI public sont placés dans courtier/mcp/<agent>-web (700), le seul
dossier remonté en lecture seule dans l'enveloppe. GET/HEAD, corps <= 64 Ko, chemins sensibles bloqués,
redirection hors accès refusée. Une requête par connexion ; jamais de tunnel HTTPS opaque.
Chaque requête est journalisée : méthode, hôte, octets et verdict, sans chemin ni paramètres d'URL.
Acces — les accès ouverts (un à la fois par agent) : ouverture, prolongation, échéance, fermeture (proxy arrêté, socket
supprimé, « accès fermé » au journal) ; l'état est écrit dans courtier/web/<agent>.json, lu par `berger web`.
Ce module ne lit ni le coffre ni la config : le courtier lui passe ses fonctions (journal, journal de l'agent)."""
import base64, datetime, hashlib, html, ipaddress, json, os, re, select, socket, ssl, struct, tempfile, threading, time
from pathlib import Path
from urllib.parse import parse_qsl, quote, quote_plus, unquote, urljoin, urlsplit

DUREE_DEFAUT, DUREE_MAX = 2 * 3600, 24 * 3600
CORPS_MAX, ENTETE_MAX, CONNEXIONS_MAX = 64 * 1024, 16 * 1024, 64
REPONSE_SESSION_MAX = 2 * 1024 * 1024       # avant et après décadrage ; jamais de streaming d'une session
METHODES = ("GET", "HEAD")
CHEMINS_BLOQUES = ("logout", "delete", "export", "settings", "payment")
PORT_ENVELOPPE = 3128                    # dans l'enveloppe : socat 127.0.0.1:3128 → le socket du proxy (bin/berger, serveur_mcp)
# même règle que les sites permis d'un projet (bin/berger, DOMAINE) : nom exact, pas de joker, d'IP ni de port
DOMAINE = re.compile(r"(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
SOUS_DOMAINES_MAX = 5
VERSIONS_TLS = (b"\x03\x01", b"\x03\x02", b"\x03\x03", b"\x03\x04")   # TLS 1.0 à 1.3 : enregistrement et legacy_version
HELLO_MAX, HELLO_ENREGISTREMENTS, HELLO_DELAI = 16 * 1024, 32, 10   # ClientHello : taille, fragments, secondes au plus
SAUT = {"connection", "keep-alive", "proxy-connection", "te", "trailer", "upgrade", "transfer-encoding"}   # en-têtes d'un seul saut
RAISONS = {400: "Bad Request", 403: "Forbidden", 405: "Method Not Allowed", 411: "Length Required", 413: "Payload Too Large",
           431: "Request Header Fields Too Large", 502: "Bad Gateway", 503: "Service Unavailable"}


def duree(texte):
    """« 2h », « 90m », « 1h30 » → secondes ; vide : 2 h. Au plus 24 h ; zéro, négatif ou illisible : ValueError."""
    t = str(texte or "").strip().lower()
    if not t: return DUREE_DEFAUT
    m = re.fullmatch(r"(?:(\d{1,3})h(?:(\d{1,2})m?)?|(\d{1,4})m(?:in)?)", t)
    if not m: raise ValueError(f"durée illisible « {t[:20]} » : par exemple 2h, 90m, 1h30")
    s = int(m.group(1)) * 3600 + int(m.group(2) or 0) * 60 if m.group(1) is not None else int(m.group(3)) * 60
    if s <= 0: raise ValueError("durée nulle")
    if s > DUREE_MAX: raise ValueError("durée de plus de 24 h refusée")
    return s


def libelle(s):
    h, m = divmod(int(s) // 60, 60)
    return f"{h} h{f' {m:02d}' if m else ''}" if h else f"{m} min"


def noms(texte):
    """« exemple.fr[,app.exemple.fr…] » → [domaine, sous-domaines écrits]. Chaque nom exact (règle DOMAINE) ; les suivants sont
    des sous-domaines du premier ; ni joker, ni IP, ni localhost, ni port. Sinon : ValueError."""
    l = []
    for x in str(texte or "").lower().split(","):
        x = x.strip().rstrip(".")
        if not DOMAINE.fullmatch(x) or x.endswith(".localhost"): raise ValueError(f"« {x[:60]} » n'est pas un nom de domaine exact (ni joker, ni IP, ni localhost, ni port)")
        if l and not x.endswith("." + l[0]): raise ValueError(f"« {x} » n'est pas un sous-domaine de {l[0]} : un domaine par demande")
        if x not in l: l.append(x)
    if len(l) > 1 + SOUS_DOMAINES_MAX: raise ValueError(f"{SOUS_DOMAINES_MAX} sous-domaines au plus")
    return l


def demande(args):
    """Arguments stricts d'une demande ; --session et durée dans l'un ou l'autre ordre."""
    if len(args) < 2 or not args[1].strip(): raise ValueError('web demander <domaine> "<motif>" [durée] [--session]')
    session, temps = False, None
    for arg in args[2:]:
        if arg == '--session' and not session: session = True
        elif arg.startswith('--'): raise ValueError('option inconnue ou répétée')
        elif temps is None: temps = arg
        else: raise ValueError('trop d’arguments')
    domaines = noms(args[0])
    if session and len(domaines) != 1: raise ValueError('une session exige un domaine exact unique')
    return domaines, duree(temps), session


def est_ip(h):
    try: ipaddress.ip_address(h.strip("[]")); return True
    except ValueError: return False


def publique(ip):
    """Une adresse joignable sur Internet (ni privée, ni boucle locale, ni lien local, ni réservée, ni multicast — IPv4 dans
    IPv6 comprise) ; illisible : non."""
    try: a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError: return False
    if a.version == 6 and a.ipv4_mapped: a = a.ipv4_mapped
    return a.is_global and not a.is_multicast


def propre(h):
    """Un hôte tel qu'il peut aller au journal : caractères d'un nom ou d'une IP, 80 au plus."""
    return re.sub(r"[^a-z0-9.:\[\]-]", "?", str(h).lower())[:80] or "?"


def sni(donnees):
    """Le nom du SNI du premier ClientHello TLS de `donnees` (enregistrements handshake, sans rien déchiffrer) ; None s'il
    manque encore des octets. ValueError : pas un ClientHello (version d'enregistrement ou legacy_version hors 0301-0304), plus de HELLO_MAX octets ou de HELLO_ENREGISTREMENTS
    fragments, illisible, ou pas exactement un nom (host_name) dans l'extension server_name."""
    hs, i, k = b"", 0, 0
    while True:
        if len(donnees) - i < 5: return None
        n = struct.unpack("!H", donnees[i + 3:i + 5])[0]
        if donnees[i] != 0x16 or donnees[i + 1:i + 3] not in VERSIONS_TLS or not 0 < n <= 16384: raise ValueError("pas un ClientHello TLS")
        k += 1
        if k > HELLO_ENREGISTREMENTS: raise ValueError(f"ClientHello fragmenté en plus de {HELLO_ENREGISTREMENTS} enregistrements")
        if len(donnees) - i - 5 < n: return None
        hs += donnees[i + 5:i + 5 + n]; i += 5 + n
        if hs[0] != 1: raise ValueError("pas un ClientHello TLS")
        if len(hs) >= 4:
            lg = int.from_bytes(hs[1:4], "big")
            if lg > HELLO_MAX: raise ValueError(f"ClientHello de plus de {HELLO_MAX // 1024} Ko")
            if len(hs) >= 4 + lg: return _nom_sni(hs[4:4 + lg])


def _nom_sni(c):
    try:
        if c[:2] not in VERSIONS_TLS: raise ValueError                  # legacy_version (0000, 03ff… : pas du TLS)
        p = 34; p += 1 + c[p]                                            # version, aléa, session
        p += 2 + struct.unpack("!H", c[p:p + 2])[0]; p += 1 + c[p]       # suites, compression
        fin = p + 2 + struct.unpack("!H", c[p:p + 2])[0]; p += 2
        if fin != len(c): raise ValueError
        noms_vus = []
        while p < fin:
            typ, lg = struct.unpack("!HH", c[p:p + 4]); d = c[p + 4:p + 4 + lg]; p += 4 + lg
            if len(d) != lg: raise ValueError
            if typ != 0: continue
            q, bout = 2, 2 + struct.unpack("!H", d[:2])[0]
            if bout != len(d): raise ValueError
            while q < bout:
                t, l = d[q], struct.unpack("!H", d[q + 1:q + 3])[0]; nom = d[q + 3:q + 3 + l]; q += 3 + l
                if len(nom) != l: raise ValueError
                if t == 0: noms_vus.append(nom)
    except (IndexError, struct.error, ValueError): raise ValueError("ClientHello illisible")
    if not noms_vus: raise ValueError("ClientHello sans SNI")
    if len(noms_vus) > 1: raise ValueError("ClientHello à plusieurs SNI")
    try: return noms_vus[0].decode("ascii").lower().rstrip(".")
    except UnicodeDecodeError: raise ValueError("SNI illisible")


def dossier_socket(sockets, agent): return Path(sockets) / f"{agent}-web"


def chemin_socket(sockets, agent): return dossier_socket(sockets, agent) / "proxy.sock"


def preparer_dossier(sockets, agent):
    """Le dossier du socket de l'agent (700), créé s'il manque ; un lien ou autre chose qu'un dossier : OSError (jamais suivi)."""
    Path(sockets).mkdir(mode=0o700, parents=True, exist_ok=True); d = dossier_socket(sockets, agent)
    try: d.mkdir(mode=0o700)
    except FileExistsError: pass
    if d.is_symlink() or not d.is_dir(): raise OSError(f"{d} n'est pas un dossier (lien refusé)")
    os.chmod(d, 0o700); return d


class Refus(Exception):
    def __init__(self, code, motif):
        super().__init__(motif); self.code, self.motif = code, motif


def recevoir(s, fin, quoi):
    """Un recv qui finit avant l'instant `fin` (délai FERME : un client qui envoie un octet de temps en temps ne le repousse pas)."""
    if fin - time.time() <= 0: raise Refus(408, f"{quoi} trop lente")
    s.settimeout(fin - time.time())
    try: return s.recv(8192)
    except TimeoutError: raise Refus(408, f"{quoi} trop lente")


def lire_entete(s, maxi, quoi, fin):
    """(en-tête jusqu'à la ligne vide, octets déjà lus après), avant l'instant `fin` ; plus de `maxi` octets : Refus."""
    b = b""
    while b"\r\n\r\n" not in b:
        if len(b) > maxi: raise Refus(431 if quoi == "requête" else 502, f"en-têtes de la {quoi} de plus de {maxi // 1024} Ko")
        x = recevoir(s, fin, quoi)
        if not x: raise Refus(400 if quoi == "requête" else 502, f"{quoi} incomplète")
        b += x
    tete, _, reste = b.partition(b"\r\n\r\n")
    if len(tete) > maxi: raise Refus(431 if quoi == "requête" else 502, f"en-têtes de la {quoi} de plus de {maxi // 1024} Ko")
    return tete, reste


def entetes(lignes):
    out = []
    for l in lignes:
        k, sep, v = l.partition(":")
        if not sep or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", k) or any(ord(c) < 32 and c != "\t" or ord(c) == 127 for c in v):
            raise Refus(400, "en-tête illisible")
        out.append((k, v.strip()))
    return out


def certificat_ephemere(noms_permis):
    """Clé distincte par accès ; seuls le certificat public et son SPKI sont exportés.
    Les fichiers PEM privés sont en 600 dans un dossier temporaire 700 hors du montage web,
    effacés dès que les contextes OpenSSL les ont chargés ; aucune autorité système ajoutée.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    cle = ec.generate_private_key(ec.SECP256R1())
    nom = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, noms_permis[0])])
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nom).issuer_name(nom).public_key(cle.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(maintenant - datetime.timedelta(minutes=1))
            .not_valid_after(maintenant + datetime.timedelta(days=2))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in noms_permis]), critical=False)
            .sign(cle, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM)
    spki = cle.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    contextes = {}
    with tempfile.TemporaryDirectory(prefix="berger-web-tls-") as dossier:
        c, k = Path(dossier) / "cert.pem", Path(dossier) / "cle.pem"
        c.write_bytes(pem)
        with k.open("xb") as f:
            os.chmod(k, 0o600)
            f.write(cle.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        for h in noms_permis:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.set_alpn_protocols(["http/1.1"])
            ctx.load_cert_chain(c, k)
            def verifier_sni(sock, nom, contexte, attendu=h):
                if (nom or "").lower().rstrip(".") != attendu:
                    return ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME
            ctx.set_servername_callback(verifier_sni)
            contextes[h] = ctx
    return pem, base64.b64encode(hashlib.sha256(spki).digest()).decode(), contextes


def parametre_methode(texte):
    """Paramètre de surcharge, y compris après encodages URL successifs."""
    for _ in range(8):
        if any(k.lower() == '_method' for k, v in parse_qsl(texte.replace(';', '&'), keep_blank_values=True)):
            return True
        suivant = unquote(texte)
        if suivant == texte: break
        texte = suivant
    return False


class Proxy:
    """Proxy à liste blanche d'UN accès. `journal(méthode, hôte, permis, détail)` reçoit chaque requête. `resoudre(nom, port)`
    et `ouvrir((ip, port))` sont remplaçables (tests : faux site local, aucune sortie réelle).
    `session_pretee=True` impose HTTPS et GET/HEAD indépendamment de METHODES.
    `fournisseur_cookie(hote, chemin)` renvoie une chaîne Cookie interne au courtier ; l'appelant lie
    explicitement l'identité de l'agent. Une erreur ferme la requête avant toute connexion amont.
    Le futur navigateur propriétaire utilisera un proxy distinct, jamais ce mode de prêt."""

    def __init__(self, noms_permis, journal, resoudre=None, ouvrir=None, delai=30, inactivite=120, connexions_max=CONNEXIONS_MAX, chemins_bloques=CHEMINS_BLOQUES, session_pretee=False, fournisseur_cookie=None, post_autorise=False, fournisseur_valeurs=None):
        self.post_autorise = post_autorise
        self.session_pretee, self.fournisseur_cookie = session_pretee, fournisseur_cookie
        self.fournisseur_valeurs = fournisseur_valeurs
        self.noms = {n.lower().rstrip(".") for n in noms_permis}; self.journal = journal
        self.certificat_pem, self.empreinte, self.contextes_tls = certificat_ephemere(list(noms_permis))
        self.tls_amont = ssl.create_default_context(); self.tls_amont.set_alpn_protocols(["http/1.1"])
        self.chemins_bloques = tuple(str(c).lower() for c in chemins_bloques)
        self.resoudre = resoudre or (lambda h, p: [a[4][0] for a in socket.getaddrinfo(h, p, type=socket.SOCK_STREAM)])
        self.ouvrir = ouvrir or (lambda adresse: socket.create_connection(adresse, timeout=delai))
        self.delai, self.inactivite, self.maxi, self.en_service, self.refusees = delai, inactivite, connexions_max, 0, [0, 0.0]
        self.arrete, self.actives, self.verrou, self.ecoute, self.chemin = False, set(), threading.Lock(), None, None

    # ── écoute et arrêt ──
    def ecouter(self, chemin):
        """Écoute sur le socket UNIX `chemin` (600), chaque connexion dans son fil."""
        try: os.unlink(chemin)
        except FileNotFoundError: pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); ancien = os.umask(0o177)
        try: s.bind(chemin)
        finally: os.umask(ancien)
        os.chmod(chemin, 0o600); s.listen(32); self.ecoute, self.chemin = s, chemin
        threading.Thread(target=self._accepter, daemon=True).start()

    def ecouter_local(self):
        """Navigateur propriétaire : loopback seul, port éphémère, mêmes limites."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", 0)); s.listen(32)
            self.ecoute = s
            threading.Thread(target=self._accepter, daemon=True).start()
            return s.getsockname()[1]
        except BaseException:
            s.close(); raise

    def _accepter(self):
        while not self.arrete:
            try: c, _ = self.ecoute.accept()
            except OSError: return
            self.accueillir(c)

    def accueillir(self, c):
        """Une connexion acceptée : la limite est contrôlée AVANT de créer un fil ; au-delà, fermée tout de suite (une ligne
        au journal toutes les 10 s au plus, avec le nombre : un flot de connexions ne remplit pas le journal)."""
        with self.verrou:
            libre = not self.arrete and self.en_service < self.maxi
            if libre: self.en_service += 1
        if libre:
            threading.Thread(target=self._servir_compte, args=(c,), daemon=True).start(); return
        try: c.close()
        except OSError: pass
        with self.verrou:
            self.refusees[0] += 1; n = self.refusees[0] if time.time() - self.refusees[1] >= 10 else 0
            if n: self.refusees[:] = [0, time.time()]
        if n: self.journal("?", "?", False, f"{n} connexion(s) fermée(s) : plus de {self.maxi} en même temps")

    def _servir_compte(self, c):
        try: self.servir(c)
        finally:
            with self.verrou: self.en_service -= 1

    def arreter(self):
        """Plus aucune connexion : écoute fermée, socket supprimé, connexions en cours coupées (tunnels compris)."""
        self.arrete = True
        if self.ecoute is not None:
            for f in (lambda: self.ecoute.shutdown(socket.SHUT_RDWR), self.ecoute.close):
                try: f()
                except OSError: pass
        if self.chemin:
            try: os.unlink(self.chemin)
            except FileNotFoundError: pass
        with self.verrou: actives = list(self.actives)
        for s in actives:
            try: s.shutdown(socket.SHUT_RDWR)
            except OSError: pass

    def _suivre(self, s):
        with self.verrou:
            if self.arrete: raise Refus(503, "accès fermé")
            self.actives.add(s)

    # ── une connexion ──
    def servir(self, c):
        """Une connexion du client : une requête (HTTP clair) ou un tunnel (CONNECT), puis fermeture."""
        ctx = {"m": "?", "h": "?", "amont": None, "fin": time.time() + self.delai}   # en-tête ET corps avant `fin`
        try:
            self._suivre(c); c.settimeout(self.delai)
            tete, reste = lire_entete(c, ENTETE_MAX, "requête", ctx["fin"])
            ligne, *autres = tete.decode("latin-1").split("\r\n")
            p = ligne.split(" ")
            if len(p) != 3 or not p[2].startswith("HTTP/1."): raise Refus(400, "ligne de requête illisible")
            ctx["m"] = re.sub(r"[^A-Z]", "?", p[0].upper())[:10]
            if ctx["m"] == "CONNECT": self._tunnel(c, p[1], reste, ctx)
            else: self._http(c, ctx["m"], p[1], reste, entetes(autres), ctx)
        except Refus as r:
            self.journal(ctx["m"], propre(ctx["h"]), False, r.motif)
            if ctx.get("reponse_commencee"): return
            if ctx.get("tunnel") and not ctx.get("tls"): return  # handshake inachevé : fermer sans HTTP
            c = ctx.get("client", c)
            corps = f"Berger : refusé — {r.motif}\n".encode()
            try:
                c.sendall(f"HTTP/1.1 {r.code} {RAISONS.get(r.code, 'Refus')}\r\nContent-Type: text/plain; charset=utf-8\r\n"
                          f"Content-Length: {len(corps)}\r\nConnection: close\r\n\r\n".encode() + corps)
                if ctx.get("tls"): return  # close_notify dans finally, sans shutdown TCP prématuré
                c.shutdown(socket.SHUT_WR); fin, lu = time.time() + 1, 0
                while lu < 65536 and fin - time.time() > 0:   # vider un peu (pas de RST avant la réponse), 1 s et 64 Ko au plus
                    c.settimeout(fin - time.time()); x = c.recv(65536)
                    if not x: break
                    lu += len(x)
            except OSError: pass
        except (OSError, ValueError) as e:
            self.journal(ctx["m"], propre(ctx["h"]), False, "TLS/SNI refusé" if isinstance(e, ssl.SSLError) else f"interrompu ({type(e).__name__}, {ctx.get('phase', 'requête')})")
        finally:
            # Un GET complet doit se terminer par close_notify, pas une coupure TCP.
            # unwrap envoie l'alerte et attend au plus une seconde la réponse du client.
            if ctx.get("tls"):
                try:
                    client = ctx["client"]; client.settimeout(min(1, self.delai))
                    client.unwrap().close()
                except (OSError, ValueError): pass
            for s in (c, ctx.get("client"), ctx["amont"]):
                if s is None: continue
                with self.verrou: self.actives.discard(s)
                try: s.close()
                except OSError: pass

    def _verifier(self, hote, port):
        """(nom, adresses vérifiées) ou Refus : IP directe, nom hors de l'accès, introuvable, adresse privée ou locale."""
        h = str(hote or "").lower().rstrip(".")
        if est_ip(h): raise Refus(403, "IP directe refusée")
        if h not in self.noms: raise Refus(403, "nom hors de l'accès")
        try: ips = list(dict.fromkeys(self.resoudre(h, port)))
        except OSError: ips = []
        if not ips: raise Refus(502, "nom introuvable")
        if not all(publique(x) for x in ips): raise Refus(403, "adresse privée ou locale après résolution")
        return h, ips

    def _connecter(self, ips, port, ctx):
        for ip in ips:
            try: s = self.ouvrir((ip, port))
            except OSError: continue
            ctx["amont"] = s; self._suivre(s); s.settimeout(self.delai); return s
        raise Refus(502, "site injoignable")

    def _tunnel(self, c, cible, reste, ctx):
        """Termine TLS pour le seul hôte du CONNECT, puis applique les règles HTTP avant tout amont."""
        hote, sep, port = cible.rpartition(":")
        ctx["h"] = hote or cible
        if not sep or not port.isdigit(): raise Refus(400, "CONNECT sans port")
        h, ips = self._verifier(hote, 443)
        if port != "443": raise Refus(403, "port refusé (443 seulement)")
        if reste: raise Refus(400, "données avant la réponse CONNECT refusées")
        c.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n"); ctx["tunnel"] = True
        tls = self.contextes_tls[h].wrap_socket(c, server_side=True, do_handshake_on_connect=False)
        ctx["client"] = tls
        with self.verrou: self.actives.discard(c)
        self._suivre(tls)
        tls.settimeout(max(0.01, ctx["fin"] - time.time())); tls.do_handshake()
        ctx["tls"] = True
        tete, reste = lire_entete(tls, ENTETE_MAX, "requête", ctx["fin"])
        ligne, *autres = tete.decode("latin-1").split("\r\n")
        p = ligne.split(" ")
        if len(p) != 3 or p[2] not in ("HTTP/1.0", "HTTP/1.1"): raise Refus(400, "ligne de requête illisible")
        ctx["m"] = re.sub(r"[^A-Z]", "?", p[0].upper())[:10]
        u = urlsplit(p[1])
        if not p[1].startswith("/") or u.scheme or u.netloc or "#" in p[1]:
            raise Refus(400, "cible HTTPS directe attendue")
        self._http(tls, ctx["m"], "https://" + h + p[1], reste, entetes(autres), ctx)

    def _sni(self, c, donnees):
        """(SNI, octets lus) du premier ClientHello du client, lu en HELLO_DELAI s au plus ; sinon Refus."""
        fin = time.time() + min(self.delai, HELLO_DELAI)
        try:
            while (nom := sni(donnees)) is None:
                if fin - time.time() <= 0: raise Refus(408, "ClientHello trop lent")
                c.settimeout(fin - time.time())
                try: x = c.recv(16384)
                except TimeoutError: raise Refus(408, "ClientHello trop lent")
                if not x: raise Refus(400, "ClientHello incomplet")
                donnees += x
        except ValueError as e: raise Refus(403, str(e))
        c.settimeout(self.delai); return nom, donnees

    def _valeurs_session(self, hote):
        try:
            if self.fournisseur_valeurs is None: raise ValueError()
            valeurs = self.fournisseur_valeurs(hote)
            if not isinstance(valeurs, (set, list, tuple)) or any(not isinstance(v, str) for v in valeurs): raise ValueError()
            if sum(len(v.encode('utf-8')) for v in valeurs) > 1024 * 1024: raise ValueError()
            return set(valeurs) - {''}
        except Exception: raise Refus(503, "filtre de session indisponible") from None

    def _reponse_session(self, amont, methode, ligne, rep, suite, valeurs, hote):
        """Cadrage terminé et contenu filtré AVANT le premier octet client. Aucun décompresseur implicite."""
        cl, te, ce = [], [], []
        for k, v in rep:
            if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", k) or any(ord(x) < 32 or ord(x) == 127 for x in v):
                raise Refus(502, "en-têtes de session invalides")
            if k.lower() == 'content-length': cl.append(v)
            if k.lower() == 'transfer-encoding': te.append(v.lower())
            if k.lower() == 'content-encoding': ce.append(v.lower())
        protocole, statut, *raison = ligne.split(' ', 2)
        if (protocole not in ('HTTP/1.0', 'HTTP/1.1') or not re.fullmatch(r'[0-9]{3}', statut)
                or any(ord(x) < 32 or ord(x) == 127 for x in (raison[0] if raison else ''))):
            raise Refus(502, "statut de session invalide")
        code = int(statut)
        if code < 200 or code == 206: raise Refus(502, "statut de session non pris en charge")
        if ce and ce != ['identity']: raise Refus(502, "réponse de session compressée refusée")
        for k,v in rep:
            if k.lower() == 'content-type':
                charset = re.search(r'(?:^|;)\s*charset\s*=\s*"?([^;"\s]+)', v, re.I)
                if charset and charset[1].lower() not in ('utf-8', 'utf8', 'ascii', 'us-ascii', 'iso-8859-1', 'latin1', 'latin-1'):
                    raise Refus(502, "charset de session non pris en charge")
        if len(cl) > 1 or (cl and not cl[0].isdigit()) or (cl and te) or (te and te != ['chunked']):
            raise Refus(502, "cadrage de session ambigu")
        tampon = bytearray(suite); total = len(suite); fin = time.time() + self.delai
        if total > REPONSE_SESSION_MAX: raise Refus(502, "réponse de session trop grande")
        def plus(n=65536):
            nonlocal total
            delai = fin - time.time()
            if delai <= 0: raise Refus(504, "réponse de session trop lente")
            amont.settimeout(delai)
            try: x = amont.recv(min(n, REPONSE_SESSION_MAX - total + 1))
            except OSError: raise Refus(502, "réponse de session interrompue") from None
            total += len(x)
            if total > REPONSE_SESSION_MAX: raise Refus(502, "réponse de session trop grande")
            tampon.extend(x)
            return bool(x)
        def prendre(n):
            while len(tampon) < n:
                if not plus(n-len(tampon)): raise Refus(502, "réponse de session incomplète")
            x = bytes(tampon[:n]); del tampon[:n]; return x
        if methode == 'HEAD' or code in (204, 304):
            if tampon: raise Refus(502, "corps de session inattendu")
            corps = b''
        elif te:
            morceaux = []
            for _ in range(4096):
                while b'\r\n' not in tampon:
                    if len(tampon) > 128 or not plus(): raise Refus(502, "chunk de session invalide")
                taille_brute = bytes(tampon).split(b'\r\n', 1)[0]
                if len(taille_brute) > 16 or not re.fullmatch(br'[0-9a-fA-F]+', taille_brute): raise Refus(502, "chunk de session invalide")
                prendre(len(taille_brute)+2); taille = int(taille_brute, 16)
                if taille > REPONSE_SESSION_MAX: raise Refus(502, "réponse de session trop grande")
                if taille == 0:
                    if prendre(2) != b'\r\n' or tampon: raise Refus(502, "trailers de session refusés")
                    break
                morceaux.append(prendre(taille))
                if prendre(2) != b'\r\n': raise Refus(502, "chunk de session invalide")
            else: raise Refus(502, "trop de chunks de session")
            corps = b''.join(morceaux)
        elif cl:
            taille = int(cl[0])
            if taille > REPONSE_SESSION_MAX: raise Refus(502, "réponse de session trop grande")
            corps = prendre(taille)
            if tampon: raise Refus(502, "octets après la réponse de session")
        else:
            while plus(): pass
            corps = bytes(tampon)
        if corps.startswith((b'\xff\xfe', b'\xfe\xff', b'\x00\x00\xfe\xff')):
            raise Refus(502, "BOM de session non pris en charge")
        textuel = any(k.lower() == 'content-type' and (v.lower().startswith('text/') or
                      any(t in v.lower().split(';',1)[0] for t in ('xml', 'json', 'javascript'))) for k,v in rep)
        if textuel and b'\x00' in corps:
            raise Refus(502, "encodage textuel de session non pris en charge")
        if corps.startswith((b'<\x00?\x00', b'\x00<\x00?', b'<\x00\x00\x00', b'\x00\x00\x00<')):
            raise Refus(502, "signature XML de session non prise en charge")
        prefixe = corps.removeprefix(b'\xef\xbb\xbf').lstrip(b' \t\r\n')
        if prefixe.startswith(b'<?xml') and prefixe[5:6] in (b' ', b'\t', b'\r', b'\n'):
            declaration, separateur, _ = prefixe.partition(b'?>')
            if not separateur: raise Refus(502, "déclaration XML de session incomplète")
            encodage = re.search(br'''\bencoding\s*=\s*['"]([^'"]+)['"]''', declaration, re.I)
            if encodage and encodage[1].lower() not in (b'utf-8', b'utf8', b'ascii', b'us-ascii', b'iso-8859-1', b'latin1', b'latin-1'):
                raise Refus(502, "encodage XML de session non pris en charge")
        # Réévaluation obligatoire : une erreur du fournisseur ne publie même pas les en-têtes.
        valeurs |= self._valeurs_session(hote)
        variantes = set()
        hexadecimales = set()
        for v in valeurs:
            # Encodages courants réfléchis par le site, décodables ensuite par le navigateur.
            # Les représentations supplémentaires des valeurs courtes seraient trop génériques.
            if len(v) >= 8:
                octets = {v.encode('utf-8')}
                try: octets.add(v.encode('latin-1'))
                except UnicodeError: pass
                for brut in octets:
                    for encoder in (base64.b64encode, base64.urlsafe_b64encode):
                        code = encoder(brut)
                        variantes.update((code, code.rstrip(b'=')))
                    code_hex = brut.hex().encode()
                    hexadecimales.add(code_hex)
                    variantes.update((code_hex, code_hex.upper()))
                    pourcentage = ''.join('%%%02X' % x for x in brut)
                    variantes.update((pourcentage.encode(), pourcentage.lower().encode()))
            for encodage in ('utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be'):
                variantes.add(v.encode(encodage))
            textes = {v, json.dumps(v, ensure_ascii=True)[1:-1], json.dumps(v, ensure_ascii=False)[1:-1],
                      html.escape(v, quote=True), quote(v, safe=''), quote_plus(v, safe='')}
            for t in list(textes): textes.add(re.sub(r'%[0-9A-F]{2}', lambda m:m[0].lower(), t))
            for t in textes:
                variantes.add(t.encode('utf-8'))
                try: variantes.add(t.encode('latin-1'))
                except UnicodeError: pass
        variantes.discard(b'')
        if sum(map(len, variantes)) > 8 * 1024 * 1024: raise Refus(503, "filtre de session trop grand")
        variantes = sorted(variantes, key=len, reverse=True)
        motifs_hex = [re.compile(re.escape(v), re.I) for v in sorted(hexadecimales, key=len, reverse=True)]
        def contient_variante(brut):
            return any(v in brut for v in variantes) or any(m.search(brut) for m in motifs_hex)
        def masquer(brut):
            for v in variantes: brut = brut.replace(v, b'')
            for motif in motifs_hex: brut = motif.sub(b'', brut)
            # Une suppression ne doit pas reconstituer une autre valeur à cheval sur ses bords.
            if contient_variante(brut): raise Refus(502, "réflexion de session ambiguë")
            # Refuser les échos combinant des échappements reconnus, sans réécrire leur grammaire.
            try: texte = brut.decode('utf-8')
            except UnicodeError: texte = brut.decode('latin-1')
            simples = {'"':'"', '\\':'\\', '/':'/', 'b':'\b', 'f':'\f', 'n':'\n', 'r':'\r', 't':'\t'}
            simples.update({"'":"'", 'v':'\v', '0':'\0'})
            def echappement(m):
                if m[5]: return simples[m[5]]
                if m[4]: return chr(int(m[4], 8))
                codepoint = int(next(x for x in m.groups()[:3] if x), 16)
                if codepoint > 0x10ffff: raise Refus(502, "échappement de session non pris en charge")
                return chr(codepoint)
            for _ in range(2):
                texte = unquote(html.unescape(texte))
                texte = re.sub(r'\\(?:\r\n|[\n\r\u2028\u2029])', '', texte)
                texte = re.sub(r'''\\(?:u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2})|u\{([0-9a-fA-F]{1,6})\}|([0-3][0-7]{0,2}|[4-7][0-7]?)|(["'\\/bfnrtv]))''',
                               echappement, texte)
                try: texte = texte.encode('utf-16', errors='surrogatepass').decode('utf-16')
                except UnicodeError: raise Refus(502, "échappement de session non pris en charge") from None
                if any(v in texte for v in valeurs): raise Refus(502, "réflexion de session encodée refusée")
            return brut
        corps = masquer(corps)
        enlever = SAUT | {'content-length', 'content-encoding', 'set-cookie', 'set-cookie2', 'etag', 'digest',
                          'content-md5', 'content-range', 'accept-ranges'}
        enlever |= {t.strip().lower() for k,v in rep if k.lower() == 'connection' for t in v.split(',')}
        propres = []
        for k,v in rep:
            if k.lower() in enlever: continue
            if contient_variante(k.encode('ascii')): continue
            propres.append(k.encode('ascii') + b': ' + masquer(v.encode('latin-1')) + b'\r\n')
        raison = masquer((raison[0] if raison else '').encode('latin-1'))
        tete = protocole.encode() + b' ' + statut.encode() + b' ' + raison + b'\r\n' + b''.join(propres)
        return tete + f"Content-Length: {len(corps)}\r\nConnection: close\r\n\r\n".encode() + corps, len(corps)

    def _http(self, c, methode, cible, reste, en, ctx):
        """GET ou HEAD http://nom/… : vers l'adresse vérifiée, Connection: close ; redirection hors de l'accès refusée."""
        u = urlsplit(cible)
        if u.scheme not in (("https",) if ctx.get("tls") else ("http",)) or not u.netloc: raise Refus(400, "requête directe refusée (URL absolue http:// attendue)")
        ctx["h"] = u.hostname or "?"
        if self.session_pretee and (not ctx.get("tls") or methode not in ("GET", "HEAD")):
            raise Refus(405, "session prêtée : HTTPS, GET et HEAD seuls")
        if methode not in (("GET", "HEAD", "POST") if self.post_autorise else METHODES): raise Refus(405, f"méthode {methode} refusée (GET et HEAD seuls)")
        port_attendu = 443 if ctx.get("tls") else 80
        try: port = u.port or port_attendu
        except ValueError: raise Refus(400, "port illisible")
        h, ips = self._verifier(u.hostname, port_attendu)
        if port != port_attendu: raise Refus(403, f"port {port} refusé (80 seulement en clair)")
        cles = {k.lower(): v for k, v in en}
        if {'x-http-method-override', 'x-http-method', 'x-method-override'} & cles.keys():
            raise Refus(403, "surcharge de méthode refusée")
        if parametre_methode(u.query): raise Refus(403, "paramètre de surcharge de méthode refusé")
        for cle in ("host", "content-length", "transfer-encoding"):
            if sum(k.lower() == cle for k, _ in en) > 1: raise Refus(400, "en-têtes ambigus refusés")
        host = cles.get("host", "").lower().rstrip(".")
        if ctx.get("tls") and host not in (h, h + ":443"):
            raise Refus(400, "Host différent du CONNECT")
        chemin_decode = (u.path + '?' + u.query).lower()
        for _ in range(8):
            suivant = unquote(chemin_decode).lower()
            if suivant == chemin_decode: break
            chemin_decode = suivant
        if any(x in chemin_decode for x in self.chemins_bloques): raise Refus(403, "chemin bloqué")
        if "host" in cles and cles["host"].lower().split(":")[0].rstrip(".") != h: raise Refus(400, "en-tête Host différent du nom de l'URL")
        if "transfer-encoding" in cles: raise Refus(411, "corps de taille inconnue (Transfer-Encoding) refusé")
        lg = cles.get("content-length", "0").strip()
        if not lg.isdigit(): raise Refus(400, "Content-Length illisible")
        if int(lg) > CORPS_MAX: raise Refus(413, f"corps de plus de {CORPS_MAX // 1024} Ko refusé")
        corps = reste
        while len(corps) < int(lg):
            x = recevoir(c, ctx["fin"], "requête")
            if not x: raise Refus(400, "corps incomplet")
            corps += x
        corps = corps[:int(lg)]
        if corps:
            texte_corps = corps.decode('utf-8', errors='replace')
            surcharge = parametre_methode(texte_corps)
            type_corps = cles.get('content-type', '').split(';', 1)[0].strip().lower()
            if type_corps == 'application/json':
                try: donnees = json.loads(corps)
                except (ValueError, UnicodeError): raise Refus(400, "corps JSON illisible") from None
                surcharge |= isinstance(donnees, dict) and any(k.lower() == '_method' for k in donnees)
            if type_corps == 'multipart/form-data':
                surcharge |= bool(re.search(r'''(?i)\bname\s*=\s*(?:["']_method["']|_method(?=[;\s]|$))''', texte_corps))
            if surcharge: raise Refus(403, "paramètre de surcharge de méthode refusé")
        enlever = SAUT | {x.strip().lower() for x in cles.get("connection", "").split(",")}
        garder = [(k, v) for k, v in en if k.lower() not in enlever and k.lower() not in {"host", "content-length"} and not k.lower().startswith("proxy-")]
        valeurs_session = set()
        if self.session_pretee:
            valeurs_session = self._valeurs_session(h)
            garder = [(k, v) for k, v in garder if k.lower() not in {"cookie", "accept-encoding", "range", "if-range"}]
            garder.append(("Accept-Encoding", "identity"))
            try:
                if self.fournisseur_cookie is None: raise ValueError()
                cookie = self.fournisseur_cookie(h, u.path or "/")
                if not isinstance(cookie, str) or any(ord(x) < 32 or ord(x) > 126 for x in cookie): raise ValueError()
            except Exception: raise Refus(503, "session indisponible") from None
            if cookie:
                garder.append(("Cookie", cookie))
                valeurs_session.update(part.partition("=")[2] for part in cookie.split("; ") if "=" in part)
        chemin = (u.path or "/") + (f"?{u.query}" if u.query else "")
        requete = f"{methode} {chemin} HTTP/1.1\r\nHost: {h}\r\nContent-Length: {len(corps)}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in garder) + "Connection: close\r\n\r\n"
        amont = self._connecter(ips, port_attendu, ctx)
        if ctx.get("tls"):
            brut = amont
            amont = self.tls_amont.wrap_socket(brut, server_hostname=h, do_handshake_on_connect=False)
            ctx["amont"] = amont
            with self.verrou: self.actives.discard(brut)
            self._suivre(amont)
            try: amont.do_handshake()
            except ssl.SSLError: raise Refus(502, "TLS du site non vérifié")
        ctx["phase"] = "envoi amont"
        amont.sendall(requete.encode("latin-1") + corps)
        ctx["phase"] = "lecture en-têtes amont"
        tete, suite = lire_entete(amont, CORPS_MAX, "réponse", time.time() + self.delai)
        amont.settimeout(self.delai); c.settimeout(self.delai)
        ligne, *autres = tete.decode("latin-1").split("\r\n")
        st = ligne.split(" ")
        if len(st) < 2 or not st[1].isdigit(): raise Refus(502, "réponse illisible")
        rep = [(k, v.strip()) for k, _, v in (l.partition(":") for l in autres)]
        loc = next((v for k, v in rep if k.strip().lower() == "location"), None)
        if 300 <= int(st[1]) < 400 and loc:
            lu = urlsplit(urljoin(cible, loc)); lh = (lu.hostname or "").rstrip(".")
            if lu.scheme not in ("http", "https") or est_ip(lh) or lh not in self.noms:
                if self.session_pretee: raise Refus(403, "redirection de session hors accès refusée")
                ctx["h"] = h; raise Refus(403, f"redirection vers {propre(lh)} refusée (hors de l'accès)")
        if self.session_pretee:
            reponse, n = self._reponse_session(amont, methode, ligne, rep, suite, valeurs_session, h)
            ctx['reponse_commencee'] = True
            c.sendall(reponse)
            self.journal(methode, h, True, f"{st[1]}, {n} octets filtrés")
            return
        cl_reponse = [v for k, v in rep if k.strip().lower() == "content-length"]
        te_reponse = any(k.strip().lower() == "transfer-encoding" for k, v in rep)
        if len(cl_reponse) > 1 or cl_reponse and not cl_reponse[0].isdigit():
            raise Refus(502, "cadrage de réponse illisible")
        # Content-Length borne le message : ne pas relire une connexion TLS déjà fermée
        # après le dernier octet. HEAD et les statuts sans corps n'en consomment aucun.
        restant = None if te_reponse or not cl_reponse else int(cl_reponse[0])
        if methode == "HEAD" or int(st[1]) in (204, 304): restant = 0
        if restant is not None: suite = suite[:restant]; restant -= len(suite)
        rep = [(k, v) for k, v in rep if k.strip().lower() not in SAUT and not (self.session_pretee and k.strip().lower() == "set-cookie")]
        ctx["phase"] = "envoi en-têtes client"
        ctx["reponse_commencee"] = True
        c.sendall((ligne + "\r\n" + "".join(f"{k}: {v}\r\n" for k, v in rep) + "Connection: close\r\n\r\n").encode("latin-1") + suite)
        n = len(suite)
        while restant is None or restant > 0:
            ctx["phase"] = "lecture corps amont"
            x = amont.recv(min(65536, restant) if restant is not None else 65536)
            if not x:
                if restant: raise Refus(502, "réponse interrompue avant Content-Length")
                break
            ctx["phase"] = "envoi corps client"
            c.sendall(x); n += len(x)
            if restant is not None: restant -= len(x)
        self.journal(methode, h, True, f"{st[1]}, {n} octets")


class Acces:
    """Les accès web ouverts, un par agent, tenus par le courtier. `journal(agent, outil, verbe, args, permis, détail)` et
    `journal_agent(agent, texte)` sont ceux du courtier ; `fabrique(noms, journal)` crée le proxy (remplaçable en test)."""

    def __init__(self, sockets, etats, journal, journal_agent, fabrique=Proxy, sessions=None, avant_effacer=None):
        self.sockets, self.etats = Path(sockets), Path(etats)
        self.journal, self.journal_agent, self.fabrique = journal, journal_agent, fabrique
        self.ouverts, self.verrou = {}, threading.RLock()
        self.verrou_nettoyage = threading.Lock()
        self.sessions, self.avant_effacer = sessions, avant_effacer
        self.residuels = {}  # agent → domaine : ancien état dont le nettoyage reste à faire

    def ouvert(self, agent): return self.ouverts.get(agent)

    def chemin(self, agent): return chemin_socket(self.sockets, agent)

    def _armer(self, agent, acces):
        """Sous verrou global : un callback ancien ne possède jamais le nouvel accès ni sa prolongation."""
        ancien = acces.get("minuteur")
        if ancien is not None: ancien.cancel()
        jeton = object(); acces["jeton"] = jeton
        minuteur = threading.Timer(max(0, acces["fin_ts"] - time.time()), self._expirer, args=(agent, acces, jeton))
        minuteur.daemon = True; acces["minuteur"] = minuteur; minuteur.start()

    def _expirer(self, agent, acces, jeton):
        self.fermer(agent, "échéance", _attendu=acces, _jeton=jeton)

    def _etat(self, agent):
        a = self.ouverts[agent]; self.etats.mkdir(parents=True, exist_ok=True)
        f = self.etats / f"{agent}.json"; tmp = self.etats / f".{agent}.json.tmp"
        tmp.write_text(json.dumps({"agent": agent, "noms": a["noms"], "fin_ts": a["fin_ts"], "session": a.get("session", False), "socket": str(self.chemin(agent)),
                                   "fin": datetime.datetime.fromtimestamp(a["fin_ts"]).isoformat(timespec="minutes")}, ensure_ascii=False))
        tmp.replace(f)

    def ouvrir(self, agent, noms_permis, secondes, session=False):
        with self.verrou:
            if agent in self.residuels: raise RuntimeError("nettoyage de l'ancien accès de cet agent en attente")
            if agent in self.ouverts: raise RuntimeError(f"un accès web est déjà ouvert pour {agent} ({self.ouverts[agent]['noms'][0]}) : un à la fois")
            dom = noms_permis[0]
            if session:
                if self.sessions is None or len(noms_permis) != 1: raise RuntimeError("session indisponible : domaine unique et coffre requis")
                if dom in self.residuels.values() or (self.etats / "nettoyage" / (dom + ".json")).exists(): raise RuntimeError("nettoyage de session en attente")
                if any(a.get("session") and a["noms"][0] == dom for a in self.ouverts.values()): raise RuntimeError("session déjà prêtée sur ce domaine")
            p = self.fabrique(list(noms_permis), lambda m, h, ok, d: self.journal(agent, f"web:{dom}", m, [h], ok, d))
            if session:
                p.session_pretee = True
                p.fournisseur_cookie = lambda h, chemin: self.sessions.cookie(h, chemin, secure=True, agent=agent)
                p.fournisseur_valeurs = lambda h: self.sessions.valeurs_session(h, agent)
            preparer_dossier(self.sockets, agent)
            try:
                p.ecouter(str(self.chemin(agent)))
                if getattr(p, "empreinte", None):
                    f = dossier_socket(self.sockets, agent) / "spki"
                    f.write_text(p.empreinte + "\n"); os.chmod(f, 0o600)
            except Exception:
                p.arreter()
                (dossier_socket(self.sockets, agent) / "spki").unlink(missing_ok=True)
                raise
            self.ouverts[agent] = {"noms": list(noms_permis), "fin_ts": time.time() + secondes, "proxy": p, "session": bool(session)}
            self._etat(agent); fin = self.ouverts[agent]["fin_ts"]
            self._armer(agent, self.ouverts[agent])
        texte = f"accès ouvert à {', '.join(noms_permis)} pour {libelle(secondes)}, jusqu'au {datetime.datetime.fromtimestamp(fin):%d/%m à %H:%M}"
        self.journal(agent, f"web:{dom}", "ouvrir", [], True, texte)
        self.journal_agent(agent, f"accès web : {texte} (GET et HEAD, proxy http://127.0.0.1:{PORT_ENVELOPPE} dans l'enveloppe de ton serveur MCP web)")
        return texte

    def prolonger(self, agent, domaine, secondes):
        with self.verrou:
            a = self.ouverts.get(agent)
            if not a or a["noms"][0] != domaine: raise RuntimeError(f"aucun accès web ouvert à {domaine} pour {agent}")
            a["fin_ts"] += secondes; self._etat(agent); fin = a["fin_ts"]
            self._armer(agent, a)
        texte = f"accès à {domaine} prolongé de {libelle(secondes)}, jusqu'au {datetime.datetime.fromtimestamp(fin):%d/%m à %H:%M}"
        self.journal(agent, f"web:{domaine}", "prolonger", [], True, texte); self.journal_agent(agent, f"accès web : {texte}")
        return texte

    def fermer(self, agent, raison, *, _attendu=None, _jeton=None):
        """Proxy arrêté, socket et état supprimés, « accès fermé » au journal ; False s'il n'y avait aucun accès."""
        with self.verrou:
            a = self.ouverts.get(agent)
            if not a: return False
            if _attendu is not None:
                if a is not _attendu or a.get("jeton") is not _jeton: return False
                if time.time() < a["fin_ts"]:
                    self._armer(agent, a); return False
            if a.get("minuteur") is not None: a["minuteur"].cancel()
            try: a["proxy"].arreter()
            except Exception: pass
            if a.get("session"):
                try: self._marquer(agent, a["noms"][0])
                except OSError:
                    a["fin_ts"] = 0  # proxy arrêté ; garder état et réservation, réessayer au prochain tour
                    return False
            self.ouverts.pop(agent, None)
            for f in (self.chemin(agent), dossier_socket(self.sockets, agent) / "spki", self.etats / f"{agent}.json"): f.unlink(missing_ok=True)
        if a.get("session"): self._nettoyages()
        self.journal(agent, f"web:{a['noms'][0]}", "fermer", [], True, f"accès fermé ({raison})")
        self.journal_agent(agent, f"accès web à {a['noms'][0]} : accès fermé ({raison})" + (" ; déconnecte-toi ou révoque la session côté site" if a.get("session") else ""))
        return True

    def _marquer(self, agent, domaine):
        d = self.etats / "nettoyage"; d.mkdir(parents=True, exist_ok=True)
        f = d / (domaine + ".json")
        with f.open("w") as flux:
            json.dump({"agent": agent, "domaine": domaine}, flux)
            flux.flush(); os.fsync(flux.fileno())

    def _nettoyages(self):
        # Une seule transaction de nettoyage, sans attente pour les autres fermetures.
        # La marque persistante réserve le domaine pendant les sauvegardes hors verrou global.
        if not self.verrou_nettoyage.acquire(blocking=False): return
        try:
            with self.verrou: fichiers = list((self.etats / "nettoyage").glob("*.json"))
            for f in fichiers:
                try:
                    with self.verrou:
                        brut = f.read_bytes(); marque = json.loads(brut)
                        identite = f.stat().st_mtime_ns
                        if self.sessions is None: continue
                    if self.avant_effacer: self.avant_effacer()
                    self.sessions.effacer(marque["domaine"])
                    with self.verrou:
                        if f.stat().st_mtime_ns == identite and f.read_bytes() == brut: f.unlink()
                except Exception:
                    # Pas d'exception ou de valeur du coffre au journal ; marque conservée, prochain tour.
                    continue
        finally: self.verrou_nettoyage.release()

    def tour(self):
        """À chaque tour de la boucle du courtier : échéances, puis fermetures demandées par `berger web fermer <agent>`."""
        self._reprendre_etats()
        with self.verrou: echeances = [(agent, a, a.get("jeton")) for agent,a in self.ouverts.items() if time.time() >= a["fin_ts"]]
        for agent, a, jeton in echeances:
            self.fermer(agent, "échéance", _attendu=a, _jeton=jeton)
        for f in self.etats.glob("*.fermer") if self.etats.is_dir() else []:
            try: par = f.read_text().strip()[:60] or "le propriétaire"
            except OSError: continue
            f.unlink(missing_ok=True); self.fermer(f.stem, f"par {par}")
        self._nettoyages()

    def _reprendre_etats(self):
        """Réserver et fermer les états sans proxy actif ; un échec sera repris au prochain tour."""
        with self.verrou:
            for f in self.etats.glob("*.json") if self.etats.is_dir() else []:
                agent = f.stem
                if agent in self.ouverts: continue
                try:
                    ancien = json.loads(f.read_text()); dom = (ancien.get("noms") or ["?"])[0]
                    if ancien.get("session"): self.residuels[agent] = dom
                except OSError: continue
                except ValueError: dom = "?"
                try:
                    # Le proxy ancien est mort : retirer ses artefacts même si la marque échoue.
                    self.chemin(agent).unlink(missing_ok=True)
                    (dossier_socket(self.sockets, agent) / "spki").unlink(missing_ok=True)
                    if agent in self.residuels: self._marquer(agent, self.residuels[agent])
                    f.unlink(missing_ok=True)  # seulement après écriture de la marque
                except OSError: continue
                self.residuels.pop(agent, None)  # la marque réserve désormais le domaine
                self.journal(agent, f"web:{dom}", "fermer", [], True, "accès fermé (redémarrage du courtier)")
                self.journal_agent(agent, f"accès web à {dom} : accès fermé (redémarrage du courtier) ; redemande-le si besoin ; déconnecte-toi ou révoque la session côté site")

    def nettoyer(self):
        """Au démarrage du courtier : fermer les anciens accès, jamais les rouvrir."""
        with self.verrou:
            for f in self.etats.glob("*.fermer") if self.etats.is_dir() else []:
                if f.stem not in self.ouverts: f.unlink(missing_ok=True)
        self._reprendre_etats()
        self._nettoyages()
