#!/usr/bin/env python3
"""Équivalence des verbes des équipes (modulaire, lot 4c, docs/plans/2026-10-27-modulaire-spec.md § Tests « Équivalence des sorties ») :
`equipe` (ouvrir, fermer, liste, domaine, domaines, go), `projet` (ouvrir, fermer, liste) et `crochet-equipe`, mesurés sur une installation JETABLE,
puis comparés à ce que mesurait `main` avant le déplacement (tests/attendus/equivalence-equipes.json).
Pour chaque scénario : code de sortie, sortie standard, dernière ligne d'erreur, fichiers écrits (dossiers d'agents, consignes régénérées par empreinte,
equipes/ : registre des projets, sites permis, go, verrou ; bibliothèque : dossiers de projet et archives ; historique d'équipe chez le chef ; échanges ;
validations), copies des développeurs (branche, forge), appels à Herdr (un faux Herdr à état par BERGER_HERDR) et ce que le cœur aurait lancé
(demarrer_agent, espace et parler relevés au lieu d'être faits, des deux côtés : moteurs.args_moteur, le lancement strict). Refus mesurés : rôle (chef,
coordinateur, membres), go absent ou seulement demandé, plafond [missions] max, sujet et nom invalides, modèle non permis, dépôt = installation, copie
avec du travail non commité, checklist non finie ; transport privé (texte positionnel, JSON invalide, imbriqué, UTF-8, plus d'un Mio) ; entrée du
crochet illisible (JSON invalide, entier de 5 000 chiffres, imbrication trop profonde, non UTF-8). Deux voies : la ligne de commande et le courtier,
appelé directement (droits d'équipe : chef, coordinateur, non-membre ; demandes de validation de domaine et de go), qui lance berger en sous-processus.
L'instantané garde CHAQUE fichier : un nom qui, normalisé (dates, heures), en rejoint un autre (archives horodatées) donne une LISTE ordonnée de ses
fichiers, chacun avec son contenu (leçon du renvoi n° 89) ; un dossier vide compte (« <dossier> »).
Ce qui varie d'une exécution à l'autre est normalisé (chemin de l'installation, dates, heures, identifiants, numéros de ligne). « commande inconnue » : la
PREMIÈRE ligne d'erreur est relevée (la suite est l'aide, qui gagne les lignes d'AIDE des familles : point 4 du correctif contrat).
Usage : python3 tests/equivalence-equipes.py               mesure ce dépôt et compare (0 = identique)
        python3 tests/equivalence-equipes.py --mesurer <source>   imprime la mesure d'un autre arbre (ex. un `git archive` de main)
        python3 tests/equivalence-equipes.py --produire <source> <fichier>   écrit la mesure de <source> dans <fichier> (les attendus)
Les attendus (tests/attendus/equivalence-equipes.json) ont été produits sur main dcb6d03, avant le lot 4c :
        d=$(mktemp -d) && git archive dcb6d03 | tar -x -C "$d" && python3 tests/equivalence-equipes.py --produire "$d" tests/attendus/equivalence-equipes.json
Refaits le 30/10/2026 sur dcb6d03 + le code du lot 1 de web-integre (WebFetch et WebSearch refusés aux stricts) : même commande, après
        git diff <base>..<branche> -- bin/berger bin/moteurs/codex.py | (cd "$d" && patch -p1) ; seul écart : ces deux refus dans les réglages.
Complétés le 03/11/2026 (accord-bypass) à la main : seul ajout, le .claude/settings.local.json (accord du mode bypass) des agents
régénérés dans « equipe domaine ajouter », « equipe ouvrir » et « equipe fermer » ; tout le reste inchangé.
Le 04/11/2026 (ci-github) : « /tmp/claude-1000 » devient « /tmp/claude-<UID> » (l'uid du compte qui les a produits), comme le fait normaliser."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import hashlib, json, os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ATTENDU = SRC / "tests/attendus/equivalence-equipes.json"

# Un faux Herdr À ÉTAT (espaces, onglets, panneaux) : chaque appel est tracé ; ce qu'il ne connaît pas rend {"result": {}}.
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
etat = Path(os.environ["FAUX_ETAT"]); d = json.loads(etat.read_text()) if etat.exists() else {"n": 0, "ws": [], "tabs": {}, "panes": {}}
a = sys.argv[1:]
with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(a) + "\n")
def opt(n): return a[a.index(n) + 1] if n in a else None
def neuf(p): d["n"] += 1; return f"{p}{d['n']}"
r = {}
if a[:2] == ["pane", "get"]:
    p = d["panes"].get(a[2]); r = {"pane": {**p, "pane_id": a[2], "agent_status": "idle"}} if p else {}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w} for w in d["ws"]]}
elif a[:2] == ["tab", "list"]: r = {"tabs": [{"tab_id": t} for t, w in d["tabs"].items() if w == opt("--workspace")]}
elif a[:2] == ["tab", "create"]:
    t = neuf("t"); p = neuf("p"); d["tabs"][t] = opt("--workspace"); d["panes"][p] = {"tab_id": t, "workspace_id": opt("--workspace")}
    r = {"tab": {"tab_id": t}, "root_pane": {"pane_id": p}}
elif a[:2] == ["pane", "split"]:
    base = d["panes"].get(opt("--pane")) or {}; p = neuf("p"); d["panes"][p] = dict(base); r = {"pane": {"pane_id": p}}
elif a[:2] == ["pane", "list"]: r = {"panes": [{"pane_id": p, **v} for p, v in d["panes"].items() if v.get("workspace_id") == opt("--workspace")]}
elif a[:2] == ["pane", "close"]: d["panes"].pop(a[2], None)
elif a[:2] == ["tab", "close"]:
    d["tabs"].pop(a[2], None); d["panes"] = {p: v for p, v in d["panes"].items() if v.get("tab_id") != a[2]}
elif a[:2] == ["workspace", "close"]:
    d["ws"] = [w for w in d["ws"] if w != a[2]]; d["panes"] = {p: v for p, v in d["panes"].items() if v.get("workspace_id") != a[2]}
elif a[:2] == ["agent", "list"]: r = {"agents": []}
etat.write_text(json.dumps(d)); print(json.dumps({"result": r}))
'''

# La ligne de commande, dans le processus : le démarrage d'un moteur, l'espace complet, la remise d'un message et l'API Herdr (fonctions du cœur, des
# deux côtés) sont relevés au lieu d'être faits ; le relevé du démarrage garde ce que le cœur aurait lancé (moteurs.args_moteur : le lancement strict).
LANCEUR = r'''
import json, os, sys
src = sys.argv[1]; g = {"__name__": "essai", "__file__": src}
exec(compile(open(src).read(), src, "exec"), g)
def trace(*x):
    with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["@"] + [str(v) for v in x]) + "\n")
def demarrer(a, m, p, reprise=None):
    try: lance = g["moteurs"].args_moteur(a, m)
    except BaseException as e: lance = f"{type(e).__name__}: {e}"
    trace("demarrer", a, m, p, json.dumps(lance)); return m
def espace(a):
    ids = g["herdr_ids"](a); ids.update({"workspace": f"ws-{a}", "agents": {g["conf"](a)["moteur"]: f"pe-{a}"}})
    (g["dossier"](a) / ".herdr.json").write_text(json.dumps(ids)); trace("espace", a)
def api(methode, params, strict=False):
    trace("api", methode, json.dumps(params, ensure_ascii=False)); return {}
g["demarrer_agent"] = demarrer; g["espace"] = espace; g["herdr_api"] = api
g["parler"] = lambda a, message, moteur=None, de=None: trace("parler", a, moteur, de, message)
g["time"].sleep = lambda s: None
g["main"](sys.argv[2:])
'''

# Le courtier, appelé directement (comme tests/hierarchie-equipe.py) : ses droits d'équipe, puis berger en sous-processus ; attend la fin de ses fils.
APPEL = r'''
import json, runpy, sys, threading, time
g = runpy.run_path(sys.argv[1], run_name="essai")
agent, req = sys.argv[2], json.loads(sys.argv[3])
d = g["AGENTS"] / agent / "courrier"; (d / "encours").mkdir(parents=True, exist_ok=True)
f = d / "encours" / "1.json"; f.write_text(json.dumps(req))
g["traiter"](agent, f, {})
for _ in range(1800):
    r = d / "reponses" / "1.json"
    if r.exists(): print(r.read_text()); r.unlink(); break
    time.sleep(0.1)
for th in threading.enumerate():
    if th is not threading.main_thread(): th.join(300)
'''

AGENTS = {
    "chef": "moteur = claude\n",
    "coord": "moteur = claude\n",
    "intrus": "moteur = claude\noutils = equipe:p\n",
}
GENERES = ("AGENTS.md", "BERGER.md", "CLAUDE.md", ".consigne-systeme.md", ".reglages-claude.json", ".mcp.json", "config.toml", "hooks.json")
HORS = ("courrier", ".transport")                     # ce que le courtier range pour lui (requêtes, réponses) : hors de ce que les verbes écrivent


UID = os.getuid()


def normaliser(texte, t):
    texte = str(texte).replace(str(t), "<T>")
    # Le dossier temporaire commun de Claude porte l'uid du compte (bin/berger TMP_COMMUN) : 1000 sur le portable, 1001 pour « runner » sur GitHub.
    texte = re.sub(rf"/tmp/claude-{UID}(?!\d)", "/tmp/claude-<UID>", texte)
    texte = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>", texte)
    texte = re.sub(r"\d{8}-\d{6}-\d{6}", "<HORODATAGE>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}[T _]\d{2}:?\d{2}(:\d{2})?", "<DATE-HEURE>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}", "<DATE>", texte)
    texte = re.sub(r"\b\d{2}:\d{2}(:\d{2})?\b", "<HEURE>", texte)
    # Python 3.11 et 3.14 : même refus JSON, formulation de la limite de pile différente.
    texte = re.sub(r"RecursionError: (?:maximum recursion depth exceeded|Stack overflow \(used (?:\d+|<N>) kB\))(?= while decoding a JSON array from a unicode string)",
                   "RecursionError: <limite de pile>", texte)
    texte = re.sub(r"\(used \d+ kB\)", "(used <N> kB)", texte)
    texte = re.sub(r"line \d+", "line <N>", texte)
    texte = re.sub(r"/tmp/[^\s\"']*herdr-absent-\d+\.sock", "<SOCKET>", texte)
    return re.sub(r"script-[A-Za-z0-9_]{8}", "script-<X>", texte)


def contenu(f, t):
    """Le texte normalisé d'un fichier ; les consignes et réglages régénérés (longs, du cœur des deux côtés) : leur empreinte."""
    x = normaliser(f.read_text(errors="replace"), t)
    if f.name in GENERES or len(x) > 4000: return "sha256:" + hashlib.sha256(x.encode()).hexdigest()[:16]
    return x


def _ranger(out, cle, val):
    """Chaque clé normalisée porte la LISTE ordonnée de ses fichiers (renvoi n° 89) : deux archives horodatées au même nom normalisé restent deux."""
    out.setdefault(cle, []).append(val)


def git(d, *a, **kw):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True, **kw)


def fichiers(t):
    """Ce que les verbes des équipes écrivent : dossiers d'agents (sauf le courrier du courtier), equipes/, la bibliothèque, les échanges, les validations ;
    les copies des développeurs (présence, branche, origine) et les branches de la forge."""
    out = {}
    for racine in ("agents", "equipes", "bibliotheque"):
        base = t / racine
        for f in sorted(base.rglob("*")) if base.is_dir() else []:
            r = f.relative_to(t)
            if racine == "agents" and len(r.parts) > 2 and r.parts[2] in HORS: continue
            if f.is_dir():
                if not any(f.iterdir()): _ranger(out, normaliser(str(r) + "/", t), "<dossier>")
            elif f.is_file(): _ranger(out, normaliser(str(r), t), contenu(f, t))
    e = t / "courtier/echanges.jsonl"; out["courtier/echanges.jsonl"] = [normaliser(e.read_text(), t) if e.exists() else None]
    v = t / "courtier/validations"
    for f in sorted(v.glob("*.json")) if v.is_dir() else []: _ranger(out, f"courtier/validations/{f.name}", normaliser(f.read_text(), t))
    c = t / "copies"
    for d in sorted(c.iterdir()) if c.is_dir() else []:
        _ranger(out, f"copies/{d.name}", [git(d, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), normaliser(git(d, "remote", "get-url", "origin").stdout.strip(), t),
                                          git(d, "status", "--porcelain").stdout.strip()])
    out["forge"] = [git(t / "forge.git", "branch", "--format=%(refname:short)").stdout.split()]
    return out


def ajouts(ancien, neuf):
    """Ce qu'un scénario ajoute à courtier/echanges.jsonl : la fin du fichier, SI son ancien contenu est resté identique au début ; sinon le fichier
    entier, marqué (renvoi n° 93 : une ancienne ligne altérée fait un écart et ne devient jamais, muette, la référence du scénario suivant)."""
    ancien, neuf = ancien or "", neuf or ""
    return neuf[len(ancien):] if neuf.startswith(ancien) else {"début du journal modifié": neuf}


def controler_journal():
    """Renvoi n° 93 : une ANCIENNE ligne du journal altérée, puis la même ligne neuve ajoutée, doit faire un écart (jamais le même relevé qu'un ajout
    correct). → la liste des défauts (vide = l'altération se voit)."""
    ancien = '{"de": "a", "texte": "ancien"}\n'; ligne = '{"de": "b", "texte": "neuf"}\n'
    correct, altere = ajouts(ancien, ancien + ligne), ajouts(ancien, ancien.replace("ancien", "ALTERE") + ligne)
    return [] if correct != altere else ["une ancienne ligne altérée du journal des échanges ne fait pas d'écart"]


def controler_instantane():
    """Leçon du renvoi n° 89 : l'instantané garde CHAQUE fichier, même quand la normalisation rend leurs noms identiques (archives horodatées) ;
    un fichier antérieur modifié ou supprimé fait un écart. → la liste des défauts (vide = l'instantané voit tout)."""
    defauts = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td); h = t / "agents/chef/historique/equipe"; h.mkdir(parents=True)
        a, b = h / "demo-2026-10-29_1000", h / "demo-2026-10-29_1100"
        for x, texte in ((a, "premier"), (b, "second")): x.mkdir(); (x / "CHECKLIST.md").write_text(texte)
        depart = fichiers(t)
        (a / "CHECKLIST.md").write_text("premier, modifié")
        if fichiers(t) == depart: defauts.append("une archive antérieure modifiée ne fait pas d'écart")
        (a / "CHECKLIST.md").unlink()
        if fichiers(t) == depart: defauts.append("une archive antérieure supprimée ne fait pas d'écart")
    return defauts


def controler_uid():
    """CI de 5cf3f0e : les attendus, pris sous l'uid 1000, portaient « /tmp/claude-1000 » ; sous l'uid 1001 du runner GitHub, 8 scénarios en écart.
    Les attendus ne portent aucun uid en clair ; normaliser ne remplace QUE l'uid du compte (un autre uid reste un écart). → la liste des défauts."""
    defauts = []
    if re.search(r"/tmp/claude-\d", ATTENDU.read_text(encoding="utf-8")): defauts.append("un uid en clair (/tmp/claude-<chiffres>) dans les attendus")
    if normaliser(f"Read(//tmp/claude-{UID}/**)", "/x") != "Read(//tmp/claude-<UID>/**)": defauts.append("l'uid du compte n'est pas normalisé")
    for autre in (UID + 1, int(f"{UID}0")):
        if "<UID>" in normaliser(f"/tmp/claude-{autre}", "/x"): defauts.append(f"un autre uid ({autre}) est normalisé comme celui du compte")
    return defauts


def ecarts(a, m, chemin=""):
    """Chaque écart, jusqu'à la feuille qui diffère : (chemin, avant, après), un texte montré autour de son PREMIER caractère différent (un long
    fichier tronqué au début cachait l'écart : la CI de 5cf3f0e n'en montrait que les 400 premiers caractères)."""
    if isinstance(a, dict) and isinstance(m, dict):
        return [e for k in sorted(set(a) | set(m), key=str) if a.get(k, "∅") != m.get(k, "∅") for e in ecarts(a.get(k, "∅"), m.get(k, "∅"), f"{chemin} › {k}")]
    if isinstance(a, list) and isinstance(m, list) and len(a) == len(m):
        return [e for i, (x, y) in enumerate(zip(a, m)) if x != y for e in ecarts(x, y, f"{chemin}[{i}]")]
    if isinstance(a, str) and isinstance(m, str):
        i = next((i for i, (x, y) in enumerate(zip(a, m)) if x != y), min(len(a), len(m))); d = max(0, i - 80)
        montrer = lambda x: ("…" if d else "") + json.dumps(x[d:i + 120], ensure_ascii=False) + ("…" if len(x) > i + 120 else "")
        return [(f"{chemin} (caractère {i})", montrer(a), montrer(m))]
    return [(chemin, json.dumps(a, ensure_ascii=False)[:400], json.dumps(m, ensure_ascii=False)[:400])]


def mesurer(src):
    src = Path(src).resolve(); resultats = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        _produit.copier(src, t, ("bin", "courtier", "commun"))
        (t / "coffre.json").write_text("{}")
        # la forge et le dépôt du chef : une spec poussée sur main (le go la lit sur la forge)
        forge, depot = t / "forge.git", t / "depot"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)], check=True)
        subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True, check=True)
        (depot / "docs/plans").mkdir(parents=True)
        (depot / "docs/plans/demo-spec.md").write_text("# Demo : un bouton\n\nConstat. Comportement. Tests.\n")
        (depot / "docs/plans/vide-spec.md").write_text("  \n")
        git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
        (t / "config.toml").write_text(
            f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n[missions]\nmax = 2\nmodeles_claude = ["sonnet"]\n\n'
            f'[equipes.p]\nchef_projet = "chef"\ncoordinateur = "coord"\ndepot = "{depot}"\ncopies = "{t}/copies"\nprefixe = "p/"\n'
            f'moteur = "claude"\nports = [5301, 5302]\n'
            "crochet_ecriture = '''python3 -c \"import json, sys; d = json.load(sys.stdin); print(json.dumps({'vu': d['tool_input'].get('file_path'), 'cwd': d['cwd']}))\"'''\n\n"
            f'[equipes.inst]\nchef_projet = "chef"\ncoordinateur = "coord"\ndepot = "{t}"\n')
        for a, c in AGENTS.items():
            d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nheures = aucune\n{c}")
        # un développeur déjà ouvert (sa mission, sa demande de fusion renvoyée, sa copie) : la liste, le plafond et le crochet le voient
        (t / "copies/p-ancien/src").mkdir(parents=True)
        d = t / "agents/p-ancien"; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = P · ancien\nheures = aucune\nmoteur = claude\nmur = strict\nprojet = p\nsujet = ancien\n"
                                      f"copie = {t}/copies/p-ancien\nbranche = p/ancien\nport = 0\n")
        (d / "MISSION.md").write_text("# Mission confiée par chef — 2026-10-29 09:00\nmoteur : claude\n\nfaire x\n")
        (d / "CHECKLIST.md").write_text("# x\n- [x] lu\n- [ ] codé\n⚠ Bloqué : une question\n")
        dem = t / "equipes/p/demandes"; dem.mkdir(parents=True)
        (dem / "ancien.json").write_text(json.dumps({"sujet": "ancien", "agent": "p-ancien", "etat": "renvoyée", "renvois": 1,
                                                     "portes": {"verify": {"etat": "vert"}, "pret": {"etat": "rouge"}}}))
        (t / "faux").mkdir(); herdr = t / "faux/herdr"; herdr.write_text(FAUX_HERDR); herdr.chmod(0o755)
        (t / "faux/notify-send").write_text("#!/bin/sh\nexit 0\n"); (t / "faux/notify-send").chmod(0o755)
        trace = t / "faux/trace.jsonl"
        (t / "tmp-agents").mkdir(mode=0o700)               # le temporaire des agents DANS l'installation jetable (normalisé) : le lanceur des suites en pose un à lui
        env = dict(os.environ, BERGER_DIR=str(t), HOME=str(t), PATH=f"{t}/faux:{os.environ['PATH']}", BERGER_NOTIFY_SEND=str(t / "faux/notify-send"),
                   BERGER_TMP_AGENTS=str(t / "tmp-agents"), BERGER_HERDR=str(herdr), FAUX_ETAT=str(t / "faux/etat.json"), FAUX_TRACE=str(trace),
                   GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.invalid")
        for k in ("BERGER_AGENT", "AGENT_PANNE"): env.pop(k, None)
        (t / "faux/etat.json").write_text(json.dumps({"n": 0, "ws": ["ws-chef", "ws-coord"], "tabs": {"t-chef": "ws-chef"},
                                                     "panes": {"pe-chef": {"tab_id": "t-chef", "workspace_id": "ws-chef"}}}))
        (t / "agents/chef/.herdr.json").write_text(json.dumps({"workspace": "ws-chef", "agents": {"claude": "pe-chef"}}))
        (t / "agents/coord/.herdr.json").write_text(json.dumps({"workspace": "ws-coord"}))
        avant = {"fichiers": fichiers(t)}

        def noter(nom, r):
            appels = [normaliser(l, t) for l in trace.read_text().splitlines()] if trace.exists() else []
            trace.unlink(missing_ok=True)
            apres = fichiers(t)
            ecrits = {k: v for k, v in apres.items() if avant["fichiers"].get(k, "∅") != v}
            if "courtier/echanges.jsonl" in ecrits:                        # les lignes ajoutées
                ecrits["courtier/echanges.jsonl"] = ajouts((avant["fichiers"].get("courtier/echanges.jsonl") or [""])[0], apres["courtier/echanges.jsonl"][0])
            ecrits.update({k: "(supprimé)" for k in avant["fichiers"] if k not in apres})
            avant["fichiers"] = apres
            err = [l for l in r.stderr.splitlines() if l.strip()]
            fin = err[0] if err and err[0].startswith("commande inconnue : ") else (err[-1] if err else "")
            resultats.append({"scenario": nom, "code": r.returncode, "stdout": normaliser(r.stdout, t),
                              "stderr_fin": normaliser(fin, t), "fichiers_ecrits": ecrits, "herdr_et_lancements": appels})

        def cli(nom, *argv, stdin=None):
            r = subprocess.run([sys.executable, "-c", LANCEUR, str(t / "bin/berger"), *argv], input=stdin, env=env, capture_output=True, timeout=600)
            r.stdout, r.stderr = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace"); noter(nom, r)

        def courtier(nom, agent, verbe, *args):
            req = json.dumps({"outil": "equipe", "verbe": verbe, "args": list(args)})
            r = subprocess.run([sys.executable, "-c", APPEL, str(t / "courtier/courtier"), agent, req], env=env, capture_output=True, text=True, timeout=900)
            try: rep = json.loads(r.stdout)
            except ValueError: rep = {"illisible": r.stdout[-200:]}
            r.stdout = json.dumps(rep, ensure_ascii=False, sort_keys=True); noter(nom, r)

        prive = lambda *v: json.dumps(list(v)).encode()
        eq = lambda nom, *v: cli(nom, "--stdin", stdin=prive("equipe", *v))
        pj = lambda nom, *v: cli(nom, "--stdin", stdin=prive("projet", *v))
        # 1. formes et transport privé (equipe et projet exigent --stdin)
        cli("equipe en texte positionnel", "equipe", "liste", "p")
        cli("projet en texte positionnel", "projet", "liste")
        eq("equipe sans sous-commande")
        eq("equipe liste sans projet", "liste")
        eq("equipe liste, projet inconnu", "liste", "inconnu")
        eq("equipe ouvrir, arguments manquants", "ouvrir", "p")
        eq("equipe fermer, arguments manquants", "fermer", "p")
        eq("equipe, sous-commande inconnue", "changer", "p")
        eq("equipe domaine, forme trop longue", "domaine", "p", "ajouter", "a.org", "b.org")
        cli("transport : JSON invalide", "--stdin", stdin=b"[equipe")
        cli("transport : pas un tableau de textes", "--stdin", stdin=b'{"equipe": 1}')
        cli("transport : verbe privé imbriqué", "--stdin", stdin=prive("--stdin", "equipe"))
        cli("transport : UTF-8 requis", "--stdin", stdin=b'["equipe", "liste", "\xff"]')
        cli("transport : plus d'un Mio", "--stdin", stdin=b"[" + b" " * (1024 * 1024) + b"]")
        # 2. liste et sites permis (lectures), puis leurs écritures
        eq("equipe liste (développeur, demande renvoyée, avertissement)", "liste", "p")
        # renvoi n° 93 : une donnée d'équipe illisible sort telle qu'avant (l'erreur du lecteur), jamais « famille écartée »
        demande = (dem / "ancien.json").read_bytes()
        for cas, octets in (("« { »", b"{"), ("pas un objet", b"[1]"), ("trop imbriquée", b"[" * 100000 + b"]" * 100000),
                            ("non UTF-8", b'{"etat": "\xff"}'), ("renvois illisibles", b'{"renvois": "trois"}')):
            (dem / "ancien.json").write_bytes(octets); eq(f"equipe liste, demande de fusion illisible : {cas}", "liste", "p")
        (dem / "ancien.json").write_bytes(demande)
        (d / "CHECKLIST.md").write_bytes(b"# x\n- [ ] \xff\n")
        eq("equipe liste, checklist du développeur non UTF-8", "liste", "p")
        (d / "CHECKLIST.md").write_text("# x\n- [x] lu\n- [ ] codé\n⚠ Bloqué : une question\n")
        eq("equipe liste, dépôt = installation (refusé)", "liste", "inst")
        eq("equipe domaines, aucun", "domaines", "p")
        (t / "equipes/p/domaines").write_bytes(b"exemple.org\n\xff\n")
        eq("equipe domaines, liste non UTF-8", "domaines", "p")
        (t / "equipes/p/domaines").unlink()
        for cas, octets in (("« { »", b"{"), ("trop imbriqué", b"[" * 100000 + b"]" * 100000), ("non UTF-8", b'{"\xff": 1}')):
            (t / "equipes/p/projets.json").write_bytes(octets); pj(f"projet liste, projets.json illisible : {cas}", "liste")
        (t / "equipes/p/projets.json").unlink()
        eq("equipe domaine, nom inexact", "domaine", "p", "ajouter", "*.joker.org")
        eq("equipe domaine, action inconnue", "domaine", "p", "changer", "exemple.org")
        eq("equipe domaine, projet inconnu", "domaine", "inconnu", "ajouter", "exemple.org")
        eq("equipe domaine ajouter --essai (aperçu seul)", "domaine", "p", "ajouter", "exemple.org", "--essai")
        eq("equipe domaine ajouter (écrit, échange, journal, régénère)", "domaine", "p", "ajouter", "exemple.org", "--par", "coord")
        eq("equipe domaine ajouter, déjà permis", "domaine", "p", "ajouter", "exemple.org")
        eq("equipe domaines, un site", "domaines", "p")
        eq("equipe domaine retirer, absent", "domaine", "p", "retirer", "absent.org")
        with open(t / "equipes/p/domaines", "a") as f: f.write("*.joker.org\nexemple.org\nautre.org\n")
        eq("equipe domaines, lignes retouchées à la main (ignorées)", "domaines", "p")
        eq("equipe domaine retirer (écrit, régénère)", "domaine", "p", "retirer", "exemple.org", "--par", "coord")
        # 3. le go du propriétaire
        eq("equipe go par un non-membre (refusé)", "go", "p", "demo", "1", "docs/plans/demo-spec.md", "--par", "intrus")
        eq("equipe go, sujet invalide", "go", "p", "Demo!", "1", "docs/plans/demo-spec.md")
        eq("equipe go, cas invalide", "go", "p", "demo", "9", "docs/plans/demo-spec.md")
        eq("equipe go, chemin de spec invalide", "go", "p", "demo", "1", "../x.md")
        eq("equipe go, spec introuvable", "go", "p", "demo", "1", "docs/plans/absente.md")
        eq("equipe go, spec vide", "go", "p", "demo", "1", "docs/plans/vide-spec.md")
        eq("equipe go, inscrire sans demande (empreinte inconnue)", "go", "p", "demo", "1", "docs/plans/demo-spec.md")
        eq("equipe go --essai (marqué « demandé »)", "go", "p", "demo", "1", "docs/plans/demo-spec.md", "--essai", "--par", "chef")
        eq("equipe go inscrit par le propriétaire", "go", "p", "demo", "1", "docs/plans/demo-spec.md")
        eq("equipe go, déjà inscrit", "go", "p", "demo", "1", "docs/plans/demo-spec.md")
        eq("equipe go --essai d'un autre sujet (secu)", "go", "p", "secu", "1,4", "docs/plans/demo-spec.md", "--essai", "--par", "coord")
        # 4. ouvrir : rôle, sujet, modèle, go, dépôt, plafond ; puis une vraie ouverture (clone, agent strict, mission)
        eq("equipe ouvrir par le coordinateur (refusé)", "ouvrir", "p", "demo", "Ajouter un bouton.", "--par", "coord")
        eq("equipe ouvrir, sujet invalide", "ouvrir", "p", "X", "Ajouter un bouton.", "--par", "chef")
        eq("equipe ouvrir, modèle non permis", "ouvrir", "p", "demo", "Ajouter un bouton.", "--par", "chef", "--modele", "haiku")
        eq("equipe ouvrir, go seulement demandé (refusé)", "ouvrir", "p", "secu", "Durcir le pare-feu.", "--par", "chef")
        eq("equipe ouvrir, dépôt = installation (refusé)", "ouvrir", "inst", "demo", "Ajouter un bouton.", "--par", "chef")
        eq("equipe ouvrir, sujet trop long pour Herdr", "ouvrir", "p", "un-sujet-bien-trop-long-xx", "Ajouter.", "--par", "chef")
        eq("equipe ouvrir (go inscrit, clone, agent strict, mission)", "ouvrir", "p", "demo", "Ajouter un bouton.", "--par", "chef", "--moteur", "claude")
        eq("equipe ouvrir, déjà ouvert", "ouvrir", "p", "demo", "Encore.", "--par", "chef")
        eq("equipe ouvrir, plafond [missions] max", "ouvrir", "p", "deux", "Autre chose.", "--par", "chef")
        eq("equipe liste, deux développeurs", "liste", "p")
        # 5. fermer : rôle, sujet, travail non commité, checklist ; puis une vraie fermeture
        eq("equipe fermer par le coordinateur (refusé)", "fermer", "p", "demo", "--par", "coord")
        eq("equipe fermer, sujet inconnu", "fermer", "p", "inexistant", "--par", "chef")
        (t / "copies/p-demo/brouillon.txt").write_text("pas commité\n")
        eq("equipe fermer, travail non commité (refusé)", "fermer", "p", "demo", "--par", "chef")
        (t / "copies/p-demo/brouillon.txt").unlink()
        eq("equipe fermer, checklist non finie (refusé)", "fermer", "p", "demo", "--par", "chef")
        (t / "agents/p-demo/CHECKLIST.md").write_text("# Bouton\n- [x] fait\nTerminé 2026-10-29 12:00\n")
        eq("equipe fermer (mission rangée, copie supprimée, journal gardé chez le chef)", "fermer", "p", "demo", "--par", "chef")
        # 6. projets d'équipe (bibliothèque)
        pj("projet ouvrir, équipe inconnue", "ouvrir", "inconnue", "demo", "chef")
        pj("projet ouvrir, nom invalide", "ouvrir", "p", "D", "chef")
        pj("projet ouvrir par un non-membre (refusé)", "ouvrir", "p", "demo", "chef", "--par", "intrus")
        pj("projet ouvrir, membres refusés", "ouvrir", "p", "demo", "chef,intrus", "--par", "chef")
        pj("projet ouvrir, aucun membre", "ouvrir", "p", "demo", " , ", "--par", "chef")
        pj("projet ouvrir (dossier, registre, régénère)", "ouvrir", "p", "demo", "chef,coord,p-ancien", "--par", "chef")
        pj("projet ouvrir, déjà ouvert", "ouvrir", "p", "demo", "chef", "--par", "chef")
        pj("projet liste", "liste")
        pj("projet liste d'une équipe", "liste", "p")
        pj("projet fermer par un non-membre (refusé)", "fermer", "p", "demo", "--par", "intrus")
        pj("projet fermer, pas ouvert", "fermer", "p", "autre", "--par", "chef")
        pj("projet fermer (archivé, droits retirés)", "fermer", "p", "demo", "--par", "coord")
        pj("projet ouvrir de nouveau (même nom)", "ouvrir", "p", "demo", "chef", "--par", "chef")
        pj("projet fermer de nouveau (seconde archive)", "fermer", "p", "demo")
        pj("projet, forme inconnue", "renommer", "p", "demo")
        pj("projet fermer, arguments manquants", "fermer", "p")
        # 7. crochet-equipe (appelé par le moteur d'un développeur : JSON du crochet sur stdin)
        cli("crochet-equipe sans agent", "crochet-equipe")
        cli("crochet-equipe, agent qui n'est pas développeur", "crochet-equipe", "chef", stdin=b'{"tool_input": {}}')
        cli("crochet-equipe, fichier de sa copie ramené au dépôt", "crochet-equipe", "p-ancien",
            stdin=json.dumps({"tool_input": {"file_path": f"{t}/copies/p-ancien/src/a.py"}, "cwd": "ailleurs"}).encode())
        cli("crochet-equipe, fichier hors de sa copie", "crochet-equipe", "p-ancien", stdin=json.dumps({"tool_input": {"file_path": "/etc/hosts"}}).encode())
        cli("crochet-equipe, entrée vide", "crochet-equipe", "p-ancien", stdin=b"")
        cli("crochet-equipe, JSON invalide", "crochet-equipe", "p-ancien", stdin=b"pas du json")
        cli("crochet-equipe, entier de 5 000 chiffres", "crochet-equipe", "p-ancien", stdin=('{"n": ' + "7" * 5000 + "}").encode())
        cli("crochet-equipe, imbrication trop profonde", "crochet-equipe", "p-ancien", stdin=b"[" * 100000 + b"]" * 100000)
        cli("crochet-equipe, entrée non UTF-8", "crochet-equipe", "p-ancien", stdin=b'{"tool_input": "\xff"}')
        # 8. le courtier : droits d'équipe (chef, coordinateur, non-membre), validations demandées
        courtier("courtier : non-membre, liste refusée", "intrus", "liste", "p")
        courtier("courtier : projet inconnu", "chef", "liste", "inconnu")
        courtier("courtier : coordinateur, ouvrir refusé (le chef seul)", "coord", "ouvrir", "p", "trois", "Faire.")
        courtier("courtier : chef, fermer un sujet inconnu refusé", "chef", "fermer", "p", "inexistant")
        courtier("courtier : coordinateur, liste", "coord", "liste", "p")
        courtier("courtier : chef, domaines refusé (le coordinateur seul)", "chef", "domaines", "p")
        courtier("courtier : coordinateur, domaines", "coord", "domaines", "p")
        courtier("courtier : coordinateur, domaine ajouter (validation demandée)", "coord", "domaine", "p", "ajouter", "nouveau.org")
        courtier("courtier : chef, go (validation demandée)", "chef", "go", "p", "trois", "2", "docs/plans/demo-spec.md")
        courtier("courtier : chef, verbe inconnu", "chef", "renommer", "p")
        courtier("courtier : chef, ouvrir (plafond, refus de berger)", "chef", "ouvrir", "p", "trois", "Faire.")
    return resultats


if __name__ == "__main__":
    if sys.argv[1:2] == ["--mesurer"]:
        print(json.dumps(mesurer(sys.argv[2]), ensure_ascii=False, indent=1)); sys.exit(0)
    if sys.argv[1:2] == ["--produire"] and len(sys.argv) == 4:
        Path(sys.argv[3]).write_text(json.dumps(mesurer(sys.argv[2]), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"attendus écrits : {sys.argv[3]} (mesurés sur {sys.argv[2]})"); sys.exit(0)
    defauts = controler_instantane() + controler_journal() + controler_uid()
    for d in defauts: print(f"ÉCHEC  instantané : {d}")
    mesure, attendu = mesurer(SRC), json.loads(ATTENDU.read_text(encoding="utf-8"))
    ko = len(defauts)
    par_nom = {x["scenario"]: x for x in attendu}
    for m in mesure:
        a = par_nom.pop(m["scenario"], None)
        if a is not None: a = {**a, "stderr_fin": normaliser(a["stderr_fin"], "<T>")}
        ok = a == m
        ko += not ok
        print(("ok     " if ok else "ÉCHEC  ") + f"{m['scenario']} : code {m['code']}, " + (m["stderr_fin"][:90] or m["stdout"].strip()[:90]))
        if not ok and a is not None:
            for chemin, av, ap in ecarts(a, m)[:8]: print(f"         {chemin}\n           avant {av}\n           après {ap}")
    for nom in par_nom: ko += 1; print(f"ÉCHEC  {nom} : mesuré avant, absent après")
    print(f"---- {ko} écart(s) sur {len(mesure)} scénario(s)")
    sys.exit(1 if ko else 0)
