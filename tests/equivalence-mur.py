#!/usr/bin/env python3
"""Équivalence des verbes du mur (modulaire, lot 4d, partie « mur », docs/plans/2026-10-27-modulaire-spec.md § Tests « Équivalence des sorties ») :
`regenerer`, `nouveau` et `agent apercu|appliquer`, mesurés sur une installation JETABLE, puis comparés à ce que mesurait `main` avant le déplacement
(tests/attendus/equivalence-mur.json).
Pour chaque scénario : code de sortie, sortie standard, dernière ligne d'erreur, fichiers écrits dans TOUTE l'installation jetable hors du produit (dossiers
d'agents : consignes et réglages du mur par empreinte, liens de skills, sauvegardes .avant ; profils Codex ; bibliothèque ; temporaires ; fichiers d'état du
courtier), les liens symboliques avec leur cible, et les appels (faux Herdr). Refus mesurés : proposition introuvable, clé interdite (supervision), mur
ouvert proposé, outil, serveur MCP ou méthode inconnus, un agent qui se propose lui-même, création sans SOUL.md, valeur du coffre et chemin du coffre cités,
empreinte changée depuis l'aperçu, usage ; nom trop long, agent existant. Deux voies : la ligne de commande et le courtier (outil d'administration :
aperçu en lecture, application qui attend la validation ; un agent sans l'outil refusé).
L'instantané garde CHAQUE fichier ; un journal n'est relevé par sa fin que si son début est resté identique (renvois n° 89 et 93).
Usage : python3 tests/equivalence-mur.py               mesure ce dépôt et compare (0 = identique)
        python3 tests/equivalence-mur.py --mesurer <source>   imprime la mesure d'un autre arbre (ex. un `git archive` de main)
        python3 tests/equivalence-mur.py --produire <source> <fichier>   écrit la mesure de <source> dans <fichier> (les attendus)
Les attendus (tests/attendus/equivalence-mur.json) ont été produits sur main 4f69605, avant le lot 4d :
        d=$(mktemp -d) && git archive b8d1831 | tar -x -C "$d" && python3 tests/equivalence-mur.py --produire "$d" tests/attendus/equivalence-mur.json"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import hashlib, json, os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ATTENDU = SRC / "tests/attendus/equivalence-mur.json"

FAUX = {
    "herdr": r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["herdr"] + a) + "\n")
print(json.dumps({"result": {}}))
''',
    "notify-send": "#!/bin/sh\nexit 0\n",
}

# La ligne de commande, dans le processus : les attentes ne durent pas ; la relance d'un agent (relancer) est relevée au lieu d'être faite, des deux côtés.
LANCEUR = r'''
import json, os, sys
src = sys.argv[1]; g = {"__name__": "essai", "__file__": src}
exec(compile(open(src).read(), src, "exec"), g)
def trace(*x):
    with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["@"] + [str(v) for v in x]) + "\n")
g["relancer"] = lambda a, m=None, force=False: trace("relancer", a, m, force)
g["TMP_COMMUN"] = g["Path"](os.environ["FAUX_TMP_COMMUN"])   # le temporaire commun de Claude n'est interdit que s'il EXISTE : celui de la machine ferait
                                                         # dépendre .codex/config.toml de l'hôte (présent pour la porte, caché dans un bac à sable)
g["TMP_MAX"] = 400   # le chemin jetable suit TMPDIR : sans cela, la mesure dépendrait de sa longueur (limite de 44 octets), des deux côtés
g["time"].sleep = lambda s: None
g["main"](sys.argv[2:])
'''

# Le courtier, appelé directement (comme tests/equivalence-equipes.py) : ses droits, puis berger en sous-processus ; attend la fin de ses fils.
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
    "gardien": "moteur = claude\nsuperviseur = oui\noutils = berger-admin\n",
    "chef": "moteur = claude\nbibliotheque = oui\nproteges = docs\n",
    "ouv": "moteur = claude\nmur = ouvert\nproteges = docs\n",
    "cx": "moteur = codex\n",
    "coord": "moteur = claude\n",
    "intrus": "moteur = claude\n",
}
GENERES = ("AGENTS.md", "BERGER.md", "CLAUDE.md", ".consigne-systeme.md", ".reglages-claude.json", ".mcp.json", "config.toml", "hooks.json", "settings.json")
HORS_RACINE = {"bin", "commun", "courtier", ".local", "faux", "tmp", "herdr-plugin"}   # le produit et les faux : jamais relevés (le courtier : son état seulement)
HORS = ("courrier", ".transport")
ETAT_COURTIER = re.compile(r"\.(log|json|jsonl|txt|decision)$")


def normaliser(texte, t):
    texte = str(texte).replace(str(t), "<T>")
    texte = re.sub(r"\b[0-9a-f]{40}\b", "<SHA>", texte)
    texte = re.sub(r"\b[0-9a-f]{10}\b", "<SHA10>", texte)
    texte = re.sub(r"tmp-agents/[0-9a-f]{12}", "tmp-agents/<H>", texte)
    texte = re.sub(r"claude-\d+(?![\d.])", "claude-<UID>", texte)
    texte = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>", texte)
    texte = re.sub(r"\d{8}-\d{6}", "<HORODATAGE>", texte)
    texte = re.sub(r"\d{8}-\d{4}\b", "<AVANT>", texte)
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
    """Tout ce que les verbes du mur écrivent dans l'installation jetable, hors du produit : chaque fichier (contenu normalisé, ou empreinte des réglages
    générés), chaque lien symbolique (sa cible), chaque dossier vide ; l'état du courtier (validations, journaux), jamais ses sources."""
    out = {}
    for f in sorted(t.rglob("*")):
        r = f.relative_to(t)
        if r.parts[0] in HORS_RACINE and not (r.parts[0] == "courtier" and "outils" not in r.parts and (f.is_dir() or ETAT_COURTIER.search(f.name))): continue
        if any(x in HORS for x in r.parts) or any(p.is_symlink() for p in list(f.parents)[:len(r.parts) - 1]): continue
        if f.is_symlink(): _ranger(out, normaliser(str(r), t), "-> " + normaliser(os.readlink(f), t))
        elif f.is_dir():
            if not any(f.iterdir()): _ranger(out, normaliser(str(r) + "/", t), "<dossier>")
        elif f.is_file(): _ranger(out, normaliser(str(r), t), contenu(f, t))
    return out


def ecart(a, m):
    """Le premier écart d'un scénario, en une ligne : le champ, et pour les fichiers écrits, le fichier (avant → après, tronqués)."""
    if a is None: return "absent de la référence"
    for k in sorted(set(a) | set(m)):
        x, y = a.get(k), m.get(k)
        if x == y: continue
        if isinstance(x, dict) and isinstance(y, dict):
            f = next(f for f in sorted(set(x) | set(y)) if x.get(f) != y.get(f))
            return f"{k} › {f} : avant {json.dumps(x.get(f, '∅'), ensure_ascii=False)[:160]} ; après {json.dumps(y.get(f, '∅'), ensure_ascii=False)[:160]}"
        return f"{k} : avant {json.dumps(x, ensure_ascii=False)[:160]} ; après {json.dumps(y, ensure_ascii=False)[:160]}"
    return "?"


def ajouts(ancien, neuf):
    """Ce qu'un scénario ajoute à un journal : la fin du fichier, SI son ancien contenu est resté identique au début ; sinon le fichier entier, marqué
    (renvoi n° 93 : une ancienne ligne altérée fait un écart et ne devient jamais, muette, la référence du scénario suivant)."""
    ancien, neuf = ancien or "", neuf or ""
    return neuf[len(ancien):] if neuf.startswith(ancien) else {"début du journal modifié": neuf}


JOURNAUX = ("courtier/appels.log", "courtier/notifications.log", "courtier/echanges.jsonl")


def controler_journal():
    """Renvoi n° 93 : une ANCIENNE ligne d'un journal altérée, puis la même ligne neuve ajoutée, doit faire un écart. → la liste des défauts."""
    ancien = "ligne ancienne\n"; ligne = "ligne neuve\n"
    return [] if ajouts(ancien, ancien + ligne) != ajouts(ancien, ancien.replace("ancienne", "ALTEREE") + ligne) else ["une ancienne ligne altérée d'un journal ne fait pas d'écart"]


def controler_instantane():
    """Leçon du renvoi n° 89 : l'instantané garde CHAQUE fichier, même quand la normalisation rend leurs noms identiques (sauvegardes .avant-<date>) ;
    un fichier antérieur modifié ou supprimé fait un écart. → la liste des défauts (vide = l'instantané voit tout)."""
    defauts = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td); d = t / "agents/chef"; d.mkdir(parents=True)
        a, b = d / "SOUL.md.avant-20261029-1000", d / "SOUL.md.avant-20261029-1100"
        a.write_text("premier"); b.write_text("second")
        depart = fichiers(t)
        a.write_text("premier, modifié")
        if fichiers(t) == depart: defauts.append("une sauvegarde antérieure modifiée ne fait pas d'écart")
        a.unlink()
        if fichiers(t) == depart: defauts.append("une sauvegarde antérieure supprimée ne fait pas d'écart")
    return defauts


def mesurer(src):
    src = Path(src).resolve(); resultats = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        _produit.copier(src, t, ("bin", "courtier", "commun"))
        (t / "coffre.json").write_text(json.dumps({"service": {"jeton": "JetonFacticeDuTestMur"}}))
        depot = t / "depot"; depot.mkdir()
        (t / "config.toml").write_text(
            f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n'
            f'[outils.berger-admin]\ntype = "commandes"\ndossier = "{t}"\n[outils.berger-admin.lecture]\nagent-apercu = "bin/berger agent apercu {{agent}} {{arg}}"\n'
            f'[outils.berger-admin.actions]\nagent-appliquer = "bin/berger agent appliquer {{agent}} {{arg}}"\nregenerer = "bin/berger regenerer"\n\n'
            f'[equipes.p]\nchef_projet = "chef"\ncoordinateur = "coord"\ndepot = "{depot}"\nprefixe = "p/"\n')
        for a, c in AGENTS.items():
            d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nheures = aucune\n{c}")
            (d / "SOUL.md").write_text(f"# {a}\n")
        (t / "equipes/p").mkdir(parents=True); (t / "equipes/p/domaines").write_text("exemple.org\n")
        (t / "equipes/p/projets.json").write_text(json.dumps({"demo": {"membres": ["chef", "coord"]}}))
        (t / "agents/cx/espace.toml").write_text("inconnue = 1\n")
        ext = t / "travail-ext"; ext.mkdir()
        d = t / "agents/ext"; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = Ext\nheures = aucune\nmoteur = claude\ndossier = {ext}\n")
        (t / "faux").mkdir(); faux = t / ".local/bin"; faux.mkdir(parents=True)   # ~/.local/bin : berger le place AVANT /usr/bin (noyau/config.py)
        for nom, texte in FAUX.items(): (faux / nom).write_text(texte); (faux / nom).chmod(0o755)
        trace = t / "faux/trace.jsonl"
        (t / "tmp").mkdir(); (t / "tmp-agents").mkdir(mode=0o700); (t / "tmp/claude-commun").mkdir(mode=0o700)   # FAUX_TMP_COMMUN
        env = dict(os.environ, BERGER_DIR=str(t), HOME=str(t), PATH=f"{faux}:{os.environ['PATH']}", BERGER_NOTIFY_SEND=str(faux / "notify-send"),
                   BERGER_TMP_AGENTS=str(t / "tmp-agents"), BERGER_HERDR=str(faux / "herdr"), FAUX_TRACE=str(trace), TMPDIR=str(t / "tmp"), FAUX_TMP_COMMUN=str(t / "tmp/claude-commun"),
                   GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.invalid", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.invalid")
        for k in ("BERGER_AGENT", "AGENT_PANNE"): env.pop(k, None)
        for k in [k for k in env if k.startswith(("CLAUDE_CODE_", "CODEX_", "ENABLE_CLAUDEAI"))]: env.pop(k)   # hérités de la session : jamais relevés
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

        def cli(nom, *argv, stdin=None):
            r = subprocess.run([sys.executable, "-c", LANCEUR, str(t / "bin/berger"), *argv], input=stdin, env=env, capture_output=True, timeout=600)
            r.stdout, r.stderr = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace"); noter(nom, r)

        def courtier(nom, agent, verbe, *args):
            req = json.dumps({"outil": "berger-admin", "verbe": verbe, "args": list(args)})
            r = subprocess.run([sys.executable, "-c", APPEL, str(t / "courtier/courtier"), agent, req], env=env, capture_output=True, text=True, timeout=900)
            try: rep = json.loads(r.stdout)
            except ValueError: rep = {"illisible": r.stdout[-200:]}
            r.stdout = json.dumps(rep, ensure_ascii=False, sort_keys=True); noter(nom, r)

        def proposer(demandeur, cible, blocs):
            p = t / "agents" / demandeur / "propositions"; p.mkdir(exist_ok=True)
            (p / f"{cible}.md").write_text("".join(f"=== {n}\n{x}" for n, x in blocs.items()))

        def empreinte(nom):
            return next((m.group(1) for m in [re.search(r"Empreinte : ([0-9a-f]{12})", x["stdout"]) for x in resultats if x["scenario"] == nom] if m), "absente")

        # 1. regenerer : règles, réglages du mur (strict, ouvert, codex, externe, sites permis du projet, bibliothèque, projets), profils Codex, skills
        cli("regenerer (premier passage)", "regenerer")
        cli("regenerer (second passage, rien ne change)", "regenerer")
        cli("regenerer, argument ignoré", "regenerer", "en-trop")
        (t / "agents/chef/espace.toml").write_text("[[[\n")
        cli("regenerer, espace.toml illisible (signalé)", "regenerer")
        (t / "agents/chef/espace.toml").write_text("")
        # 2. nouveau : depuis les modèles (SOUL d'un rôle), refus
        cli("nouveau sans argument", "nouveau")
        cli("nouveau, nom trop long pour Herdr", "nouveau", "un-nom-d-agent-bien-trop-long-x")
        cli("nouveau, agent existant", "nouveau", "chef")
        cli("nouveau (nom donné)", "nouveau", "neuf", "Le Neuf")
        cli("nouveau (modèle d'un rôle : master)", "nouveau", "master")
        # 3. agent apercu / appliquer : proposition d'un agent pour un autre, refus, empreinte, application
        cli("agent sans sous-commande", "agent")
        cli("agent apercu, arguments manquants", "agent", "apercu", "gardien")
        cli("agent apercu, proposition introuvable", "agent", "apercu", "gardien", "aide")
        proposer("gardien", "aide", {"agent.conf": "nom = Aide\nsuperviseur = oui\nmur = ouvert\noutils = inconnu, ecrire:gardien\nmcp = absent\nskills = absente\n",
                                     "SOUL.md": f"# Aide\nLe coffre : {t}/coffre.json ; JetonFacticeDuTestMur\n", "secret.txt": "x\n"})
        cli("agent apercu, proposition refusée (clé interdite, mur ouvert, outil, mcp, méthode, fichier, coffre)", "agent", "apercu", "gardien", "aide")
        cli("agent appliquer, proposition refusée", "agent", "appliquer", "gardien", "aide.000000000000")
        proposer("gardien", "gardien", {"agent.conf": "nom = Gardien\noutils = berger-admin, mission:chef\n"})
        cli("agent apercu, un agent qui se propose lui-même", "agent", "apercu", "gardien", "gardien")
        proposer("gardien", "aide", {"agent.conf": "nom = Aide\nmoteur = claude\nheures = aucune\n"})
        cli("agent apercu, création sans SOUL.md", "agent", "apercu", "gardien", "aide")
        proposer("gardien", "aide", {"agent.conf": "nom = Aide\nmoteur = claude\nheures = aucune\noutils = ecrire:chef\n", "SOUL.md": "# Aide\n\nAide le chef.\n",
                                     "taches/revue.md": "# Revue\n"})
        cli("agent apercu, création applicable", "agent", "apercu", "gardien", "aide")
        cli("agent appliquer, usage (sans empreinte)", "agent", "appliquer", "gardien", "aide")
        cli("agent appliquer, empreinte changée", "agent", "appliquer", "gardien", "aide.0123456789ab")
        cli("agent appliquer, création (nouveau, regenerer, journaux)", "agent", "appliquer", "gardien", "aide." + empreinte("agent apercu, création applicable"))
        proposer("gardien", "cx", {"agent.conf": "nom = Cx\nheures = 8-19\nmoteur = codex\noutils = ecrire:chef\n", "SOUL.md": "# cx, revu\n"})
        cli("agent apercu, modification (droits avant → après)", "agent", "apercu", "gardien", "cx")
        cli("agent appliquer, modification (sauvegardes .avant, relance)", "agent", "appliquer", "gardien", "cx." + empreinte("agent apercu, modification (droits avant → après)"))
        proposer("gardien", "ouv", {"espace.toml": "a_cote = [\"fichiers\"]\n"})
        cli("agent apercu, disposition seule (espace.toml)", "agent", "apercu", "gardien", "ouv")
        cli("agent appliquer, disposition seule (espace auto)", "agent", "appliquer", "gardien", "ouv." + empreinte("agent apercu, disposition seule (espace.toml)"))
        # 4. le courtier : l'outil d'administration (aperçu en lecture, application et regenerer validés), un agent sans l'outil
        proposer("gardien", "aide", {"SOUL.md": "# Aide\n\nAide le chef et le coordinateur.\n"})
        courtier("courtier : agent sans l'outil, aperçu refusé", "intrus", "agent-apercu", "aide")
        courtier("courtier : aperçu par le gardien (lecture)", "gardien", "agent-apercu", "aide")
        courtier("courtier : application demandée (validation)", "gardien", "agent-appliquer", "aide.0123456789ab")
        courtier("courtier : regenerer demandé (validation)", "gardien", "regenerer")
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
        print(("ok     " if ok else "ÉCHEC  ") + f"{m['scenario']}" + ("" if ok else f" [écart : {ecart(a, m)}]")   # la porte ne garde que les lignes ÉCHEC :
              + f" : code {m['code']}, " + (m["stderr_fin"][:90] or m["stdout"].strip()[:90]))                    # la cause y est nommée, avant la sortie
        if not ok and a is not None:
            for k in sorted(set(a) | set(m)):
                if a.get(k) != m.get(k): print(f"         {k} : avant {json.dumps(a.get(k), ensure_ascii=False)[:400]}\n         {' ' * len(k)}   après {json.dumps(m.get(k), ensure_ascii=False)[:400]}")
    for nom in par_nom: ko += 1; print(f"ÉCHEC  {nom} : mesuré avant, absent après")
    print(f"---- {ko} écart(s) sur {len(mesure)} scénario(s)")
    sys.exit(1 if ko else 0)
