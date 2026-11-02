#!/usr/bin/env python3
"""Vue « Livrables » (spec docs/plans/2026-10-13-interface-spec.md §6.1, lot 1b) — sans modèle, faux Herdr, installation
JETABLE (tests/_jeu_vues.py, jeu avec marquages : bibliothèque d'un agent, À lire, dépôt du chef avec une branche en cours).
Vérifie : les trois sources et rien d'autre (lien symbolique, fichier caché, fichier déjà sur main, fichier hors des dossiers
`livrables` : ignorés) ; aucun chemin absolu ; les plus récents d'abord ; la vue d'objet (texte d'un .md, aucun texte pour un
.html) ; `berger livrable <id> --brut <genre>` (contenu tel quel, genre vérifié, id piégé et fichier de plus de 20 Mo refusés) ;
le serveur : GET /api/livrable/<id>/<genre> derrière le cookie, un .html servi à ORIGINE OPAQUE et SANS RÉSEAU (CSP
« sandbox allow-scripts », jamais allow-same-origin, connect-src 'none' : un aperçu ne lit pas le cookie de session et ne fait
aucune requête ; encadrable par la page seule), un autre genre en téléchargement, genre faux → refus sans contenu.
Usage : python3 tests/livrables.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import http.client, http.server, importlib.util, json, os, shutil, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def port_libre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True); m = i.parent
    env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}         # l'installation jetable agit comme le propriétaire
    b = lambda *a: J.commande(i, env, *a)
    brut = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), "livrable", *a], env=env, capture_output=True, timeout=60)

    r = b("vue", "documents", "--json"); l = json.loads(r.stdout)["donnees"]["documents"]
    par = {(x["origine"], x["chemin"]): x for x in l}
    liv = json.loads(b("vue", "livrables", "--json").stdout)["donnees"]["livrables"]
    tr = i / "bibliotheque/agents/vigie/travail"; co = i / "bibliotheque/commun"
    dire({("travail", "travail/ecran/maquette.html"), ("travail", "travail/ecran/notes.md"), ("travail", "travail/capture.bin"),
          ("commun", "commun/guide.pdf"), ("commun", "commun/procedures/sauvegarde.md"), ("projet", "plan.md"),
          ("branche", "docs/plans/ecran-spec.md"), ("branche", "docs/apercu/ecran.html")} <= set(par) and any(x["origine"] == "a_lire" for x in l),
         "Documents, racines fixes : commun (sous-dossiers compris), projets d'équipe, dossiers de travail, À lire, branche en cours")
    dire(not [k for k in par if k[1].endswith(("lien.md", ".cache", "ancienne-spec.md", "lisezmoi.md", "ecran.py", "ancien.md"))
              and k[1] != "commun/procedures/sauvegarde.md"] and not [k for k in par if "/.prive/" in k[1] or "raccourci" in k[1]],
         "ignorés : lien de fichier et de dossier, fichier ou dossier caché, archives des projets, fichier déjà sur main, hors des dossiers déclarés")
    dire(par[("projet", "plan.md")]["projet"] == "demo/site", "projet d'équipe : projet = <équipe>/<projet>")
    dire({x["id"] for x in liv} == {x["id"] for x in l if x["origine"] in ("travail", "a_lire", "branche") and x["genre"] in ("md", "html", "pdf")} and liv,
         "Livrables = un FILTRE de Documents (même lister, mêmes ids) : md, html, pdf des dossiers de travail, À lire et branches")
    dire(par[("commun", "commun/guide.pdf")]["genre"] == "pdf" and par[("commun", "commun/piege.pdf")]["genre"] == "autre"
         and par[("commun", "commun/logo.png")]["genre"] == "png" and par[("commun", "commun/dessin.svg")]["genre"] == "autre",
         "genre = extension VÉRIFIÉE par la signature : un vrai pdf est pdf, un « .pdf » qui est du HTML est « autre », png reconnu, .svg jamais affiché")
    mq = par[("travail", "travail/ecran/maquette.html")]; sp = par[("branche", "docs/plans/ecran-spec.md")]
    dire(mq["titre"] == "Maquette de l'écran" and mq["genre"] == "html" and mq["auteur"]["id"] == "vigie" and mq["lu"] is None
         and par[("travail", "travail/capture.bin")]["genre"] == "autre", "dossier de travail : titre lu dans <title>, genre, auteur = l'agent du dossier")
    dire(sp["titre"] == "Spec de l'écran de connexion" and sp["projet"] == "demo" and sp["branche"] == "demo/ecran" and sp["auteur"]["id"] == "demo-ecran",
         "branche : titre (1re ligne du .md), projet, branche, auteur = le développeur de la branche")
    dire(str(m) not in r.stdout and not any(x["chemin"].startswith("/") for x in l), "aucun chemin absolu : chaque chemin est relatif à sa racine")
    dire([x["date"] for x in l] == sorted((x["date"] for x in l), reverse=True), "les plus récents d'abord")

    d = json.loads(b("vue", "livrable", par[("travail", "travail/ecran/notes.md")]["id"], "--json").stdout)["donnees"]
    dire(d["genre"] == "md" and "**deux** variantes" in d["texte"] and not d["tronque"], "vue d'objet : un .md donne son texte")
    d = json.loads(b("vue", "livrable", mq["id"], "--json").stdout)["donnees"]
    dire(d["genre"] == "html" and d["texte"] is None, "vue d'objet : un .html ne donne pas de texte (il s'ouvre dans le cadre isolé)")
    r = b("vue", "livrable", "0" * 16, "--json")
    dire(r.returncode != 0 and "livrable inconnu" in r.stderr, "vue d'objet : id inconnu → refus clair")

    r = brut(mq["id"], "--brut", "html")
    dire(r.returncode == 0 and r.stdout == (tr / "ecran/maquette.html").read_bytes(), "berger livrable <id> --brut html : le contenu tel quel")
    ap = par[("branche", "docs/apercu/ecran.html")]
    r = brut(ap["id"], "--brut", "html")
    dire(r.returncode == 0 and b"Aper\xc3\xa7u de l'\xc3\xa9cran" in r.stdout, "--brut sur une branche : le contenu lu dans le dépôt du chef (git, sans fetch)")
    r = brut(mq["id"], "--brut", "md")
    dire(r.returncode != 0 and not r.stdout and "genre html" in r.stderr.decode(), "genre demandé ≠ genre du livrable : refus, rien de servi")
    r = brut("../config.toml", "--brut", "html")
    dire(r.returncode != 0 and not r.stdout, "id piégé (chemin) : refus, rien de servi")
    with open(tr / "grande.html", "wb") as f: f.write(b"<p>"); f.truncate(20_000_001)      # fichier creux : 20 Mo + 1 octet
    gr = next(x for x in json.loads(b("vue", "livrables", "--json").stdout)["donnees"]["livrables"] if x["chemin"] == "travail/grande.html")
    r = brut(gr["id"], "--brut", "html")
    dire(r.returncode != 0 and not r.stdout and "trop grand" in r.stderr.decode(), "fichier de plus de 20 Mo : refus, rien de servi")

    notes = tr / "ecran/notes.md"; avant = par[("travail", "travail/ecran/notes.md")]["id"]
    J.ecrire(notes, "# Notes de maquette\n\n- trois variantes\n", 2)                  # le fichier est modifié
    apres = {x["chemin"]: x["id"] for x in json.loads(b("vue", "documents", "--json").stdout)["donnees"]["documents"]}
    dire(apres.get("travail/ecran/notes.md") == avant, "l'id d'un document est STABLE quand le fichier est modifié (origine + chemin, pas la date)")

    # ── le serveur ──
    port = port_libre()
    with open(i / "config.toml", "a") as f: f.write(f"[interface]\nport = {port}\n")
    jeton = subprocess.run([sys.executable, str(i / "bin/berger"), "interface", "lien"], env=env, capture_output=True, text=True).stdout.strip().partition("#jeton=")[2]
    srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(50):
        try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
        except OSError: time.sleep(0.1)

    def req(methode, chemin, corps=None, cookie=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=30); h = {"Host": f"localhost:{port}"}
        if cookie: h["Cookie"] = cookie
        if corps is not None: h["Content-Type"] = "application/json"
        c.request(methode, chemin, body=corps, headers=h)
        rep = c.getresponse(); return rep.status, {k.lower(): v for k, v in rep.getheaders()}, rep.read()

    try:
        cookie = req("POST", "/connexion", json.dumps({"jeton": jeton}))[1].get("set-cookie", "").split(";")[0]
        dire(req("GET", f"/api/livrable/{mq['id']}/html")[0] == 401, "GET /api/livrable/<id>/html sans cookie : 401")
        st, h, corps = req("GET", f"/api/livrable/{mq['id']}/html", cookie=cookie)
        csp = h.get("content-security-policy", "")
        dire(st == 200 and corps == (tr / "ecran/maquette.html").read_bytes() and h.get("content-type", "").startswith("text/html"),
             "un .html : servi tel quel, en text/html")
        dire(csp.startswith("sandbox allow-scripts;") and "allow-same-origin" not in csp and "default-src 'none'" in csp and "connect-src 'none'" in csp
             and "form-action 'none'" in csp and "img-src data:" in csp and "script-src 'unsafe-inline'" in csp,
             "un .html : origine opaque (sandbox sans allow-same-origin : le cookie de session et la page lui sont inaccessibles), "
             "ses scripts en ligne permis, AUCUN réseau (default-src, connect-src, form-action 'none')")
        dire("frame-ancestors 'self'" in csp and "x-frame-options" not in h and h.get("x-content-type-options") == "nosniff" and h.get("cache-control") == "no-store",
             "un .html : encadrable par la page seule (frame-ancestors 'self'), nosniff, no-store")
        st, h, corps = req("GET", f"/api/livrable/{par[('travail', 'travail/ecran/notes.md')]['id']}/md", cookie=cookie)
        dire(st == 200 and h.get("content-disposition", "").startswith("attachment") and h.get("content-security-policy", "").startswith("sandbox;")
             and h.get("x-frame-options") == "DENY", "un .md tel quel : téléchargé (attachment), isolé s'il était ouvert, jamais encadré")
        st, h, corps = req("GET", f"/api/livrable/{mq['id']}/md", cookie=cookie)
        dire(st == 502 and b"<script>" not in corps and "genre" in json.loads(corps)["erreur"], "genre faux dans l'adresse : refus, aucun contenu servi")
        dire(req("GET", "/api/livrable/..%2Fconfig.toml/html", cookie=cookie)[0] == 404 and req("GET", f"/api/livrable/{mq['id']}/exe", cookie=cookie)[0] == 404,
             "id ou genre hors motif : 404 sans rien lancer")
        dire(req("POST", f"/api/livrable/{mq['id']}/html", "{}", cookie=cookie)[0] == 405, "écriture sur un livrable : 405")
        # Documents : pdf et images affichés avec le type de leur EXTENSION (vérifiée par signature) ; le reste téléchargé
        def doc(chemin): return par[("commun", chemin)]["id"]
        st, h, corps = req("GET", f"/api/livrable/{doc('commun/guide.pdf')}/pdf", cookie=cookie)
        dire(st == 200 and corps.startswith(b"%PDF-") and h.get("content-type") == "application/pdf" and h.get("x-content-type-options") == "nosniff"
             and h.get("content-disposition", "").startswith("inline") and h.get("content-security-policy") == "default-src 'none'; object-src 'none'; frame-ancestors 'none'"
             and h.get("x-frame-options") == "DENY", "pdf : application/pdf (type de l'extension), nosniff, inline, CSP stricte, jamais encadré")
        st, h, corps = req("GET", f"/api/livrable/{doc('commun/logo.png')}/png", cookie=cookie)
        dire(st == 200 and h.get("content-type") == "image/png" and h.get("content-disposition", "").startswith("inline") and h.get("x-content-type-options") == "nosniff"
             and h.get("content-security-policy", "").startswith("sandbox;"), "image : image/png, nosniff, inline, CSP sandbox")
        piege = doc("commun/piege.pdf")
        st, h, corps = req("GET", f"/api/livrable/{piege}/pdf", cookie=cookie)
        dire(st == 502 and b"<script>" not in corps, "un « .pdf » qui est du HTML (sans %PDF-) : jamais servi comme pdf")
        st, h, corps = req("GET", f"/api/livrable/{piege}/autre", cookie=cookie)
        dire(st == 200 and h.get("content-type") == "application/octet-stream" and h.get("content-disposition", "").startswith("attachment")
             and "text/html" not in h.get("content-type", "") and h.get("x-content-type-options") == "nosniff",
             "…il n'est que téléchargé : application/octet-stream, attachment, nosniff (jamais text/html)")
        st, h, corps = req("GET", f"/api/livrable/{doc('commun/dessin.svg')}/autre", cookie=cookie)
        dire(st == 200 and h.get("content-disposition", "").startswith("attachment") and "svg" not in h.get("content-type", ""), ".svg (porte du script) : téléchargé, jamais affiché")
        dire(all(req("GET", f"/api/livrable/{par[k]['id']}/{par[k]['genre']}", cookie=cookie)[1].get("content-security-policy") for k in par
                 if k[0] == "commun"), "une CSP sur chaque réponse d'un document")
        h = req("GET", "/")[1]
        dire("frame-ancestors 'none'" in h.get("content-security-policy", "") and h.get("x-frame-options") == "DENY", "la page elle-même reste non encadrable")
    finally:
        srv.terminate(); srv.wait(timeout=10)

# ── preuve dans un VRAI navigateur (chromium, s'il est présent et démarre : PAS une dépendance ; sinon « NON JOUÉ ») : une
# page pose un cookie de session LISIBLE (le pire cas : le vrai est HttpOnly) et encadre une sonde comme la page encadre un
# livrable (<iframe sandbox="allow-scripts">, CSP_LIVRABLE du serveur) ; la sonde essaie de lire le cookie, la page, le
# stockage, et de faire des requêtes (fetch, image) ; elle ne peut que poster son constat à la page.
nav = next((x for x in ("chromium", "chromium-browser", "google-chrome") if shutil.which(x)), None)
spec_ = importlib.util.spec_from_file_location("serveur_interface", Path(__file__).resolve().parent.parent / "bin/interface.py")
srv_mod = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(srv_mod)
PARENT = (b"<!doctype html><title>page</title><pre id=r>attente</pre><script>addEventListener('message', e => "
          b"{ document.getElementById('r').textContent = 'SONDE ' + JSON.stringify(e.data); });</script>"
          b"<iframe sandbox=\"allow-scripts\" src=\"/sonde\"></iframe>")
SONDE = (b"<!doctype html><script>const r = {};"
         b"try { r.cookie = document.cookie; } catch (e) { r.cookie = 'refus ' + e.name; }"
         b"try { r.page = String(parent.document.title); } catch (e) { r.page = 'refus ' + e.name; }"
         b"try { localStorage.setItem('x', '1'); r.stockage = 'permis'; } catch (e) { r.stockage = 'refus ' + e.name; }"
         b"new Image().src = '/compteur?image';"
         b"fetch('/compteur?fetch').then(() => { r.fetch = 'permis'; parent.postMessage(r, '*'); },"
         b" e => { r.fetch = 'refus ' + e.name; parent.postMessage(r, '*'); });</script>")
coups = []


class Essai(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/compteur"): coups.append(self.path); self.send_response(204); self.end_headers(); return
        corps, plus = (PARENT, [("Set-Cookie", "berger=valeur-de-session-lisible; Path=/; SameSite=Strict")]) if self.path == "/" else \
                      (SONDE, [("Content-Security-Policy", srv_mod.CSP_LIVRABLE)])
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        for k, v in plus: self.send_header(k, v)
        self.end_headers(); self.wfile.write(corps)


if not nav: print("NON JOUÉ preuve dans un navigateur : chromium absent de cette machine")
else:
    with tempfile.TemporaryDirectory() as t:
        s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Essai); threading.Thread(target=s.serve_forever, daemon=True).start()
        try:
            r = subprocess.run([nav, "--headless", "--no-sandbox", "--disable-gpu", "--no-proxy-server", "--no-first-run", "--disable-crash-reporter",
                                f"--user-data-dir={t}/profil", "--virtual-time-budget=5000", "--dump-dom", f"http://127.0.0.1:{s.server_address[1]}/"],
                               capture_output=True, text=True, timeout=90, env={**os.environ, "HOME": t})
            sortie = r.stdout
        except (subprocess.TimeoutExpired, OSError) as e: sortie = ""; r = None
        s.shutdown(); s.server_close()
    if "SONDE " not in sortie:
        print("NON JOUÉ preuve dans un navigateur : chromium n'a pas rendu la page (" + ((r.stderr.strip().splitlines() or ["?"])[-1][:160] if r else "délai") + ")")
    else:
        import html as _h
        x = json.loads(_h.unescape(sortie.split("SONDE ", 1)[1].split("</pre>", 1)[0]))
        dire(x.get("cookie", "").startswith("refus") and x.get("page", "").startswith("refus") and x.get("stockage", "").startswith("refus"),
             f"navigateur réel : un livrable .html ne lit NI le cookie, NI la page qui l'encadre, NI le stockage ({x})")
        dire(x.get("fetch", "").startswith("refus") and not coups, f"navigateur réel : un livrable .html ne fait AUCUNE requête — fetch et image bloqués (requêtes reçues : {coups})")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
