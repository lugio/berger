#!/usr/bin/env python3
"""Extensions, lot 3 : un serveur MCP installé par `berger extension` (spec docs/plans/2026-11-07-extensions-spec.md § 4 « mcp », go n° 181 ;
décisions docs/plans/2026-11-07-extensions-decisions.md, lot 3). Installation JETABLE, coffre fictif (valeur construite à l'exécution).
Vérifie :
 1. un refus par cas de la spec, rien d'écrit : commande relative, introuvable, dans un dossier d'agent ou dans extensions/, lanceur qui
    télécharge, réseau demandé sans --reseau (et --reseau sans demande), web + réseau, développeur d'équipe, nom pris par un [mcp] de
    config.toml, clé inconnue de [mcp] ; refus de serveur_mcp APRÈS écriture (variable de secret, mur ouvert, écriture hors du dossier de
    l'agent) → retour automatique à l'état d'avant ;
 2. l'ajout : `mcp =` posé dans agent.conf, `.mcp-berger.json` ne porte que le relais (`berger-mcp <agent> <serveur>`), `berger
    mcp-enveloppe` rend l'enveloppe (commande déclarée, écriture dans le dossier de l'agent, variables nommées PRÉSENTES et VIDES, réseau
    coupé) ; `liste` ; le retrait rend l'état d'avant à l'octet près (agent.conf, extensions.toml absent) et le relais disparaît ;
 3. le réseau : installé seulement avec --reseau, signalé par une ligne « ⚠ réseau ouvert » de regenerer (extension ET [mcp] de
    config.toml), par `berger etat --json` › mcp_reseau, jamais par une notification ;
 4. la page Extensions : dernier usage d'un MCP lu dans le journal du courtier (courtier/appels.log, appel accepté « mcp:<nom> ») ;
 5. renvoi n° 187 : chaque argument qui désigne un chemin (absolu, --option=, lien, ligne #!) hors des dossiers d'agent, d'extensions/ et
    des dossiers inscriptibles par un agent ; chemin relatif et interpréteur en commande[0] refusés ; lanceur repéré par sa sous-commande
    n'importe où ; `revenir` reprend l'accord réseau donné à CETTE version (reseau_versions), jamais un accord nouveau.
Usage : python3 tests/extensions-mcp.py (0 = tout passe). Les suites mcp et mcp-trous (enveloppe bwrap réelle) restent la preuve du relais."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import json, os, random, re, string, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def lettres(n): return "".join(random.choice(string.ascii_letters) for _ in range(n))


SECRET = "Fac" + lettres(14) + "Tice"


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre").mkdir(); coffre = m / "coffre/coffre-essai.json"; coffre.write_text(json.dumps({"service": {"jeton": SECRET}}))
    py = os.path.realpath(sys.executable)
    exe = m / "outils-mcp/serveur-essai"; exe.parent.mkdir(); exe.write_text(f"#!{py}\nimport sys\nsys.exit(0)\n"); exe.chmod(0o755)
    base_conf = (f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{coffre}"\n\n[equipes.proj]\ndepot = "{m}/depot"\n'
                 f'\n[mcp.pris]\ncommande = ["{exe}"]\n')
    (i / "config.toml").write_text(base_conf)
    livrables = m / "livrables"; livrables.mkdir()                                  # un dossier « ecrire_aussi » de beta : inscriptible par un agent
    agents = {"alpha": "", "beta": f"mcp = pris\necrire_aussi = {livrables}", "ouvert": "mur = ouvert", "dev": "projet = proj\nsujet = essai"}
    for a, plus in agents.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils =\n{plus}\n".replace("\n\n", "\n"))
    (i / "agents/alpha/agent.conf").write_bytes((i / "agents/alpha/agent.conf").read_bytes().rstrip(b"\n"))   # sans saut de ligne final
    env = {k: v for k, v in os.environ.items() if k != "BERGER_AGENT"}
    env.update(HOME=str(m), BERGER_DIR=str(i), BERGER_HERDR="/bin/false", BERGER_NOTIFY_SEND="/bin/true",
               BERGER_TMP_AGENTS=str(Path(tempfile.mkdtemp(prefix="bt", dir="/tmp")) if os.access("/tmp", os.W_OK) else m / "bt"))
    berger = lambda *a: subprocess.run([py, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=300)
    r = berger("regenerer")
    dire(r.returncode == 0, "installation jetable : regenerer réussit" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr)[-300:]}"))
    src = m / "sources"; src.mkdir()

    def paquet(nom, commande=None, droits="", mcp_plus="", version="1.0.0"):
        d = src / f"{nom}-{version}-{lettres(4)}"; d.mkdir()
        cmd = json.dumps(commande if commande is not None else [str(exe), "--stdio"])
        (d / "extension.toml").write_text(f'nom = "{nom}"\ngenre = "mcp"\nversion = "{version}"\ndescription = "Serveur d\'essai {nom}."\n'
                                          f'{droits}\n[mcp]\ncommande = {cmd}\n{mcp_plus}')
        (d / "LISEZMOI.md").write_text(f"Serveur {nom}.\n")
        return d

    def photo():
        out = {}
        for p in sorted((i / "extensions").rglob("*")) if (i / "extensions").exists() else []:
            if p.name == ".verrou": continue
            out[str(p.relative_to(i))] = ("lien", os.readlink(p)) if p.is_symlink() else (p.read_bytes() if p.is_file() else "dossier")
        for f in [i / "extensions.toml", *sorted((i / "agents").glob("*/agent.conf")), *sorted((i / "agents").glob("*/.mcp-berger.json"))]:
            out[str(f.relative_to(i))] = f.read_bytes() if f.exists() else None
        return out

    def ext(*args): r = berger("extension", *args); return r.returncode, r.stdout + r.stderr

    def refus(texte, args, attendu):
        avant = photo(); c, o = ext(*args); apres = photo()
        ok = c != 0 and re.search(attendu, o) is not None and avant == apres and SECRET not in o
        dire(ok, f"refus : {texte}" + ("" if ok else f" — code {c}, état {'inchangé' if avant == apres else 'MODIFIÉ'} : {' '.join(o.split())[-240:]}"))

    # ── 1. refus, rien d'écrit ──
    refus("commande relative", ("ajouter", "mcp", str(paquet("rel", ["serveur-essai", "--stdio"])), "--agents", "alpha"), r"chemin absolu")
    refus("commande introuvable", ("ajouter", "mcp", str(paquet("absent", [str(m / "absent/serveur")])), "--agents", "alpha"), r"introuvable")
    dans_agent = i / "agents/alpha/bin/serveur"; dans_agent.parent.mkdir(parents=True); dans_agent.write_text(exe.read_text()); dans_agent.chmod(0o755)
    refus("commande dans un dossier d'agent", ("ajouter", "mcp", str(paquet("agent", [str(dans_agent)])), "--agents", "alpha"), r"dossier d'agent")
    (i / "extensions/skill/x/1.0.0").mkdir(parents=True); dans_ext = i / "extensions/skill/x/1.0.0/serveur"; dans_ext.write_text(exe.read_text()); dans_ext.chmod(0o755)
    refus("commande dans extensions/", ("ajouter", "mcp", str(paquet("dansext", [str(dans_ext)])), "--agents", "alpha"), r"extensions/")
    import shutil; shutil.rmtree(i / "extensions"); shutil.rmtree(dans_agent.parent)
    fnpx = m / "outils-mcp/npx"; fnpx.write_text(exe.read_text()); fnpx.chmod(0o755)
    refus("lanceur qui télécharge (npx)", ("ajouter", "mcp", str(paquet("npx", [str(fnpx), "-y", "serveur"])), "--agents", "alpha"), r"télécharge")
    fuv = m / "outils-mcp/uv"; fuv.write_text(exe.read_text()); fuv.chmod(0o755)
    refus("lanceur qui télécharge (uv tool)", ("ajouter", "mcp", str(paquet("uvtool", [str(fuv), "tool", "run", "x"])), "--agents", "alpha"), r"télécharge")
    refus("réseau demandé sans --reseau", ("ajouter", "mcp", str(paquet("net", droits="[droits]\nreseau = true\n")), "--agents", "alpha"), r"--reseau")
    refus("--reseau sans demande du manifeste", ("ajouter", "mcp", str(paquet("sansnet")), "--agents", "alpha", "--reseau"), r"--reseau")
    refus("web + réseau", ("ajouter", "mcp", str(paquet("webnet", droits="[droits]\nreseau = true\n", mcp_plus="web = true\n")), "--agents", "alpha", "--reseau"), r"web")
    refus("développeur d'équipe", ("ajouter", "mcp", str(paquet("pourdev")), "--agents", "dev"), r"développeur")
    refus("nom pris par un [mcp] de config.toml", ("ajouter", "mcp", str(paquet("pris")), "--agents", "alpha"), r"nom pris")
    # ── 1 bis (renvoi n° 187, point 1) : TOUS les arguments — chemins, interpréteurs, lanceurs ──
    dans_agent.parent.mkdir(parents=True); dans_agent.write_text(exe.read_text()); dans_agent.chmod(0o755)
    script_agent = i / "agents/alpha/bin/serveur.py"; script_agent.write_text("import sys\n")
    refus("interpréteur + script dans un dossier d'agent", ("ajouter", "mcp", str(paquet("pyagent", [py, str(script_agent)])), "--agents", "alpha"), r"interpréteur|dossier d'agent")
    script_hors = m / "outils-mcp/serveur.py"; script_hors.write_text("import sys\n")
    refus("interpréteur + script hors de tout dossier figé", ("ajouter", "mcp", str(paquet("pyhors", [py, str(script_hors)])), "--agents", "alpha"), r"interpréteur")
    if Path("/usr/bin/env").exists():
        refus("interpréteur : /usr/bin/env", ("ajouter", "mcp", str(paquet("parenv", ["/usr/bin/env", "serveur-essai"])), "--agents", "alpha"), r"interpréteur")
    enrobe = m / "outils-mcp/enrobe"; enrobe.write_text(f"#!{py} {script_agent}\n"); enrobe.chmod(0o755)
    refus("script dont la ligne #! lance un fichier d'un dossier d'agent", ("ajouter", "mcp", str(paquet("shebang", [str(enrobe)])), "--agents", "alpha"), r"dossier d'agent")
    refus("argument : chemin dans un dossier d'agent", ("ajouter", "mcp", str(paquet("argagent", [str(exe), "--config", str(i / "agents/alpha/c.json")])), "--agents", "alpha"), r"dossier d'agent")
    refus("argument --option=<chemin dans un dossier d'agent>", ("ajouter", "mcp", str(paquet("argegal", [str(exe), f"--config={i / 'agents/alpha/c.json'}"])), "--agents", "alpha"), r"dossier d'agent")
    raccourci = m / "raccourci"; raccourci.symlink_to(i / "agents/alpha")
    refus("argument : lien vers un dossier d'agent (resolve)", ("ajouter", "mcp", str(paquet("arglien", [str(exe), str(raccourci / "c.json")])), "--agents", "alpha"), r"dossier d'agent")
    refus("argument : chemin dans extensions/", ("ajouter", "mcp", str(paquet("argext", [str(exe), str(i / "extensions/mcp/x/1.0.0/c.json")])), "--agents", "alpha"), r"extensions/")
    refus("argument : dossier inscriptible par un agent (ecrire_aussi)", ("ajouter", "mcp", str(paquet("argecrit", [str(exe), str(livrables / "c.json")])), "--agents", "alpha"), r"inscriptible")
    refus("argument : bibliothèque (dossiers de travail des agents)", ("ajouter", "mcp", str(paquet("argbib", [str(exe), str(i / "bibliotheque/agents/alpha/travail/c.json")])), "--agents", "alpha"), r"inscriptible")
    refus("argument : dossier temporaire des agents", ("ajouter", "mcp", str(paquet("argtmp", [str(exe), env["BERGER_TMP_AGENTS"] + "/c.json"])), "--agents", "alpha"), r"inscriptible")
    refus("argument : chemin relatif (lu depuis le dossier courant du serveur, celui de l'agent)", ("ajouter", "mcp", str(paquet("argrel", [str(exe), "conf/c.json"])), "--agents", "alpha"), r"relatif")
    refus("argument : chemin sous ~", ("ajouter", "mcp", str(paquet("argtilde", [str(exe), "~/c.json"])), "--agents", "alpha"), r"relatif|~")
    shutil.rmtree(dans_agent.parent); raccourci.unlink()
    for lanceur, args in (("npm", ["--yes", "exec", "serveur"]), ("pnpm", ["--silent", "dlx", "serveur"]), ("yarn", ["--silent", "dlx", "serveur"]),
                          ("bun", ["--bun", "x", "serveur"]), ("uv", ["--quiet", "tool", "run", "serveur"]), ("pipx", ["--verbose", "run", "serveur"])):
        f = m / "outils-mcp" / lanceur; f.write_text(exe.read_text()); f.chmod(0o755)
        refus(f"lanceur qui télécharge, sous-commande plus loin ({lanceur} {' '.join(args[:2])})", ("ajouter", "mcp", str(paquet(f"loin{lanceur}", [str(f), *args])), "--agents", "alpha"), r"télécharge")
    refus("clé inconnue dans [mcp]", ("ajouter", "mcp", str(paquet("cleinc", mcp_plus="arguments_secrets = 1\n")), "--agents", "alpha"), r"\[mcp\]")
    refus("variable d'environnement de secret (refusée par serveur_mcp, retour arrière)", ("ajouter", "mcp", str(paquet("envsecret", droits='[droits]\nenv = ["API_TOKEN"]\n')), "--agents", "alpha"), r"secret")
    refus("agent en mur ouvert (refusé par serveur_mcp, retour arrière)", ("ajouter", "mcp", str(paquet("pourouvert")), "--agents", "ouvert"), r"mur ouvert")
    refus("écriture hors du dossier de l'agent", ("ajouter", "mcp", str(paquet("hors", droits='[droits]\necriture = ["../beta"]\n')), "--agents", "alpha"), r"ecriture")

    # ── 2. l'ajout, l'enveloppe, la liste, le retrait à l'octet près ──
    dire(not (i / "extensions.toml").exists(), "départ : extensions.toml absent")
    avant = photo(); conf_alpha = (i / "agents/alpha/agent.conf").read_bytes()
    c, o = ext("ajouter", "mcp", str(paquet("sonde", droits='[droits]\necriture = ["echantillons"]\nenv = ["SONDE_MODE", "SONDE_LANGUE"]\n')), "--agents", "alpha")
    dire(c == 0, "ajouter mcp sonde pour alpha" + ("" if c == 0 else f" — {o[-300:]}"))
    dire(re.search(r"(?m)^mcp = sonde$", (i / "agents/alpha/agent.conf").read_text()) is not None, "agent.conf d'alpha : mcp = sonde")
    mj = i / "agents/alpha/.mcp-berger.json"; j = json.loads(mj.read_text()) if mj.is_file() else {}
    srv = (j.get("mcpServers") or {}).get("sonde", {})
    dire(srv.get("args") == ["alpha", "sonde"] and str(exe) not in mj.read_text(), f".mcp-berger.json : le relais seulement, jamais la vraie commande ({srv})")
    r = berger("mcp-enveloppe", "alpha", "sonde")
    try: e = json.loads(r.stdout)
    except ValueError: e = {}
    dire(e.get("commande", [None])[0] == str(exe) and e.get("ecriture") == [str((i / "agents/alpha/echantillons").resolve())] and e.get("reseau") is False,
         f"berger mcp-enveloppe : commande déclarée, écriture dans le dossier de l'agent, réseau coupé ({(r.stdout or r.stderr)[-200:]})")
    dire(e.get("env", {}).get("SONDE_MODE") == "" and e.get("env", {}).get("SONDE_LANGUE") == "", f"variables nommées par le manifeste : présentes et VIDES ({e.get('env')})")
    c, o = ext("liste", "--json"); l = json.loads(o) if c == 0 else []
    dire(any(x["genre"] == "mcp" and x["nom"] == "sonde" and x["agents"] == ["alpha"] for x in l), "liste : le serveur mcp sonde, donné à alpha")
    c, o = ext("retirer", "mcp", "sonde")
    dire(c == 0 and (i / "agents/alpha/agent.conf").read_bytes() == conf_alpha, "retirer : agent.conf d'alpha à l'octet près (sans saut de ligne final)" + ("" if c == 0 else f" — {o[-200:]}"))
    dire(not (i / "extensions.toml").exists() and not mj.exists(), "retirer : extensions.toml absent comme au départ ; plus de relais chez alpha")

    # ── 3. le réseau : --reseau, ligne « ⚠ réseau ouvert », etat --json › mcp_reseau, aucune notification ──
    notif = i / "courtier/notifications.log"; n0 = notif.read_bytes() if notif.exists() else b""
    c, o = ext("ajouter", "mcp", str(paquet("reseau", droits="[droits]\nreseau = true\n")), "--agents", "alpha", "--reseau")
    dire(c == 0, "réseau demandé ET --reseau : installé" + ("" if c == 0 else f" — {o[-300:]}"))
    (i / "config.toml").write_text(base_conf + "reseau = true\n")                     # [mcp.pris] de config.toml : réseau, donné à beta
    r = berger("regenerer"); out = r.stdout + r.stderr
    dire("⚠ réseau ouvert : serveur MCP reseau (extension) pour alpha" in out, f"regenerer : ligne « ⚠ réseau ouvert » pour l'extension ({out[-300:]})")
    dire("⚠ réseau ouvert : serveur MCP pris (config.toml) pour beta" in out, "regenerer : la même ligne pour un [mcp] de config.toml")
    r = berger("etat", "--json")
    try: mr = json.loads(r.stdout)["donnees"]["mcp_reseau"]
    except (ValueError, KeyError): mr = None
    dire(mr == [{"serveur": "pris", "origine": "config.toml", "agents": ["beta"]}, {"serveur": "reseau", "origine": "extension", "agents": ["alpha"]}],
         f"berger etat --json › mcp_reseau : noms, origine, agents ({mr})")
    dire((notif.read_bytes() if notif.exists() else b"") == n0, "aucune notification pour le réseau ouvert (ni à l'ajout, ni à regenerer)")
    r = berger("mcp-enveloppe", "alpha", "reseau")
    try: e = json.loads(r.stdout)
    except ValueError: e = {}
    dire(e.get("reseau") is True, "l'enveloppe du serveur réseau : réseau ouvert (accordé par --reseau)")

    # ── 4. la page : dernier usage lu dans le journal du courtier ──
    (i / "courtier").mkdir(exist_ok=True)
    with open(i / "courtier/appels.log", "a") as f: f.write("2026-11-07 09:15:00\talpha\tmcp:reseau\ttools/call\t\taccepté\t\n")
    r = berger("vue", "extensions", "--json")
    try: x = next(y for y in json.loads(r.stdout)["donnees"]["extensions"] if y["nom"] == "reseau")
    except (ValueError, KeyError, StopIteration): x = {}
    dire(x.get("dernier_usage") == "2026-11-07 09:15" and x.get("reseau") is True, f"page Extensions : dernier usage d'un MCP lu au journal du courtier, réseau en évidence ({x})")
    c, o = ext("retirer", "mcp", "reseau")
    dire(c == 0, "retirer le serveur réseau")

    # ── 5 (renvoi n° 187, point 2) : revenir reprend l'accord réseau donné à CETTE version, jamais un accord nouveau ──
    c, o = ext("ajouter", "mcp", str(paquet("retour", droits="[droits]\nreseau = true\n")), "--agents", "alpha", "--reseau")
    dire(c == 0, "retour : v1 ajoutée avec --reseau" + ("" if c == 0 else f" — {o[-300:]}"))
    c, o = ext("ajouter", "mcp", str(paquet("retour", version="2.0.0")), "--agents", "alpha")
    dire(c == 0, "retour : v2 ajoutée, sans réseau" + ("" if c == 0 else f" — {o[-300:]}"))
    c, o = ext("revenir", "mcp", "retour")
    r = berger("mcp-enveloppe", "alpha", "retour")
    try: e = json.loads(r.stdout)
    except ValueError: e = {}
    dire(c == 0 and e.get("reseau") is True, f"revenir → v1 avec le réseau déjà accordé à v1 ({' '.join(o.split())[-200:]} ; réseau {e.get('reseau')})")
    c, o = ext("retirer", "mcp", "retour")
    c, o = ext("ajouter", "mcp", str(paquet("jamais", droits="[droits]\nreseau = true\n")), "--agents", "alpha", "--reseau")
    c2, o2 = ext("ajouter", "mcp", str(paquet("jamais", droits="[droits]\nreseau = true\n", version="2.0.0")), "--agents", "alpha", "--reseau")
    t = (i / "extensions.toml").read_text()                                     # l'accord de v1 effacé : comme une version jamais accordée
    t2 = re.sub(r'(?m)^reseau_versions = \["1\.0\.0", "2\.0\.0"\]$', 'reseau_versions = ["2.0.0"]', t)
    dire(c == 0 and c2 == 0 and t2 != t, "jamais : v1 et v2 ajoutées avec --reseau, accord enregistré par version (reseau_versions)" + ("" if c == 0 and c2 == 0 else f" — {(o + o2)[-300:]}"))
    (i / "extensions.toml").write_text(t2)
    refus("revenir vers une version dont le réseau n'a jamais été accordé", ("revenir", "mcp", "jamais"), r"réseau|--reseau")
    ext("retirer", "mcp", "jamais")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
