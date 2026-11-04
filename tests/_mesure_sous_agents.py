#!/usr/bin/env python3
"""MESURE (lecture seule) pour le témoin de la condition (13) — codex-sous-agents, 01/11/2026. N'est pas une suite de tests.

Question : où un sous-agent de codex exec apparaît-il dans une source MACHINE, et sous quelle forme (identité de l'enfant,
commande exacte, sortie) ? Trois pistes, mesurées sur le VRAI codex, piloté par un FAUX MODÈLE SCRIPTÉ sur la boucle locale
(127.0.0.1, wire_api responses) : aucun vrai modèle, aucun site joint, aucun secret (la clé du fournisseur est factice, passée
par l'environnement, jamais par l'argv), CODEX_HOME et dossier de travail jetables.
  1. les requêtes au faux fournisseur : celles de l'enfant (autre fil / autre conversation que le parent ?) ;
  2. les fichiers de session (rollouts) du CODEX_HOME de l'essai, avec et sans --ephemeral ;
  3. les événements --json : un collab_tool_call « spawn_agent » ? un command_execution de l'enfant ? — en mode code
     (le modèle appelle spawn_agent depuis exec, comme le vrai modèle), et par appel DIRECT de l'outil collaboration.
Le faux modèle joue : parent → spawn_agent(tâche) puis wait_agent ; enfant → exec_command(commande témoin) puis rend la sortie.
La commande témoin est inoffensive : l'interpréteur imprime une ligne marquée d'un jeton tiré pour la mesure.

Usage : python3 tests/_mesure_sous_agents.py --agent <agent strict>     (ses arguments, son cwd et son environnement, comme le
        contrat : `berger args <agent> codex --non-interactif --contrat` ; --ephemeral seulement)
        python3 tests/_mesure_sous_agents.py [-- <arguments codex>…]
        (sans arguments : les réglages mesurés de Berger pour un strict, -c features.multi_agent=false -c features.sleep_tool=false
        -c web_search="disabled", et --sandbox workspace-write)
Sortie : un rapport JSON sur stdout (formes et extraits courts, jamais l'environnement ni les consignes de Codex)."""
import http.server, json, os, secrets, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path

CLE = "BERGER_MESURE_CLE"                            # nom de la variable de la clé factice (jamais dans l'argv)
MARQUE_P, MARQUE_E = "CONSIGNE-PARENT-MESURE", "TACHE-ENFANT-MESURE"
EN_TETES = ("session_id", "conversation_id", "x-codex-turn-metadata", "x-client-request-id", "x-codex-parent-thread-id",
            "x-codex-subagent", "originator", "openai-beta", "x-openai-subagent")


def sse(*items, rid):
    out = [("response.created", {"type": "response.created", "response": {"id": rid}})]
    for k, it in enumerate(items):
        out.append(("response.output_item.done", {"type": "response.output_item.done", "output_index": k, "item": it}))
    out.append(("response.completed", {"type": "response.completed", "response": {"id": rid, "usage": {
        "input_tokens": 1, "input_tokens_details": None, "output_tokens": 1, "output_tokens_details": None, "total_tokens": 2}}}))
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in out).encode()


def message(texte, n):
    return {"type": "message", "role": "assistant", "id": f"msg_{n}", "content": [{"type": "output_text", "text": texte}]}


def sans_installation(v):
    """Une valeur d'en-tête sans l'identifiant d'installation de Codex (jamais relevé)."""
    try: o = json.loads(v)
    except (TypeError, ValueError): return v
    return {k: x for k, x in o.items() if "installation" not in k} if isinstance(o, dict) else v


def textes(corps):
    """Tout le texte de l'input d'une requête (pour reconnaître parent / enfant et l'avancement), sans le garder."""
    return json.dumps(corps.get("input", ""), ensure_ascii=False) if isinstance(corps, dict) else ""


def sorties(corps):
    """Types des sorties d'outil déjà présentes dans l'input (l'avancement du tour)."""
    e = corps.get("input") if isinstance(corps, dict) else None
    return [x.get("type") for x in e or [] if isinstance(x, dict) and str(x.get("type", "")).endswith("_output")]


class FauxModele:
    def __init__(self, mode, cmd, tache):
        self.mode, self.cmd, self.tache, self.n, self.journal = mode, cmd, tache, 0, []
        verrou, moi = threading.Lock(), self
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                moi.journal.append({"methode": "GET", "chemin": self.path}); self.send_response(404); self.end_headers()
            def do_POST(self):
                b = self.rfile.read(int(self.headers.get("content-length") or 0))
                try: corps = json.loads(b)
                except ValueError: corps = None
                with verrou:
                    moi.n += 1; n = moi.n
                    rep, role = moi.repondre(corps, n)
                    moi.journal.append(moi.relever(self, corps, role, rep))
                    if os.environ.get("MESURE_BRUT"):              # relevé complet (fixtures) : métadonnées sans installation, corps
                        with open(os.environ["MESURE_BRUT"], "a") as fb:
                            fb.write(json.dumps({"mode": moi.mode, "meta": sans_installation(self.headers.get("x-codex-turn-metadata")),
                                                 "corps": corps, "reponse": rep}, ensure_ascii=False) + "\n")
                self.send_response(200); self.send_header("content-type", "text/event-stream"); self.end_headers()
                self.wfile.write(sse(*rep, rid=f"resp_{n}"))
            def log_message(self, *a): pass
        self.s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.s.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.s.server_address[1]}/v1"

    def repondre(self, corps, n):
        t, faits = textes(corps), sorties(corps)
        if MARQUE_E in t and MARQUE_P not in t:
            role = "enfant"
            if not faits:
                a = {"cmd": self.cmd, "login": False}
                if os.environ.get("MESURE_SHELL"): a["shell"] = os.environ["MESURE_SHELL"]   # shell imposé par chemin exact
                if self.mode in ("code", "mixte"):                 # mixte : parent par appel direct, enfant en mode code
                    js = f"const r = await tools.exec_command({json.dumps(a)});\ntext(JSON.stringify(r));"
                    return [{"type": "custom_tool_call", "id": f"ctc_{n}", "call_id": f"call_{n}", "name": "exec", "input": js}], role
                return [{"type": "function_call", "id": f"fc_{n}", "call_id": f"call_{n}", "name": "exec_command",
                         "arguments": json.dumps(a)}], role
            return [message(f"ENFANT-FINI {t[-400:]}", n)], role
        if MARQUE_P in t:
            role = "parent"
            args = {"task_name": "mesure_enfant", "message": self.tache, "fork_turns": "none"}
            if self.mode == "code":
                if not faits:
                    # en mode code, le nom JavaScript de spawn_agent n'est pas connu d'avance : on le cherche dans ALL_TOOLS / tools
                    js = ("const noms = (typeof ALL_TOOLS === 'undefined' ? [] : ALL_TOOLS).map(t => t.name);\n"
                          "text('ALL_TOOLS ' + JSON.stringify(noms.filter(x => /agent|collab|wait|spawn/i.test(x))));\n"
                          "let cles = []; try { cles = Object.keys(tools); } catch (e) { text('keys ' + e); }\n"
                          "text('CLES ' + JSON.stringify(cles.filter(x => /agent|collab|wait|spawn/i.test(x))));\n"
                          "const f = [...cles, ...noms].find(x => /spawn_agent/.test(x));\n"
                          "if (f) { const s = await tools[f](" + json.dumps(args) + "); text('SPAWN ' + JSON.stringify(s));\n"
                          "  const g = [...cles, ...noms].find(x => /wait_agent/.test(x));\n"
                          "  if (g) { const w = await tools[g]({timeout_ms: 60000}); text('WAIT ' + JSON.stringify(w)); } }")
                    return [{"type": "custom_tool_call", "id": f"ctc_{n}", "call_id": f"call_{n}", "name": "exec", "input": js}], role
                return [message("PARENT-FINI", n)], role
            if len(faits) == 0:
                return [{"type": "function_call", "id": f"fc_{n}", "call_id": f"call_{n}", "name": "spawn_agent",
                         "namespace": "collaboration", "arguments": json.dumps(args)}], role
            if len(faits) == 1:
                return [{"type": "function_call", "id": f"fc_{n}", "call_id": f"call_{n}", "name": "wait_agent",
                         "namespace": "collaboration", "arguments": json.dumps({"timeout_ms": 60000})}], role
            return [message("PARENT-FINI", n)], role
        return [message("OK", n)], "annexe"

    def relever(self, h, corps, role, rep):
        """Forme d'une requête : en-têtes d'identité (noms et valeurs non secrètes), champs d'identité du corps, types de
        l'input, sorties d'outil (extraits), et ce que le faux modèle a répondu."""
        e = corps.get("input") if isinstance(corps, dict) else None
        sorties_outil = [{"type": x.get("type"), "call_id": x.get("call_id"), "extrait": str(x.get("output"))[:600]}
                         for x in e or [] if isinstance(x, dict) and str(x.get("type", "")).endswith("_output")]
        return {"n": len(self.journal) + 1, "role_suppose": role, "chemin": h.path,
                "en_tetes_noms": sorted(k.lower() for k in h.headers.keys()),
                "en_tetes": {k: sans_installation(h.headers.get(k)) for k in EN_TETES if h.headers.get(k) is not None},
                "corps_cles": sorted(corps) if isinstance(corps, dict) else None,
                "prompt_cache_key": corps.get("prompt_cache_key") if isinstance(corps, dict) else None,
                "client_metadata": sorted(corps.get("client_metadata") or {}) if isinstance(corps, dict) else None,
                "input_types": [x.get("type") for x in e or [] if isinstance(x, dict)] if isinstance(e, list) else type(e).__name__,
                "sorties_outil": sorties_outil,
                "jeton_dans_input": [x.get("type") for x in e or [] if isinstance(x, dict) and SORTIE in json.dumps(x)], "reponse": [{k: r.get(k) for k in ("type", "name", "namespace")} for r in rep]}

    def fermer(self): self.s.shutdown(); self.s.server_close()


def rollouts(home):
    """Fichiers de session du CODEX_HOME : chemin relatif, nombre de lignes, types de lignes, ids de session, et les lignes
    qui portent le jeton (types seulement + extrait court)."""
    out = []
    for f in sorted(Path(home).rglob("*.jsonl")):
        lignes = f.read_text(errors="replace").splitlines()
        types, ids, jeton = [], set(), []
        for l in lignes:
            try: o = json.loads(l)
            except ValueError: types.append("illisible"); continue
            p = o.get("payload") if isinstance(o, dict) else None
            types.append(f"{o.get('type')}:{p.get('type') if isinstance(p, dict) else ''}")
            if isinstance(p, dict) and o.get("type") == "session_meta":
                ids.add(json.dumps({k: p.get(k) for k in ("id", "forked_from_id", "source", "parent_thread_id", "agent_nickname",
                                                          "agent_role", "thread_source") if k in p}, ensure_ascii=False))
            if SORTIE in l: jeton.append({"type": types[-1], "extrait": l[:700]})
        out.append({"fichier": str(f.relative_to(home)), "mode": oct(f.stat().st_mode & 0o777), "lignes": len(lignes),
                    "types": sorted(set(types)), "session_meta": sorted(ids), "lignes_avec_jeton": jeton})
    return out


def evenements(flux):
    """Événements --json : chaque item (type, outil, fil, ids des enfants, commande, statut, extrait de sortie)."""
    out = []
    for l in flux.splitlines():
        try: o = json.loads(l)
        except ValueError: out.append({"illisible": l[:200]}); continue
        it = o.get("item") if isinstance(o, dict) else None
        r = {"type": o.get("type"), "thread_id": o.get("thread_id")}
        if isinstance(it, dict):
            r.update({k: it.get(k) for k in ("type", "tool", "status", "sender_thread_id", "receiver_thread_ids", "command",
                                             "exit_code", "thread_id") if k in it})
            r["item_type"] = r.pop("type", None); r["type"] = o.get("type")
            for k in ("aggregated_output", "agents_states", "text", "prompt"):
                if k in it: r[k] = json.dumps(it[k], ensure_ascii=False)[:500]
        out.append(r)
    return out


JETON = "jeton-" + secrets.token_hex(8)
SORTIE = JETON[::-1]                                 # ce que la commande imprime : jamais dans la commande elle-même


def essai(mode, ephemere, args, lanc=None, codex="codex"):
    """Un essai. lanc (--agent) : cwd et environnement de l'agent strict, donnés par `berger args … --contrat` — son CODEX_HOME
    est celui de Berger : on n'y lit rien et on n'y écrit pas de session (--ephemeral seulement)."""
    w = Path(tempfile.mkdtemp(prefix="mesure-sa-")); home, travail = w / "codex-home", w / "travail"
    home.mkdir(); travail.mkdir()
    cmd = (f"{sys.executable} -I -c \"import os; print('SOUS-AGENT-MESURE', '{JETON}'[::-1], "
           f"'cle-visible' if '{CLE}' in os.environ else 'cle-absente')\"")
    tache = f"{MARQUE_E} : lance exactement la commande {cmd} puis rends sa sortie."
    f = FauxModele(mode, cmd, tache); p = "berger-mesure"
    reglages = [f'model_provider="{p}"', f'model_providers.{p}.name="{p}"', f'model_providers.{p}.base_url="{f.url}"',
                f'model_providers.{p}.env_key="{CLE}"', f'model_providers.{p}.wire_api="responses"',
                f"model_providers.{p}.request_max_retries=0", f"model_providers.{p}.stream_max_retries=0"]
    if lanc:
        env, travail = {**os.environ, **lanc["env"]}, Path(lanc["cwd"])
    else:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CODEX_", "OPENAI_"))}
        env["CODEX_HOME"] = str(home)
    env.update({CLE: "cle-factice-de-la-mesure", "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
    argv = [codex, "exec", *(["--ephemeral"] if ephemere else []), "--skip-git-repo-check", "--json", *args,
            *[x for c in reglages for x in ("-c", c)], f"{MARQUE_P} : lance un sous-agent."]
    debut = time.time()
    try:
        r = subprocess.run(argv, cwd=travail, env=env, capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
        flux, err, code = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        flux = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err, code = "délai dépassé", None
    time.sleep(1)
    try:
        return {"mode": mode, "ephemere": ephemere, "code_sortie": code, "duree_s": round(time.time() - debut, 1),
                "stderr_fin": "\n".join(err.splitlines()[-8:])[-1200:], "requetes": f.journal, "evenements": evenements(flux),
                "sortie_dans_evenements": SORTIE in flux, "rollouts": rollouts(home) if not lanc else "non lus (--agent)",
                "fichiers_codex_home": sorted(str(x.relative_to(home)) for x in home.rglob("*") if x.is_file())[:60]}
    finally:
        f.fermer(); shutil.rmtree(w, ignore_errors=True)


def main():
    lanc, essais = None, (("code", True), ("direct", True), ("direct", False), ("mixte", True))
    if len(sys.argv) == 3 and sys.argv[1] == "--agent":
        r = subprocess.run(["berger", "args", sys.argv[2], "codex", "--non-interactif", "--contrat"], capture_output=True, text=True)
        if r.returncode: sys.exit(f"berger args : {(r.stderr or r.stdout).strip()[:300]}")
        lanc = json.loads(r.stdout); args = lanc["args"]
        essais = (("code", True), ("direct", True), ("mixte", True))          # jamais de session écrite chez Berger
    else:
        args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [
            "--sandbox", "workspace-write", "-c", "features.multi_agent=false", "-c", "features.sleep_tool=false",
            "-c", 'web_search="disabled"']
    if not shutil.which("codex"): sys.exit("codex introuvable")
    v = subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout.strip()
    rapport = {"codex": v, "jeton": JETON, "args": args, "essais": []}
    for mode, eph in essais:
        rapport["essais"].append(essai(mode, eph, args, lanc))
    json.dump(rapport, sys.stdout, ensure_ascii=False, indent=1); print()


if __name__ == "__main__":
    main()
