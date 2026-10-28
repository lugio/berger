#!/usr/bin/env python3
"""Tests du serveur de l'interface web (spec docs/plans/2026-10-13-interface-spec.md, §3 test 7 et §5) — sans modèle, faux
Herdr, installation JETABLE (tests/_jeu_vues.py), vraies requêtes HTTP sur un port libre de 127.0.0.1. Vérifie : lien
d'entrée (jeton dans le fragment, fichier 600, inchangé sans --nouveau, refusé à un agent) ; écoute sur 127.0.0.1 seulement ;
sans cookie → 401, mauvais jeton → 401, bon jeton → cookie HttpOnly SameSite=Strict ; mauvais Host → 403 ; données =
`berger vue … --json` ; chemins et arguments piégés → 404/400 sans rien lancer ; toute écriture → 405 (lot 1 : lecture
seule) ; en-têtes stricts ; journal sans paramètres ; nouveau jeton → l'ancienne session tombe ; délai dépassé → 504 ;
trop de commandes à la fois → 503. Usage : python3 tests/interface-serveur.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import http.client, json, os, re, shutil, socket, ssl, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def port_libre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t); m = i.parent; port = port_libre()
    env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}         # l'installation jetable agit comme le propriétaire
    base_conf = (i / "config.toml").read_text()
    with open(i / "config.toml", "a") as f: f.write(f"[interface]\nport = {port}\n")
    b = lambda *a, **k: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env={**env, **k.get("env", {})}, capture_output=True, text=True, timeout=60)
    jf = m / ".config/berger/interface.jeton"

    # ── lien d'entrée ──
    r = b("interface", "lien"); lien = r.stdout.strip()
    jeton = lien.partition("#jeton=")[2]
    dire(r.returncode == 0 and lien.startswith(f"http://localhost:{port}/#jeton=") and len(jeton) >= 40 and jf.read_text().strip() == jeton,
         "berger interface lien : http://localhost:<port>/#jeton=… (jeton dans le fragment, gardé dans le dossier masqué)")
    dire(oct(jf.stat().st_mode & 0o777) == "0o600", f"fichier du jeton : droits 600 ({oct(jf.stat().st_mode & 0o777)})")
    dire(b("interface", "lien").stdout.strip() == lien, "un second appel rend le même lien (le jeton ne change qu'avec --nouveau)")
    r = b("interface", "lien", env={"BERGER_AGENT": "vigie"})
    dire(r.returncode != 0 and "propriétaire" in r.stderr and jeton not in r.stdout + r.stderr, "berger interface lien : refusé à un agent, sans rien montrer")

    # ── le serveur, lancé comme le service (berger interface servir) ──
    srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(50):
        try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
        except OSError: time.sleep(0.1)
    hote = f"localhost:{port}"

    def req(methode, chemin, corps=None, cookie=None, host=hote, plus=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=30); h = dict(plus or {})
        if host is not None: h["Host"] = host
        if cookie: h["Cookie"] = cookie
        c.putrequest(methode, chemin, skip_host=True)
        for k, v in h.items(): c.putheader(k, v)
        corps = corps.encode() if isinstance(corps, str) else corps
        if corps is not None: c.putheader("Content-Length", str(len(corps)))
        c.endheaders(corps)
        rep = c.getresponse(); return rep.status, {k.lower(): v for k, v in rep.getheaders()}, rep.read()

    st, h, corps = req("GET", "/")
    dire(st == 200 and b"/app.js" in corps and "default-src 'self'" in h.get("content-security-policy", "") and h.get("x-frame-options") == "DENY"
         and h.get("x-content-type-options") == "nosniff" and h.get("cache-control") == "no-store", "GET / : la page, avec CSP stricte, X-Frame-Options, nosniff, no-store")
    dire(req("GET", "/app.js")[0] == 200 and req("GET", "/app.css")[0] == 200, "les deux autres fichiers de la page sont servis")
    dire(req("GET", "/api/vues")[0] == 401, "sans cookie : 401")
    dire(req("POST", "/connexion", json.dumps({"jeton": "x" * 43}), plus={"Content-Type": "application/json"})[0] == 401, "mauvais jeton : 401")
    st, h, _ = req("POST", "/connexion", json.dumps({"jeton": jeton}), plus={"Content-Type": "application/json"})
    ck = h.get("set-cookie", "")
    dire(st == 204 and "HttpOnly" in ck and "SameSite=Strict" in ck and jeton not in ck, "bon jeton : 204, cookie HttpOnly SameSite=Strict, dérivé (jamais le jeton lui-même)")
    cookie = ck.split(";")[0]
    dire(req("GET", "/api/vues", cookie="berger=" + "0" * 64)[0] == 401, "cookie inventé : 401")

    st, _, corps = req("GET", "/api/vue/alire", cookie=cookie)
    attendu = json.loads(b("vue", "alire", "--json").stdout)["donnees"]
    dire(st == 200 and json.loads(corps)["donnees"] == attendu, "GET /api/vue/alire = les données de `berger vue alire --json`")
    st, _, corps = req("GET", "/api/vue/tableau?a=vigie", cookie=cookie)
    dire(st == 200 and json.loads(corps)["donnees"]["agent"]["id"] == "vigie", "vue d'agent : ?a=<agent>")
    dire(req("GET", "/api/vues", cookie=cookie, host="evil.example")[0] == 403 and req("GET", "/api/vues", cookie=cookie, host=None)[0] == 403,
         "en-tête Host étranger ou absent : 403 (DNS rebinding)")
    dire(req("GET", "/", host=f"localhost:{port + 1}")[0] == 403, "Host avec un autre port : 403")
    st, _, corps = req("GET", "/api/schema/alire", cookie=cookie)
    dire(st == 200 and json.loads(corps)["$id"] == "alire.schema.json" and req("GET", "/api/schema/communs", cookie=cookie)[0] == 200, "schémas servis (vue et communs)")
    pieges = [("/api/schema/..%2Fberger", 404), ("/api/schema/../../bin/berger", 404), ("/api/vue/..%2F..%2Fberger", 404),
              ("/api/vue/tableau?a=-x", 400), ("/api/vue/tableau?a=vigie%20--force", 400), ("/etc/passwd", 404), ("/api/inconnue", 404)]
    obtenus = [(c, req("GET", c, cookie=cookie)[0]) for c, _ in pieges]
    dire(obtenus == pieges, f"chemins et arguments piégés : refusés (obtenu {obtenus})")
    ecritures = [req("POST", "/api/vue/alire", "{}", cookie=cookie)[0], req("PUT", "/", "x", cookie=cookie)[0],
                 req("DELETE", "/api/vues", cookie=cookie)[0], req("PATCH", "/api/vues", "{}", cookie=cookie)[0]]
    dire(ecritures == [405] * 4, f"lot 1 en lecture seule : toute écriture → 405 ({ecritures})")
    req("GET", "/api/vue/checklists?a=SECRETDANSLADRESSE", cookie=cookie)

    # nouveau jeton : l'ancienne session tombe
    r = b("interface", "lien", "--nouveau")
    dire(r.returncode == 0 and r.stdout.strip() != lien and req("GET", "/api/vues", cookie=cookie)[0] == 401, "berger interface lien --nouveau : nouveau jeton, l'ancienne session → 401")
    srv.terminate(); _, journal = srv.communicate(timeout=10)
    dire("GET /api/vue/alire 200" in journal and "SECRETDANSLADRESSE" not in journal and jeton not in journal and "berger=" not in journal,
         "journal du serveur : méthode, chemin, code — jamais les paramètres, le cookie ni le jeton")

    # ── dans le processus : adresse, délai, place ──
    prog = (f"import runpy, threading, http.client, json\ng = runpy.run_path({str(i / 'bin/interface.py')!r}, run_name='essai')\n"
            f"s = g['Serveur'](0, {str(jf)!r}); adr = s.server_address[0]\n"
            "threading.Thread(target=s.serve_forever, daemon=True).start()\n"
            "import hmac, hashlib\nj = open(" + repr(str(jf)) + ").read().strip(); ck = 'berger=' + g['deriver'](j, 'session')\n"
            "def get(ch):\n    c = http.client.HTTPConnection('127.0.0.1', s.port if s.port else s.server_address[1], timeout=30)\n"
            "    c.request('GET', ch, headers={'Host': 'localhost:%d' % s.server_address[1], 'Cookie': ck}); return c.getresponse().status\n"
            "s.hotes = {'localhost:%d' % s.server_address[1]}\n"
            "g['Requete'].commande.__globals__['DELAI'] = 0.001; delai = get('/api/vues')\n"
            "g['Requete'].commande.__globals__['DELAI'] = 10; s.place = threading.BoundedSemaphore(1); s.place.acquire(); occupe = get('/api/vues')\n"
            # course (vue le 14/10 : 1 échec sur 3 sous charge) : la place doit être rendue au sémaphore qui l'a donnée, même si
            # server.place change pendant la commande — on le provoque à coup sûr en changeant place PENDANT subprocess.run
            "import types, subprocess as sp\ns2 = g['Serveur'](0, " + repr(str(jf)) + "); ancien = threading.BoundedSemaphore(1); s2.place = ancien\n"
            "neuf = threading.BoundedSemaphore(1); neuf.acquire()\n"
            "def faux_run(*a, **k):\n    s2.place = neuf; return sp.CompletedProcess(a, 0, '{}', '')\n"
            "G = g['Requete'].commande.__globals__; vrai = G['subprocess'].run; G['subprocess'].run = faux_run\n"
            "g['Requete'].lancer(types.SimpleNamespace(server=s2, erreur=lambda *x: None), ['vues', '--json'])\n"   # lancer() : prend et rend la place
            "G['subprocess'].run = vrai; s2.server_close()\n"
            "course = {'neuf_reste_pris': not neuf.acquire(blocking=False), 'ancien_rendu': ancien.acquire(blocking=False)}\n"
            "print(json.dumps({'adresse': adr, 'delai': delai, 'occupe': occupe, 'course': course}))")
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True, timeout=120)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): x = {}; print(r.stderr[-800:])
    dire(x.get("adresse") == "127.0.0.1", f"écoute sur 127.0.0.1 seulement (adresse en dur, obtenue {x.get('adresse')})")
    dire(x.get("delai") == 504, f"commande trop longue : 504 « délai dépassé », jamais une vue vide (obtenu {x.get('delai')})")
    dire(x.get("occupe") == 503, f"plus de commandes à la fois que permis : 503 (obtenu {x.get('occupe')})")
    c_ = x.get("course") or {}
    dire(c_.get("neuf_reste_pris") is True and c_.get("ancien_rendu") is True,
         f"une commande rend sa place au sémaphore qui l'a donnée, même s'il a changé entre-temps ({c_})")

    # ── la page : aucune ressource extérieure, aucune vue nommée en dur ──
    page = {f.name: f.read_text() for f in (i / "bin/page").iterdir()}
    dire(sorted(page) == ["app.css", "app.js", "index.html"], f"la page = trois fichiers ({sorted(page)})")
    ns_svg = "http://www.w3.org/2000/svg"                                # un espace de noms (createElementNS), jamais chargé
    dire(not any(re.search(r"https?://", x.replace(ns_svg, "")) for x in page.values()), "aucune ressource extérieure (aucune adresse http(s) dans la page, hors l'espace de noms SVG)")
    dire("innerHTML" not in page["app.js"] and "eval(" not in page["app.js"], "app.js n'insère jamais de HTML venu des données (pas d'innerHTML, pas d'eval)")

    # ── lot 1c (spec §6 ter) : réglages contrôlés, certificat interne, TLS sur l'adresse déclarée, sources, Host, cookie ──
    # adresses d'essai construites à l'exécution : une seconde adresse de boucle locale (la « VM ») et une adresse de la plage
    # de documentation (RFC 5737), jamais une adresse du cabinet
    ICI2, AUTRE = ".".join(("127", "0", "0", "2")), ".".join(("192", "0", "2", "7"))
    def conf_interface(texte): (i / "config.toml").write_text(base_conf + "[interface]\n" + texte)
    for reglage, attendu in (('adresse = "0.0.0.0"', "partout"), ('adresse = "berger.exemple.invalid"', "pas une adresse IP"),
                             ('sources = ["swag.exemple.invalid"]', "pas une adresse IP"), ('nom = "pas un nom"', "nom de domaine")):
        conf_interface(f"port = {port}\n{reglage}\n"); r = b("interface", "servir")
        dire(r.returncode != 0 and attendu in r.stderr, f"[interface] {reglage} : refusé, rien n'écoute ({r.stderr.strip()[-80:]})")
    p2 = port_libre(); nom = "berger.exemple.invalid"
    conf_interface(f'port = {p2}\nadresse = \"{ICI2}\"\nnom = "{nom}"\nsources = ["127.0.0.1"]\ntls = true\n')
    certif, cle = m / ".config/berger/interface/certificat.pem", m / ".config/berger/interface/cle.pem"
    r = b("interface", "servir")
    dire(r.returncode != 0 and "berger interface certificat" in r.stderr, "tls = true sans certificat : refus clair, rien n'écoute")
    r = b("interface", "certificat", env={"BERGER_AGENT": "vigie"})
    dire(r.returncode != 0 and not certif.exists(), "berger interface certificat : refusé à un agent, rien créé")
    if not shutil.which("openssl"): print("NON JOUÉ certificat interne : openssl absent de cette machine")
    else:
        r = b("interface", "certificat")
        dire(r.returncode == 0 and certif.is_file() and oct(cle.stat().st_mode & 0o777) == "0o600" and oct(cle.parent.stat().st_mode & 0o777) == "0o700"
             and "PRIVATE" not in r.stdout + r.stderr and "empreinte SHA-256" in r.stdout,
             f"certificat interne créé : clé en 600 dans un dossier 700, jamais affichée, empreinte donnée ({r.stdout.strip()[-60:]})")
        avant = certif.read_bytes(); r = b("interface", "certificat")
        dire(r.returncode == 0 and certif.read_bytes() == avant and "valable jusqu'au" in r.stdout, "sans --nouveau : le certificat existant n'est jamais écrasé (état affiché)")
        r = b("interface", "certificat", "--nouveau")
        dire(r.returncode == 0 and certif.read_bytes() != avant, "--nouveau : un certificat neuf")
        dire(b("interface", "lien").stdout.strip().startswith(f"https://{nom}/#jeton="), "lien d'entrée : https://<nom>/#jeton=… dès que nom est déclaré")
        # état à une date future (horloge fixée) : bientôt, puis expiré — message clair
        def etat_le(jours):
            prog = (J.HORLOGE.replace(repr(J.TS), repr(time.time() + jours * 86400))
                    + f"import runpy, json\ng = runpy.run_path({str(i / 'bin/berger')!r}, run_name='essai')\nprint(json.dumps(g['certificat_etat']()))")
            x = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True, timeout=60)
            try: return json.loads(x.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError): return [None, x.stderr[-200:]]
        e1, e2, e3 = etat_le(1), etat_le(380), etat_le(400)
        dire(e1[0] == "ok" and e2[0] == "bientot" and "expire dans" in e2[1] and e3[0] == "expire" and "EXPIRÉ" in e3[1] and "--nouveau" in e3[1],
             f"échéance du certificat : ok, puis « expire dans N jours » (≤ 30), puis « EXPIRÉ le … » avec la commande ({e2[0]}, {e3[0]})")

        def demarrer():
            s = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for _ in range(50):
                try: socket.create_connection((ICI2, p2), timeout=0.2).close(); break
                except OSError: time.sleep(0.1)
            return s

        def tls_req(methode, chemin, host=nom, corps=None, plus=None):
            ctx = ssl.create_default_context(cafile=str(certif)); ctx.check_hostname = True
            c = http.client.HTTPSConnection(ICI2, p2, timeout=20, context=ctx)
            c._create_connection = lambda adr, *a, **k: socket.create_connection(adr, *a, **k)
            h = {"Host": host, **(plus or {})}
            c.putrequest(methode, chemin, skip_host=True)
            for k, v in h.items(): c.putheader(k, v)
            corps = corps.encode() if isinstance(corps, str) else corps
            if corps is not None: c.putheader("Content-Length", str(len(corps)))
            # le nom vérifié est celui du certificat (SWAG fait de même avec proxy_ssl_name)
            c.sock = ctx.wrap_socket(socket.create_connection((ICI2, p2), timeout=20), server_hostname=nom)
            c.endheaders(corps); rep = c.getresponse()
            return rep.status, {k.lower(): v for k, v in rep.getheaders()}, rep.read()

        srv2 = demarrer()
        st, _, corps = tls_req("GET", "/")
        dire(st == 200 and b"/app.js" in corps, "TLS : la page servie en HTTPS sur l'adresse déclarée, certificat vérifié avec le nom déclaré")
        try:
            c = http.client.HTTPConnection(ICI2, p2, timeout=5); c.request("GET", "/", headers={"Host": nom}); clair = c.getresponse().status
        except (OSError, http.client.HTTPException) as e: clair = type(e).__name__
        dire(not isinstance(clair, int), f"tls = true : une requête HTTP en clair n'obtient AUCUNE réponse HTTP ({clair})")
        dire(tls_req("GET", "/", host=f"localhost:{p2}")[0] == 403 and tls_req("GET", "/", host=f"127.0.0.1:{p2}")[0] == 403,
             "nom déclaré : localhost et 127.0.0.1 ne sont plus des hôtes admis (403)")
        jeton2 = jf.read_text().strip()
        st, h, _ = tls_req("POST", "/connexion", corps=json.dumps({"jeton": jeton2}), plus={"Content-Type": "application/json"})
        ck2 = h.get("set-cookie", "")
        dire(st == 204 and "Secure" in ck2 and "HttpOnly" in ck2 and "SameSite=Strict" in ck2, "derrière SWAG : cookie Secure, HttpOnly, SameSite=Strict")
        st, _, _ = tls_req("GET", "/api/vues", plus={"Cookie": ck2.split(";")[0], "X-Forwarded-For": AUTRE, "X-Real-IP": AUTRE,
                                                      "X-Forwarded-Host": "evil.example", "X-Forwarded-Proto": "http"})
        dire(st == 200, "en-têtes X-Forwarded-* forgés : sans aucun effet (le contrôle porte sur le pair et le jeton)")
        srv2.terminate(); srv2.communicate(timeout=10)
        conf_interface(f'port = {p2}\nadresse = \"{ICI2}\"\nnom = "{nom}"\nsources = [\"{AUTRE}\"]\ntls = true\n')
        srv3 = demarrer()
        st1 = tls_req("GET", "/")[0]; st2 = tls_req("GET", "/", plus={"X-Forwarded-For": AUTRE})[0]
        srv3.terminate(); _, j3 = srv3.communicate(timeout=10)
        dire(st1 == 403 and st2 == 403, f"pair hors de [interface] sources : 403, même avec un X-Forwarded-For qui imite la source ({st1}, {st2})")
        dire(AUTRE not in j3, "journal : jamais l'adresse d'un en-tête X-Forwarded-For")
        ligne = next((l for l in j3.splitlines() if l.startswith("source refusée")), "")
        dire(ligne == "source refusée : " + ".".join(("127", "0", "0", "1")) + " GET /" and "Cookie" not in j3 and "berger=" not in j3,
             f"journal : une requête « source refusée » donne l'adresse du PAIR (pour mesurer la source de SWAG), la méthode et le chemin, rien d'autre ({ligne})")
    (i / "config.toml").write_text(base_conf + f"[interface]\nport = {port}\n")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
