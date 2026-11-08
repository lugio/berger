#!/usr/bin/env python3
"""Équivalence des verbes du courtier (modulaire, lot 4d, partie « courtier », docs/plans/2026-10-27-modulaire-spec.md § Tests « Équivalence des sorties ») :
`valider`, `refuser`, `courtier redemarrer`, `lancer`, `moteur` et `args`, mesurés sur une installation JETABLE, puis comparés à ce que mesurait `main`
avant le déplacement (tests/attendus/equivalence-courtier.json).
Pour chaque scénario : code de sortie, sortie standard, dernière ligne d'erreur, fichiers écrits (dossiers d'agents, réglages régénérés par empreinte, temporaires
des agents, contrats des moteurs, fichiers d'état du courtier : validations et décisions, marque de fermeture, installations.log, notifications), appels
(faux Herdr, faux systemctl et systemd-run, faux bubblewrap, ce que le moteur aurait reçu : arguments et NOMS des variables du lancement strict, jamais leurs
valeurs hors de l'installation jetable). Refus mesurés : validation absente ou déjà faite, durée hors accès web ou invalide, file tenue (installation en
attente, redémarrage en cours) ; mur strict sans bac à sable, moteur non admis ou jamais vu (bascule, aucun moteur), dossier temporaire ; redémarrage abandonné
(demande en cours), contrôlé raté (retour arrière) ; arguments manquants ou mal formés ; voie privée (`--stdin`).
L'instantané garde CHAQUE fichier ; un journal (installations.log, notifications.log, échanges) n'est relevé par sa fin que si son début est resté identique
(leçons des renvois n° 89 et 93 : controler_instantane, controler_journal).
Ce qui varie d'une exécution à l'autre est normalisé (chemin de l'installation, dates, heures, identifiants de commit). « commande inconnue » : la PREMIÈRE
ligne d'erreur est relevée (la suite est l'aide, qui gagne les lignes d'AIDE des familles : point 4 du correctif contrat).
Usage : python3 tests/equivalence-courtier.py               mesure ce dépôt et compare (0 = identique)
        python3 tests/equivalence-courtier.py --mesurer <source>   imprime la mesure d'un autre arbre (ex. un `git archive` de main)
        python3 tests/equivalence-courtier.py --produire <source> <fichier>   écrit la mesure de <source> dans <fichier> (les attendus)
Les attendus (tests/attendus/equivalence-courtier.json) ont été produits sur main b8d1831 (refaits à chaque mise à jour depuis main) :
        d=$(mktemp -d) && git archive b8d1831 | tar -x -C "$d" && python3 tests/equivalence-courtier.py --produire "$d" tests/attendus/equivalence-courtier.json"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import hashlib, json, os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ATTENDU = SRC / "tests/attendus/equivalence-courtier.json"

# Faux programmes : chacun trace son appel. Le moteur répond à --version (9.9.9) ; lancé, il dit ses arguments et les NOMS des variables de Berger.
FAUX = {
    "herdr": r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["herdr"] + a) + "\n")
r = {}
if a[:2] == ["pane", "get"]: r = {"pane": {"pane_id": a[2], "agent_status": "idle"}}
elif a[:2] == ["pane", "split"]: r = {"pane": {"pane_id": "p-neuf"}}
print(json.dumps({"result": r}))
''',
    "moteur": r'''#!/usr/bin/env python3
import json, os, sys
nom = os.path.basename(sys.argv[0])
if sys.argv[1:] == ["--version"]: print("9.9.9 (faux)"); sys.exit(0)
with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["moteur", nom, sys.argv[1:], os.getcwd()]) + "\n")
t = os.environ["FAUX_RACINE"]; noms = ("BERGER_AGENT", "BERGER_DIR", "CLAUDE_CODE_TMPDIR", "CODEX_HOME", "ENABLE_CLAUDEAI_MCP_SERVERS", "TMPDIR")
print(json.dumps({"moteur": nom, "args": sys.argv[1:], "variables": {k: os.environ[k] if os.environ[k].startswith(t) or k in ("BERGER_AGENT", "ENABLE_CLAUDEAI_MCP_SERVERS") else "<ailleurs>" for k in noms if k in os.environ}}))
''',
    "bwrap": "#!/bin/sh\nif [ \"$FAUX_BWRAP\" = ko ]; then echo 'bwrap: échec simulé du bac à sable' >&2; exit 1; fi\nexit 0\n",
    "systemctl": r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["systemctl"] + sys.argv[1:]) + "\n")
if "is-active" in sys.argv: print(os.environ.get("FAUX_ACTIF", "active"))
''',
    "systemd-run": "#!/usr/bin/env python3\nimport json, os, sys\nwith open(os.environ['FAUX_TRACE'], 'a') as f: f.write(json.dumps(['systemd-run'] + sys.argv[1:]) + '\\n')\n",
    "notify-send": "#!/bin/sh\nexit 0\n",
}

# La ligne de commande, dans le processus : le démarrage d'un moteur dans un panneau (demarrer_agent) est relevé au lieu d'être fait, des deux côtés ;
# le relevé garde ce que le cœur aurait lancé (moteurs.args_moteur : le lancement strict). Les attentes (time.sleep) ne durent pas.
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
g["demarrer_agent"] = demarrer
if os.environ.get("FAUX_TMP_MAX"): g["TMP_MAX"] = int(os.environ["FAUX_TMP_MAX"])   # le chemin jetable est long : la limite est desserrée, des deux côtés (un scénario la garde)
g["time"].sleep = lambda s: None
g["main"](sys.argv[2:])
'''

AGENTS = {
    "chef": "moteur = claude\n",
    "ouv": "moteur = claude\nmur = ouvert\n",
    "cx": "moteur = codex\n",
}
GENERES = ("AGENTS.md", "BERGER.md", "CLAUDE.md", ".consigne-systeme.md", ".reglages-claude.json", ".mcp.json", "config.toml", "hooks.json")
HORS = ("courrier", ".transport")                     # ce que le courtier range pour lui (requêtes, réponses)
ETAT_COURTIER = re.compile(r"\.(log|json|jsonl|txt|decision)$|^fermeture$")   # les fichiers d'état du courtier, jamais ses sources


def normaliser(texte, t):
    texte = str(texte).replace(str(t), "<T>")
    texte = re.sub(r"\b[0-9a-f]{40}\b", "<SHA>", texte)
    texte = re.sub(r"\b[0-9a-f]{10}\b", "<SHA10>", texte)
    texte = re.sub(r"tmp-agents/[0-9a-f]{12}", "tmp-agents/<H>", texte)
    texte = re.sub(r"claude-\d+(?![\d.])", "claude-<UID>", texte)
    texte = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>", texte)
    texte = re.sub(r"\d{8}-\d{6}", "<HORODATAGE>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}[T _]\d{2}:?\d{2}(:\d{2}(\.\d+)?)?", "<DATE-HEURE>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}", "<DATE>", texte)
    texte = re.sub(r"\b\d{2}/\d{2}(/\d{4})?\b", "<JJ/MM>", texte)
    texte = re.sub(r"\b\d{2}:\d{2}(:\d{2})?\b", "<HEURE>", texte)
    texte = re.sub(r"\b\d{2} h \d{2}\b", "<HEURE>", texte)
    texte = re.sub(r"\"(jusqu|depuis)\": [0-9.]+", r'"\1": <TS>', texte)
    texte = re.sub(r"line \d+", "line <N>", texte)
    texte = re.sub(r"fait \d+ octets", "fait <N> octets", texte)                     # la longueur dépend du chemin de l'installation jetable
    return re.sub(r"/tmp/[^\s\"']*herdr-absent-\d+\.sock", "<SOCKET>", texte)


def contenu(f, t):
    """Le texte normalisé d'un fichier ; les consignes et réglages régénérés (longs, du cœur des deux côtés) : leur empreinte."""
    x = normaliser(f.read_text(errors="replace"), t)
    if f.name in GENERES or len(x) > 4000: return "sha256:" + hashlib.sha256(x.encode()).hexdigest()[:16]
    return x


def _ranger(out, cle, val):
    """Chaque clé normalisée porte la LISTE ordonnée de ses fichiers (renvoi n° 89) : deux fichiers horodatés au même nom normalisé restent deux."""
    out.setdefault(cle, []).append(val)


def fichiers(t):
    """Ce que les verbes du courtier écrivent : dossiers d'agents (sauf le courrier du courtier), temporaires des agents, contrats des moteurs, réglages
    du moteur dans le dossier personnel, fichiers d'état du courtier (jamais ses sources)."""
    out = {}
    for racine, filtre in (("agents", None), ("tmp-agents", None), ("tests/contrats", None), ("courtier", ETAT_COURTIER), (".claude.json", None)):
        base = t / racine
        for f in ([base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []):
            r = f.relative_to(t)
            if racine == "agents" and len(r.parts) > 2 and r.parts[2] in HORS: continue
            if racine == "courtier" and ("outils" in r.parts or not filtre.search(f.name)): continue
            if f.is_dir():
                if not any(f.iterdir()): _ranger(out, normaliser(str(r) + "/", t), "<dossier>")
            elif f.is_file(): _ranger(out, normaliser(str(r), t), contenu(f, t))
    return out


def ajouts(ancien, neuf):
    """Ce qu'un scénario ajoute à un journal : la fin du fichier, SI son ancien contenu est resté identique au début ; sinon le fichier entier, marqué
    (renvoi n° 93 : une ancienne ligne altérée fait un écart et ne devient jamais, muette, la référence du scénario suivant)."""
    ancien, neuf = ancien or "", neuf or ""
    return neuf[len(ancien):] if neuf.startswith(ancien) else {"début du journal modifié": neuf}


JOURNAUX = ("courtier/installations.log", "courtier/notifications.log", "courtier/echanges.jsonl")


def controler_journal():
    """Renvoi n° 93 : une ANCIENNE ligne d'un journal altérée, puis la même ligne neuve ajoutée, doit faire un écart. → la liste des défauts."""
    ancien = "ligne ancienne\n"; ligne = "ligne neuve\n"
    return [] if ajouts(ancien, ancien + ligne) != ajouts(ancien, ancien.replace("ancienne", "ALTEREE") + ligne) else ["une ancienne ligne altérée d'un journal ne fait pas d'écart"]


def controler_instantane():
    """Leçon du renvoi n° 89 : l'instantané garde CHAQUE fichier, même quand la normalisation rend leurs noms identiques ; un fichier antérieur modifié ou
    supprimé fait un écart. → la liste des défauts (vide = l'instantané voit tout)."""
    defauts = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td); h = t / "agents/chef/historique"; h.mkdir(parents=True)
        a, b = h / "2026-10-29_1000-MISSION.md", h / "2026-10-29_1100-MISSION.md"
        a.write_text("premier"); b.write_text("second")
        depart = fichiers(t)
        a.write_text("premier, modifié")
        if fichiers(t) == depart: defauts.append("un fichier antérieur modifié ne fait pas d'écart")
        a.unlink()
        if fichiers(t) == depart: defauts.append("un fichier antérieur supprimé ne fait pas d'écart")
    return defauts


def mesurer(src):
    src = Path(src).resolve(); resultats = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        _produit.copier(src, t, ("bin", "courtier", "commun"))
        (t / "coffre.json").write_text("{}")
        (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n[courtier]\nredemarrage_attente = 0\n'
                                       'redemarrage_essais = 3\nredemarrage_reessai = 60\n')
        for a, c in AGENTS.items():
            d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nheures = aucune\n{c}")
        (t / "agents/chef/.herdr.json").write_text(json.dumps({"workspace": "ws-chef", "agents": {"claude": "pe-chef"}}))
        contrats = t / "tests/contrats"; contrats.mkdir(parents=True)
        (contrats / "claude-9.9.9.txt").write_text("ADMIS\n" + _produit.LIGNES_12["claude"])   # (12) exigé depuis main a1cec6a ; codex : jamais vu (aucun contrat ni script : « impossible à jouer »)
        v = t / "courtier/validations"; v.mkdir(parents=True)
        (v / "1.json").write_text(json.dumps({"n": 1, "agent": "chef", "outil": "essai", "verbe": "ecrire", "args": []}))
        (v / "2.json").write_text(json.dumps({"n": 2, "agent": "chef", "outil": "essai", "verbe": "ecrire", "args": []}))
        (v / "3.json").write_text(json.dumps({"n": 3, "agent": "chef", "outil": "web", "verbe": "ouvrir", "args": ["exemple.org"]}))
        (v / "4.json").write_text(json.dumps({"n": 4, "agent": "chef", "outil": "essai", "verbe": "ecrire", "args": []}))
        (v / "4.fait.json").write_text(json.dumps({"n": 4, "etat": "faite", "resultat": "ok"}))
        (v / "5.json").write_text(json.dumps({"n": 5, "agent": "chef", "outil": "essai", "verbe": "ecrire", "args": []}))   # --empreinte (interface web, main b8d1831)
        (t / "faux").mkdir(); faux = t / ".local/bin"; faux.mkdir(parents=True)   # ~/.local/bin : berger le place AVANT /usr/bin (noyau/config.py, PATH_MISE)
        for nom, texte in (*FAUX.items(), ("claude", FAUX["moteur"]), ("codex", FAUX["moteur"])):
            if nom == "moteur": continue
            (faux / nom).write_text(texte); (faux / nom).chmod(0o755)
        trace = t / "faux/trace.jsonl"
        (t / "tmp").mkdir(); (t / "tmp-agents").mkdir(mode=0o700)               # le temporaire des agents DANS l'installation jetable (normalisé)
        env = dict(os.environ, BERGER_DIR=str(t), HOME=str(t), PATH=f"{faux}:{os.environ['PATH']}", BERGER_NOTIFY_SEND=str(faux / "notify-send"),
                   BERGER_TMP_AGENTS=str(t / "tmp-agents"), BERGER_HERDR=str(faux / "herdr"), FAUX_TRACE=str(trace),
                   BERGER_CONTROLE_PAUSE="0", BERGER_REDEMARRAGE_PAS="0", FAUX_RACINE=str(t), FAUX_TMP_MAX="400", TMPDIR=str(t / "tmp"),
                   GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.invalid")
        for k in ("BERGER_AGENT", "AGENT_PANNE", "FAUX_BWRAP", "FAUX_ACTIF"): env.pop(k, None)
        for k in [k for k in env if k.startswith(("CLAUDE_CODE_", "CODEX_", "ENABLE_CLAUDEAI"))]: env.pop(k)   # hérités de la session qui lance le test : jamais relevés
        # l'installation est un dépôt git (redémarrage contrôlé : retour arrière au commit d'avant)
        subprocess.run(["git", "init", "-q", "-b", "main", str(t)], check=True, env=env)
        subprocess.run(["git", "-C", str(t), "add", "bin", "courtier", "commun"], check=True, env=env)
        subprocess.run(["git", "-C", str(t), "commit", "-qm", "installation"], check=True, env=env)
        tete = subprocess.run(["git", "-C", str(t), "rev-parse", "HEAD"], capture_output=True, text=True, env=env).stdout.strip()
        avant = {"fichiers": fichiers(t)}

        def noter(nom, r):
            appels = [normaliser(l, t) for l in trace.read_text().splitlines()] if trace.exists() else []
            trace.unlink(missing_ok=True)
            apres = fichiers(t)
            ecrits = {k: x for k, x in apres.items() if avant["fichiers"].get(k, "∅") != x}
            for j in JOURNAUX:                                              # les lignes ajoutées (début vérifié)
                if j in ecrits and j in avant["fichiers"]: ecrits[j] = ajouts(avant["fichiers"][j][0], apres[j][0])
            ecrits.update({k: "(supprimé)" for k in avant["fichiers"] if k not in apres})
            avant["fichiers"] = apres
            err = [l for l in r.stderr.splitlines() if l.strip()]
            fin = err[0] if err and err[0].startswith("commande inconnue : ") else (err[-1] if err else "")
            resultats.append({"scenario": nom, "code": r.returncode, "stdout": normaliser(r.stdout, t),
                              "stderr_fin": normaliser(fin, t), "fichiers_ecrits": ecrits, "appels": appels})

        def cli(nom, *argv, stdin=None, plus=None):
            r = subprocess.run([sys.executable, "-c", LANCEUR, str(t / "bin/berger"), *argv], input=stdin, env={**env, **(plus or {})},
                               capture_output=True, timeout=600)
            r.stdout, r.stderr = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace"); noter(nom, r)

        # 1. valider / refuser : la décision du propriétaire, que le courtier exécute (fichier .decision atomique)
        cli("valider sans numéro", "valider")
        cli("valider, aucune demande (validation absente)", "valider", "99")
        cli("valider, déjà faite", "valider", "4")
        cli("refuser --duree (valider seulement)", "refuser", "2", "--duree", "8h")
        cli("valider --duree hors accès web", "valider", "1", "--duree", "8h")
        cli("valider --duree invalide (accès web)", "valider", "3", "--duree", "99h")
        cli("valider --duree sans valeur", "valider", "3", "--duree")
        (t / "courtier/file-tenue.json").write_text(json.dumps({"depuis": 0}))
        cli("valider, file tenue (installation en attente)", "valider", "1")
        (t / "courtier/file-tenue.json").unlink(); (v / "1.decision").unlink()
        (t / "courtier/fermeture").write_text(json.dumps({"jusqu": 4102444800, "depuis": 0}))
        cli("refuser, file tenue (redémarrage en cours)", "refuser", "2")
        (t / "courtier/fermeture").unlink(); (v / "2.decision").unlink()
        cli("valider (le courtier ne tourne pas)", "valider", "1")
        cli("refuser par la voie privée", "--stdin", stdin=json.dumps(["refuser", "2"]).encode())
        cli("valider --duree 8h (accès web)", "valider", "3", "--duree", "8h")
        # --empreinte (interface web) : le sha256 de la demande vue, revérifié sous le verrou des décisions ; une décision n'est jamais remplacée
        juste = hashlib.sha256((v / "5.json").read_bytes()).hexdigest()
        cli("valider --empreinte fausse (demande modifiée)", "valider", "5", "--empreinte", "0" * 64)
        cli("refuser --empreinte fausse (demande modifiée)", "refuser", "5", "--empreinte", "f" * 64)
        cli("refuser --empreinte sans valeur", "refuser", "5", "--empreinte")
        cli("valider --empreinte juste", "valider", "5", "--empreinte", juste)
        cli("refuser, déjà décidée (une décision n'est jamais remplacée)", "refuser", "5")
        # 2. courtier redemarrer : marque de fermeture, attente, contrôle, retour arrière
        cli("courtier sans sous-commande", "courtier")
        cli("courtier, sous-commande inconnue", "courtier", "arreter")
        cli("courtier redemarrer (rien en cours)", "courtier", "redemarrer")
        cli("courtier redemarrer --essai illisible", "courtier", "redemarrer", "--essai", "x")
        cli("courtier redemarrer --essai sans valeur", "courtier", "redemarrer", "--essai")
        cli("courtier redemarrer --controle court", "courtier", "redemarrer", "--controle", "abc")
        cli("courtier redemarrer --controle (actif, contrôlé)", "courtier", "redemarrer", "--controle", tete)
        cli("courtier redemarrer --controle (inactif : retour arrière)", "courtier", "redemarrer", "--controle", tete, plus={"FAUX_ACTIF": "failed"})
        (t / "agents/chef/courrier/encours").mkdir(parents=True); (t / "agents/chef/courrier/encours/1.json").write_text("{}")
        cli("courtier redemarrer, demande en cours (abandon, nouvel essai)", "courtier", "redemarrer", "--essai", "2")
        cli("courtier redemarrer, dernier essai abandonné", "courtier", "redemarrer", "--essai", "3")
        (t / "agents/chef/courrier/encours/1.json").unlink()
        # 3. lancer : bac à sable, temporaire, admission du moteur (bascule), lancement strict
        cli("lancer sans agent", "lancer")
        cli("lancer, agent inconnu", "lancer", "inconnu")
        cli("lancer, mur strict sans bac à sable", "lancer", "chef", plus={"FAUX_BWRAP": "ko"})
        cli("lancer, dossier temporaire trop long (refusé)", "lancer", "chef", plus={"FAUX_TMP_MAX": ""})
        cli("lancer (claude admis)", "lancer", "chef")
        cli("lancer sous codex jamais vu (bascule sur claude)", "lancer", "chef", "codex")
        cli("lancer, agent codex (bascule sur claude)", "lancer", "cx")
        (contrats / "claude-9.9.9.txt").write_text("NON ADMIS\n✗ outil vu hors du bac\n")
        cli("lancer, aucun moteur admis", "lancer", "chef")
        cli("lancer, mur ouvert (admission hors sujet)", "lancer", "ouv")
        (contrats / "claude-9.9.9.txt").write_text("ADMIS\n" + _produit.LIGNES_12["claude"])
        cli("lancer, moteur inconnu", "lancer", "ouv", "autre")
        # 4. moteur : un moteur de plus dans un panneau (demarrer_agent, le mur)
        cli("moteur sans argument", "moteur")
        cli("moteur, moteur manquant", "moteur", "chef")
        cli("moteur, tourne déjà", "moteur", "chef", "claude")
        cli("moteur, un moteur de plus", "moteur", "chef", "codex")
        cli("moteur, agent inconnu", "moteur", "inconnu", "claude")
        # 5. args : dossier, arguments et variables du moteur, pour un pont
        cli("args sans argument", "args")
        cli("args, moteur manquant", "args", "chef")
        cli("args, mur strict sans bac à sable", "args", "chef", "claude", plus={"FAUX_BWRAP": "ko"})
        cli("args (claude, interactif)", "args", "chef", "claude")
        cli("args (claude, non interactif)", "args", "chef", "claude", "--non-interactif")
        cli("args, codex jamais vu (refusé)", "args", "cx", "codex")
        cli("args --contrat (admission non jouée)", "args", "cx", "codex", "--contrat")
        cli("args, mur ouvert", "args", "ouv", "codex")
        cli("args, agent inconnu", "args", "inconnu", "claude")
        cli("args par la voie privée", "--stdin", stdin=json.dumps(["args", "ouv", "claude"]).encode())
        cli("args, voie privée : texte positionnel en plus", "--stdin", "args", stdin=b"[]")
    return resultats


if __name__ == "__main__":
    if sys.argv[1:2] == ["--mesurer"]:
        print(json.dumps(mesurer(sys.argv[2]), ensure_ascii=False, indent=1)); sys.exit(0)
    if sys.argv[1:2] == ["--produire"] and len(sys.argv) == 4:
        Path(sys.argv[3]).write_text(json.dumps(mesurer(sys.argv[2]), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"attendus écrits : {sys.argv[3]} (mesurés sur {sys.argv[2]})"); sys.exit(0)
    defauts = controler_instantane() + controler_journal()
    for d in defauts: print(f"ÉCHEC  instantané : {d}")
    mesure, attendu = mesurer(SRC), json.loads(ATTENDU.read_text(encoding="utf-8"))
    ko = len(defauts)
    par_nom = {x["scenario"]: x for x in attendu}
    for m in mesure:
        a = par_nom.pop(m["scenario"], None)
        ok = a == m
        ko += not ok
        print(("ok     " if ok else "ÉCHEC  ") + f"{m['scenario']} : code {m['code']}, " + (m["stderr_fin"][:90] or m["stdout"].strip()[:90]))
        if not ok and a is not None:
            for k in sorted(set(a) | set(m)):
                if a.get(k) != m.get(k): print(f"         {k} : avant {json.dumps(a.get(k), ensure_ascii=False)[:400]}\n         {' ' * len(k)}   après {json.dumps(m.get(k), ensure_ascii=False)[:400]}")
    for nom in par_nom: ko += 1; print(f"ÉCHEC  {nom} : mesuré avant, absent après")
    print(f"---- {ko} écart(s) sur {len(mesure)} scénario(s)")
    sys.exit(1 if ko else 0)
