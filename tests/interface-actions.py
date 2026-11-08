#!/usr/bin/env python3
"""Tests des actions du propriétaire dans l'interface web (interface web v2, lot 2 ; spec docs/plans/2026-11-03-interface-web-v2-spec.md,
go n° 140) — sans modèle, faux Herdr, installation JETABLE (tests/_jeu_vues.py), vraies requêtes HTTP sur 127.0.0.1, et un FAUX
COURTIER (un fil qui lit les fichiers <n>.decision comme le vrai et écrit <n>.fait.json).

Vérifie chaque refus NOMMÉ : actions absentes de config.toml, source hors local/VPN, sans session, sans jeton anti-rejeu, d'une autre
origine (ou sans origine), jeton déjà servi (rejeu), demande modifiée depuis l'aperçu (confirmation périmée), refus sans motif ; la
VALEUR ÉGALE à la ligne de commande (même fichier de décision que `berger valider` / `berger refuser`, même issue que `berger parler`,
le même « lu » que `berger lire`) avec « via l'interface web » au journal de l'agent ; chaque tentative au journal du serveur, refus
compris, sans le texte du motif ni de la réponse ; 30 actions par heure ; `berger action` refusé à un agent.
Usage : python3 tests/interface-actions.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import hashlib, http.client, importlib.util, json, os, socket, ssl, subprocess, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def port_libre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def attendre(port):
    for _ in range(80):
        try: socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); return
        except OSError: time.sleep(0.1)


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True); m = i.parent
    env = {k: v for k, v in env.items() if k != "BERGER_AGENT"}         # l'installation jetable agit comme le propriétaire
    b = lambda *a, entree=None, **k: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env={**env, **k.get("env", {})}, input=entree,
                                                    capture_output=True, text=True, timeout=90)
    # une question posée AU PROPRIÉTAIRE : scribe (ni développeur, ni arrêté dans son terminal comme vigie)
    (i / "agents/scribe/CHECKLIST.md").write_text("# Rétention\n- [x] Relever\n- [ ] Choisir   ← en cours\n❓ Question : faut-il garder l'ancien écran ?\n")
    V = i / "courtier/validations"; journal_srv = m / ".config/berger/interface-actions.jsonl"

    # ── faux courtier : la décision écrite par `berger valider|refuser` est relevée, gardée, puis « exécutée » ──
    vues_decisions = {}; arret = threading.Event(); pause = threading.Event()      # pause : la décision reste en attente du courtier
    def courtier():
        while not arret.is_set():
            if pause.is_set(): time.sleep(0.05); continue
            for f in V.glob("*.decision"):
                try: contenu = f.read_text()
                except OSError: continue
                n = f.stem; vues_decisions[n] = contenu
                d = json.loads((V / f"{n}.json").read_text()) if (V / f"{n}.json").exists() else {"n": int(n)}
                d.update(etat="validé et exécuté" if contenu.startswith("valider") else "refusé")
                (V / f"{n}.fait.json").write_text(json.dumps(d)); f.unlink(); (V / f"{n}.json").unlink(missing_ok=True)
            time.sleep(0.05)
    threading.Thread(target=courtier, daemon=True).start()
    def nouvelle(n, agent="vigie", apercu="une écriture d'essai"):
        (V / f"{n}.json").write_text(json.dumps({"n": n, "agent": agent, "outil": "berger-admin", "verbe": "espace", "args": [agent],
                                                 "apercu": apercu, "valideur": None, "demande": "2026-10-13T10:00"}))

    port = port_libre(); hote = f"localhost:{port}"; origine = f"http://{hote}"
    base_conf = (i / "config.toml").read_text()
    def servir(actions):
        (i / "config.toml").write_text(base_conf + f"[interface]\nport = {port}\n" + ("actions = true\n" if actions else ""))
        s = subprocess.Popen([sys.executable, str(i / "bin/berger"), "interface", "servir"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        attendre(port); return s

    def req(methode, chemin, corps=None, cookie=None, plus=None, p=None):
        c = http.client.HTTPConnection("127.0.0.1", p or port, timeout=90); h = {"Host": f"localhost:{p or port}", **(plus or {})}
        if cookie: h["Cookie"] = cookie
        c.putrequest(methode, chemin, skip_host=True)
        for k, v in h.items(): c.putheader(k, v)
        corps = json.dumps(corps).encode() if isinstance(corps, dict) else corps
        if corps is not None: c.putheader("Content-Length", str(len(corps)))
        c.endheaders(corps)
        rep = c.getresponse(); brut = rep.read()
        try: x = json.loads(brut or b"{}")
        except ValueError: x = {}
        return rep.status, x

    jeton = b("interface", "lien").stdout.strip().partition("#jeton=")[2]

    # ── 1. sans [interface] actions = true : lecture seule ──
    srv = servir(False)
    st, h = None, None
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30); c.putrequest("POST", "/connexion", skip_host=True)
    corps = json.dumps({"jeton": jeton}).encode()
    for k, v in {"Host": hote, "Content-Type": "application/json", "Content-Length": str(len(corps))}.items(): c.putheader(k, v)
    c.endheaders(corps); r = c.getresponse(); r.read(); cookie_brut = r.getheader("Set-Cookie"); cookie = cookie_brut.split(";")[0]
    st, x = req("GET", "/api/actions", cookie=cookie)
    dire(st == 200 and x.get("actives") is False, f"sans « actions = true » : GET /api/actions → actives false ({x})")
    st, x = req("POST", "/api/action", {"action": "valider", "cible": "1"}, cookie=cookie, plus={"Origin": origine, "Content-Type": "application/json"})
    dire(st == 403 and "actions désactivées" in x.get("erreur", ""), f"sans « actions = true » : POST refusé, nommé ({st} {x.get('erreur')})")
    st, x = req("GET", "/api/action/apercu?action=valider&cible=1", cookie=cookie)
    dire(st == 403 and "actions désactivées" in x.get("erreur", ""), "sans « actions = true » : l'aperçu aussi est refusé")
    dire(not list(V.glob("*.decision")) and "1" not in vues_decisions, "…et rien n'est décidé")
    srv.terminate(); srv.communicate(timeout=10)

    # ── faux Herdr : une API qui REÇOIT agent.prompt (une remise réussie se prouve par ce qu'elle reçoit) ──
    recus = []; api = Path(t) / "api.sock"
    try:
        so_api = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); so_api.bind(str(api)); so_api.listen(); herdr_ok = True
    except (OSError, AttributeError): herdr_ok = False
    if herdr_ok:
        env["BERGER_HERDR_SOCKET"] = str(api)
        def api_servir():
            while True:
                try: conn, _ = so_api.accept()
                except OSError: return
                with conn:
                    try:
                        with conn.makefile("rb") as flux: req_api = json.loads(flux.readline())
                        recus.append(req_api); conn.sendall((json.dumps({"id": req_api["id"], "result": {}}) + "\n").encode())
                    except (OSError, ValueError, KeyError): pass
        threading.Thread(target=api_servir, daemon=True).start()

    # ── 2. avec actions = true ──
    dire("Secure" not in cookie_brut, "sans TLS ni nom : cookie sans Secure (le navigateur le refuserait en HTTP)")
    srv = servir(True)
    st, x = req("GET", "/api/actions", cookie=cookie)
    dire(st == 200 and x.get("actives") is True, "avec « actions = true » : actives true (même session : le cookie est dérivé du même jeton)")
    def apercu(action, cible):
        return req("GET", f"/api/action/apercu?action={action}&cible={cible}", cookie=cookie)
    def poster(action, cible, ap, plus_corps=None, entetes=None, ck=cookie):
        corps = {"action": action, "cible": cible, "empreinte": ap.get("empreinte"), "nonce": ap.get("nonce"), **(plus_corps or {})}
        h = {"Origin": origine, "Content-Type": "application/json", "X-Berger-Jeton": ap.get("jeton", "")}
        h.update(entetes or {}); h = {k: v for k, v in h.items() if v is not None}
        return req("POST", "/api/action", corps, cookie=ck, plus=h)

    st, ap = apercu("valider", "1")
    dire(st == 200 and ap.get("titre", "").startswith("Écriture n° 1") and ap.get("apercu") == "recréer l'espace de vigie" and len(ap.get("empreinte", "")) == 64
         and ap.get("nonce") and ap.get("jeton"), f"aperçu : numéro, aperçu EXACT, empreinte, jeton anti-rejeu ({ {k: ap.get(k) for k in ('titre', 'apercu')} })")
    dire(req("GET", "/api/action/apercu?action=valider&cible=1")[0] == 401, "aperçu sans session : 401")
    dire(apercu("effacer", "1")[0] == 400 and apercu("valider", "-x")[0] == 400, "aperçu : action inconnue ou cible piégée → 400")
    st, x = apercu("valider", "99")
    dire(st == 409 and "pas de demande n° 99" in x.get("erreur", ""), f"aperçu d'une demande absente : refusé, nommé ({x.get('erreur')})")

    # refus nommés, un par garde-fou (aucun ne consomme le jeton servi : l'action reste possible ensuite)
    st, x = poster("valider", "1", ap, ck=None)
    dire(st == 401, f"POST sans session : 401 ({x.get('erreur')})")
    st, x = poster("valider", "1", ap, entetes={"X-Berger-Jeton": None})
    dire(st == 403 and "jeton anti-rejeu" in x.get("erreur", ""), f"POST sans jeton anti-rejeu : refusé, nommé ({x.get('erreur')})")
    st, x = poster("valider", "1", ap, entetes={"X-Berger-Jeton": "0" * 64})
    dire(st == 403 and "jeton anti-rejeu" in x.get("erreur", ""), "POST avec un jeton inventé : refusé")
    st, x = poster("valider", "1", ap, entetes={"Origin": "http://evil.example"})
    dire(st == 403 and "origine refusée" in x.get("erreur", ""), f"POST d'une autre origine : refusé, nommé ({x.get('erreur')})")
    st, x = poster("valider", "1", ap, entetes={"Origin": None})
    dire(st == 403 and "origine refusée" in x.get("erreur", ""), "POST sans en-tête Origin : refusé")
    st, x = poster("valider", "1", ap, entetes={"Content-Type": "text/plain"})
    dire(st == 415, "POST qui n'est pas du JSON : 415 (un formulaire d'un autre site ne passe pas)")
    st, x = poster("valider", "1", {**ap, "empreinte": "f" * 64})
    dire(st == 409 and "demande modifiée" in x.get("erreur", ""), f"empreinte qui n'est pas celle de l'aperçu : refusé ({x.get('erreur')})")
    dire(not list(V.glob("*.decision")) and "1" not in vues_decisions, "…aucun de ces refus n'a rien décidé")

    # valider : le MÊME fichier de décision que `berger valider`, puis le journal « via l'interface web »
    st, ap = apercu("valider", "1")
    st, x = poster("valider", "1", ap)
    dire(st == 200 and x.get("fait") is True and vues_decisions.get("1") == "valider\n", f"valider : fait, décision « valider » écrite comme par la ligne de commande ({st} {x})")
    jv = (i / f"agents/vigie/memory/{time.strftime('%Y-%m-%d')}.md")
    dire("via l'interface web (127.0.0.1) : écriture n° 1 validée" in (jv.read_text() if jv.exists() else ""), "valider : « via l'interface web » et la source au journal de l'agent")
    st, x = poster("valider", "1", ap)
    dire(st == 403 and "déjà servi" in x.get("erreur", ""), f"le même jeton une seconde fois (rejeu) : refusé, nommé ({x.get('erreur')})")

    # confirmation périmée : la demande change entre l'aperçu et le clic
    nouvelle(5); st, ap = apercu("valider", "5")
    nouvelle(5, apercu="une AUTRE écriture sous le même numéro")
    st, x = poster("valider", "5", ap)
    dire(st == 409 and "demande modifiée" in x.get("erreur", "") and "5" not in vues_decisions, f"confirmation périmée (demande changée) : refusée, rien décidé ({x.get('erreur')})")
    dire("REFUSÉ — la demande a changé" in jv.read_text(), "…et le refus est au journal de l'agent")

    # refuser : motif obligatoire ; même décision que `berger refuser` ; motif au journal et aux échanges de l'agent
    st, ap = apercu("refuser", "5")
    st, x = poster("refuser", "5", ap, {"motif": "   "})
    dire(st == 400 and "motif" in x.get("erreur", "") and "5" not in vues_decisions, f"refuser sans motif : refusé, nommé ({x.get('erreur')})")
    st, ap = apercu("refuser", "5")
    st, x = poster("refuser", "5", ap, {"motif": "le périmètre est trop large, découpe-la"})
    nouvelle(6); r = b("refuser", "6")
    dire(st == 200 and vues_decisions.get("5") == vues_decisions.get("6") == "refuser\n",
         f"refuser : la même décision que `berger refuser` ({vues_decisions.get('5')!r} = {vues_decisions.get('6')!r})")
    dire("motif : le périmètre est trop large" in jv.read_text(), "refuser : le motif au journal de l'agent")
    ech = (i / "courtier/echanges.jsonl").read_text()
    dire("motif du refus de l'écriture n° 5 : le périmètre est trop large" in ech, "refuser : le motif dans les échanges (le courtier dit à l'agent d'aller l'y lire)")

    # répondre : une remise RÉUSSIE (le faux Herdr la reçoit), par le même chemin que `berger parler` ; la question citée dans la remise
    st, ap = apercu("repondre", "scribe")
    dire(st == 200 and "garder l'ancien écran" in ap.get("apercu", ""), f"aperçu d'une question : son texte exact ({ap.get('apercu') or ap.get('erreur')})")
    st, x = poster("repondre", "scribe", ap, {"texte": ""})
    dire(st == 400 and "réponse obligatoire" in x.get("erreur", ""), "répondre sans texte : refusé, nommé")
    ck_scribe = i / "agents/scribe/CHECKLIST.md"; question = ck_scribe.read_text()
    st, ap = apercu("repondre", "scribe"); avant = len(recus)
    ck_scribe.write_text(question.replace("faut-il garder l'ancien écran ?", "peut-on supprimer les archives ?"))
    st, x = poster("repondre", "scribe", ap, {"texte": "oui"})
    dire(st == 409 and "demande modifiée" in x.get("erreur", "") and len(recus) == avant, f"course — répondre : la question a changé après l'aperçu → refusé, rien remis ({st} {x.get('erreur')})")
    ck_scribe.write_text(question)
    st, ap = apercu("repondre", "scribe")
    st, x = poster("repondre", "scribe", ap, {"texte": "oui, garde-le une semaine"})
    if herdr_ok:
        web = recus[-1] if len(recus) > avant else {}
        texte_remis = str((web.get("params") or {}).get("text", ""))
        dire(st == 200 and web.get("method") == "agent.prompt" and (web.get("params") or {}).get("target") == "scribe-claude"
             and "oui, garde-le une semaine" in texte_remis and "garder l'ancien écran" in texte_remis,
             f"répondre : remise RÉUSSIE à l'agent (agent.prompt reçu par Herdr, question citée, réponse) ({st} {x.get('message') or x.get('erreur')})")
        n_avant = len(recus); cli = b("parler", "scribe", "--stdin", entree="oui, garde-le une semaine")
        dire(cli.returncode == 0 and len(recus) == n_avant + 1 and recus[-1].get("method") == web.get("method") and recus[-1]["params"].get("target") == web["params"].get("target"),
             "répondre : même chemin que `berger parler` (même méthode Herdr, même cible)")
        ech = (i / "courtier/echanges.jsonl").read_text()
        dire("oui, garde-le une semaine" in ech, "répondre : la réponse est tracée dans les échanges, comme `berger parler`")
    else:
        print("NON JOUÉ remise réussie de « Répondre » : socket UNIX indisponible dans ce bac (faux Herdr)")
        cli = b("parler", "scribe", "--stdin", entree="oui, garde-le une semaine")
        dire((st == 200) == (cli.returncode == 0), "répondre : même issue que `berger parler` (sans faux Herdr)")
    dire(apercu("repondre", "vigie")[0] == 409, "répondre à un agent sans question qui t'attend : refusé")

    # courses — valider et refuser : l'empreinte va jusqu'à l'écriture (berger valider|refuser --empreinte, sous le verrou des décisions)
    nouvelle(8); st, ap8 = apercu("valider", "8"); nouvelle(8, apercu="une AUTRE écriture sous le même numéro")
    for verbe in ("valider", "refuser"):
        r = b(verbe, "8", "--empreinte", ap8.get("empreinte", ""))
        dire(r.returncode != 0 and "demande modifiée" in r.stderr and "8" not in vues_decisions,
             f"course — {verbe} : la demande a changé après l'aperçu → `berger {verbe} 8 --empreinte` refuse au moment d'écrire ({r.stderr.strip()[-70:]})")
    bonne = hashlib.sha256((V / "8.json").read_bytes()).hexdigest()
    st, ap = apercu("refuser", "8")
    dire(ap.get("empreinte") == bonne, "l'empreinte de l'aperçu est le sha256 du fichier de la demande, celle que revérifie `berger refuser --empreinte`")
    r = b("refuser", "8", "--empreinte", bonne)
    for _ in range(40):
        if "8" in vues_decisions: break
        time.sleep(0.05)
    dire(r.returncode == 0 and vues_decisions.get("8") == "refuser\n", "…avec la bonne empreinte, la décision est écrite")

    # course — décision écrasable : une décision écrite (ou en cours d'exécution) n'est jamais remplacée, sous le verrou des décisions
    pause.set(); nouvelle(10); premiere = {}
    fil = threading.Thread(target=lambda: premiere.update(r=b("refuser", "10"))); fil.start()
    for _ in range(100):
        if (V / "10.decision").exists(): break
        time.sleep(0.05)
    r = b("valider", "10")
    dire(r.returncode != 0 and "déjà décidée" in r.stderr and (V / "10.decision").read_text() == "refuser\n",
         f"course — refuser puis valider avant le courtier : le second est refusé, la décision reste « refuser » ({r.stderr.strip()[-80:]})")
    nouvelle(11); (V / "11.execution").write_text("valider\n"); r = b("refuser", "11")
    dire(r.returncode != 0 and "déjà décidée" in r.stderr and not (V / "11.decision").exists(), f"décision en cours d'exécution (.execution) : une autre est refusée ({r.stderr.strip()[-80:]})")
    (V / "11.execution").unlink(); pause.clear(); fil.join(60)
    dire(premiere.get("r") is not None and premiere["r"].returncode == 0 and vues_decisions.get("10") == "refuser\n", "…la première décision est celle que le courtier exécute")

    # courses — deux confirmations CONCURRENTES (deux fils, en même temps) : une seule passe
    def ensemble(*envois):
        depart = threading.Barrier(len(envois)); out = [None] * len(envois)
        def un(k, envoi): depart.wait(); out[k] = poster(*envoi)
        fils = [threading.Thread(target=un, args=(k, e)) for k, e in enumerate(envois)]
        for f in fils: f.start()
        return fils, out
    nouvelle(12); st, ap12 = apercu("valider", "12")
    fils, out = ensemble(("valider", "12", ap12), ("valider", "12", ap12))
    for f in fils: f.join(90)
    codes = sorted(s for s, _ in out)
    dire(codes == [200, 403] and any("déjà servi" in x.get("erreur", "") for s, x in out if s == 403) and vues_decisions.get("12") == "valider\n",
         f"course — le même jeton d'aperçu dans deux confirmations simultanées : une seule passe, l'autre est un rejeu ({codes})")
    pause.set(); nouvelle(13); st, apv = apercu("valider", "13"); st, apr = apercu("refuser", "13")
    fils, out = ensemble(("valider", "13", apv), ("refuser", "13", apr, {"motif": "non, pas maintenant"}))
    for _ in range(200):
        if any(o is not None for o in out): break
        time.sleep(0.05)
    decision13 = (V / "13.decision").read_text() if (V / "13.decision").exists() else None
    pause.clear()
    for f in fils: f.join(90)
    codes = sorted(s for s, _ in out); gagnant = [a for (s, _), a in zip(out, ("valider\n", "refuser\n")) if s == 200]
    dire(codes == [200, 409] and any("déjà décidée" in x.get("erreur", "") for s, x in out if s == 409) and gagnant == [decision13] == [vues_decisions.get("13")],
         f"course — valider et refuser la même demande en même temps (deux aperçus) : une seule décision écrite, l'autre refusée ({codes} ; {decision13!r})")

    # marquer lu : le même « lu » que `berger lire`
    al = json.loads(b("vue", "alire", "--json").stdout)["donnees"]["documents"]
    doc = next((d for d in al if not d["lu"] and not d["regle"]), None)
    if doc:
        st, ap = apercu("lu", doc["id"])
        st, x = poster("lu", doc["id"], ap)
        apres = {d["id"]: d["lu"] for d in json.loads(b("vue", "alire", "--json").stdout)["donnees"]["documents"]}
        dire(st == 200 and apres.get(doc["id"]) is True, f"marquer lu : le document est lu, comme après `berger lire` ({st} {x})")
    else: dire(False, "le jeu de données a un document À lire non lu")

    # course — marquer lu : aperçu de A, B arrive (la liste bouge), A est marqué lu et B ne l'est pas ; A modifié après l'aperçu → refusé
    dos = i / "agents/scribe/a-lire"; da = dos / "2026-10-14_a.md"; da.write_text("# Document A de la course\n"); os.utime(da, (time.time() - 7200, time.time() - 7200))
    ids = lambda: {d["titre"]: (d["id"], d["lu"]) for d in json.loads(b("vue", "alire", "--json").stdout)["donnees"]["documents"]}
    ida = ids()["Document A de la course"][0]; st, apa = apercu("lu", ida)
    (dos / "2026-10-15_b.md").write_text("# Document B arrivé entre-temps\n")
    st, x = poster("lu", ida, apa); etat_lu = ids()
    dire(st == 200 and etat_lu["Document A de la course"][1] is True and etat_lu["Document B arrivé entre-temps"][1] is False,
         f"course — marquer lu : A est lu, B arrivé entre l'aperçu et le clic ne l'est pas ({st} {x})")
    dc = dos / "2026-10-13_c.md"; dc.write_text("# Document C\n"); os.utime(dc, (time.time() - 9000, time.time() - 9000))
    idc = ids()["Document C"][0]; st, apc = apercu("lu", idc)
    dc.write_text("# Document C\n\nModifié après l'aperçu.\n")
    st, x = poster("lu", idc, apc)
    dire(st == 409 and "demande modifiée" in x.get("erreur", "") and ids().get("Document C", (None, False))[1] is False,
         f"course — marquer lu : document modifié après l'aperçu → refusé, pas marqué ({st} {x.get('erreur')})")

    # un refus d'hôte sur un chemin d'action va au journal des actions
    st, x = req("POST", "/api/action", {"action": "valider", "cible": "1"}, cookie=cookie, plus={"Host": "evil.example", "Origin": origine, "Content-Type": "application/json"})
    dire(st == 403 and '"motif": "hôte refusé"' in journal_srv.read_text(), "refus d'hôte sur /api/action : au journal des actions")
    # le journal ne s'écrit pas → l'action n'est pas faite
    nouvelle(9); st, ap9 = apercu("valider", "9"); os.chmod(journal_srv, 0o400)
    try: st, x = poster("valider", "9", ap9)
    finally: os.chmod(journal_srv, 0o600)
    dire(st == 503 and "journal" in x.get("erreur", "") and "9" not in vues_decisions, f"journal impossible à écrire : l'action est refusée, rien décidé ({st} {x.get('erreur')})")
    # journal du serveur : chaque tentative, refus compris ; jamais le texte du motif ni de la réponse
    lignes = [json.loads(l) for l in journal_srv.read_text().splitlines()] if journal_srv.exists() else []
    motifs = {l.get("motif") for l in lignes}
    dire(any(l["resultat"] == "fait" for l in lignes) and {"jeton anti-rejeu absent ou faux", "origine refusée", "demande modifiée"} <= motifs
         and all(l.get("via") == "interface web" and l.get("source") and l.get("quand") for l in lignes),
         f"journal du serveur : chaque tentative, refus compris, avec l'heure et la source ({len(lignes)} lignes ; {sorted(m for m in motifs if m)})")
    brut = journal_srv.read_text() if journal_srv.exists() else ""
    dire("périmètre" not in brut and "garde-le" not in brut and jeton not in brut, "journal du serveur : ni motif, ni réponse, ni jeton")
    dire(oct(journal_srv.stat().st_mode & 0o777) == "0o600", "journal du serveur : droits 600, dans le dossier masqué aux agents")

    # débit : 30 tentatives par heure (une tentative = un POST d'une session valide)
    comptees = lambda: sum(1 for l in journal_srv.read_text().splitlines() if json.loads(l).get("compte"))
    vu429 = None
    for k in range(40):
        st, x = req("POST", "/api/action", {"action": "valider", "cible": "1"}, cookie=cookie, plus={"Origin": origine, "Content-Type": "application/json"})
        if st == 429: vu429 = x; break
    dire(vu429 is not None and "30 actions par heure" in vu429.get("erreur", "") and comptees() == 30, f"débit : la 31e tentative de l'heure est refusée, nommée ({vu429} ; {comptees()} comptées)")
    srv.terminate(); srv.communicate(timeout=10)
    with open(journal_srv, "a") as f:                                       # saturation : 600 refus non comptés APRÈS les 30 tentatives de l'heure
        for _ in range(600): f.write(json.dumps({"quand": time.strftime("%Y-%m-%dT%H:%M:%S"), "via": "interface web", "source": "127.0.0.1", "action": None,
                                                 "cible": None, "resultat": "refusé", "motif": "sans session", "compte": False}) + "\n")
    srv = servir(True)
    st, x = req("POST", "/api/action", {"action": "valider", "cible": "1"}, cookie=cookie, plus={"Origin": origine, "Content-Type": "application/json"})
    dire(st == 429, "débit : un redémarrage, même après 600 lignes de refus, ne remet pas le compteur à zéro (toute l'heure est relue)")
    srv.terminate(); srv.communicate(timeout=10)

    # source hors local/VPN : refusée même authentifiée (serveur dans ce processus, adresse du pair simulée hors réseau privé)
    spec = importlib.util.spec_from_file_location("interface_essai", i / "bin/interface.py"); ifc = importlib.util.module_from_spec(spec); spec.loader.exec_module(ifc)
    dire(all(ifc.source_locale(a) for a in ("127.0.0.1", "::1", "10.1.2.3", "192.168.1.5", "172.16.0.9", "100.64.3.4", "fd12::1", "::ffff:127.0.0.1"))
         and not any(ifc.source_locale(a) for a in ("8.8.8.8", "2a00:1450::1", "100.128.0.1", "pas-une-ip")),
         "source_locale : boucle locale, réseaux privés et VPN (100.64.0.0/10) seulement")
    os.environ.update(env); journal_srv.unlink()
    ifc.source_locale = lambda ip: False
    p2 = port_libre(); s2 = ifc.Serveur(p2, m / ".config/berger/interface.jeton", actions=True)
    threading.Thread(target=s2.serve_forever, daemon=True).start()
    st, x = req("GET", "/api/actions", cookie=cookie, p=p2)
    dire(st == 200 and x.get("actives") is False, "source hors local/VPN : actives false")
    nouvelle(7)
    st, x = req("GET", "/api/action/apercu?action=valider&cible=7", cookie=cookie, p=p2)
    dire(st == 403 and "hors local/VPN" in x.get("erreur", ""), f"source hors local/VPN : aperçu refusé, nommé ({x.get('erreur')})")
    st, x = req("POST", "/api/action", {"action": "valider", "cible": "7"}, cookie=cookie, p=p2, plus={"Origin": f"http://localhost:{p2}", "Content-Type": "application/json"})
    dire(st == 403 and "hors local/VPN" in x.get("erreur", "") and "7" not in vues_decisions, f"source hors local/VPN : POST refusé même authentifié ({x.get('erreur')})")
    s2.shutdown()
    # la ligne finale « fait » ne s'écrit pas → une erreur, jamais un 200 (l'action, elle, est faite : le message le dit)
    srv_mod = importlib.util.spec_from_file_location("interface_final", i / "bin/interface.py"); ifn = importlib.util.module_from_spec(srv_mod); srv_mod.loader.exec_module(ifn)
    os.environ.pop("BERGER_AGENT", None)                                   # le serveur d'essai agit comme le propriétaire
    p4 = port_libre(); s4 = ifn.Serveur(p4, m / ".config/berger/interface.jeton", actions=True)
    noter = s4.noter_action; s4.noter_action = lambda *a: False if a[3] == "fait" else noter(*a)
    threading.Thread(target=s4.serve_forever, daemon=True).start()
    nouvelle(14); st, ap14 = req("GET", "/api/action/apercu?action=valider&cible=14", cookie=cookie, p=p4)
    corps = {"action": "valider", "cible": "14", "empreinte": ap14.get("empreinte"), "nonce": ap14.get("nonce")}
    dire(st == 200, f"aperçu sur le serveur d'essai ({st} {ap14.get('erreur')})")
    st, x = req("POST", "/api/action", corps, cookie=cookie, p=p4, plus={"Origin": f"http://localhost:{p4}", "Content-Type": "application/json", "X-Berger-Jeton": ap14.get("jeton", "")})
    dire(st == 500 and "« fait »" in x.get("erreur", ""), f"ligne finale « fait » impossible à écrire : erreur 500, pas 200 ({st} {x.get('erreur')})")
    s4.shutdown()
    admis = [json.loads(l) for l in journal_srv.read_text().splitlines() if '"admis"' in l]
    dire(admis and all(l["compte"] for l in admis), "la ligne « admis » compte la tentative : elle reste comptée après un redémarrage, même sans ligne finale")


    # cookie Secure dès que TLS est actif (même sans nom)
    cert, cle = Path(t) / "c.pem", Path(t) / "k.pem"
    o = subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-days", "2", "-subj", "/CN=localhost",
                        "-keyout", str(cle), "-out", str(cert)], capture_output=True)
    if o.returncode == 0:
        p3 = port_libre(); s3 = ifc.Serveur(p3, m / ".config/berger/interface.jeton", tls=(str(cert), str(cle)))
        threading.Thread(target=s3.serve_forever, daemon=True).start()
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        c = http.client.HTTPSConnection("127.0.0.1", p3, timeout=30, context=ctx); corps = json.dumps({"jeton": jeton})
        c.request("POST", "/connexion", corps, {"Host": f"localhost:{p3}", "Content-Type": "application/json"}); r = c.getresponse(); r.read()
        dire("Secure" in (r.getheader("Set-Cookie") or ""), "TLS actif sans nom : cookie Secure")
        s3.shutdown()
    else: print("NON JOUÉ cookie Secure sous TLS : openssl indisponible")

    # berger action : propriétaire seul
    r = b("action", "apercu", "valider", "7", env={"BERGER_AGENT": "vigie"})
    dire(r.returncode != 0 and "propriétaire" in r.stderr, "berger action : refusé à un agent")
    arret.set()

print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
