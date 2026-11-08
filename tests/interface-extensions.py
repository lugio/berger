#!/usr/bin/env python3
"""Extensions, lot 2 (spec docs/plans/2026-11-07-extensions-spec.md § 6, go n° 181) : la page « Extensions » en LECTURE SEULE. Sans modèle, faux
Herdr, installation JETABLE (tests/_jeu_vues.py), vraies requêtes HTTP sur 127.0.0.1. Vérifie :
 1. la vue `berger vue extensions` (texte et --json) : une carte par extension — genre, nom, version, empreinte courte, agents, droits (réseau en
    évidence), date d'installation, dernier usage (« non mesuré » pour une skill), état (active, ou écartée avec la raison) ;
 2. le filtre de sortie, sur un extensions.toml PIÉGÉ (mêmes cas que Réglages) : des MARQUEURS uniques, construits à l'exécution, dans une valeur à
    forme de clé, une marque privée, une clé inconnue, un agent, une version, une empreinte invalides, un droit inconnu, ne sortent JAMAIS ; aucun
    chemin privé (dossier personnel) ; une description ordinaire, si ;
 3. lire la page n'écrit rien (extensions/, extensions.toml, agent.conf inchangés) ; extensions.toml illisible : dit sans son contenu ;
 4. le serveur : GET /api/vue/extensions (session exigée, Host contrôlé) → mêmes données que la vue, sans marqueur (corps ET en-têtes), journal du
    serveur non plus ; toute autre méthode (POST, PUT, DELETE, PATCH, HEAD, OPTIONS) → 405, Allow: GET ;
 5. web seulement (aucun onglet Herdr) ; la page (app.js) la rend sans champ, bouton ni requête ; icône et onglet dans icones.json ;
 6. AVEC Playwright (s'il est présent ; sinon « NON JOUÉ », jamais « ok ») : tests/_page_extensions.js aux largeurs de Réglages, 2 thèmes.
Usage : python3 tests/interface-extensions.py (0 = tout passe). Playwright : BERGER_PLAYWRIGHT=<dossier du module>."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import http.client, json, os, random, re, shutil, socket, string, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def marqueur():
    """Un marqueur unique, en lettres seulement (aucun chiffre ni signe : jamais pris pour une fuite)."""
    return "repere" + "".join(random.choice(string.ascii_lowercase) for _ in range(14))


def forme_de_cle():
    return "-".join(["sk", "ant", "api"]) + "".join(random.choice(string.ascii_letters) for _ in range(40))


def toml(v):
    return json.dumps(v, ensure_ascii=False)


def photo(i):
    out = {}
    for p in sorted((i / "extensions").rglob("*")) if (i / "extensions").exists() else []:
        if p.name == ".verrou": continue
        out[str(p.relative_to(i))] = ("lien", os.readlink(p)) if p.is_symlink() else (p.read_bytes() if p.is_file() else "dossier")
    for f in [i / "extensions.toml", *sorted((i / "agents").glob("*/agent.conf"))]:
        out[str(f.relative_to(i))] = f.read_bytes() if f.exists() else None
    return out


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True)
    m = i.parent
    env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=300)
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    marque = marqueur()
    base = (i / "config.toml").read_text()
    (i / "config.toml").write_text(f"marques_privees = [{toml(marque)}]\n" + base + f"\n[interface]\nport = {port}\n")

    # une extension installée pour de vrai (skill, agent scribe)
    pq = Path(t) / "source-revue"; pq.mkdir()
    visible = marqueur()
    (pq / "extension.toml").write_text(f'nom = "relecture"\ngenre = "skill"\nversion = "1.2.0"\ndescription = "Méthode de relecture {visible}."\n')
    (pq / "SKILL.md").write_text("---\nname: relecture\ndescription: essai\n---\nMéthode de relecture.\n")
    r = b("extension", "ajouter", "skill", str(pq), "--agents", "vigie")
    dire(r.returncode == 0, "installation jetable : une skill d'extension installée (relecture, pour vigie)" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr)[-300:]}"))

    # le piège : des entrées écrites à la main dans extensions.toml (mêmes cas que Réglages)
    caches = {k: marqueur() for k in ("cle", "marque", "inconnue", "agent", "version", "empreinte", "droit", "table")}
    piege = (f'\n[skill.piegee]\nversion = "{caches["version"]}"\nempreinte = "{caches["empreinte"]}"\n'
             f'description = {toml("Note " + forme_de_cle() + caches["cle"] + " et " + marque + caches["marque"] + " dans " + str(m) + "/prive")}\n'
             f'installee = "2026-11-07 10:00"\nagents = ["vigie", {toml("../" + caches["agent"])}]\ncle_inconnue = {toml(caches["inconnue"])}\n'
             f'[skill.piegee.droits]\nreseau_accorde = true\nhors_liste = {toml(caches["droit"])}\n'
             f'[skill.piegee.table_inconnue]\nx = {toml(caches["table"])}\n'
             f'[skill.absente]\nversion = "2.0.0"\nempreinte = "{"a" * 64}"\ndescription = "Fichiers retirés à la main."\ninstallee = "2026-11-07 11:00"\nagents = []\n')
    (i / "extensions.toml").write_text((i / "extensions.toml").read_text() + piege)
    tous = list(caches.values())
    avant = photo(i)

    # 1 et 2. la vue
    r = b("vue", "extensions", "--json"); rt = b("vue", "extensions")
    try: dv = json.loads(r.stdout)
    except ValueError: dv = {}
    d = dv.get("donnees", {}); ex = {x.get("nom"): x for x in d.get("extensions", [])}
    dire(r.returncode == 0 and dv.get("vue") == "extensions" and d.get("lisible") is True, f"berger vue extensions --json : les extensions ({(r.stderr or '')[-200:]})")
    x = ex.get("relecture", {})
    dire(x.get("genre") == "skill" and x.get("version") == "1.2.0" and re.fullmatch(r"[0-9a-f]{12}", x.get("empreinte") or "")
         and x.get("agents") == ["vigie"] and re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", x.get("installee") or "") and x.get("etat") == "active",
         f"carte : genre, nom, version, empreinte courte, agents, date d'installation, état actif ({x})")
    dire(x.get("dernier_usage") == "non mesuré", f"dernier usage d'une skill : « non mesuré », jamais inventé ({x.get('dernier_usage')})")
    dire(x.get("reseau") is False and visible in (x.get("description") or ""), "une skill sans réseau ; sa description ordinaire s'affiche")
    p = ex.get("piegee", {})
    dire(p.get("reseau") is True, f"réseau accordé : en évidence sur la carte ({p.get('reseau')})")
    dire(p.get("agents") == ["vigie"], f"un agent au nom invalide n'est pas montré ({p.get('agents')})")
    dire(p.get("version") == "invalide" and p.get("empreinte") == "invalide", f"version et empreinte invalides : dites « invalide », jamais recopiées ({p.get('version')}, {p.get('empreinte')})")
    dire("[masqué" in (p.get("description") or ""), f"description à forme de clé : « [masqué] » ({(p.get('description') or '')[:60]})")
    a = ex.get("absente", {})
    dire((a.get("etat") or "").startswith("écartée") and "absent" in (a.get("etat") or ""), f"fichiers absents : écartée, avec la raison ({a.get('etat')})")
    sortie = r.stdout + r.stderr + rt.stdout + rt.stderr
    dire(not [c for c in tous if c in sortie], f"berger vue extensions (texte et --json) : aucun des {len(tous)} marqueurs cachés ({[k for k, c in caches.items() if c in sortie]})")
    dire(str(m) not in sortie and marque not in sortie, "aucun chemin privé (dossier personnel) ni marque privée dans la vue")
    dire(rt.returncode == 0 and "lecture seule" in rt.stdout and "relecture" in rt.stdout and "RÉSEAU" in rt.stdout, "le texte de la vue : lecture seule, les cartes, le réseau en évidence")
    dire(photo(i) == avant, "lire la vue n'écrit rien (extensions/, extensions.toml, agent.conf inchangés)")
    vues = json.loads(b("vues", "--json").stdout or "{}").get("vues", [])
    v = next((y for y in vues if y["type"] == "extensions"), None)
    dire(v is not None and v["onglet"] == "berger" and v["titre"] == "Extensions" and v["icone"] == "extensions", f"la vue Extensions est un onglet de la page web, avec son icône ({v})")
    pb = J.executer(i, env, 'print(json.dumps({"panneaux": list(g["PANNEAUX_BERGER"]), "onglets": [x[0] for x in g["ONGLETS_BERGER"]]}, ensure_ascii=False))')
    dire("Extensions" not in pb["panneaux"] and "Extensions" not in pb["onglets"], f"aucun onglet Extensions dans l'espace Herdr : web seulement ({pb['panneaux']})")

    # 4. le serveur
    lien = b("interface", "lien").stdout.strip(); jeton = lien.partition("#jeton=")[2]
    srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    m_inv = marqueur(); journal = ""
    try:
        for _ in range(100):
            try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
            except OSError: time.sleep(0.1)
        def req(methode, chemin, cookie=None, corps=None, hote=None, entetes=()):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=60); c.putrequest(methode, chemin, skip_host=True, skip_accept_encoding=True)
            c.putheader("Host", hote or f"localhost:{port}")
            if cookie: c.putheader("Cookie", cookie)
            for k, y in entetes: c.putheader(k, y)
            if corps is not None: c.putheader("Content-Type", "application/json"); c.putheader("Content-Length", str(len(corps)))
            c.endheaders(corps)
            rr = c.getresponse(); return rr.status, rr.getheaders(), rr.read()
        st, h, _ = req("POST", "/connexion", corps=json.dumps({"jeton": jeton}).encode())
        cookie = next((y for k, y in h if k.lower() == "set-cookie"), "").split(";")[0]
        dire(st == 204 and cookie, "connexion : une session")
        st, _, _ = req("GET", "/api/vue/extensions")
        dire(st == 401, f"sans session : 401 ({st})")
        st, _, _ = req("GET", "/api/vue/extensions", cookie, hote="ailleurs.invalid")
        dire(st == 403, f"Host étranger : 403 ({st})")
        st, h, c = req("GET", "/api/vue/extensions", cookie)
        brut = "\n".join(f"{k}: {y}" for k, y in h) + "\n" + c.decode("utf-8", "replace")
        try: dd = json.loads(c)
        except ValueError: dd = {}
        dire(st == 200 and dd.get("vue") == "extensions" and dd.get("donnees", {}).get("lisible") is True, f"GET /api/vue/extensions : 200, les extensions ({st})")
        dire(dd.get("donnees") == d, "le serveur et `berger vue extensions --json` rendent les mêmes données")
        dire(not [y for y in tous if y in brut] and str(m) not in brut and marque not in brut,
             f"réponse HTTP complète (en-têtes et corps) : aucun marqueur, aucun chemin privé, aucune marque ({[k for k, y in caches.items() if y in brut]})")
        hd = {k: y for k, y in h}
        dire(hd.get("Content-Security-Policy", "").startswith("default-src 'self'; script-src 'self'") and hd.get("Cache-Control") == "no-store"
             and hd.get("X-Frame-Options") == "DENY", "mêmes en-têtes stricts que les autres vues (CSP inchangée, pas de cache)")
        for meth in ("POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            st, h, _ = req(meth, "/api/vue/extensions", cookie, corps=b"{}" if meth in ("POST", "PUT", "PATCH") else None, entetes=[("Origin", f"http://localhost:{port}")])
            dire(st == 405 and dict(h).get("Allow") == "GET", f"{meth} /api/vue/extensions : 405, Allow: GET ({st})")
        dire(photo(i) == avant, "les requêtes (GET et refusées) n'ont rien écrit")
        # 3. extensions.toml illisible : dit sans son contenu
        sauve = (i / "extensions.toml").read_bytes()
        (i / "extensions.toml").write_text(f'[skill.casse\ndescription = "{m_inv}"\n')
        st, h, c = req("GET", "/api/vue/extensions", cookie)
        try: di = json.loads(c)["donnees"]
        except (ValueError, KeyError): di = {}
        dire(st == 200 and di.get("lisible") is False and any("illisible" in y["quoi"] for y in di.get("signalements", [])) and m_inv.encode() not in c,
             f"extensions.toml illisible : la page le dit (200, lisible = non), sans son contenu ({st})")
        (i / "extensions.toml").write_bytes(sauve)
    finally:
        srv.terminate()
        try: _, journal = srv.communicate(timeout=10)
        except subprocess.TimeoutExpired: srv.kill(); _, journal = srv.communicate()
    dire(not [y for y in tous + [m_inv] if y in journal] and "GET /api/vue/extensions 200" in journal,
         f"journal du serveur : la requête (méthode, chemin, code), aucun marqueur ({journal.count(chr(10))} lignes)")

    # 6. le navigateur
    module = os.environ.get("BERGER_PLAYWRIGHT") or next((q for q in ("playwright", "playwright-core") if shutil.which("node") and subprocess.run(
        ["node", "-e", f"require.resolve('{q}')"], capture_output=True).returncode == 0), None)
    if not module or not shutil.which("node"):
        print("NON JOUÉ navigateur réel (Extensions à 390, 820, 1280, 1440, 1920 px, 2 thèmes) : Playwright absent de cette machine")
    else:
        (i / "docs/assets").mkdir(parents=True, exist_ok=True); shutil.copy2(SRC / "docs/assets/berger.png", i / "docs/assets/berger.png")
        srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
                except OSError: time.sleep(0.1)
            r = subprocess.run(["node", str(SRC / "tests/_page_extensions.js"), lien, ",".join(tous + [str(m), marque])], env={**os.environ, "BERGER_PLAYWRIGHT": module},
                               capture_output=True, text=True, timeout=900)
            try: res = json.loads(r.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError): res = {"#lancement": "ERREUR " + (r.stderr or r.stdout)[-400:]}
            if str(res.get("#lancement", "")).startswith("NON JOUÉ"): print(res["#lancement"])
            else:
                dire(len(res) >= 10 and "#exécution" not in res and "#lancement" not in res, f"navigateur : {len(res)} mesures jouées ({res.get('#exécution', res.get('#lancement', 'sans erreur'))})")
                for k, y in res.items():
                    if not k.startswith("#"): dire(y == "ok", f"navigateur : {k} ({y})")
        finally:
            srv.terminate(); srv.wait(timeout=10)

# 5. la page : aucun champ, bouton ni requête ; l'onglet et son icône
app = (SRC / "bin/page/app.js").read_text(); src = json.loads((SRC / "bin/page/icones.json").read_text())
f = re.search(r"\nfunction extensions\(d\) \{.*?\n\}\n", app, re.S)
code = f.group(0) if f else ""
dire(bool(f) and not re.search(r'"(input|textarea|select|form|button)"|bouton\(|data-geste|fetch\(|method', code),
     "app.js : le rendu des Extensions n'a ni champ, ni bouton, ni requête (lecture seule)")
dire(re.search(r"extensions: \{ rendre: d => extensions\(d\), fixe: true \}", app) is not None, "app.js : la vue Extensions, relue à chaque ouverture de l'onglet")
dire(src["onglets"].get("Extensions", {}).get("icone") == "extensions" and "extensions" in src["icones"], "icones.json : l'onglet Extensions et son icône (source commune)")
srv_code = (SRC / "bin/interface.py").read_text()
dire('ROUTE_EXTENSIONS = "/api/vue/extensions"' in srv_code, "bin/interface.py : la route des extensions, GET seulement")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
