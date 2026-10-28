#!/usr/bin/env python3
"""Tests de l'accès web d'un agent (voie B, fusion 1/3 : proxy et cycle ; docs/plans/2026-10-18-retro-web-spec.md §1) —
sans modèle, sans réseau (faux site local, résolution remplacée), installation JETABLE, VRAI courtier chargé comme module.
PROXY (courtier/_web.py) — nom permis : page reçue ; autre nom, IP directe, adresse privée ou locale APRÈS résolution,
redirection hors de l'accès, méthode hors GET/HEAD, corps > 64 Ko, requête directe, Host différent : refusés, sans connexion
au site ; CONNECT tunnelé sans déchiffrement (443 seulement) ; chaque requête au journal (méthode, hôte, octets, permis ou
refusé), jamais de paramètres d'URL ; arrêt : le tunnel ouvert tombe ; socket UNIX réel (NON JOUÉ si AF_UNIX est refusé).
DURÉE ET NOMS — 2 h par défaut, 24 h au plus ; un nom exact (+ sous-domaines écrits), ni joker, ni IP, ni localhost.
CYCLE (courtier) — droit `web` ; demande → validation (propriétaire seul, auto-validation refusée, lecture seule refusée) ;
durée fixée dans la validation (`berger valider <n> --duree`) ; ouverture ; un accès à la fois ; prolongation = nouvelle
validation ; refus et expiration : rien d'ouvert ; échéance et `berger web fermer` : proxy arrêté, socket supprimé,
« accès fermé » au journal ; redémarrage du courtier : accès fermés, jamais rouverts en silence.
Usage : python3 tests/web.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.machinery, importlib.util, json, os, socket, struct, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def charger(nom, f):
    loader = importlib.machinery.SourceFileLoader(nom, str(f))
    spec = importlib.util.spec_from_loader(nom, loader); m = importlib.util.module_from_spec(spec); loader.exec_module(m); return m


W = charger("web_essai", SRC / "courtier/_web.py")

# ───────────── faux site local (HTTP clair) et faux 443 (écho : un tunnel ne déchiffre rien) ─────────────
vus = []                                               # (méthode, chemin, en-têtes) reçus par le faux site


class Site(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def repondre(self, corps=True):
        vus.append((self.command, self.path, dict(self.headers)))
        n = int(self.headers.get("Content-Length") or 0)
        if n: self.rfile.read(n)
        cibles = {"/redir-dehors": "http://ailleurs.test/", "/redir-dedans": "http://permis.test/autre", "/redir-relative": "/autre",
                  "/redir-sous": "http://sous.permis.test/", "/redir-ip": "http://93.184.215.14/"}
        if self.path in cibles:
            self.send_response(302); self.send_header("Location", cibles[self.path]); self.send_header("Content-Length", "0"); self.end_headers(); return
        b = b"PERMIS-OK" + (f" corps={n}".encode() if n else b"")
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers()
        if corps: self.wfile.write(b)

    def do_GET(self): self.repondre()
    def do_HEAD(self): self.repondre(False)
    def do_POST(self): self.repondre()


site = ThreadingHTTPServer(("127.0.0.1", 0), Site); threading.Thread(target=site.serve_forever, daemon=True).start()
echo = socket.socket(); echo.bind(("127.0.0.1", 0)); echo.listen(8)


def servir_echo():
    while True:
        c, _ = echo.accept()
        def un(c):
            while True:
                try: x = c.recv(65536)
                except OSError: break
                if not x: break
                c.sendall(x)
            c.close()
        threading.Thread(target=un, args=(c,), daemon=True).start()


threading.Thread(target=servir_echo, daemon=True).start()
PUB = "93.184.215.14"                                  # adresse publique factice : jamais contactée, le test la relie au faux site
RESOLUTION = {"permis.test": [PUB], "sous.permis.test": [PUB], "prive.permis.test": ["10.0.0.5"], "boucle.permis.test": ["127.0.0.1"],
              "lien.permis.test": ["169.254.169.254"], "v6.permis.test": ["::1"], "ula.permis.test": ["fd00::1"],
              "mixte.permis.test": [PUB, "192.168.1.1"], "mappe.permis.test": ["::ffff:127.0.0.1"], "cgnat.permis.test": ["100.64.0.1"],
              "ailleurs.test": [PUB]}
appels = []                                            # connexions sortantes demandées par le proxy


def ouvrir(adresse):
    appels.append(adresse); ip, port = adresse[:2]
    if ip == PUB and port == 80: return socket.create_connection(site.server_address, timeout=10)
    if ip == PUB and port == 443: return socket.create_connection(echo.getsockname(), timeout=10)
    raise OSError(f"adresse inattendue {adresse}")


jx = []
NOMS = ["permis.test", "sous.permis.test"] + [n for n in RESOLUTION if n.endswith(".permis.test") and n != "sous.permis.test"]
P = W.Proxy(NOMS, lambda *a: jx.append(a), resoudre=lambda h, p: RESOLUTION.get(h, []), ouvrir=ouvrir, delai=10)


def requete(brut, p=P, apres=None):
    """Envoie `brut` au proxy par une paire de sockets (AF_UNIX n'est pas requis) ; rend tout ce qu'il renvoie."""
    a, b = socket.socketpair(); th = threading.Thread(target=p.servir, args=(b,), daemon=True); th.start()
    a.settimeout(10); a.sendall(brut); out = b""
    if apres: out = apres(a)
    try:
        while True:
            x = a.recv(65536)
            if not x: break
            out += x
    except OSError: pass
    a.close(); th.join(5); return out


def cas(brut, attendu, texte, connexion=None):
    del jx[:]; n = len(appels); out = requete(brut)
    ok = out.startswith(attendu.encode()) if isinstance(attendu, str) else attendu(out)
    if connexion is not None: ok = ok and (len(appels) > n) == connexion
    dire(ok and len(jx) == 1, texte + ("" if ok and len(jx) == 1 else f" — reçu {out[:120]!r}, journal {jx}"))
    return out


g = lambda u, m="GET", plus="": f"{m} {u} HTTP/1.1\r\nHost: {u.split('/')[2]}\r\n{plus}\r\n".encode()

# ── PROXY : permis ──
out = cas(g("http://permis.test/"), lambda o: o.startswith(b"HTTP/1.") and b" 200 " in o.split(b"\r\n")[0] and o.endswith(b"PERMIS-OK"),
          "GET http://permis.test/ : page reçue", connexion=True)
dire(jx and jx[0][:3] == ("GET", "permis.test", True) and "octets" in jx[0][3], f"journal : méthode, hôte, octets, permis ({jx[:1]})")
dire(vus and vus[-1][2].get("Connection", "").lower() == "close" and not any(k.lower().startswith("proxy-") for k in vus[-1][2]),
     "vers le site : Connection: close, aucun en-tête Proxy-*")
cas(g("http://permis.test/", "HEAD"), lambda o: b" 200 " in o.split(b"\r\n")[0] and b"PERMIS-OK" not in o, "HEAD permis : en-têtes reçus, sans corps", connexion=True)
cas(g("http://sous.permis.test/"), lambda o: o.endswith(b"PERMIS-OK"), "sous-domaine écrit dans l'accès : permis", connexion=True)
cas(g("http://PERMIS.TEST./"), lambda o: o.endswith(b"PERMIS-OK"), "nom en majuscules et point final : ramené au nom exact, permis")
del jx[:]; cas(g("http://permis.test/page?jeton=valeurfactice&x=y#frag"), lambda o: o.endswith(b"PERMIS-OK"), "GET avec paramètres : permis")
dire(not any("jeton" in str(x) or "valeurfactice" in str(x) or "page" in str(x) for x in jx), f"journal sans chemin ni paramètres d'URL ({jx})")
cas(g("http://permis.test/", plus="Content-Length: 1000\r\n") + b"x" * 1000, lambda o: o.endswith(b"PERMIS-OK corps=1000"), "GET avec un corps de 1 000 octets : permis")

# ── PROXY : refus ──
for u, quoi in (("http://ailleurs.test/", "autre nom"), ("http://permis.test.ailleurs.test/", "nom qui commence par le nom permis"),
                ("http://permis.test@ailleurs.test/", "nom permis en identifiant d'URL"), ("http://93.184.215.14/", "IP directe"),
                ("http://[::1]/", "IP v6 directe"), ("http://permis.test:8080/", "autre port")):
    cas(g(u), lambda o: b" 403 " in o.split(b"\r\n")[0] or b" 400 " in o.split(b"\r\n")[0], f"{quoi} ({u}) : refusé, aucune connexion", connexion=False)
    dire(jx and jx[0][2] is False, f"{quoi} : REFUSÉ au journal ({jx[:1]})")
for h in ("prive", "boucle", "lien", "v6", "ula", "mixte", "mappe", "cgnat"):
    cas(g(f"http://{h}.permis.test/"), lambda o: b" 403 " in o.split(b"\r\n")[0], f"{h}.permis.test ({RESOLUTION[h + '.permis.test']}) : adresse privée ou locale après résolution, refusé", connexion=False)
dire(jx and "priv" in jx[0][3], f"motif au journal : adresse privée ({jx[:1]})")
cas(b"GET http://inconnu.permis.test/ HTTP/1.1\r\nHost: inconnu.permis.test\r\n\r\n", lambda o: b" 403 " in o.split(b"\r\n")[0], "nom non écrit dans l'accès : refusé", connexion=False)
for m in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
    cas(g("http://permis.test/", m, "Content-Length: 0\r\n"), lambda o: b" 405 " in o.split(b"\r\n")[0], f"{m} : refusé (GET et HEAD seuls)", connexion=False)
cas(g("http://permis.test/", plus="Content-Length: 70000\r\n") + b"x" * 1024, lambda o: b" 413 " in o.split(b"\r\n")[0], "corps de plus de 64 Ko : refusé", connexion=False)
cas(g("http://permis.test/", plus="Transfer-Encoding: chunked\r\n") + b"0\r\n\r\n", lambda o: b" 4" in o.split(b"\r\n")[0][8:12], "corps « chunked » (taille inconnue) : refusé", connexion=False)
cas(b"GET / HTTP/1.1\r\nHost: permis.test\r\n\r\n", lambda o: b" 400 " in o.split(b"\r\n")[0], "requête directe (sans URL absolue) : refusée", connexion=False)
cas(b"GET http://permis.test/ HTTP/1.1\r\nHost: ailleurs.test\r\n\r\n", lambda o: b" 400 " in o.split(b"\r\n")[0], "Host différent du nom de l'URL : refusé", connexion=False)
cas(b"GET http://permis.test/ HTTP/1.1\r\nX: " + b"a" * 20000 + b"\r\n\r\n", lambda o: b" 431 " in o.split(b"\r\n")[0], "en-têtes de plus de 16 Ko : refusés", connexion=False)
cas(g("http://permis.test/redir-dehors"), lambda o: b" 403 " in o.split(b"\r\n")[0], "redirection vers un autre nom : refusée")
dire(jx and "redirection" in jx[0][3] and jx[0][2] is False, f"redirection hors de l'accès : REFUSÉ au journal ({jx[:1]})")
cas(g("http://permis.test/redir-ip"), lambda o: b" 403 " in o.split(b"\r\n")[0], "redirection vers une IP : refusée")
for c in ("dedans", "relative", "sous"):
    cas(g(f"http://permis.test/redir-{c}"), lambda o: b" 302 " in o.split(b"\r\n")[0], f"redirection dans l'accès ({c}) : transmise")

# ── PROXY : CONNECT (tunnel, sans déchiffrement ; SNI du premier ClientHello lu avant de relayer) ──
def client_hello(sni=None, fragments=1, longueur=None, enr=b"\x03\x01", legacy=b"\x03\x03"):
    """Un ClientHello TLS minimal (enregistrement handshake), SNI facultatif, découpé en `fragments` enregistrements ; `enr` :
    version de l'enregistrement, `legacy` : legacy_version du ClientHello."""
    ext = b""
    if sni is not None:
        n = sni.encode(); e = b"\x00" + struct.pack("!H", len(n)) + n; ext = struct.pack("!HH", 0, len(e) + 2) + struct.pack("!H", len(e)) + e
    corps = legacy + b"\x00" * 32 + b"\x00" + b"\x00\x02\x13\x01" + b"\x01\x00" + struct.pack("!H", len(ext)) + ext
    hs = b"\x01" + struct.pack("!I", longueur if longueur is not None else len(corps))[1:] + corps
    k = -(-len(hs) // fragments)
    return b"".join(b"\x16" + enr + struct.pack("!H", len(hs[x:x + k])) + hs[x:x + k] for x in range(0, len(hs), k))


HELLO = client_hello("permis.test")


def refuse_sni(donnees):
    try: W.sni(donnees); return False
    except ValueError: return True


def aller_retour(a, hello=HELLO, morceaux=1, pause=0.0):
    tete = b""
    while b"\r\n\r\n" not in tete:
        x = a.recv(4096)
        if not x: return tete
        tete += x
    k = -(-len(hello) // morceaux)
    try:
        for x in range(0, len(hello), k): a.sendall(hello[x:x + k]); time.sleep(pause)
        time.sleep(0.2); retour = a.recv(65536); a.shutdown(socket.SHUT_WR)
    except OSError: retour = b""
    return tete + b"|" + retour


del jx[:]
out = requete(b"CONNECT permis.test:443 HTTP/1.1\r\nHost: permis.test:443\r\n\r\n", apres=aller_retour)
dire(b" 200 " in out.split(b"\r\n")[0] and not out.endswith(b"|" + HELLO), f"CONNECT permis.test:443, SNI permis.test : ClientHello factice refusé, aucun tunnel opaque ({out[:60]!r})")
dire(len(jx) == 1 and jx[0][:3] == ("CONNECT", "permis.test", False), f"CONNECT : une ligne au journal à la fin du tunnel ({jx})")
for brut, quoi in ((b"CONNECT ailleurs.test:443 HTTP/1.1\r\n\r\n", "autre nom"), (b"CONNECT 93.184.215.14:443 HTTP/1.1\r\n\r\n", "IP directe"),
                   (b"CONNECT permis.test:22 HTTP/1.1\r\n\r\n", "port autre que 443"), (b"CONNECT prive.permis.test:443 HTTP/1.1\r\n\r\n", "adresse privée après résolution"),
                   (b"CONNECT permis.test HTTP/1.1\r\n\r\n", "sans port")):
    cas(brut, lambda o: b" 403 " in o.split(b"\r\n")[0] or b" 400 " in o.split(b"\r\n")[0], f"CONNECT {quoi} : refusé, aucune connexion", connexion=False)

# Défaut (1) de la revue du 18/10 : SNI d'un autre site derrière la même IP (CDN) — refusé, sans connexion au site
P4 = W.Proxy(NOMS, lambda *a: jx.append(a), resoudre=lambda h, p: RESOLUTION.get(h, []), ouvrir=ouvrir, delai=2)
for hello, quoi, plus in ((client_hello("ailleurs.test"), "SNI d'un autre site", {}), (client_hello("sous.permis.test"), "SNI d'un autre nom de l'accès", {}),
                          (client_hello(None), "ClientHello sans SNI", {}), (b"GET / HTTP/1.1\r\nHost: ailleurs.test\r\n\r\n", "pas un ClientHello TLS", {}),
                          (client_hello("permis.test", longueur=70000), "ClientHello annoncé de plus de 16 Ko", {}),
                          (client_hello("permis.test", enr=b"\x03\xff"), "enregistrement TLS de version 03ff", {}),
                          (client_hello("permis.test", legacy=b"\x00\x00"), "ClientHello de legacy_version 0000", {}),
                          (HELLO, "ClientHello trop lent (au-delà de la borne de temps)", {"morceaux": len(HELLO), "pause": 0.05})):
    del jx[:]; n = len(appels); t0 = time.time()
    out = requete(b"CONNECT permis.test:443 HTTP/1.1\r\n\r\n", p=P4, apres=lambda a: aller_retour(a, hello, **plus))
    dire(len(appels) == n and not out.split(b"|", 1)[-1].startswith(b"HTTP/") and jx and jx[-1][2] is False and time.time() - t0 < 12,
         f"CONNECT permis.test puis {quoi} : refusé, aucune connexion au site, REFUSÉ au journal ({jx[-1:]})")
# contre-revue du 18/10 : versions hors TLS refusées (enregistrement 0301-0304, legacy_version 0301-0304), les vraies acceptées
for v in (b"\x03\x00", b"\x03\x05", b"\x03\xff", b"\x00\x00", b"\x02\x00"):
    dire(refuse_sni(client_hello("permis.test", enr=v)) and refuse_sni(client_hello("permis.test", legacy=v)),
         f"sni() : enregistrement ou legacy_version {v.hex()} refusé (ValueError)")
dire(all(W.sni(client_hello("permis.test", enr=b"\x03" + bytes([k]), legacy=b"\x03" + bytes([j]))) == "permis.test" for k in (1, 2, 3, 4) for j in (1, 2, 3, 4)),
     "sni() : versions TLS 0301 à 0304 (enregistrement et legacy_version) acceptées")
h2 = client_hello("permis.test", fragments=2); n1 = 5 + struct.unpack("!H", h2[3:5])[0]
dire(refuse_sni(h2[:n1] + b"\x16\x03\xff" + h2[n1 + 3:]), "sni() : second enregistrement du ClientHello en version 03ff : refusé")
del jx[:]
out = requete(b"CONNECT permis.test:443 HTTP/1.1\r\n\r\n", p=P4, apres=lambda a: aller_retour(a, client_hello("permis.test", fragments=3), morceaux=4, pause=0.05))
dire(not out.endswith(b"|" + client_hello("permis.test", fragments=3)) and jx and jx[-1][2] is False, "ClientHello factice fragmenté : pas de tunnel opaque (vrai TLS dans web-https.py)")
dire(jx and jx[-1][2] is False, f"journal : TLS factice refusé ({jx[-1:]})")

# Défaut (2) : déni de service — limite AVANT le fil, connexion refusée fermée vite, délai ferme (en-tête, corps)
def goutte(a, debut, n=40, pause=0.25):
    try:
        a.sendall(debut)
        for _ in range(n): a.sendall(b"x"); time.sleep(pause)
    except OSError: pass


def tenu(brut_debut, p, attente):
    """Vrai si le fil de `servir` tourne encore après `attente` s alors que le client envoie un octet tous les 0,25 s."""
    a, b = socket.socketpair(); th = threading.Thread(target=p.servir, args=(b,), daemon=True); th.start()
    threading.Thread(target=goutte, args=(a, brut_debut), daemon=True).start()
    th.join(attente); vivant = th.is_alive(); a.close(); return vivant


P5 = W.Proxy(NOMS, lambda *a: None, resoudre=lambda h, p: RESOLUTION.get(h, []), ouvrir=ouvrir, delai=2)
dire(not tenu(b"GET http://permis.test/ HTTP/1.1\r\nX: ", P5, 5), "en-tête envoyé goutte à goutte : coupé au délai (2 s), pas tenu indéfiniment")
dire(not tenu(b"GET http://permis.test/ HTTP/1.1\r\nContent-Length: 60000\r\n\r\n", P5, 5), "corps envoyé goutte à goutte : coupé au délai")
dire(not tenu(b"POST http://permis.test/ HTTP/1.1\r\n\r\n", P5, 3), "connexion refusée (POST) puis octets réguliers : fermée vite, jamais vidée sans fin")
paires = [socket.socketpair() for _ in range(3)]; avant = threading.active_count()
try:
    P6 = W.Proxy(NOMS, lambda *a: None, resoudre=lambda h, p: RESOLUTION.get(h, []), ouvrir=ouvrir, delai=5, connexions_max=2)
    for a, b in paires[:2]: P6.accueillir(b)
    pendant = threading.active_count(); P6.accueillir(paires[2][1]); paires[2][0].settimeout(2)
    try: ferme = paires[2][0].recv(10) == b""
    except OSError: ferme = True
    dire(pendant == avant + 2 and threading.active_count() == pendant and ferme,
         f"limite de connexions (2) contrôlée AVANT le fil : la 3e est fermée tout de suite, aucun fil créé ({avant} → {pendant} → {threading.active_count()})")
except (AttributeError, TypeError):
    dire(False, "limite de connexions contrôlée avant le fil (Proxy.accueillir ou connexions_max absent)")
for a, b in paires: a.close()

# ── PROXY : arrêt (le tunnel ouvert tombe) ──
P2 = W.Proxy(["permis.test"], lambda *a: None, resoudre=lambda h, p: RESOLUTION.get(h, []), ouvrir=ouvrir, delai=30)
a, b = socket.socketpair(); threading.Thread(target=P2.servir, args=(b,), daemon=True).start()
a.settimeout(10); a.sendall(b"CONNECT permis.test:443 HTTP/1.1\r\n\r\n"); t = b""
while b"\r\n\r\n" not in t: t += a.recv(4096)
P2.arreter(); t0 = time.time()
try: fin = a.recv(10) == b""
except OSError: fin = True
dire(fin and time.time() - t0 < 5, "arrêt du proxy : le tunnel ouvert est coupé")

# ── PROXY : socket UNIX réel ──
try: socket.socket(socket.AF_UNIX).close(); unix = True
except OSError: unix = False
if not unix:
    print("NON JOUÉ socket UNIX réel du proxy : AF_UNIX refusé ici (bac à sable) — joué par la porte tests")
else:
    with tempfile.TemporaryDirectory() as t:
        ch = Path(t) / "essai-web.sock"; P3 = W.Proxy(["permis.test"], lambda *a: None, resoudre=lambda h, p: RESOLUTION.get(h, []), ouvrir=ouvrir)
        P3.ecouter(str(ch)); c = socket.socket(socket.AF_UNIX); c.settimeout(10); c.connect(str(ch)); c.sendall(g("http://permis.test/")); out = b""
        while True:
            x = c.recv(65536)
            if not x: break
            out += x
        c.close()
        dire(out.endswith(b"PERMIS-OK") and (ch.stat().st_mode & 0o777) == 0o600, "socket UNIX : page reçue, socket en 600")
        P3.arreter(); c = socket.socket(socket.AF_UNIX)
        try: c.connect(str(ch)); refuse = False
        except OSError: refuse = True
        dire(refuse, "socket UNIX : plus aucune connexion après l'arrêt")

# ── DURÉE ET NOMS ──
dire(W.duree("") == 7200 and W.duree(None) == 7200, "durée : 2 h par défaut")
dire((W.duree("8h"), W.duree("90m"), W.duree("1h30"), W.duree("24h")) == (28800, 5400, 5400, 86400), "durée : 8h, 90m, 1h30, 24h")
for x in ("25h", "24h01", "0h", "0m", "abc", "-2h", "2"):
    try: W.duree(x); r = False
    except ValueError: r = True
    dire(r, f"durée « {x} » : refusée")
dire(W.noms("exemple.fr") == ["exemple.fr"] and W.noms("Exemple.fr,app.exemple.fr") == ["exemple.fr", "app.exemple.fr"], "noms : un domaine exact, + sous-domaines écrits")
for x in ("*.exemple.fr", "1.2.3.4", "localhost", "exemple.fr,autre.fr", "exemple.fr,xexemple.fr", "", "exemple", "exemple.fr:443", "exemple.localhost"):
    try: W.noms(x); r = False
    except ValueError: r = True
    dire(r, f"noms « {x} » : refusé")

# ───────────── CYCLE : courtier réel, installation jetable ─────────────
with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    temoin = "Temoin" + "Coffre" + "Web"                       # valeur secrète du coffre d'essai, construite à l'exécution
    (m / "coffre-essai.json").write_text(json.dumps({"service": {"jeton": temoin}}))
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    for a, plus in (("retro", "outils = web"), ("autre", "outils ="), ("lecteur", "outils = web\nlecture_seule = oui")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nheures = aucune\nmur = strict\n{plus}\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false", "BERGER_NOTIFY_SEND": "/bin/true"}
    os.environ.update(HOME=str(m), BERGER_DIR=str(i), BERGER_HERDR="/bin/false", BERGER_NOTIFY_SEND="/bin/true")
    berger = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=120)
    C = charger("courtier_web_essai", i / "courtier/courtier")
    V = i / "courtier/validations"; E = i / "courtier/web"

    class FauxProxy:                                   # le proxy réel est prouvé plus haut ; ici, le cycle
        tous = []
        def __init__(self, noms, journal): self.noms, self.journal, self.arrete = noms, journal, False; FauxProxy.tous.append(self)
        def ecouter(self, chemin): Path(chemin).parent.mkdir(parents=True, exist_ok=True); Path(chemin).write_text("")
        def arreter(self): self.arrete = True
    C.WEB.fabrique = FauxProxy

    def outil(agent, verbe, *args):
        d = i / "agents" / agent / "courrier"; (d / "encours").mkdir(parents=True, exist_ok=True)
        f = d / "encours" / f"{time.time_ns()}.json"; f.write_text(json.dumps({"outil": "web", "verbe": verbe, "args": list(args)}))
        C.traiter(agent, f, {}); return json.loads((d / "reponses" / f.name).read_text())

    def decider(n, *plus):
        """berger valider|refuser <n> [--duree …] pendant que l'exécuteur du courtier tourne."""
        p = subprocess.Popen([sys.executable, str(i / "bin/berger"), plus[0], str(n), *plus[1:]], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while p.poll() is None: C.traiter_decisions(); time.sleep(0.1)
        return p.returncode, p.stdout.read()

    appels_log = lambda: (i / "courtier/appels.log").read_text() if (i / "courtier/appels.log").exists() else ""
    jour = lambda a: "".join(f.read_text() for f in (i / "agents" / a / "memory").glob("*.md"))
    sock = i / "courtier/mcp/retro-web/proxy.sock"

    r = outil("autre", "demander", "permis.test", "essai")
    dire(not r["ok"] and "droit" in r["erreur"], f"sans `web` dans outils : refusé ({r.get('erreur', '')[:80]})")
    r = outil("lecteur", "demander", "permis.test", "essai")
    dire(not r["ok"] and "LECTURE SEULE" in r["erreur"], "agent en lecture seule : refusé")
    for args, quoi in ((("1.2.3.4", "essai"), "IP"), (("*.permis.test", "essai"), "joker"), (("permis.test", "essai", "25h"), "durée > 24 h"),
                       (("permis.test", ""), "sans motif"), (("permis.test,ailleurs.test", "essai"), "deux domaines")):
        r = outil("retro", "demander", *args)
        dire(not r["ok"] and not list(V.glob("*.json")), f"demande {quoi} : refusée, aucune validation créée ({r.get('erreur', '')[:70]})")
    r = outil("retro", "demander", "permis.test", "observer le site")
    n = r.get("en_attente"); dv = json.loads((V / f"{n}.json").read_text()) if n else {}
    dire(r["ok"] and n and dv.get("valideur") is None and dv.get("verbe") == "demander", f"demande valide : validation n° {n}, propriétaire seul")
    dire("CGU" in dv.get("apercu", "") and "2 h" in dv.get("apercu", "") and "--duree" in dv.get("apercu", ""), f"aperçu : rappel CGU, 2 h, durée réglable ({dv.get('apercu', '')[:160]})")
    r2 = outil("retro", "demander", "permis.test", "encore")
    dire(not r2["ok"] and "attente" in r2["erreur"], f"seconde demande pendant la première : refusée ({r2.get('erreur', '')[:80]})")
    d = i / "agents/retro/courrier/encours"; f = d / "auto.json"; f.write_text(json.dumps({"outil": "validation", "verbe": "accepter", "args": [str(n)]}))
    C.traiter("retro", f, {}); ra = json.loads((d.parent / "reponses/auto.json").read_text())
    dire(not ra["ok"] and not (V / f"{n}.decision").exists(), f"auto-validation : refusée ({ra.get('erreur', '')[:70]})")
    rc, o = decider(n, "valider", "--duree", "25h")
    dire(rc != 0 and not (V / f"{n}.decision").exists() and (V / f"{n}.json").exists(), f"berger valider --duree 25h : refusé, rien décidé ({o.strip()[:80]})")
    rc, o = decider(n, "refuser", "--duree", "2h")
    dire(rc != 0 and (V / f"{n}.json").exists(), "berger refuser --duree : refusé (une durée ne vaut que pour valider)")
    rc, o = decider(n, "valider", "--duree", "8h")
    ouvert = json.loads((E / "retro.json").read_text()) if (E / "retro.json").exists() else {}
    dire(rc == 0 and "validé et exécuté" in o and ouvert.get("noms") == ["permis.test"] and 8 * 3600 - 60 < ouvert.get("fin_ts", 0) - time.time() <= 8 * 3600,
         f"berger valider {n} --duree 8h : accès ouvert pour 8 h ({o.strip()[:120]})")
    dire(sock.exists() and FauxProxy.tous and FauxProxy.tous[-1].noms == ["permis.test"], "proxy lancé, socket courtier/mcp/retro-web/proxy.sock")
    dire(oct(sock.parent.stat().st_mode & 0o777) == "0o700" and oct(sock.parent.parent.stat().st_mode & 0o777) == "0o700",
         "dossier du socket (courtier/mcp/retro-web) et courtier/mcp en 700")
    dire("web:permis.test" in appels_log() and "accès ouvert" in appels_log() and "accès web" in jour("retro"), "ouverture au journal du courtier et de l'agent")
    FauxProxy.tous[-1].journal("GET", "permis.test", True, "200, 9 octets"); FauxProxy.tous[-1].journal("CONNECT", "ailleurs.test", False, "nom hors de l'accès")
    dire("retro\tweb:permis.test\tGET\tpermis.test\taccepté\t200, 9 octets" in appels_log()
         and "retro\tweb:permis.test\tCONNECT\tailleurs.test\tREFUSÉ\tnom hors de l'accès" in appels_log(),
         "requêtes du proxy au journal du courtier : web:<domaine>, méthode, hôte, permis/REFUSÉ, détail")
    r = outil("retro", "etat"); dire(r["ok"] and "permis.test" in json.dumps(r["donnees"], ensure_ascii=False), f"web etat : l'accès ouvert ({str(r.get('donnees'))[:100]})")
    r = berger("web"); dire(r.returncode == 0 and "retro" in r.stdout and "permis.test" in r.stdout, f"berger web : l'accès ouvert ({r.stdout.strip().splitlines()[0][:100] if r.stdout.strip() else ''})")
    r = outil("retro", "demander", "sous.permis.test", "autre")
    dire(not r["ok"] and "déjà ouvert" in r["erreur"], "un accès à la fois : seconde demande refusée")

    # prolongation : nouvelle validation
    r = outil("retro", "prolonger", "ailleurs.test", "2h"); dire(not r["ok"], "prolonger un autre domaine : refusé")
    r = outil("retro", "prolonger", "permis.test", "30h"); dire(not r["ok"], "prolonger de plus de 24 h : refusé")
    fin0 = C.WEB.ouvert("retro")["fin_ts"]
    r = outil("retro", "prolonger", "permis.test", "2h"); n2 = r.get("en_attente")
    dire(r["ok"] and n2 and C.WEB.ouvert("retro")["fin_ts"] == fin0, f"prolonger : validation n° {n2}, rien ne change avant le go")
    rc, o = decider(n2, "valider")
    dire(rc == 0 and abs(C.WEB.ouvert("retro")["fin_ts"] - fin0 - 7200) < 2, f"prolongation validée : +2 h ({o.strip()[:100]})")

    # échéance
    C.WEB.ouvert("retro")["fin_ts"] = time.time() - 1; C.WEB.tour()
    dire(C.WEB.ouvert("retro") is None and not sock.exists() and not (E / "retro.json").exists() and FauxProxy.tous[-1].arrete,
         "échéance : proxy arrêté, socket et état supprimés")
    dire("accès fermé (échéance)" in appels_log() and "accès fermé" in jour("retro"), "échéance : « accès fermé » au journal")
    r = outil("retro", "prolonger", "permis.test", "2h"); dire(not r["ok"], "prolonger sans accès ouvert : refusé")

    # refus et expiration : rien d'ouvert
    r = outil("retro", "demander", "permis.test", "essai refus"); n3 = r.get("en_attente"); k = len(FauxProxy.tous)
    rc, o = decider(n3, "refuser")
    dire(rc == 0 and C.WEB.ouvert("retro") is None and len(FauxProxy.tous) == k and not sock.exists(), "demande refusée : rien d'ouvert")
    r = outil("retro", "demander", "permis.test", "essai expiration"); n4 = r.get("en_attente")
    C.expirer_web(); dire((V / f"{n4}.json").exists(), "demande récente : n'expire pas")
    C.WEB_ATTENTE = 0; C.expirer_web()
    fx = json.loads((V / f"{n4}.fait.json").read_text()) if (V / f"{n4}.fait.json").exists() else {}
    dire(fx.get("etat") == "expiré" and not (V / f"{n4}.json").exists() and C.WEB.ouvert("retro") is None, "demande sans réponse : expirée, rien d'ouvert")
    r = berger("valider", str(n4)); dire(r.returncode != 0 and "déjà faite" in r.stdout + r.stderr, "valider une demande expirée : « déjà faite »")
    # Défaut (3) de la revue : un secret écrit dans le motif ne va ni dans une validation ni au journal de l'agent
    r = outil("retro", "demander", "permis.test", f"motif avec {temoin}")
    dire(not r["ok"] and not [f for f in V.glob("*.json") if f.stem.isdigit()], "motif qui contient un secret du coffre : demande refusée, aucune validation")
    (V / "90.json").write_text(json.dumps({"n": 90, "agent": "retro", "outil": "web", "verbe": "demander", "args": ["permis.test", temoin, ""],
                                           "apercu": f"ouvrir l'accès web — motif : {temoin}", "valideur": None}))
    C.expirer_web()
    dire((V / "90.fait.json").exists() and temoin not in jour("retro") and temoin not in appels_log() and "masqué" in jour("retro"),
         "expiration d'une demande dont l'aperçu porte un secret : masqué au journal de l'agent et du courtier")
    C.WEB_ATTENTE = 3600

    # berger web fermer <agent>
    r = outil("retro", "demander", "permis.test", "essai fermer"); rc, o = decider(r.get("en_attente"), "valider")
    dire(C.WEB.ouvert("retro") is not None and C.WEB.ouvert("retro")["fin_ts"] - time.time() > 7100, "validé sans --duree : 2 h")
    p = subprocess.Popen([sys.executable, str(i / "bin/berger"), "web", "fermer", "retro"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while p.poll() is None: C.WEB.tour(); time.sleep(0.1)
    o = p.stdout.read()
    dire(p.returncode == 0 and "fermé" in o and C.WEB.ouvert("retro") is None and not sock.exists(), f"berger web fermer retro : fermé ({o.strip()[:80]})")
    dire("accès fermé (par Proprio)" in appels_log(), "fermeture par le propriétaire au journal")
    r = berger("web", "fermer", "retro"); dire(r.returncode != 0 and "aucun" in r.stdout + r.stderr, "berger web fermer sans accès : « aucun accès »")

    # l'agent ferme lui-même ; redémarrage du courtier
    r = outil("retro", "demander", "permis.test", "essai agent"); decider(r.get("en_attente"), "valider")
    r = outil("retro", "fermer"); dire(r["ok"] and C.WEB.ouvert("retro") is None and not sock.exists(), "web fermer (l'agent lui-même) : fermé")
    r = outil("retro", "demander", "permis.test", "essai redémarrage"); decider(r.get("en_attente"), "valider")
    C.WEB.ouverts.clear()                              # le courtier s'arrête : ses proxys meurent avec lui
    C.WEB.nettoyer()
    dire(not sock.exists() and not (E / "retro.json").exists() and "redémarrage" in appels_log(), "redémarrage du courtier : accès fermé, jamais rouvert en silence")
print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
