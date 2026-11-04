#!/usr/bin/env python3
"""Tests du lot 1 de web-integre (30/10/2026, docs/plans/2026-10-29-web-integre-spec.md) — sans modèle ni réseau, installation
JETABLE : les outils web intégrés du moteur (WebFetch et WebSearch de Claude, recherche web de Codex) passent hors du bac à
sable (qui ne coupe le réseau que pour Bash) et hors du courtier : refusés par défaut à tout agent strict.
GÉNÉRATION — strict Claude : WebFetch et WebSearch dans permissions.deny (.claude/settings.json, et .reglages-claude.json d'un
strict dans un dossier existant) ; mur ouvert inchangé. Strict Codex : -c web_search="disabled" dans ses arguments (lancement
interactif et non interactif, berger args) ; mur ouvert inchangé.
CONTRAT (12), hors moteur : WebFetch/WebSearch vus dans l'événement init = rouge ; Codex : outils web lus dans SA requête à un
faux fournisseur local (un faux `codex` ici), témoin sans le réglage de Berger obligatoire, aucune requête = pas de source machine.
LOT 1 BIS : (12) jamais vert par défaut — init sans liste d'outils, requête Codex {} ou sans liste d'outils exploitable = non
mesurable (rouge, même après un témoin positif) ; noms web sans casse ni séparateurs. ADMISSION : un verdict ADMIS sans
« ✓ (12) » (et « ✓ témoin (12) » sous Codex) n'admet plus : « à rejouer », contrat rejoué au prochain lancement (factice ici),
admis s'il porte (12), non admis sinon ; deux moteurs anciens : aucun blocage sans tentative. Une ligne ✗ : non admis.
La preuve dans les vrais moteurs est faite par tests/contrat-moteur.sh (joué par le propriétaire).
Usage : python3 tests/web-integre.py [--sans-reseau] (0 = tout passe).
--sans-reseau : rejoue les mêmes faux exécutables en mémoire ; seul le transport HTTP local n'est pas prouvé."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import contextlib, importlib.util, io, json, os, runpy, subprocess, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
WEB = ("WebFetch", "WebSearch")
COUPE = ["-c", 'web_search="disabled"']
SOUS_AGENTS = ["-c", "features.multi_agent=false", "-c", "features.sleep_tool=false"]   # 31/10, demande du propriétaire : sous-agents et clock coupés
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def contient(args, sous):
    return any(args[k:k + len(sous)] == sous for k in range(len(args) - len(sous) + 1))


SANS_RESEAU = "--sans-reseau" in sys.argv


@contextlib.contextmanager
def fournisseur_sans_reseau(dossier):
    """Exécute les scripts factices ci-dessous ; intercepte leur requête avant toute ouverture de socket."""
    import urllib.request
    class Fournisseur:
        url = "http://fournisseur.invalid/v1"
        def __init__(self): self.corps = []
        def fermer(self): pass
    f = Fournisseur()
    def recevoir(req, **kw):
        try: f.corps.append(json.loads(req.data))
        except ValueError: f.corps.append(None)
        raise OSError("réponse factice 500")
    def lancer(args, **kw):
        assert Path(args[0]).parent == dossier, "seuls les exécutables factices du test sont permis"
        f.corps = []
        with patch.object(sys, "argv", args), patch.object(urllib.request, "urlopen", recevoir):
            try: runpy.run_path(args[0], run_name="__main__")
            except SystemExit: pass
    with patch.object(C, "FauxFournisseur", return_value=f), patch.object(C.subprocess, "run", side_effect=lancer):
        yield


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"; ext = m / "projet-existant"; ext.mkdir()
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    for a, mur, moteur, plus in (("compta", "strict", "claude", "panneaux = claude"), ("essai-codex", "strict", "codex", "panneaux = codex"),
                                 ("dehors", "strict", "claude", f"panneaux = claude\ndossier = {ext}"),
                                 ("ouvert", "ouvert", "claude", "panneaux = claude, codex")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\n{plus}\nmur = {mur}\nheures = aucune\noutils =\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false", "BERGER_TMP_AGENTS": str(m / "bt")}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0, "regenerer réussit" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-200:]}"))

    # ── GÉNÉRATION : Claude ──
    for a, f in (("compta", i / "agents/compta/.claude/settings.json"), ("essai-codex", i / "agents/essai-codex/.claude/settings.json")):
        deny = json.loads(f.read_text())["permissions"]["deny"]
        dire(all(x in deny for x in WEB), f"{a} (strict) : WebFetch et WebSearch dans permissions.deny de .claude/settings.json")
    os.environ.update({k: env[k] for k in ("HOME", "BERGER_DIR", "BERGER_HERDR", "BERGER_TMP_AGENTS")})
    sys.argv = ["berger"]; g = runpy.run_path(str(i / "bin/berger"), run_name="essai")["lancer"].__globals__
    g["bac_a_sable_ok"] = lambda: True; g["exiger_tmp"] = g["preparer_tmp"] = lambda a: None
    claude, codex = g["moteurs"].MODULES["claude"], g["moteurs"].MODULES["codex"]
    claude.args("dehors")                                         # écrit .reglages-claude.json (strict dans un dossier existant)
    rq = json.loads((i / "agents/dehors/.reglages-claude.json").read_text())
    dire(all(x in rq["permissions"]["deny"] for x in WEB), "dehors (strict, dossier existant) : WebFetch et WebSearch dans le deny passé par --settings")
    dire(all(x in g["reglages_claude"](a)["permissions"]["deny"] for a in ("compta", "dehors") for x in WEB), "reglages_claude : le refus pour chaque strict")
    SORTANTS = ("RemoteTrigger", "PushNotification", "DesignSync", "SendMessage", "ListAgents", "Workflow", "CronCreate", "CronDelete", "CronList", "ScheduleWakeup")
    dire(all(x in g["reglages_claude"](a)["permissions"]["deny"] for a in ("compta", "dehors") for x in SORTANTS),
         "reglages_claude (31/10) : RemoteTrigger et les autres outils sortants refusés à chaque strict")
    o = json.loads((i / "agents/ouvert/.claude/settings.json").read_text())
    dire("deny" not in o.get("permissions", {}) and not any(x in json.dumps(o) for x in WEB), "mur ouvert : réglages Claude inchangés (aucun refus web)")

    # ── GÉNÉRATION : Codex ──
    for a in ("essai-codex", "compta"):
        for inter in (True, False):
            dire(contient(codex.args(a, inter), COUPE), f"{a} (strict) : -c web_search=\"disabled\" dans les arguments de Codex ({'interactif' if inter else 'non interactif'})")
    dire(contient(g["moteurs"].args_moteur("essai-codex", "codex", False), COUPE), "args_moteur (lancements réels : exec, panneau, demander) : la recherche web coupée")
    for a in ("essai-codex", "compta"):
        for inter in (True, False):
            dire(contient(codex.args(a, inter), SOUS_AGENTS), f"{a} (strict) : sous-agents (multi_agent) et clock (sleep_tool) coupés dans les arguments de Codex ({'interactif' if inter else 'non interactif'})")
    oc = codex.args("ouvert")
    dire(not any("web_search" in x for x in oc), "mur ouvert : arguments de Codex inchangés (aucun réglage web)")
    dire(not any("multi_agent" in x or "sleep_tool" in x for x in oc), "mur ouvert : sous-agents et clock inchangés")
    g["exiger_bac_a_sable"] = lambda a: None                      # le bac à sable de la machine n'est pas l'objet du test
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie): g["verbe_args"](["essai-codex", "codex", "--non-interactif", "--contrat"])
    try: ba = json.loads(sortie.getvalue())["args"]
    except (ValueError, KeyError): ba = []
    dire(contient(ba, COUPE), "berger args (contrat, autre accès) : la recherche web coupée")

    # ── ADMISSION (lot 1 bis) : un verdict ADMIS qui ne porte pas (12) est « à rejouer » — contrat rejoué au prochain lancement
    # (même chemin que « jamais vu »), admis seulement si le nouveau verdict porte (12) ; jamais de blocage sans tentative ──
    M = g["moteurs"]; M.CONTRATS = m / "contrats"; M.CONTRATS.mkdir(); M.version_moteur = lambda mo: "9.9.9"
    notes = []; M.notifier = lambda titre, texte, urgent=False: notes.append(texte)
    def verdict(mo, texte): (M.CONTRATS / f"{mo}-9.9.9.txt").write_text(texte)
    LIGNE_12 = {"claude": "✓ témoin (12) : sans le refus de Berger, Claude voit ses outils web (init) — ['WebFetch', 'WebSearch']\n"
                          "✓ (12) liste fermée : outils de l'agent strict (init), tous connus et non web — 22 outils\n",
                "codex": "✓ témoin (12) : sans le réglage de Berger, Codex envoie son outil de recherche web au modèle — vu\n"
                         "✓ (12) liste fermée : outils de la requête de Codex au modèle, tous connus et non web — 13 outils\n"}
    # renvoi n° 108 : les lignes (12) du lot 1 et du lot 1 bis (liste noire de noms web) ne prouvent rien — « à rejouer »
    LISTE_NOIRE = {"claude": "✓ témoin (12) : sans le refus de Berger, Claude voit ses outils web (init) — ['WebFetch', 'WebSearch']\n"
                             "✓ (12) outils web intégrés vus (init) : aucun\n",
                   "codex": "✓ témoin (12) : sans le réglage de Berger, Codex envoie son outil de recherche web au modèle — vu\n"
                            "✓ (12) recherche web de Codex, outils de sa requête au modèle : aucun outil web\n"}
    ANCIEN = lambda mo: f"ADMIS\nmoteur : {mo} 9.9.9\nagent : compta\n✓ (1) outils vus\n✓ (6) connect() AF_UNIX : refusé\n"
    joues = []
    def rejoue(nouveau):
        def jouer(mo, a):
            joues.append((mo, a))
            if nouveau: verdict(mo, nouveau(mo))
        return jouer
    for mo in ("claude", "codex"):
        verdict(mo, ANCIEN(mo))
        e, v, raison = M.verdict_moteur(mo)
        dire(e == "à rejouer" and "(12)" in raison and f"bash tests/contrat-moteur.sh {mo}" in raison,
             f"{mo} : verdict ADMIS antérieur au contrôle (12) = « à rejouer » (jamais admis), commande dite — {raison}")
        joues.clear(); M.jouer_contrat = rejoue(lambda x: f"ADMIS\nmoteur : {x} 9.9.9\n✓ (1) outils vus\n{LIGNE_12[x]}")
        dire(M.moteur_admis(mo, "compta") is None and joues == [(mo, "compta")], f"{mo} : ancien verdict → contrat rejoué au lancement → admis (le nouveau porte (12))")
        dire(M.moteur_admis(mo, "compta") is None and len(joues) == 1, f"{mo} : nouveau verdict avec (12) : pas rejoué une 2e fois")
        verdict(mo, ANCIEN(mo)); joues.clear(); n = len(notes)
        M.jouer_contrat = rejoue(lambda x: f"NON ADMIS\nmoteur : {x} 9.9.9\n✗ (12) outils web intégrés vus (init) : ['WebFetch']\n")
        pb = M.moteur_admis(mo, "compta")
        dire(pb and "non admis" in pb and "WebFetch" in pb and joues == [(mo, "compta")] and len(notes) == n + 1,
             f"{mo} : ancien verdict → contrat rejoué qui échoue → NON admis, notifié")
        verdict(mo, ANCIEN(mo)); joues.clear(); M.jouer_contrat = rejoue(ANCIEN)
        pb = M.moteur_admis(mo, "compta")
        dire(pb and "non admis" in pb and joues == [(mo, "compta")], f"{mo} : contrat rejoué qui rend encore un verdict sans (12) = NON admis (jamais admis sans (12))")
        verdict(mo, ANCIEN(mo)); joues.clear(); M.jouer_contrat = rejoue(None)
        pb = M.moteur_admis(mo, "compta")
        dire(pb and "contrat impossible" in pb and joues == [(mo, "compta")], f"{mo} : ancien verdict, contrat impossible à jouer = NON admis, après tentative")
        verdict(mo, f"ADMIS\nmoteur : {mo} 9.9.9\n✓ (1) outils vus\n{LIGNE_12[mo]}")
        dire(M.verdict_moteur(mo)[0] == "admis", f"{mo} : verdict ADMIS qui porte le contrôle (12) = admis")
        verdict(mo, f"ADMIS\nmoteur : {mo} 9.9.9\n✓ (1) outils vus\n# ✓ (12) écrit à la main\n✓ (12x) autre chose\n")
        dire(M.verdict_moteur(mo)[0] == "à rejouer", f"{mo} : une mention de (12) hors d'une ligne ✓ (12) n'admet pas")
        verdict(mo, f"ADMIS\nmoteur : {mo} 9.9.9\n{LIGNE_12[mo]}✗ (6) connect() AF_UNIX : CONNECTÉ\n")
        dire(M.verdict_moteur(mo)[0] == "non admis", f"{mo} : ADMIS avec une ligne ✗ = non admis (verdict incohérent)")
    for mo in ("claude", "codex"):
        verdict(mo, f"ADMIS\nmoteur : {mo} 9.9.9\n✓ (12) liste fermée : outils tous connus\n")
        dire(M.verdict_moteur(mo)[0] == "à rejouer", f"{mo} : (12) sans son témoin = à rejouer (le témoin fait partie du contrôle)")
        verdict(mo, f"ADMIS\nmoteur : {mo} 9.9.9\n✓ (1) outils vus\n{LISTE_NOIRE[mo]}")
        e, v, raison = M.verdict_moteur(mo)
        dire(e == "à rejouer" and "liste fermée" in raison, f"{mo} : verdict ADMIS rendu par l'ancien (12) (liste noire de noms web) = « à rejouer » — {raison}")
    # les DEUX moteurs avec un ancien verdict (cas de l'installation) : aucun blocage sans tentative de contrat
    for mo in ("claude", "codex"): verdict(mo, ANCIEN(mo))
    joues.clear(); M.jouer_contrat = rejoue(lambda x: f"ADMIS\nmoteur : {x} 9.9.9\n{LIGNE_12[x]}")
    dire(M.choisir_moteur("compta", "claude") == ("claude", None) and joues == [("claude", "compta")],
         "deux moteurs anciens : l'agent strict démarre (contrat rejoué pour SON moteur, admis), aucun blocage")
    for mo in ("claude", "codex"): verdict(mo, ANCIEN(mo))
    joues.clear(); M.jouer_contrat = rejoue(lambda x: f"NON ADMIS\nmoteur : {x} 9.9.9\n✗ (12) outils web intégrés vus\n" if x == "claude" else f"ADMIS\nmoteur : {x} 9.9.9\n{LIGNE_12[x]}")
    dire(M.choisir_moteur("compta", "claude") == ("codex", M.choisir_moteur.__globals__["moteur_admis"]("claude", "compta")) and ("codex", "compta") in joues,
         "deux moteurs anciens, claude échoue au contrat rejoué : bascule sur codex après SON contrat rejoué")
    for mo in ("claude", "codex"): verdict(mo, ANCIEN(mo))
    joues.clear(); M.jouer_contrat = rejoue(None)
    mo_, pb = M.choisir_moteur("compta", "claude")
    dire(mo_ is None and "aucun moteur admis" in pb and sorted(joues) == [("claude", "compta"), ("codex", "compta")],
         "deux moteurs anciens, contrats impossibles : refus SEULEMENT après une tentative pour chacun")
    for mo in ("claude", "codex"): verdict(mo, ANCIEN(mo))
    al = M.alertes_moteurs()
    dire(any(c == "jaune" and "claude" in x and "(12)" in x and "contrat-moteur.sh claude" in x for c, _, x in al) and not any(c == "rouge" for c, _, x in al),
         "Synthèse : ancien verdict sans (12) en JAUNE (à rejouer, commande dite), pas en rouge")

# ── CONTRAT (12), hors moteur ──
sp = importlib.util.spec_from_file_location("contrat", SRC / "tests/contrat-moteur.py"); C = importlib.util.module_from_spec(sp); sp.loader.exec_module(C)
# renvoi n° 108 : (12) par LISTE FERMÉE — la liste d'outils de l'agent strict doit être INCLUSE dans les outils connus non web de
# CE moteur et de CETTE version (tests/outils-connus/<moteur>-<version>.json) ; tout outil inconnu, toute forme non reconnue = rouge,
# outils inconnus nommés. Le témoin positif reste : sans le refus de Berger, CHAQUE outil web de la liste doit apparaître.
CL = {"fichier": "tests/outils-connus/claude-9.9.9.json", "version": "9.9.9", "exacte": True, "raison": None,
      "web": ["WebFetch", "WebSearch"], "outils": ["Bash", "Read", "Write"]}
def wc(init, temoin, connus=CL, permis=()):
    """Les deux lignes (témoin, contrôle) de conditions_web_claude → [(vert, texte), (vert, texte)]."""
    out = []; C.conditions_web_claude(lambda b, t: out.append((bool(b), t)), init, temoin, connus, set(permis)); return out
TEMOIN = {"tools": ["Bash", "Read", "WebFetch", "WebSearch", "Write"]}
r = wc({"tools": ["Bash", "Read", "Write"]}, TEMOIN)
dire(len(r) == 2 and r[0][0] and r[1][0] and r[0][1].startswith("témoin (12)") and r[1][1].startswith("(12) liste fermée"),
     f"contrat (12) Claude : témoin porte WebFetch et WebSearch, outils de l'agent tous dans la liste fermée = vert — {r}")
r = wc({"tools": ["Bash", "Read", "RemoteTrigger", "Write"]}, TEMOIN)
dire(r[0][0] and not r[1][0] and "RemoteTrigger" in r[1][1], "contrat (12) Claude (31/10) : RemoteTrigger vu chez un strict = rouge, nommé (il n'est pas dans la liste fermée)")
r = wc({"tools": ["Bash", "Read", "WebFetch", "WebSearch"]}, TEMOIN)
dire(r[0][0] and not r[1][0] and "WebFetch" in r[1][1] and "WebSearch" in r[1][1], "contrat (12) Claude : WebFetch/WebSearch vus avec Berger = rouge, nommés")
# BLOQUANT 1 du renvoi n° 108 : renommage PARTIEL (WebSearch → InternetSearch, WebFetch gardé)
r = wc({"tools": ["Bash", "InternetSearch"]}, {"tools": ["Bash", "WebFetch", "InternetSearch"]})
dire(not r[0][0] and "WebSearch" in r[0][1] and not r[1][0] and "InternetSearch" in r[1][1],
     f"contrat (12) Claude : renommage partiel (témoin Bash, WebFetch, InternetSearch ; agent Bash, InternetSearch) = témoin ET contrôle ROUGES — {r}")
r = wc({"tools": ["Bash", "InternetSearch"]}, TEMOIN)
dire(r[0][0] and not r[1][0] and "InternetSearch" in r[1][1] and "inconnu" in r[1][1], "contrat (12) Claude : outil inconnu chez l'agent (InternetSearch) = rouge, nommé « inconnu »")
r = wc({"tools": ["Bash", "Read"]}, {"tools": ["Bash", "Read", "WebFetch"]})
dire(not r[0][0] and "WebSearch" in r[0][1], "contrat (12) Claude : témoin où manque UN outil web de la liste (WebSearch) = rouge (renommé ou introuvable)")
for temoin, quoi in (({"tools": ["Bash", "Read", "InternetSearch"]}, "renommé InternetSearch"), ({"tools": ["Bash", "Read"]}, "absent")):
    r = wc({"tools": ["Bash", "Read"]}, temoin)
    dire(not r[0][0] and "renommé ou introuvable" in r[0][1] and not r[1][0], f"contrat (12) Claude : outils web {quoi} dans le témoin = ÉCHEC « renommé ou introuvable »")
for nom in ("Glob", "TodoWrite", "bash", "Bash ", "WEBFETCH", "web_fetch", "Web Fetch", "web_search", "websearch"):
    r = wc({"tools": ["Bash", nom]}, TEMOIN)
    dire(r[0][0] and not r[1][0] and repr(nom) in r[1][1], f"contrat (12) Claude : « {nom} » hors de la liste fermée = rouge, nommé")
r = wc({"tools": ["Bash"]}, {"tools": ["Bash", "WEBFETCH", "WEBSEARCH"]})
dire(not r[0][0], "contrat (12) Claude : témoin aux noms web d'une autre casse = rouge (noms exacts de la liste)")
# outils MCP relayés par berger-mcp : ceux des serveurs de SON `mcp =` seulement
r = wc({"tools": ["Bash", "mcp__berger-contrat__web", "mcp__berger-contrat__sonde"]}, TEMOIN, permis={"berger-contrat"})
dire(r[1][0], f"contrat (12) Claude : outils mcp__<serveur>__… d'un serveur de son `mcp =` = connus (vert) — {r[1]}")
for outil, permis, quoi in (("mcp__berger-contrat__web", (), "sans `mcp =`"), ("mcp__autre__lire", {"berger-contrat"}, "d'un serveur hors de son `mcp =`"),
                            ("mcp__berger-contrat__", {"berger-contrat"}, "sans nom d'outil"), ("mcp__berger-contrat", {"berger-contrat"}, "sans séparateur"),
                            ("mcp__berger-contrat-bis__x", {"berger-contrat"}, "d'un serveur au nom prolongé")):
    r = wc({"tools": ["Bash", outil]}, TEMOIN, permis=permis)
    dire(not r[1][0] and repr(outil) in r[1][1], f"contrat (12) Claude : outil MCP {quoi} ({outil}) = rouge, nommé")
# liste fermée absente ou d'une autre version : jamais vert, les outils inconnus nommés par rapport à la plus récente
r = wc({"tools": ["Bash", "Read"]}, TEMOIN, connus={**CL, "web": None, "outils": None, "exacte": False, "raison": "pas de liste fermée pour claude 9.9.9"})
dire(not r[0][0] and not r[1][0] and "pas de liste fermée" in r[1][1], f"contrat (12) Claude : aucune liste fermée = rouge (témoin et contrôle) — {r}")
r = wc({"tools": ["Bash", "Read", "Glob"]}, TEMOIN, connus={**CL, "exacte": False, "version": "9.9.8", "raison": "pas de liste fermée pour claude 9.9.9 — comparée à celle de 9.9.8"})
dire(not r[1][0] and "pas de liste fermée" in r[1][1] and "'Glob'" in r[1][1], f"contrat (12) Claude : liste d'une version précédente = rouge, l'outil nouveau nommé — {r[1]}")
r = wc({"tools": ["Bash", "Read"]}, TEMOIN, connus={**CL, "exacte": False, "version": "9.9.8", "raison": "pas de liste fermée pour claude 9.9.9"})
dire(not r[1][0], "contrat (12) Claude : liste d'une autre version, même sans outil nouveau = rouge (la liste se relit par version)")
# jamais de faux vert — une source absente, partielle ou mal formée n'est PAS mesurée, donc rouge (des deux côtés)
MAL = (({}, "sans champ tools"), ({"tools": None}, "tools nul"), ({"tools": "Bash,Read"}, "tools en texte"),
       ({"tools": {"Bash": 1}}, "tools en objet"), ({"tools": []}, "tools vide"), ({"tools": ["Bash", 3]}, "un outil qui n'est pas un nom"),
       ({"tools": [""]}, "un seul nom vide"), ({"tools": ["Bash", ""]}, "un nom vide parmi d'autres"), ({"tools": ["Bash", "   "]}, "un nom fait d'espaces"),
       (None, "init absent"), ("init", "init qui n'est pas un objet"))
for init, quoi in MAL:
    r = wc(init, TEMOIN)
    dire(not r[1][0] and r[1][1].startswith("(12) liste fermée") and "non mesurable" in r[1][1], f"contrat (12) Claude : init {quoi} = NON mesurable, rouge (jamais « aucun »)")
    r = wc({"tools": ["Bash", "Read"]}, init)
    dire(not r[0][0] and "non mesurable" in r[0][1] and not r[1][0], f"contrat (12) Claude : témoin {quoi} = NON mesurable, rouge (le contrôle ne prouve rien)")
dire(C.args_temoin_claude() and "--strict-mcp-config" in C.args_temoin_claude() and not any("settings" == x.lstrip("-") for x in C.args_temoin_claude()),
     "contrat (12) Claude : le témoin garde le mur MCP strict, sans --settings de Berger")
dire(C.sans_reglage_web(["-C", "/x", "-p", "a", *COUPE, "-m", "y"]) == ["-C", "/x", "-p", "a", "-m", "y"], "contrat (12) Codex : le témoin retire le seul réglage de Berger")

# les listes fermées livrées : une par moteur ET par version, relue par le contrat (forme réelle mesurée le 31/10/2026)
CLAUDE_REEL = ["Task", "Bash", "Edit", "EnterWorktree", "ExitWorktree", "Monitor", "NotebookEdit", "Read", "ReportFindings", "Skill",
               "TaskStop", "ToolSearch", "Write"]          # 31/10 : les outils sortants de REFUS_STRICT n'y sont plus
cl = C.charger_connus("claude", "2.1.312")
dire(cl["exacte"] and sorted(cl["outils"]) == sorted(CLAUDE_REEL) and cl["web"] == ["WebFetch", "WebSearch"] and cl["fichier"].endswith("tests/outils-connus/claude-2.1.312.json"),
     f"liste fermée claude 2.1.312 : les 22 outils mesurés, WebFetch et WebSearch à part — {cl.get('raison')}")
r = wc({"tools": CLAUDE_REEL + ["mcp__berger-contrat__sonde", "mcp__berger-contrat__web"]},
       {"tools": CLAUDE_REEL[:20] + ["WebFetch", "WebSearch"] + CLAUDE_REEL[20:] + ["mcp__berger-contrat__sonde"]}, connus=cl, permis={"berger-contrat"})
dire(r[0][0] and r[1][0], f"contrat (12) Claude : traces réelles de claude 2.1.312 (témoin 24 outils, strict 22 + MCP de l'agent) = vert — {r}")
# listes des versions du serveur de développement (01/11/2026, go du propriétaire) : copies exactes, seule la version change ; aucun outil web en plus
for m, v, ref in (("claude", "2.1.314", "2.1.312"), ("claude", "2.1.316", "2.1.314"), ("codex", "0.160.0", "0.165.0")):
    a, b = C.charger_connus(m, v), C.charger_connus(m, ref)
    dire(a["exacte"] and a["fichier"].endswith(f"tests/outils-connus/{m}-{v}.json") and all(a[k] == b[k] for k in ("types", "web", "outils", "si_13", "modele_temoin") if k in b),
         f"liste fermée {m} {v} : mêmes outils, mêmes outils web à part, même condition (13) que {m} {ref} — {a.get('raison')}")
cx = C.charger_connus("codex", "0.165.0")
dire(cx["exacte"] and cx["web"] == [(("web_search", None),)] and (("function", "exec_command"),) in cx["outils"] and (("custom", "apply_patch"),) in cx["outils"]
     and len(cx["outils"]) == 17 and not any("mcp__" in str(x) for c in cx["outils"] for p in c for x in p),
     f"liste fermée codex 0.165.0 : 17 outils mesurés (dont additional_tools du modèle par défaut), en paires structurées (type, nom), MCP hors liste (ceux de l'agent, par son `mcp =`) — {cx.get('raison')}")
dire(not any(c[0] in (("namespace", "multi_agent_v1"), ("namespace", "collaboration"), ("namespace", "clock")) for c in cx["outils"]),
     "liste fermée codex 0.165.0 (31/10, demande du propriétaire) : ni sous-agents (multi_agent_v1, collaboration) ni clock parmi les outils connus")
dire(cx["types"] == {"function": {"nom": True}, "custom": {"nom": True}, "namespace": {"nom": True, "outils": True}, "tool_search": {}, "web_search": {}},
     "liste fermée codex 0.165.0 : liste fermée des TYPES, avec leur structure (nom, outils imbriqués)")
dire(not set(cl["outils"]) & set(cl["web"]) and not any(C.nom_web(x) for x in cl["outils"]), "liste fermée claude-2.1.312.json : aucun outil web parmi les outils connus")
dire(not set(cx["outils"]) & set(cx["web"]) and not any(C.nom_web(x) for c in cx["outils"] for p in c for x in p if x),
     "liste fermée codex-0.165.0.json : aucun outil web parmi les outils connus")
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "claude-2.1.312.json").write_text((SRC / "tests/outils-connus/claude-2.1.312.json").read_text())
    n = C.charger_connus("claude", "2.1.400", d)
    dire(not n["exacte"] and n["version"] == "2.1.312" and "pas de liste fermée pour claude 2.1.400" in n["raison"] and "2.1.312" in n["raison"]
         and str(d / "claude-2.1.400.json") in n["raison"], f"mise à jour de claude (2.1.400, sans liste) : comparée à la plus récente (2.1.312), jamais exacte — {n['raison']}")
    r = wc({"tools": CLAUDE_REEL + ["NouvelOutil"]}, {"tools": CLAUDE_REEL + ["WebFetch", "WebSearch"]}, connus=n)
    dire(not r[1][0] and "'NouvelOutil'" in r[1][1] and "2.1.400" in r[1][1], f"mise à jour de claude : le contrat échoue en NOMMANT l'outil nouveau — {r[1]}")
    dire(C.charger_connus("codex", "0.165.0", d)["outils"] is None, "aucune liste pour ce moteur : rien de connu (rouge)")
    for nom, contenu, quoi in (("claude-1.0.0.json", "{", "JSON illisible"),
                               ("claude-1.0.1.json", json.dumps({"moteur": "claude", "version": "1.0.0", "web": ["WebFetch"], "outils": ["Bash"]}), "version qui ne colle pas au nom"),
                               ("claude-1.0.2.json", json.dumps({"moteur": "claude", "version": "1.0.2", "web": ["WebFetch"], "outils": ["Bash", "WebFetch"]}), "outil web parmi les connus"),
                               ("claude-1.0.3.json", json.dumps({"moteur": "claude", "version": "1.0.3", "web": ["WebFetch"], "outils": ["Bash", "web_fetch"]}), "nom web déguisé parmi les connus"),
                               ("claude-1.0.4.json", json.dumps({"moteur": "claude", "version": "1.0.4", "web": [], "outils": ["Bash"]}), "aucun outil web (le témoin ne prouverait rien)"),
                               ("claude-1.0.5.json", json.dumps({"moteur": "claude", "version": "1.0.5", "web": ["WebFetch"], "outils": ["Bash", ""]}), "nom vide"),
                               ("claude-1.0.6.json", json.dumps({"moteur": "claude", "version": "1.0.6", "web": ["WebFetch"], "outils": ["Bash", "mcp__x__y"]}), "outil MCP dans la liste")):
        (d / nom).write_text(contenu); v = nom[len("claude-"):-len(".json")]
        n = C.charger_connus("claude", v, d)
        dire(n["outils"] is None and not n["exacte"] and "mal formée" in n["raison"], f"liste fermée {quoi} = refusée (mal formée), jamais vert — {n['raison']}")
    TY = {"function": {"nom": True}, "namespace": {"nom": True, "outils": True}, "web_search": {}}
    base = lambda v, **x: json.dumps({"moteur": "codex", "version": v, "types": TY, "web": [{"type": "web_search"}],
                                      "outils": [{"type": "function", "name": "exec_command"}], **x})
    (d / "codex-2.0.0.json").write_text(base("2.0.0")); n = C.charger_connus("codex", "2.0.0", d)
    dire(n["exacte"] and n["outils"] == [(("function", "exec_command"),)], f"liste fermée codex en paires structurées : lue — {n['raison']}")
    for v, contenu, quoi in (("2.0.1", base("2.0.1", outils=["function:exec_command"]), "à l'ancien format (chaînes concaténées)"),
                             ("2.0.2", base("2.0.2", types=None), "sans liste des types"),
                             ("2.0.3", base("2.0.3", outils=[{"type": "function:exec_command"}]), "type qui contient « : »"),
                             ("2.0.4", base("2.0.4", outils=[{"type": "function", "name": "a/b"}]), "nom qui contient « / »"),
                             ("2.0.5", base("2.0.5", outils=[{"type": "custom", "name": "apply_patch"}]), "type hors de la liste des types"),
                             ("2.0.6", base("2.0.6", outils=[{"type": "web_search", "name": "x"}]), "nom sur un type qui n'en porte pas"),
                             ("2.0.7", base("2.0.7", outils=[{"type": "function"}]), "nom manquant"),
                             ("2.0.8", base("2.0.8", outils=[{"type": "namespace", "name": "n"}]), "namespace sans ses outils"),
                             ("2.0.9", base("2.0.9", outils=[{"type": "function", "name": "x", "tools": [{"type": "function", "name": "y"}]}]), "outils imbriqués sous un function"),
                             ("2.0.10", base("2.0.10", outils=[{"type": "function", "name": "x", "strict": True}]), "champ inattendu"),
                             ("2.0.11", base("2.0.11", types={**TY, "a:b": {}}), "type de la liste des types qui contient « : »"),
                             ("2.0.12", base("2.0.12", outils=[{"type": "namespace", "name": "mcp__x", "tools": [{"type": "function", "name": "y"}]}]), "outil MCP dans la liste")):
        (d / f"codex-{v}.json").write_text(contenu); n = C.charger_connus("codex", v, d)
        dire(n["outils"] is None and not n["exacte"] and "mal formée" in n["raison"], f"liste fermée codex {quoi} = refusée (mal formée) — {n['raison']}")

with tempfile.TemporaryDirectory() as t, contextlib.ExitStack() as pile:
    t = Path(t); faux = t / "codex"
    if SANS_RESEAU:
        print("Transport HTTP local NON JOUÉ : requêtes des faux exécutables rejouées en mémoire (--sans-reseau)")
        pile.enter_context(fournisseur_sans_reseau(t))
    CX = {"fichier": "tests/outils-connus/codex-9.9.9.json", "version": "9.9.9", "exacte": True, "raison": None,
          "types": {"function": {"nom": True}, "namespace": {"nom": True, "outils": True}, "web_search": {}},
          "web": [(("web_search", None),)],
          "outils": [(("function", "exec_command"),), (("namespace", "multi_agent_v1"),), (("namespace", "multi_agent_v1"), ("function", "spawn_agent"))]}
    # faux Codex : comme le vrai (mesuré, 0.165.0), il envoie l'outil web_search au modèle sauf avec -c web_search="disabled"
    faux.write_text("#!/usr/bin/env python3\nimport json, re, sys, urllib.request\na = sys.argv[1:]\n"
                    "c = [a[k + 1] for k in range(len(a) - 1) if a[k] == '-c']\n"
                    "base = next(re.match(r'model_providers\\.[\\w-]+\\.base_url=\"(.*)\"$', x).group(1) for x in c if re.match(r'model_providers\\.[\\w-]+\\.base_url=', x))\n"
                    "outils = [{'type': 'function', 'name': 'exec_command'}] + ([] if 'web_search=\"disabled\"' in c else [{'type': 'web_search', 'external_web_access': False}])\n"
                    "if 'MUET' in a: sys.exit(1)\n"
                    "rq = urllib.request.Request(base + '/responses', data=json.dumps({'model': 'm', 'tools': outils}).encode(), headers={'content-type': 'application/json'})\n"
                    "try: urllib.request.urlopen(rq, timeout=10)\nexcept Exception: pass\nsys.exit(1)\n")
    faux.chmod(0o755)
    lignes = []
    def note(bon, txt): lignes.append((bool(bon), txt))
    def wx(args, codex, connus=CX, permis=()):
        lignes.clear(); C.condition_web_codex(note, args, t, dict(os.environ), connus, set(permis), codex=codex); return lignes
    wx(["-C", str(t), "-p", "a", *COUPE], str(faux))
    dire(len(lignes) == 2 and all(b for b, _ in lignes) and "témoin" in lignes[0][1] and lignes[1][1].startswith("(12) liste fermée"),
         "contrat (12) Codex : témoin vu sans le réglage, puis outils tous dans la liste fermée (faux fournisseur local)" + ("" if all(b for b, _ in lignes) else f" — {lignes}"))
    wx(["-C", str(t), "-p", "a"], str(faux))
    dire(len(lignes) == 2 and lignes[0][0] and not lignes[1][0] and "web_search" in lignes[1][1], "contrat (12) Codex : réglage absent des arguments = rouge, l'outil nommé")
    wx(["-C", str(t), "-p", "a", *COUPE, "MUET"], str(faux))
    dire(len(lignes) == 2 and not lignes[0][0] and not lignes[1][0] and "source machine" in lignes[1][1],
         "contrat (12) Codex : aucune requête reçue = rouge (pas de source machine), jamais vert par défaut")

    def faux_codex(nom, corps_sans, corps_avec):
        f = t / nom
        f.write_text("#!/usr/bin/env python3\nimport json, re, sys, urllib.request\na = sys.argv[1:]\n"
                     "c = [a[k + 1] for k in range(len(a) - 1) if a[k] == '-c']\n"
                     "base = next(re.match(r'model_providers\\.[\\w-]+\\.base_url=\"(.*)\"$', x).group(1) for x in c if re.match(r'model_providers\\.[\\w-]+\\.base_url=', x))\n"
                     f"corps = {corps_avec!r} if 'web_search=\"disabled\"' in c else {corps_sans!r}\n"
                     "rq = urllib.request.Request(base + '/responses', data=corps.encode(), headers={'content-type': 'application/json'})\n"
                     "try: urllib.request.urlopen(rq, timeout=10)\nexcept Exception: pass\nsys.exit(1)\n")
        f.chmod(0o755); return str(f)
    temoin_ok = json.dumps({"model": "m", "tools": [{"type": "function", "name": "exec_command"}, {"type": "web_search"}]})
    for corps, quoi in (("{}", "requête {}"), (json.dumps({"model": "m"}), "sans champ tools"), (json.dumps({"tools": None}), "tools nul"),
                        (json.dumps({"tools": "web_search"}), "tools en texte"), (json.dumps({"tools": []}), "tools vide"),
                        (json.dumps({"tools": ["web_search"]}), "un outil qui n'est pas un objet"),
                        (json.dumps({"tools": [{"name": "exec_command"}]}), "un outil sans type"),
                        (json.dumps({"tools": [{"type": "function"}]}), "un outil function sans nom"),
                        (json.dumps({"tools": [{"type": "function", "name": "exec_command"}, {"type": "function", "name": ""}]}), "un outil function au nom vide"),
                        (json.dumps({"tools": [{"type": ""}]}), "un type vide"), (json.dumps({"tools": [{"type": "  ", "name": "x"}]}), "un type fait d'espaces"),
                        (json.dumps({"tools": [{"type": "function", "name": "exec_command"}, {"type": "web_search", "name": ""}]}), "un nom présent mais vide"),
                        (json.dumps({"tools": [{"type": "function", "name": "exec_command"}, {"type": "namespace", "name": "multi_agent_v1"}]}), "un namespace sans outils"),
                        (json.dumps({"tools": [{"type": "namespace", "name": "multi_agent_v1", "tools": [{"type": "function"}]}]}), "un namespace dont un outil n'a pas de nom"),
                        (json.dumps({"tools": [{"type": "namespace", "tools": [{"type": "function", "name": "spawn_agent"}]}]}), "un namespace sans nom")):
        wx(["-C", str(t), *COUPE], faux_codex("codex-vide", temoin_ok, corps))
        dire(len(lignes) == 2 and lignes[0][0] and not lignes[1][0] and "non mesurable" in lignes[1][1],
             f"contrat (12) Codex : {quoi} avec le réglage = NON mesurable, rouge même après un témoin positif" + ("" if len(lignes) == 2 and not lignes[1][0] else f" — {lignes}"))
    # 31/10 (contrat rejoué sur le vrai codex 0.165.0 : « non mesurable ») : une requête ANNEXE sans champ tools ne compte pas,
    # pourvu qu'une requête porte une liste complète ; seule, elle reste non mesurable (cas « sans champ tools » ci-dessus)
    def faux_codex2(nom, corps_sans, corps_avec, annexe):
        f = t / nom
        f.write_text("#!/usr/bin/env python3\nimport json, re, sys, urllib.request\na = sys.argv[1:]\n"
                     "c = [a[k + 1] for k in range(len(a) - 1) if a[k] == '-c']\n"
                     "base = next(re.match(r'model_providers\\.[\\w-]+\\.base_url=\"(.*)\"$', x).group(1) for x in c if re.match(r'model_providers\\.[\\w-]+\\.base_url=', x))\n"
                     f"corps = {corps_avec!r} if 'web_search=\"disabled\"' in c else {corps_sans!r}\n"
                     f"for b in ({annexe!r}, corps):\n"
                     "    rq = urllib.request.Request(base + '/responses', data=b.encode(), headers={'content-type': 'application/json'})\n"
                     "    try: urllib.request.urlopen(rq, timeout=10)\n    except Exception: pass\n"
                     "sys.exit(1)\n")
        f.chmod(0o755); return str(f)
    complet = json.dumps({"model": "m", "tools": [{"type": "function", "name": "exec_command"}]})
    wx(["-C", str(t), *COUPE], faux_codex2("codex-annexe", temoin_ok, complet, json.dumps({"model": "m", "input": "titre"})))
    dire(len(lignes) == 2 and lignes[0][0] and lignes[1][0],
         "contrat (12) Codex : une requête annexe SANS champ tools à côté d'une requête complète ne rend pas non mesurable (forme réelle 0.165.0)" + ("" if len(lignes) == 2 and lignes[1][0] else f" — {lignes}"))
    wx(["-C", str(t), *COUPE], faux_codex2("codex-annexe-mal", temoin_ok, complet, json.dumps({"model": "m", "tools": [{"type": "function"}]})))
    dire(len(lignes) == 2 and not lignes[1][0] and "non mesurable" in lignes[1][1],
         "contrat (12) Codex : une requête annexe AVEC un champ tools incomplet reste non mesurable, rouge")
    wx(["-C", str(t), *COUPE], faux_codex("codex-temoin-vide", "{}", temoin_ok))
    dire(len(lignes) == 2 and not lignes[0][0], "contrat (12) Codex : témoin sans liste d'outils exploitable = rouge (le témoin ne prouve rien)")
    wx(["-C", str(t), *COUPE], faux_codex("codex-temoin-sans-web", json.dumps({"tools": [{"type": "function", "name": "exec_command"}, {"type": "WEB_SEARCH"}]}), temoin_ok))
    dire(len(lignes) == 2 and not lignes[0][0] and "WEB_SEARCH" in lignes[0][1] and "non mesurable" in lignes[0][1],
         "contrat (12) Codex : témoin au type inconnu WEB_SEARCH = non mesurable, rouge (nommé)")
    # BLOQUANT 2 du renvoi n° 108 : type mal formé ou inconnu — forme non reconnue = rouge, nommée
    for outil, nomme in (({"type": "Function"}, "'Function'"), ({"type": "FUNCTION", "name": "exec_command"}, "'FUNCTION:exec_command'"),
                         ({"type": "local_shell"}, "'local_shell'"), ({"type": "function", "name": "inconnu"}, "'function:inconnu'"),
                         ({"type": "custom", "name": "exec_command"}, "'custom:exec_command'"),
                         ({"type": "namespace", "name": "multi_agent_v1", "tools": [{"type": "function", "name": "lire_page"}]}, "'namespace:multi_agent_v1/function:lire_page'"),
                         ({"type": "function", "name": "exec_command", "tools": [{"type": "web_search"}]}, "'function:exec_command/web_search'"),
                         ({"type": "WEB_SEARCH"}, "'WEB_SEARCH'"), ({"type": "Web-Search-Preview"}, "'Web-Search-Preview'"),
                         ({"type": "function", "name": "WebFetch"}, "'function:WebFetch'"), ({"type": "function", "name": "web_fetch"}, "'function:web_fetch'")):
        corps = json.dumps({"tools": [{"type": "function", "name": "exec_command"}, outil]})
        wx(["-C", str(t), *COUPE], faux_codex("codex-inconnu", temoin_ok, corps))
        dire(len(lignes) == 2 and lignes[0][0] and not lignes[1][0] and nomme in lignes[1][1] and "inconnu" in lignes[1][1],
             f"contrat (12) Codex : {outil} hors de la liste fermée = rouge, nommé {nomme}" + ("" if len(lignes) == 2 and not lignes[1][0] else f" — {lignes}"))
    # BLOQUANT du renvoi n° 111 : collisions de l'encodage type « : » nom — un TYPE qui imite un outil connu, un outil
    # imbriqué ou un outil MCP permis ; la structure est validée d'abord, puis des paires (type, nom) sont comparées
    for outil, connus, permis, quoi in (({"type": "function:exec_command"}, CX, (), "type « function:exec_command » sans nom"),
                                        ({"type": "custom:apply_patch"}, cx, (), "type « custom:apply_patch » sans nom (liste réelle)"),
                                        ({"type": "namespace:mcp__berger_contrat/function:InternetSearch"}, CX, {"berger-contrat"}, "type qui imite un outil MCP permis"),
                                        ({"type": "namespace:multi_agent_v1/function:spawn_agent"}, CX, (), "type qui imite un outil imbriqué connu"),
                                        ({"type": "function", "name": "exec_command:x"}, CX, (), "nom qui contient « : »"),
                                        ({"type": "namespace", "name": "multi_agent_v1/function:spawn_agent", "tools": [{"type": "function", "name": "spawn_agent"}]}, CX, (), "nom qui contient « / »"),
                                        ({"type": "tool_search", "name": "tool_search"}, cx, (), "nom sur un type qui n'en porte pas"),
                                        ({"type": "custom"}, cx, (), "custom sans nom"),
                                        ({"type": "function", "name": "exec_command", "tools": [{"type": "function", "name": "exec_command"}]}, CX, (), "outils imbriqués sous un function")):
        corps = json.dumps({"tools": [{"type": "function", "name": "exec_command"}, outil]})
        wx(["-C", str(t), *COUPE], faux_codex("codex-collision", temoin_ok, corps), connus=connus, permis=permis)
        n = 3 if connus.get("modele_temoin") else 2                # liste livrée : liste fermée sur le défaut ET le modèle témoin
        dire(len(lignes) == n and lignes[0][0] and not any(b for b, _ in lignes[1:]) and "inconnu" in lignes[1][1],
             f"contrat (12) Codex : {quoi} = structure non reconnue, ROUGE" + ("" if len(lignes) == n and not lignes[1][0] else f" — {lignes}"))
    wx(["-C", str(t), *COUPE], faux_codex("codex-collision", temoin_ok, json.dumps({"tools": [{"type": "function:exec_command"}]})))
    dire(not lignes[1][0] and "forme non reconnue" in lignes[1][1] and "function:exec_command" in lignes[1][1],
         f"contrat (12) Codex : la forme non reconnue est nommée telle quelle, jamais confondue avec l'outil connu — {lignes[1]}")
    wx(["-C", str(t), *COUPE], faux_codex("codex-temoin-colle", json.dumps({"tools": [{"type": "function", "name": "exec_command"}, {"type": "web_search:x"}]}), temoin_ok))
    dire(not lignes[0][0], "contrat (12) Codex : témoin dont l'outil web n'a pas la forme exacte (web_search:x) = rouge")
    # outils MCP relayés par berger-mcp : Codex les range dans un namespace mcp__<serveur> (tiret → souligné, mesuré le 31/10)
    mcp = {"type": "namespace", "name": "mcp__berger_contrat", "tools": [{"type": "function", "name": "web"}, {"type": "function", "name": "sonde"}]}
    corps = json.dumps({"tools": [{"type": "function", "name": "exec_command"}, mcp]})
    wx(["-C", str(t), *COUPE], faux_codex("codex-mcp", temoin_ok, corps), permis={"berger-contrat"})
    dire(len(lignes) == 2 and lignes[1][0], f"contrat (12) Codex : namespace mcp__<serveur> d'un serveur de son `mcp =` (outils function) = connu, vert — {lignes}")
    wx(["-C", str(t), *COUPE], faux_codex("codex-mcp", temoin_ok, corps))
    dire(len(lignes) == 2 and not lignes[1][0] and "namespace:mcp__berger_contrat" in lignes[1][1], "contrat (12) Codex : namespace MCP sans `mcp =` = rouge, nommé")
    for ns, quoi in (({**mcp, "name": "mcp__autre"}, "d'un serveur hors de son `mcp =`"),
                     ({**mcp, "tools": [{"type": "web_search"}]}, "qui porte un outil non function (web_search)"),
                     ({**mcp, "tools": [{"type": "function", "name": "a", "tools": [{"type": "function", "name": "b"}]}]}, "à outils imbriqués")):
        wx(["-C", str(t), *COUPE], faux_codex("codex-mcp-ko", temoin_ok, json.dumps({"tools": [{"type": "function", "name": "exec_command"}, ns]})), permis={"berger-contrat"})
        dire(len(lignes) == 2 and not lignes[1][0] and "inconnu" in lignes[1][1], f"contrat (12) Codex : namespace MCP {quoi} = rouge — {lignes[1:]}")
    wx(["-C", str(t), *COUPE], str(faux), connus={**CX, "exacte": False, "version": "9.9.8", "raison": "pas de liste fermée pour codex 9.9.9 — comparée à celle de 9.9.8"})
    dire(len(lignes) == 2 and not lignes[1][0] and "pas de liste fermée" in lignes[1][1], "contrat (12) Codex : liste d'une autre version = rouge")
    wx(["-C", str(t), *COUPE], str(faux), connus={**CX, "web": None, "outils": None, "exacte": False, "raison": "pas de liste fermée pour codex 9.9.9"})
    dire(len(lignes) == 2 and not lignes[0][0] and not lignes[1][0], "contrat (12) Codex : aucune liste fermée = rouge (témoin et contrôle)")
    # forme RÉELLE mesurée sur codex 0.165.0 (31/10, 13 modèles, faux fournisseur local) : function nommés, custom apply_patch,
    # tool_search (type seul), namespace multi_agent_v1 et mcp__<serveur>, web_search SANS nom — témoin vu, puis tout connu = vert
    fn = lambda *n: [{"type": "function", "name": x, "strict": False, "parameters": {}} for x in n]
    reel = (fn("exec_command", "write_stdin", "list_mcp_resources", "list_mcp_resource_templates", "read_mcp_resource", "request_user_input", "view_image")
            + [{"type": "namespace", "name": "mcp__berger_contrat", "tools": fn("echo", "gros", "piege", "sonde", "web")}]
            + fn("get_goal", "create_goal", "update_goal") + [{"type": "custom", "name": "apply_patch"}, {"type": "tool_search"}])
    wx(["-C", str(t), *COUPE], faux_codex("codex-reel", json.dumps({"tools": reel + [{"type": "web_search", "external_web_access": False}]}), json.dumps({"tools": reel})),
       connus=cx, permis={"berger-contrat"})
    dire(len(lignes) == 3 and all(b for b, _ in lignes), f"contrat (12) Codex : forme réelle de codex 0.165.0 avec la liste livrée = vert (défaut et modèle témoin) — {lignes}")
    sa = reel + [{"type": "namespace", "name": "multi_agent_v1", "tools": fn("close_agent", "resume_agent", "send_input", "spawn_agent", "wait_agent")}]
    wx(["-C", str(t), *COUPE], faux_codex("codex-reel-sa", json.dumps({"tools": sa + [{"type": "web_search"}]}), json.dumps({"tools": sa})), connus=cx, permis={"berger-contrat"})
    dire(len(lignes) == 3 and lignes[0][0] and not lignes[1][0] and "multi_agent_v1" in lignes[1][1],
         f"contrat (12) Codex : sous-agents (namespace multi_agent_v1) restés malgré le réglage = rouge, nommés — {lignes[1:2]}")

    # FIXTURE RÉELLE (31/10, tests/fixtures/codex-0.165.0-requetes.json) : modèle par défaut gpt-6.1-sol (code_mode_only) SANS
    # champ tools, ses outils dans input[] de type additional_tools, aucun outil web ; gpt-5.5 (modèle témoin de la liste) : tools,
    # web_search sans le réglage. Le faux codex rejoue ces corps : -m <modèle témoin> ou modèle par défaut, avec ou sans le réglage.
    FX = json.loads((SRC / "tests/fixtures/codex-0.165.0-requetes.json").read_text())["requetes"]
    def faux_fixture(nom, corps):
        f = t / nom
        f.write_text("#!/usr/bin/env python3\nimport json, re, sys, urllib.request\na = sys.argv[1:]\n"
                     "c = [a[k + 1] for k in range(len(a) - 1) if a[k] == '-c']\n"
                     "base = next(re.match(r'model_providers\\.[\\w-]+\\.base_url=\"(.*)\"$', x).group(1) for x in c if re.match(r'model_providers\\.[\\w-]+\\.base_url=', x))\n"
                     "m = a[a.index('-m') + 1] if '-m' in a else 'defaut'\n"
                     "cle = m + ('-avec-reglage' if 'web_search=\"disabled\"' in c else '-sans-reglage')\n"
                     f"corps = {json.dumps(corps)!r}\n"
                     "for b in (json.dumps({'model': m, 'input': 'titre'}), json.dumps(json.loads(corps).get(cle, {}))):\n"
                     "    rq = urllib.request.Request(base + '/responses', data=b.encode(), headers={'content-type': 'application/json'})\n"
                     "    try: urllib.request.urlopen(rq, timeout=10)\n    except Exception: pass\n"
                     "sys.exit(1)\n")
        f.chmod(0o755); return str(f)
    dire(cx.get("modele_temoin") == "gpt-5.5", f"liste fermée codex 0.165.0 : modèle témoin nommé (gpt-5.5) — {cx.get('modele_temoin')!r}")
    wx(["-C", str(t), "-p", "a", *COUPE, *SOUS_AGENTS], faux_fixture("codex-fixture", FX), connus=cx)
    dire(len(lignes) == 3 and lignes[0][0] and "gpt-5.5" in lignes[0][1] and lignes[2][0] and "gpt-5.5" in lignes[2][1]
         and not lignes[1][0] and "défaut" in lignes[1][1] and "namespace:collaboration/function:spawn_agent" in lignes[1][1] and "clock" not in lignes[1][1],
         f"contrat (12) Codex : requêtes RÉELLES de 0.165.0 avec les réglages de Berger = témoin vu (gpt-5.5), gpt-5.5 vert, défaut ROUGE (collaboration, "
         f"qu'aucun réglage ne retire, nommé ; clock retiré) — {lignes}")
    sans_collab = {**FX, **{k: {**v, "input": [({**i, "tools": [x for x in i["tools"] if x.get("name") != "collaboration"]} if i.get("type") == "additional_tools" else i)
                                               for i in v["input"]]} for k, v in FX.items() if k.startswith("defaut")}}
    wx(["-C", str(t), "-p", "a", *COUPE, *SOUS_AGENTS], faux_fixture("codex-fixture-sc", sans_collab), connus=cx)
    dire(len(lignes) == 3 and all(b for b, _ in lignes), f"contrat (12) Codex : le même relevé sans collaboration = vert sur les deux modèles — {lignes}")
    d = C.ids_requete(FX["defaut-avec-reglage"])
    dire(isinstance(d, list) and (("namespace", "functions"), ("custom", "exec")) in d and (("namespace", "collaboration"), ("function", "spawn_agent")) in d,
         "contrat (12) Codex : outils de additional_tools lus en paires (type, nom), imbriqués compris")
    dire(C.ids_requete({"input": [{"type": "message", "role": "user"}]}) is None and C.outils_codex is not None,
         "contrat (12) Codex : requête sans tools ni additional_tools : aucune liste d'outils (annexe)")
    for item, quoi in (({"type": "additional_tools"}, "sans ses outils"), ({"type": "additional_tools", "tools": []}, "aux outils vides"),
                       ({"type": "additional_tools", "tools": [{"type": "namespace", "name": "functions"}]}, "dont un namespace n'a pas d'outils"),
                       ({"type": "additional_tools", "tools": [{"type": "function"}]}, "dont un outil n'a pas de nom")):
        corps = {"input": [item, {"type": "message", "role": "user"}]}
        wx(["-C", str(t), *COUPE], faux_codex("codex-add-mal", temoin_ok, json.dumps(corps)))
        dire(len(lignes) == 2 and not lignes[1][0] and "non mesurable" in lignes[1][1], f"contrat (12) Codex : additional_tools {quoi} = NON mesurable, rouge — {lignes[1:]}")
    for outil, nomme in (({"type": "web_search"}, "'web_search'"), ({"type": "namespace", "name": "functions", "tools": [{"type": "function", "name": "web_fetch"}]}, "web_fetch")):
        corps = {"input": [{"type": "additional_tools", "tools": [outil]}]}
        wx(["-C", str(t), *COUPE], faux_codex("codex-add-web", temoin_ok, json.dumps(corps)), connus=cx)
        dire(len(lignes) == 3 and not lignes[1][0] and nomme in lignes[1][1], f"contrat (12) Codex : outil web dans additional_tools = rouge, nommé {nomme} — {lignes[1:]}")
    wx(["-C", str(t), "-p", "a", *COUPE], faux_fixture("codex-fixture-sans-web", {**FX, "gpt-5.5-sans-reglage": FX["gpt-5.5-avec-reglage"]}), connus=cx)
    dire(len(lignes) == 3 and not lignes[0][0] and "web_search" in lignes[0][1], f"contrat (12) Codex : modèle témoin sans web_search = témoin rouge — {lignes[:1]}")
    wx(["-C", str(t), "-p", "a", *COUPE], faux_fixture("codex-fixture-web-temoin", {**sans_collab, "gpt-5.5-avec-reglage": FX["gpt-5.5-sans-reglage"]}), connus=cx)
    dire(len(lignes) == 3 and lignes[1][0] and not lignes[2][0] and "web_search" in lignes[2][1],
         f"contrat (12) Codex : web_search présent AVEC le réglage sur le modèle témoin = liste fermée rouge — {lignes[2:]}")
    dire(C.avec_modele(["-C", "/x", "-m", "autre", "-p", "a"], "gpt-5.5") == ["-C", "/x", "-p", "a", "-m", "gpt-5.5"],
         "contrat (12) Codex : le modèle témoin remplace un -m déjà présent")

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    lc = json.loads((SRC / "tests/outils-connus/codex-0.165.0.json").read_text())
    for v, mt, quoi in (("3.0.1", "", "vide"), ("3.0.2", 5, "qui n'est pas un texte"), ("3.0.3", "gpt 5", "avec un espace"), ("3.0.4", "-c", "qui commence par un tiret")):
        (d / f"codex-{v}.json").write_text(json.dumps({**lc, "version": v, "modele_temoin": mt})); n = C.charger_connus("codex", v, d)
        dire(n["outils"] is None and "mal formée" in n["raison"], f"liste fermée codex au modèle témoin {quoi} = refusée (mal formée) — {n['raison']}")

sys.exit(1 if ko else 0)
