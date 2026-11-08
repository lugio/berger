#!/usr/bin/env python3
"""Interface web v2, lot 3 : la page « Conversation » (spec docs/plans/2026-11-05-interface-web-v2-lot3-spec.md, go n° 166). Sans modèle,
faux Herdr, installation JETABLE (tests/_jeu_vues.py), vraies requêtes HTTP sur 127.0.0.1.
1. Lecture du fil : une transcription Claude d'essai (messages, appels d'outils ET leurs sorties, rappel du moteur, conversation annexe,
   forme de clé) puis une session Codex d'essai : messages de chaque côté, actions regroupées en « N actions » (outil et cible courte),
   AUCUNE sortie d'outil, forme de clé masquée (message et cible), demande de validation en carte à son heure ; 50 tours et 200 Kio au
   plus ; page fermée pour un agent non déclaré ; la transcription n'est jamais écrite (empreinte et date inchangées) ; servi par HTTP.
Usage : python3 tests/interface-conversation.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import hashlib, http.client, json, os, re, socket, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

SRC = Path(__file__).resolve().parent.parent
ko = 0
CLE = "sk-" + "factice" * 4                                               # une forme de clé construite à l'exécution (jamais écrite en clair)


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def port_libre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True); m = i.parent
    env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=120)
    def fil(a):
        r = b("vue", "conversation", a, "--json")
        try: return json.loads(r.stdout)["donnees"], r.stdout
        except (ValueError, KeyError): return {"ouverte": None, "tours": [], "erreur": r.stderr[-300:]}, r.stdout

    # ── 1. Claude : la transcription d'essai du jeu (vigie) ──
    tr = m / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(i / "agents/vigie")) / "conv-essai.jsonl"
    avant = (hashlib.sha256(tr.read_bytes()).hexdigest(), tr.stat().st_mtime_ns)
    d, brut = fil("vigie")
    tours = d["tours"]; genres = [x["genre"] for x in tours]
    dire(d["ouverte"] is True and d["moteur"] == "claude", f"vigie (déclaré dans [conversation] agents) : page ouverte, moteur claude ({d.get('raison') or d.get('erreur')})")
    dire(genres[:2] == ["proprio", "agent"] and genres.count("proprio") == 2, f"messages du propriétaire (à droite) et de l'agent (à gauche), dans l'ordre ({genres})")
    acts = [x for x in tours if x["genre"] == "actions"]
    dire(len(acts) == 1 and [a["outil"] for a in acts[0]["actions"]] == ["Bash", "Read", "Bash"] and acts[0]["actions"][0]["cible"] == "ls -la /sauvegardes"
         and acts[0]["actions"][1]["cible"] == "/etc/retention.conf", f"les appels d'outils entre deux messages : UNE ligne « 3 actions », outil et cible courte ({acts})")
    dire("SORTIE-D-OUTIL-JAMAIS-RENDUE" not in brut and "retention=30" not in brut, "aucune sortie d'outil dans les données (ni dans la réponse)")
    dire("CONVERSATION-ANNEXE-IGNOREE" not in brut and "réflexion jamais montrée" not in brut and "rappel interne du moteur" not in brut,
         "ni conversation annexe, ni réflexion du modèle, ni rappel ajouté par le moteur")
    dire(CLE not in brut and "[masqué : secret possible]" in [x["texte"] for x in tours if x["genre"] == "agent"]
         and acts and acts[0]["actions"][2]["cible"] == "[masqué : secret possible]", "une forme de clé (MOTIFS_CLES) est masquée, dans un message comme dans la cible d'une action")
    vals = [x for x in tours if x["genre"] == "validation"]
    dire([v["validation"]["n"] for v in vals] == [1, 3] and genres.index("validation") > genres.index("proprio") and vals[0]["quand"] == "2026-10-13T09:00:00",
         f"les demandes de validation de l'agent paraissent dans le fil, en carte, à leur heure ({[(v['validation']['n'], v['quand']) for v in vals]})")
    dire(d["vivant"] is False and d["raison"] == "au repos : relance-le depuis Herdr", "agent sans panneau vivant dans Herdr : « au repos : relance-le depuis Herdr »")
    dire((hashlib.sha256(tr.read_bytes()).hexdigest(), tr.stat().st_mtime_ns) == avant, "la transcription n'est jamais écrite (empreinte et date inchangées)")
    d2, _ = fil("demo-ecran")
    dire(d2["ouverte"] is False and "[conversation] agents" in (d2["raison"] or "") and d2["tours"] == [], "un agent non déclaré : page fermée, rien lu")
    r = b("vue", "conversation", "vigie")
    dire(r.returncode == 0 and "3 actions" in r.stdout and "SORTIE-D-OUTIL" not in r.stdout and CLE not in r.stdout, "le rendu texte (Herdr) : mêmes données, mêmes masques")

    # 50 tours au plus, 200 Kio au plus
    long = [{"type": "user" if k % 2 else "assistant", "timestamp": f"2026-10-13T07:{k // 60:02d}:{k % 60:02d}Z",
             "message": {"content": "question " + str(k) if k % 2 else [{"type": "text", "text": ("réponse " + str(k) + " ") * 900}]}} for k in range(120)]
    tr2 = tr.with_name("conv-longue.jsonl"); tr2.write_text("".join(json.dumps(e) + "\n" for e in long))
    (i / "agents/vigie/.conversation-claude").write_text("conv-longue\n")
    d, brut = fil("vigie")
    dire(len(d["tours"]) <= 50 and d["tronque"] is True and len(brut.encode()) <= 200 * 1024, f"fil long : {len(d['tours'])} tours (≤ 50), {len(brut.encode()) // 1024} Kio (≤ 200), « coupé » dit")
    dire(d["tours"] and "réponse 119" in (d["tours"][-1]["texte"] or "") or any("question 119" in (x["texte"] or "") for x in d["tours"]), "ce sont les DERNIERS tours qui restent")
    (i / "agents/vigie/.conversation-claude").write_text("conv-essai\n")

    # ── Codex : la session en cours de scribe (déclaré), son moteur codex ──
    (i / "agents/scribe/.herdr.json").write_text(json.dumps({"agents": {"codex": "p-scribe-codex"}}))
    ses = i / ".codex/sessions/2026/10/13"; ses.mkdir(parents=True)
    cwd = next((l.split("=", 1)[1].strip() for l in (i / "agents/scribe/agent.conf").read_text().splitlines() if l.startswith("dossier")), str(i / "agents/scribe"))
    cwd = str(Path(os.path.expanduser(cwd)).resolve()) if cwd.startswith("~") else cwd
    q = lambda mn: f"2026-10-13T07:{mn:02d}:00Z"
    ev = [{"type": "session_meta", "timestamp": q(0), "payload": {"cwd": cwd}},
          {"type": "response_item", "timestamp": q(1), "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<environment_context>cwd</environment_context>"}]}},
          {"type": "response_item", "timestamp": q(2), "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Rédige le compte rendu."}]}},
          {"type": "response_item", "timestamp": q(3), "payload": {"type": "reasoning", "summary": [{"type": "summary_text", "text": "RAISONNEMENT-CACHE"}]}},
          {"type": "response_item", "timestamp": q(4), "payload": {"type": "function_call", "name": "shell", "arguments": json.dumps({"command": ["bash", "-lc", "cat notes.md"]}), "call_id": "c1"}},
          {"type": "response_item", "timestamp": q(4), "payload": {"type": "function_call_output", "call_id": "c1", "output": "SORTIE-CODEX-JAMAIS-RENDUE"}},
          {"type": "response_item", "timestamp": q(5), "payload": {"type": "custom_tool_call", "name": "apply_patch", "input": "*** Begin Patch\n*** Add File: cr.md\n+texte\n*** End Patch", "call_id": "c2"}},
          {"type": "response_item", "timestamp": q(6), "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Compte rendu écrit."}]}},
          {"type": "event_msg", "timestamp": q(6), "payload": {"type": "agent_message", "message": "DOUBLON-EVENEMENT"}}]
    vieux = ses / "rollout-ancienne.jsonl"; vieux.write_text(json.dumps({"type": "session_meta", "payload": {"cwd": cwd}}) + "\n"
                                                            + json.dumps({"type": "response_item", "timestamp": q(0), "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ANCIENNE-SESSION"}]}}) + "\n")
    os.utime(vieux, (time.time() - 3600, time.time() - 3600))
    (ses / "rollout-autre-agent.jsonl").write_text(json.dumps({"type": "session_meta", "payload": {"cwd": str(i / "agents/vigie")}}) + "\n")
    (ses / "rollout-courante.jsonl").write_text("".join(json.dumps(e) + "\n" for e in ev))
    d, brut = fil("scribe")
    g = [(x["genre"], x["texte"] or [a["outil"] + " " + a["cible"] for a in x["actions"] or []]) for x in d["tours"]]
    dire(d["moteur"] == "codex" and g == [("proprio", "Rédige le compte rendu."), ("actions", ["shell bash -lc cat notes.md", "apply_patch cr.md"]), ("agent", "Compte rendu écrit.")],
         f"Codex : la session EN COURS de l'agent (la plus récente à son dossier), messages et « 2 actions » ({g})")
    dire(not any(x in brut for x in ("SORTIE-CODEX-JAMAIS-RENDUE", "RAISONNEMENT-CACHE", "ANCIENNE-SESSION", "DOUBLON-EVENEMENT", "environment_context")),
         "Codex : ni sortie d'outil, ni raisonnement, ni ancienne session, ni doublon d'événement, ni contexte du moteur")

    # ── servi par l'interface : la vue et la liste des pages ouvertes ──
    port = port_libre()
    with open(i / "config.toml", "a") as f: f.write(f"[interface]\nport = {port}\n")
    jeton = b("interface", "lien").stdout.strip().partition("#jeton=")[2]
    srv = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); break
            except OSError: time.sleep(0.1)
        def req(methode, chemin, corps=None, cookie=None):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=60); c.putrequest(methode, chemin, skip_host=True)
            c.putheader("Host", f"localhost:{port}")
            if cookie: c.putheader("Cookie", cookie)
            if corps is not None: c.putheader("Content-Type", "application/json"); c.putheader("Content-Length", str(len(corps)))
            c.endheaders(corps); r = c.getresponse(); x = r.read()
            return r.status, r.getheader("Set-Cookie"), x
        _, ck, _ = req("POST", "/connexion", json.dumps({"jeton": jeton}).encode()); ck = ck.split(";")[0]
        st, _, x = req("GET", "/api/conversations", cookie=ck)
        dire(st == 200 and json.loads(x)["agents"] == ["vigie", "scribe"], f"GET /api/conversations : les pages ouvertes ({x[:120]})")
        dire(req("GET", "/api/conversations")[0] == 401, "GET /api/conversations sans session : 401")
        st, _, x = req("GET", "/api/vue/conversation?a=vigie", cookie=ck)
        dire(st == 200 and json.loads(x)["donnees"]["ouverte"] is True and b"SORTIE-D-OUTIL" not in x and CLE.encode() not in x and len(x) <= 200 * 1024,
             "GET /api/vue/conversation?a=vigie : le fil, sans sortie d'outil ni clé, sous 200 Kio")
    finally:
        srv.terminate(); srv.wait(timeout=10)

# ══ 2, 3, 4. envoyer : texte, pièces jointes, micro — vraies requêtes HTTP sur un serveur d'essai, faux Herdr qui REÇOIT agent.prompt ══
import base64, importlib.util, shutil, threading, wave
EMP = lambda agent, texte, ps: hashlib.sha256("\0".join([agent, texte] + [f"{n.rsplit('.', 1)[-1].lower()}:{len(o)}:{hashlib.sha256(o).hexdigest()}" for n, o in ps]).encode()).hexdigest()
PNG = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + b"\0" * 64


def wav(secondes):
    import io as _io
    f = _io.BytesIO()
    with wave.open(f, "wb") as w: w.setnchannels(1); w.setsampwidth(1); w.setframerate(8000); w.writeframes(b"\x80" * (8000 * secondes))
    return f.getvalue()


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True); m = i.parent
    env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}
    # faux Herdr : vigie VIVANT (vigie-claude), scribe déclaré mais au repos ; l'API reçoit agent.prompt
    fh = Path(t) / "herdr-vivant"; fh.write_text("#!/usr/bin/env python3\nimport json, sys\na = sys.argv[1:]\n"
        "if a[:2] == ['agent', 'list']: print(json.dumps({'result': {'agents': [{'name': 'vigie-claude', 'pane_id': 'p-vigie'}]}}))\n"
        "elif a[:2] == ['pane', 'get']: print(json.dumps({'result': {'pane': {'pane_id': a[2], 'agent_status': 'idle'}}}))\n"
        "else: print(json.dumps({'result': {}}))\n"); os.chmod(fh, 0o755)
    recus_ = []; api = Path(t) / "api.sock"
    try: so_api = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); so_api.bind(str(api)); so_api.listen(); par_socket = True
    except OSError: par_socket = False
    if not par_socket:
        # repli (bac à sable qui interdit les sockets UNIX) : dans l'installation JETABLE seulement, l'API Herdr écrit chaque requête dans un
        # fichier au lieu du socket — les mêmes contrôles se jouent ; sous les portes, c'est le vrai socket ci-dessus
        print("info  sockets UNIX interdites ici : l'API Herdr de l'installation jetable écrit ses requêtes dans un fichier (mêmes contrôles)")
        h_ = i / "bin/noyau/herdr.py"; src_ = h_.read_text(); fq = Path(t) / "herdr-api.jsonl"
        assert src_.count("    import socket\n    chemin = socket_herdr()") == 1
        h_.write_text(src_.replace("    import socket\n    chemin = socket_herdr()", "    import socket\n    if True:\n        with open(" + repr(str(fq))
                                   + ", 'a') as f_: f_.write(json.dumps({'id': 'berger', 'method': methode, 'params': params}) + '\\n')\n        return {}\n    chemin = socket_herdr()"))
    class Recus:
        def _l(self): return recus_ if par_socket else [json.loads(l) for l in fq.read_text().splitlines()] if fq.exists() else []
        def __len__(self): return len(self._l())
        def __getitem__(self, k): return self._l()[k]
    recus = Recus()
    def api_servir():
        while True:
            try: conn, _ = so_api.accept()
            except OSError: return
            with conn:
                try:
                    with conn.makefile("rb") as flux: q_ = json.loads(flux.readline())
                    recus_.append(q_); conn.sendall((json.dumps({"id": q_["id"], "result": {}}) + "\n").encode())
                except (OSError, ValueError, KeyError): pass
    if par_socket: threading.Thread(target=api_servir, daemon=True).start()
    env.update(BERGER_HERDR=str(fh), BERGER_HERDR_SOCKET=str(api)); os.environ.update(env); os.environ.pop("BERGER_AGENT", None)   # le serveur d'essai agit comme le propriétaire
    b = lambda *a, entree=None: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, input=entree, capture_output=True, text=True, timeout=120)
    base_conf = (i / "config.toml").read_text()
    def regler(**k): (i / "config.toml").write_text(base_conf + "[interface]\nactions = true\n" + "".join(f"{x} = {json.dumps(v)}\n" for x, v in k.items()))
    regler()
    jf = m / ".config/berger/interface.jeton"; jeton = b("interface", "lien").stdout.strip().partition("#jeton=")[2]
    journal_srv = jf.with_name("interface-actions.jsonl")
    spec = importlib.util.spec_from_file_location("interface_lot3", i / "bin/interface.py"); IF = importlib.util.module_from_spec(spec); spec.loader.exec_module(IF)
    def demarrer(**k):
        p_ = port_libre(); s_ = IF.Serveur(p_, jf, **{"actions": True, **k}); threading.Thread(target=s_.serve_forever, daemon=True).start(); return s_, p_
    srv, port = demarrer()
    cookie = IF.COOKIE + "=" + IF.deriver(jeton, "session")
    def req(methode, chemin, corps=None, plus=None, p=None, hote=None, ip="127.0.0.1", depuis=None):
        p = p or port; c = http.client.HTTPConnection(ip, p, timeout=120, source_address=(depuis, 0) if depuis else None); c.putrequest(methode, chemin, skip_host=True)
        h = {"Host": hote or f"localhost:{p}", "Cookie": cookie, **(plus or {})}
        corps = json.dumps(corps).encode() if isinstance(corps, dict) else corps
        if corps is not None: h.setdefault("Content-Type", "application/json"); h["Content-Length"] = str(len(corps))
        for k_, v_ in h.items():
            if v_ is not None: c.putheader(k_, v_)
        c.endheaders(corps); r = c.getresponse(); x = r.read()
        try: return r.status, json.loads(x or b"{}")
        except ValueError: return r.status, {}
    def envoyer(agent, texte, ps=(), modif=None, entetes=None, p=None, jeton_=None, hote=None, ip="127.0.0.1"):
        st, j = req("GET", f"/api/message/jeton?agent={agent}", p=p, hote=hote, ip=ip)
        if st != 200: return st, j
        corps = {"agent": agent, "texte": texte, "pieces": [{"nom": n, "donnees": base64.b64encode(o).decode()} for n, o in ps], "empreinte": EMP(agent, texte, ps), "nonce": j["nonce"]}
        corps.update(modif or {})
        h = {"Origin": f"http://localhost:{p or port}", "X-Berger-Jeton": j["jeton"] if jeton_ is None else jeton_, **(entetes or {})}
        return req("POST", "/api/message", corps, h, p=p, hote=hote, ip=ip)
    lignes = lambda: [json.loads(l) for l in journal_srv.read_text().splitlines()] if journal_srv.exists() else []

    # ── 2. texte : même chemin que berger parler ──
    n0 = len(recus); st, x = envoyer("vigie", "Bonjour vigie,\n\tla rétention passe à 90 jours.")
    via_web = recus[n0:]
    r = b("parler", "vigie", "--stdin", entree="Bonjour vigie,\n\tla rétention passe à 90 jours.")
    via_cli = recus[n0 + len(via_web):]
    dire(st == 200 and x.get("fait") is True and via_web and via_cli and [q_["method"] for q_ in via_web] == ["agent.prompt"]
         and via_web[0]["params"] == via_cli[0]["params"] == {"target": "vigie-claude", "text": "Bonjour vigie,\n\tla rétention passe à 90 jours."},
         f"envoi texte : le faux Herdr reçoit le MÊME agent.prompt que « berger parler vigie --stdin » ({st} {x.get('erreur')} {via_web[:1]})")
    ech = [json.loads(l) for l in (i / "courtier/echanges.jsonl").read_text().splitlines()]
    web = [e for e in ech if "via l'interface web" in e["texte"]]
    dire(web and web[-1]["de"] == "Proprio" and web[-1]["a"] == "vigie" and web[-1]["genre"] == "message" and "la rétention passe à 90 jours" in web[-1]["texte"],
         f"Échanges reçoit la même ligne que berger parler, avec « via l'interface web » ({web[-1:] })")
    jl = [l for l in lignes() if l.get("genre") == "message"]
    dire([l["resultat"] for l in jl[-2:]] == ["admis", "fait"] and jl[-1]["agent"] == "vigie" and jl[-1]["taille_texte"] == len("Bonjour vigie,\n\tla rétention passe à 90 jours.") and "rétention" not in journal_srv.read_text(),
         f"journal interface-actions.jsonl : « admis » AVANT, puis « fait », l'agent et la taille du texte, JAMAIS le texte ({jl[-2:]})")
    jv = (i / f"agents/vigie/memory/{time.strftime('%Y-%m-%d')}.md").read_text() if (i / f"agents/vigie/memory/{time.strftime('%Y-%m-%d')}.md").exists() else ""
    dire("via l'interface web (127.0.0.1) : message de Proprio" in jv, "le journal de l'agent note le message « via l'interface web », avec la source")

    # ── garde-fous : chaque refus, nommé ──
    s_off, p_off = demarrer(actions=False)
    st, x = req("GET", "/api/message/jeton?agent=vigie", p=p_off)
    dire(st == 403 and "actions désactivées" in x.get("erreur", ""), f"sans « actions = true » : refusé, nommé ({x.get('erreur')})")
    s_off.shutdown()
    try:
        s_vpn, p_vpn = demarrer(sources=("127.0.0.1", "127.0.0.2"))       # une source admise (lot 2) qui n'est pas 127.0.0.1
        st, x = req("GET", "/api/message/jeton?agent=vigie", p=p_vpn, depuis="127.0.0.2")
        st2, x2 = req("POST", "/api/message", {"agent": "vigie", "texte": "x"}, {"Origin": f"http://localhost:{p_vpn}"}, p=p_vpn, depuis="127.0.0.2")
        dire(st == 403 and st2 == 403 and "hors 127.0.0.1" in x.get("erreur", "") and "hors 127.0.0.1" in x2.get("erreur", ""),
             f"hors 127.0.0.1 (une autre source, comme un relais ou le VPN) : jeton et envoi refusés, nommés ({x.get('erreur')})")
        s_vpn.shutdown()
    except OSError as e: print(f"NON JOUÉ refus hors 127.0.0.1 : 127.0.0.2 indisponible ici ({e})")
    st, x = req("GET", "/api/message/jeton?agent=vigie", hote="exemple.invalid")
    dire(st == 403 and "hôte refusé" in x.get("erreur", "") and lignes()[-1].get("motif") == "hôte refusé", "mauvais Host : refusé, au journal")
    st, x = envoyer("vigie", "x", entetes={"Origin": "http://exemple.invalid"})
    dire(st == 403 and "origine refusée" in x.get("erreur", ""), f"mauvaise Origin : refusé ({x.get('erreur')})")
    st, x = envoyer("vigie", "x", jeton_="")
    dire(st == 403 and "jeton anti-rejeu" in x.get("erreur", ""), f"sans jeton anti-rejeu : refusé ({x.get('erreur')})")
    st, j = req("GET", "/api/message/jeton?agent=vigie")
    corps = {"agent": "vigie", "texte": "une fois", "pieces": [], "empreinte": EMP("vigie", "une fois", []), "nonce": j["nonce"]}
    h = {"Origin": f"http://localhost:{port}", "X-Berger-Jeton": j["jeton"]}
    st1, _ = req("POST", "/api/message", corps, h); st2, x = req("POST", "/api/message", corps, h)
    dire(st1 == 200 and st2 == 403 and "déjà servi" in x.get("erreur", ""), f"jeton déjà servi : le second envoi est refusé ({st1}, {st2} {x.get('erreur')})")
    st, x = envoyer("vigie", "texte montré", modif={"texte": "texte changé"})
    dire(st == 409 and "empreinte périmée" in x.get("erreur", ""), f"empreinte périmée (texte changé après l'aperçu) : refusé ({x.get('erreur')})")
    for agent, attendu in (("inconnu", "agent inconnu"), ("demo-ecran", "non ouverte"), ("scribe", "au repos : relance-le depuis Herdr")):
        n0 = len(recus); st, x = envoyer(agent, "bonjour")
        dire(st == 409 and attendu in x.get("erreur", "") and len(recus) == n0, f"{agent} : refusé, « {attendu} », rien remis ({x.get('erreur')})")
    for quoi, texte, attendu in (("texte trop long", "a" * 20001, "trop long"), ("caractère de contrôle", "cloche\x07", "caractère de contrôle"),
                                 ("contrôle C1 (U+009B, CSI)", "avant\u009b31mrouge", "caractère de contrôle"),
                                 ("forme de clé", "voici " + CLE, "forme de clé")):
        st, x = envoyer("vigie", texte)
        dire(st == 409 and attendu in x.get("erreur", "") and (quoi != "forme de clé" or "coffre" in x["erreur"]), f"{quoi} : refusé, nommé ({x.get('erreur', '')[:90]})")
    dire(CLE not in journal_srv.read_text() and CLE not in (i / "courtier/echanges.jsonl").read_text(), "la forme de clé refusée n'est écrite nulle part")
    # deux envois avec le MÊME jeton depuis deux fils : un seul passe
    st, j = req("GET", "/api/message/jeton?agent=vigie")
    corps = {"agent": "vigie", "texte": "course", "pieces": [], "empreinte": EMP("vigie", "course", []), "nonce": j["nonce"]}
    h = {"Origin": f"http://localhost:{port}", "X-Berger-Jeton": j["jeton"]}; res = []; depart = threading.Barrier(2)
    def fil_():
        depart.wait(); res.append(req("POST", "/api/message", corps, h)[0])
    fs = [threading.Thread(target=fil_) for _ in range(2)]
    for f_ in fs: f_.start()
    for f_ in fs: f_.join()
    dire(sorted(res) == [200, 403], f"même jeton depuis deux fils à la fois : un seul passe ({sorted(res)})")
    # la ligne finale du journal ne s'écrit pas → une erreur, jamais un 200
    s_f, p_f = demarrer(); noter = s_f.noter_message; s_f.noter_message = lambda *a, **k: False if a[3] == "fait" else noter(*a, **k)
    st, x = envoyer("vigie", "ligne finale", p=p_f)
    dire(st == 500 and "« fait »" in x.get("erreur", ""), f"ligne « fait » impossible à écrire : erreur 500, jamais 200 ({st} {x.get('erreur')})")
    s_f.noter_message = lambda *a, **k: False if a[3] == "admis" else noter(*a, **k); n0 = len(recus)
    st, x = envoyer("vigie", "sans ligne admis", p=p_f)
    dire(st == 503 and len(recus) == n0, f"ligne « admis » impossible à écrire : 503, rien n'est envoyé ({st})")
    s_f.shutdown()
    # débit : recompté sur l'heure entière, même après un redémarrage
    maintenant = datetime_ = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    with open(journal_srv, "a") as f:
        for _ in range(60): f.write(json.dumps({"quand": maintenant, "genre": "message", "resultat": "admis", "pieces": []}) + "\n")
        for _ in range(300): f.write(json.dumps({"quand": maintenant, "genre": "message", "resultat": "refusé", "motif": "origine refusée"}) + "\n")
    s_d, p_d = demarrer(); st, x = envoyer("vigie", "un de trop", p=p_d)
    dire(st == 429 and "60 messages par heure" in x.get("erreur", ""), f"débit : 60 messages par heure, relus au journal après un redémarrage (même après 300 refus) ({st} {x.get('erreur')})")
    st, ap = req("GET", "/api/action/apercu?action=valider&cible=1", p=p_d)
    dire(st == 200, "le débit des messages est À PART des 30 actions du lot 2 (un aperçu reste possible)")
    s_d.shutdown(); journal_srv.write_text("")
    srv.shutdown(); srv, port = demarrer()

    # ── 3. pièces jointes ──
    jour = time.strftime("%Y-%m-%d"); E = i / "agents/vigie/entrees"
    long_ = "\n".join(f"ligne {k} du long collage" for k in range(120))
    n0 = len(recus); st, x = envoyer("vigie", "voir le collage", [("collage.txt", long_.encode())])
    p0 = (x.get("pieces") or [{}])[0]; ch = Path(p0.get("chemin", "/absent"))
    dire(st == 200 and ch.is_file() and ch.parent == E / jour and re.fullmatch(r"\d{6}-\d+\.txt", ch.name) and oct(ch.stat().st_mode & 0o777) == "0o600"
         and oct(E.stat().st_mode & 0o777) == "0o700" and oct((E / jour).stat().st_mode & 0o777) == "0o700" and ch.read_text() == long_,
         f"long collage : un .txt en 0600 sous entrees/AAAA-MM-JJ/ (dossiers 0700), nom fait par Berger ({st} {x.get('erreur')} {ch})")
    txt = recus[-1]["params"]["text"] if len(recus) > n0 else ""
    dire(re.search(r"^Pièce jointe : entrees/" + jour + r"/\d{6}-\d+\.txt \(texte, \d+ Kio\)$", txt, re.M) is not None and txt.startswith("voir le collage\n"),
         f"le message porte une ligne par pièce : « Pièce jointe : entrees/…/….txt (texte, … Kio) » ({txt[-80:]!r})")
    st, x = envoyer("vigie", "", [("collage.txt", ("clé : " + CLE).encode())])
    dire(st == 409 and "forme de clé" in x.get("erreur", ""), "le même garde-secrets s'applique au contenu d'un long collage")
    # un PNG valide ; un lien posé à l'avance (aux noms des secondes qui viennent) n'est pas suivi
    dehors = Path(t) / "dehors.txt"; dehors.write_text("intact")
    (E / jour).mkdir(parents=True, exist_ok=True)
    for k in range(0, 8): (E / jour / f"{time.strftime('%H%M%S', time.localtime(time.time() + k))}-1.png").symlink_to(dehors)
    st, x = envoyer("vigie", "", [("capture d'écran.png", PNG)])
    ch = Path((x.get("pieces") or [{}])[0].get("chemin", "/absent"))
    dire(st == 200 and ch.is_file() and not ch.is_symlink() and ch.read_bytes() == PNG and oct(ch.stat().st_mode & 0o777) == "0o600" and "capture" not in ch.name
         and re.fullmatch(r"\d{6}-\d+\.png", ch.name) and dehors.read_text() == "intact",
         f"image PNG : rangée en 0600 sous un nom fait par Berger ; le lien posé à l'avance n'est pas suivi ({st} {x.get('erreur')} {ch.name})")
    for f_ in (E / jour).iterdir():
        if f_.is_symlink(): f_.unlink()
    for quoi, piece, attendu in (("PNG renommé en .wav", ("son.wav", PNG), "premiers octets"), ("SVG", ("dessin.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>"), "type de pièce refusé"),
                                 ("MP3", ("chanson.mp3", b"ID3\x03\0\0\0\0\0\0"), "type de pièce refusé"), ("HEIC", ("photo.heic", b"\0\0\0\x18ftypheic"), "type de pièce refusé"),
                                 ("PDF", ("doc.pdf", b"%PDF-1.4\n"), "type de pièce refusé"), ("trop gros", ("grande.png", PNG + b"\0" * (10 * 1024 * 1024)), "trop grosse")):
        st, x = envoyer("vigie", "", [piece])
        dire(st == 409 and attendu in x.get("erreur", ""), f"{quoi} : refusé, nommé ({x.get('erreur', '')[:90]})")
    if shutil.which("ffprobe"):
        st, x = envoyer("vigie", "", [("dictee.wav", wav(2))])
        dire(st == 200 and (x.get("pieces") or [{}])[0].get("genre") == "audio", f"audio WAV de 2 s : accepté ({st} {x.get('erreur')})")
        st, x = envoyer("vigie", "", [("longue.wav", wav(601))])
        dire(st == 409 and "trop long" in x.get("erreur", ""), f"audio de plus de 10 minutes (durée lue par ffprobe) : refusé ({x.get('erreur')})")
    else: print("NON JOUÉ audio trop long : ffprobe absent")
    with open(E / jour / "gros.bin", "wb") as f: f.truncate(500 * 1024 * 1024)       # creux : ne prend pas de place, compte pour le quota
    st, x = envoyer("vigie", "", [("capture.png", PNG)])
    dire(st == 409 and "quota" in x.get("erreur", "") and (E / jour / "gros.bin").exists(), f"quota de 500 Mio dépassé : refusé, rien n'est supprimé ({x.get('erreur', '')[:90]})")
    (E / jour / "gros.bin").unlink()
    # deux dépôts simultanés quand il reste 10 Mio : un seul passe (renvoi n° 172 : compte et écriture sous entrees/.verrou)
    journal_srv.write_text(""); srv.shutdown(); srv, port = demarrer()
    with open(E / jour / "gros.bin", "wb") as f: f.truncate(490 * 1024 * 1024)
    # la fenêtre entre le compte et l'écriture est élargie (1,5 s), dans l'installation JETABLE seulement : sans verrou, les deux passeraient
    fc = i / "bin/commandes/conversation.py"; avant_c = fc.read_text()
    assert len(re.findall(r"deja = occupe\(racine\)[^\n]*", avant_c)) == 1
    fc.write_text(re.sub(r"(deja = occupe\(racine\)[^\n]*)", r"\1; time.sleep(1.5)", avant_c))
    six = PNG + b"\0" * (6 * 1024 * 1024); res = []; depart = threading.Barrier(2)
    def depot():
        depart.wait(); res.append(envoyer("vigie", "", [("capture.png", six)]))
    fs = [threading.Thread(target=depot) for _ in range(2)]
    for f_ in fs: f_.start()
    for f_ in fs: f_.join()
    dire(sorted(r_[0] for r_ in res) == [200, 409] and any("quota" in r_[1].get("erreur", "") for r_ in res),
         f"deux dépôts simultanés à 490 Mio (6 Mio chacun, quota 500) : un seul passe ({[(r_[0], r_[1].get('erreur', '')[:40]) for r_ in res]})")
    fc.write_text(avant_c); (E / jour / "gros.bin").unlink()
    # un WebM (ou Ogg) qui porte une piste vidéo : refusé, la vidéo est hors périmètre ; le même sans vidéo passe
    if shutil.which("ffmpeg"):
        fv, fa = Path(t) / "film.webm", Path(t) / "son.webm"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=16x16:d=1", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "1",
                        "-c:v", "libvpx", "-c:a", "libopus", str(fv)], capture_output=True, timeout=60)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "1", "-c:a", "libopus", str(fa)], capture_output=True, timeout=60)
        if fv.is_file() and fa.is_file():
            st, x = envoyer("vigie", "", [("dictee.webm", fv.read_bytes())])
            dire(st == 409 and "piste vidéo" in x.get("erreur", ""), f"WebM avec une piste vidéo : refusé ({x.get('erreur', '')[:90]})")
            st, x = envoyer("vigie", "", [("dictee.webm", fa.read_bytes())])
            dire(st == 200, f"le même WebM, audio seul : accepté ({st} {x.get('erreur')})")
        else: print("NON JOUÉ WebM avec piste vidéo : ffmpeg n'a pas su le fabriquer ici")
    else: print("NON JOUÉ WebM avec piste vidéo : ffmpeg absent")
    shutil.move(str(E), str(Path(t) / "entrees-gardees")); E.symlink_to(Path(t) / "ailleurs", target_is_directory=True); (Path(t) / "ailleurs").mkdir()
    st, x = envoyer("vigie", "", [("capture.png", PNG)])
    dire(st == 409 and "lien" in x.get("erreur", "") and not any((Path(t) / "ailleurs").iterdir()), f"entrees/ remplacé par un lien : refusé, rien n'est écrit dehors ({x.get('erreur', '')[:90]})")
    E.unlink()
    jl = [l for l in lignes() if l.get("genre") == "message" and l.get("resultat") == "admis" and l.get("pieces")]
    dire(jl and all(set(p_) == {"type", "taille", "sha256"} for l in jl for p_ in l["pieces"]) and "long collage" not in journal_srv.read_text(),
         "journal : chaque pièce avec son type, sa taille et son sha256, jamais son contenu")

    journal_srv.write_text(""); srv.shutdown(); srv, port = demarrer()       # un débit neuf pour la suite
    # ── navigateur (Playwright, s'il est là ; sinon « NON JOUÉ », jamais « ok ») ──
    module = os.environ.get("BERGER_PLAYWRIGHT") or next((p_ for p_ in ("playwright", "playwright-core") if shutil.which("node") and subprocess.run(
        ["node", "-e", f"require.resolve('{p_}')"], capture_output=True).returncode == 0), None)
    if not module or not shutil.which("node"):
        print("NON JOUÉ navigateur réel (zone de saisie, Entrée et Maj+Entrée, collage d'une image, dépliage de « N actions ») : Playwright absent de cette machine")
    else:
        r = subprocess.run(["node", str(SRC / "tests/_page_conversation.js"), f"http://localhost:{port}/#jeton={jeton}", "vigie"], env={**os.environ, "BERGER_PLAYWRIGHT": module},
                           capture_output=True, text=True, timeout=900)
        try: res = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): res = {"#lancement": "ERREUR " + (r.stderr or r.stdout)[-400:]}
        if str(res.get("#lancement", "")).startswith("NON JOUÉ"): print(res["#lancement"])
        else:
            dire(len(res) >= 60 and "#exécution" not in res, f"navigateur : {len(res)} mesures jouées ({res.get('#exécution', 'sans erreur')})")
            for k, v in res.items():
                if k != "#exécution": dire(v == "ok", f"navigateur : {k} ({v})")

    journal_srv.write_text(""); srv.shutdown(); srv, port = demarrer()
    # ── 4. micro ──
    st, x = req("GET", "/api/conversations")
    dire(st == 200 and x.get("micro", {}).get("actif") is False and "aucune transcription locale déclarée" in x["micro"].get("raison", ""),
         f"micro sans module déclaré : grisé, avec sa raison ({x.get('micro')})")
    def corps_dictee(nom, o, p=None, empreinte=None):
        st_, j_ = req("GET", "/api/message/jeton?usage=transcription&agent=vigie", p=p)
        return {"agent": "vigie", "nom": nom, "donnees": base64.b64encode(o).decode(), "empreinte": empreinte or hashlib.sha256(o).hexdigest(), "nonce": j_.get("nonce")}
    entetes_dictee = lambda p=None: {"Origin": f"http://localhost:{p or port}", "X-Berger-Jeton": IF.deriver(jeton, "message")}
    transcrire = lambda nom, o, p=None: req("POST", "/api/transcrire", corps_dictee(nom, o, p), entetes_dictee(p), p=p)
    st, x = transcrire("dictee.wav", wav(1))
    dire(st == 409 and "aucune transcription locale déclarée" in x.get("erreur", ""), f"transcription demandée quand même : refusée CÔTÉ SERVEUR ({x.get('erreur')})")
    # rejeu (renvoi n° 172) : la MÊME requête deux fois — la seconde est refusée ; une empreinte qui n'est pas celle de l'audio aussi
    c_ = corps_dictee("dictee.wav", wav(1)); st1, _ = req("POST", "/api/transcrire", c_, entetes_dictee()); st2, x2 = req("POST", "/api/transcrire", c_, entetes_dictee())
    dire(st1 == 409 and st2 == 403 and "déjà servi" in x2.get("erreur", ""), f"transcription rejouée (même requête deux fois) : la seconde refusée, « déjà servi » ({st1}, {st2} {x2.get('erreur')})")
    st, x = req("POST", "/api/transcrire", corps_dictee("dictee.wav", wav(1), empreinte="0" * 64), entetes_dictee())
    dire(st == 409 and "empreinte périmée" in x.get("erreur", ""), f"transcription dont l'empreinte n'est pas celle de l'audio : refusée ({x.get('erreur')})")
    dire(len([l for l in lignes() if l.get("genre") == "transcription" and l.get("resultat") == "admis"]) == 2, "chaque transcription admise compte dans le débit (ligne « admis »), le rejeu et l'empreinte fausse non")
    regler(transcription="relatif/stt")
    dire(json.loads(b("conversation", "liste", "--json").stdout)["micro"]["actif"] is False, "transcription déclarée par un chemin relatif : micro grisé")
    # le faux binaire : ses réglages (mode, port) écrits DANS son code — rien à côté de lui ne lui est visible (/tmp est recouvert)
    stt = Path(t) / "stt"; bus = f"/run/user/{os.getuid()}/bus"
    # masques_si_presents (relecture de la n° 175) : un dossier optionnel PRÉSENT (.aws, avec un fichier) doit être recouvert aussi
    maison = Path(env["HOME"]); aws = maison / ".aws" / "credentials"; aws.parent.mkdir(exist_ok=True); aws.write_text("factice-du-test\n")
    base_conf = 'masques_si_presents = [".aws", ".absent-du-test"]\n' + base_conf
    def ecrire_stt(mode):
        stt.write_text("#!/usr/bin/python3\nimport os, socket, sys, time\na = open(sys.argv[1], 'rb').read(4)\n"
            f"MODE, PORT, BUS, HERDR, AWS = {mode!r}, {port}, {bus!r}, {str(api)!r}, {str(aws)!r}\n"
            # seuls permis sous /tmp : le dossier de la dictée et le dossier où bwrap remonte le binaire seul — où que soit TMPDIR
            "tete = lambda q: q[5:].split('/')[0] if q.startswith('/tmp/') else None\n"
            "PERMIS = {tete(os.path.abspath(sys.argv[1])), tete(os.path.abspath(sys.argv[0]))}\n"
            "if os.environ.get('MODE_ESSAI'): print('FUITE-ENV')\n"
            "fuite = [k for k in os.environ if k.startswith('BERGER') or k.startswith('DBUS') or k.startswith('XDG_RUNTIME')]\n"
            "s = socket.socket(); s.settimeout(1)\n"
            "try: s.connect(('127.0.0.1', PORT)); res = 'RESEAU'\n"
            "except OSError: res = 'sans-reseau'\n"
            "vus = [x for x in (BUS, HERDR, AWS) if os.path.exists(x) and os.path.getsize(x)] + [x for x in os.listdir('/tmp') if x not in PERMIS]\n"
            "if MODE == 'bavard':\n    while True: sys.stdout.write('x' * 65536); sys.stdout.flush()\n"
            "if MODE == 'lent': time.sleep(10)\n"
            "if MODE == 'cle': print('sk-' + 'factice' * 4); sys.exit(0)\n"
            "print('bonjour depuis la dictée', res, 'fuite' if fuite else 'propre', 'RIFF' if a == b'RIFF' else '?', 'VUS:' + ','.join(vus) if vus else 'rien-de-plus')\n")
        os.chmod(stt, 0o755)
    ecrire_stt("normal")
    regler(transcription=str(stt), transcription_delai=3)
    os.environ["MODE_ESSAI"] = "1"; srv.shutdown(); srv, port = demarrer(); ecrire_stt("normal")
    st, x = req("GET", "/api/conversations")
    dire(st == 200 and x.get("micro", {}).get("actif") is True, "binaire local déclaré, exécutable : micro actif")
    bac = subprocess.run(["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--unshare-net", "true"], capture_output=True).returncode == 0 if shutil.which("bwrap") else False
    st, x = transcrire("dictee.wav", wav(1))
    if bac:
        dire(st == 200 and x.get("texte") == "bonjour depuis la dictée sans-reseau propre RIFF rien-de-plus",
             f"faux binaire local : le texte revient — sans réseau, sans variable de Berger ni bus de session, sans {bus} ni socket de Herdr, "
             f"/tmp vide hors du dossier de la dictée ({st} {x})")
        ecrire_stt("lent"); st, x = transcrire("dictee.wav", wav(1))
        dire(st == 409 and "délai" in x.get("erreur", ""), f"transcription trop longue : délai dépassé, refusée ({x.get('erreur')})")
        ecrire_stt("bavard"); t0 = time.monotonic(); st, x = transcrire("dictee.wav", wav(1))
        dire(st == 409 and "sortie trop longue" in x.get("erreur", "") and time.monotonic() - t0 < 3,
             f"transcripteur qui écrit sans fin : arrêté dès 64 Kio, refus nommé, avant le délai ({x.get('erreur')})")
        ecrire_stt("cle"); st, x = transcrire("dictee.wav", wav(1))
        dire(st == 409 and "forme de clé" in x.get("erreur", "") and CLE not in json.dumps(x), f"transcription qui porte une forme de clé : refusée, rien montré ({x.get('erreur')})")
    else:
        print("NON JOUÉ transcription par le faux binaire (texte rendu, délai dépassé, forme de clé) : bubblewrap ne démarre pas ici")
        dire(st == 409 and "isolement" in x.get("erreur", ""), f"sans isolement réseau possible, la transcription est refusée, jamais lancée sans ({x.get('erreur')})")
    src_c = (SRC / "bin/commandes/conversation.py").read_text()
    argv_c = src_c[src_c.index("def argv_transcription"):src_c.index("def transcrire")]
    ordre = [argv_c.find(x) for x in ('"--tmpfs", "/run"', '"--tmpfs", "/tmp"', '"--tmpfs", "/var/run"', '"--clearenv"', '"--bind", str(t)')]
    dire(all(k >= 0 for k in ordre) and max(ordre[:3]) < ordre[4], f"bac à sable de la transcription : /run, /var/run et /tmp recouverts AVANT le dossier de la dictée, environnement vidé ({ordre})")
    # les fonctions du bac à sable, appelées directement (jouées partout, même sans bubblewrap)
    def dans_conversation(corps):
        code = (f"import runpy,sys,json,time;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='essai');"
                "c=g['commandes'].FAMILLES['conversation']\n" + corps)
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
        try: return json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): return {"erreur-du-test": (r.stderr or r.stdout)[-300:]}
    mq = dans_conversation("print(json.dumps({'masques': [str(p) for p in c.masques_transcription()], "
                           "'argv': c.argv_transcription('/usr/bin/true', '/tmp/d', '/tmp/d/f.wav')}))")
    dire(str(aws.parent) in mq.get("masques", []) and not any("absent-du-test" in x for x in mq.get("masques", []))
         and str(aws.parent) in mq.get("argv", []) and mq["argv"].index(str(aws.parent)) < mq["argv"].index("--bind"),
         f"masques_si_presents : un dossier optionnel présent (.aws) recouvert dans le bac à sable de la dictée, avant le dossier de la dictée ; "
         f"un absent ignoré ({mq.get('erreur-du-test') or [x for x in mq.get('masques', []) if '.aws' in x]})")
    bav = dans_conversation("t0=time.monotonic()\ntry: c.executer_borne([sys.executable, '-c', 'import sys\\nwhile True: sys.stderr.write(\"e\" * 65536); sys.stderr.flush()'], 20); r = 'lu'\n"
                            "except c.Refus as e: r = str(e)\nprint(json.dumps({'r': r, 'duree': time.monotonic() - t0}))")
    dire("sortie trop longue" in bav.get("r", "") and bav.get("duree", 99) < 5,
         f"sortie du transcripteur bornée PENDANT la lecture (stderr sans fin) : processus tué, refus nommé, sans attendre le délai ({bav})")
    ok_ = dans_conversation("k, o, e = c.executer_borne([sys.executable, '-c', 'print(\"bonjour\")'], 20)\nprint(json.dumps({'r': [k, o.decode()]}))")
    dire(ok_.get("r") == [0, "bonjour\n"], f"sortie courte : lue en entier, code rendu ({ok_})")
    st, x = transcrire("image.png", PNG)
    dire(st == 409 and "audio" in x.get("erreur", ""), f"transcription d'un fichier qui n'est pas de l'audio : refusée ({x.get('erreur')})")
    del os.environ["MODE_ESSAI"]
    r = b("conversation", "liste", "--json"); r2 = subprocess.run([sys.executable, str(i / "bin/berger"), "conversation", "liste", "--json"], env={**env, "BERGER_AGENT": "vigie"}, capture_output=True, text=True)
    dire(r2.returncode != 0 and "propriétaire" in r2.stderr, "berger conversation : refusé à un agent")
    srv.shutdown()

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
