#!/usr/bin/env python3
"""Équivalence des verbes des messages et des besoins (modulaire, lot 4b, docs/plans/2026-10-27-modulaire-spec.md § Tests « Équivalence des sorties ») :
`message-deposer`, `message-remettre`, `delegation-suivi`, `demander`, `parler`, `parler-interactif`, `echange`, `besoin`, `besoin-ranger`, `annonce-outil`,
mesurés sur une installation JETABLE, puis comparés à ce que mesurait `main` avant le déplacement (tests/attendus/equivalence-messages.json).
Pour chaque scénario : code de sortie, sortie standard, dernière ligne d'erreur, fichiers écrits (file de messages attente/remis, TODO.md, journal,
échanges, besoins ouverts et clos, consignes régénérées, débits du courtier), appels à Herdr (un faux Herdr à état par BERGER_HERDR, et un faux
API Herdr doublée : la remise agent.prompt) et le moteur lancé par `demander` (un faux claude et un faux codex en tête du
PATH : la bascule). L'API Herdr (la remise agent.prompt) est doublée dans le processus : `herdr_api` du cœur, le même des deux côtés. Deux voies : la ligne de commande (formes, refus, transport privé --stdin) et le courtier, appelé directement (droits entre agents
ecrire:<agent> et deleguer:<agent>, débit d'ecrire, besoin et son gardien), qui lance berger en sous-processus.
Ce qui varie d'une exécution à l'autre est normalisé (chemin de l'installation, dates, heures, numéros de ligne). « commande inconnue » : la PREMIÈRE
ligne d'erreur est relevée (la suite est l'aide, qui gagne les lignes d'AIDE des familles : point 4 du correctif contrat).
Usage : python3 tests/equivalence-messages.py               mesure ce dépôt et compare (0 = identique)
        python3 tests/equivalence-messages.py --mesurer <source>   imprime la mesure d'un autre arbre (ex. un `git archive` de main)
        python3 tests/equivalence-messages.py --produire <source> <fichier>   écrit la mesure de <source> dans <fichier> (les attendus)
Les attendus (tests/attendus/equivalence-messages.json) ont été produits sur 1acc0ea (main à jour, sans le lot 4b ; d'abord sur ba46c43) :
        d=$(mktemp -d) && git archive 1acc0ea | tar -x -C "$d" && python3 tests/equivalence-messages.py --produire "$d" tests/attendus/equivalence-messages.json"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import hashlib, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ATTENDU = SRC / "tests/attendus/equivalence-messages.json"

# Un faux Herdr (ligne de commande) : chaque appel est tracé ; `agent list` rend les agents « vivants » du fichier d'état.
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
a = sys.argv[1:]
with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["cli"] + a) + "\n")
etat = Path(os.environ["FAUX_ETAT"]); d = json.loads(etat.read_text()) if etat.exists() else {}
r = {"agents": [{"name": n} for n in d.get("vivants", [])]} if a[:2] == ["agent", "list"] else {}
print(json.dumps({"result": r}))
'''

# Un faux moteur : il trace son nom, lit la consigne sur stdin et répond (codex écrit dans le fichier -o, claude sur sa sortie).
FAUX_MOTEUR = r'''#!/usr/bin/env python3
import json, os, sys
nom = os.path.basename(sys.argv[0]); consigne = sys.stdin.read()
with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["moteur", nom, os.environ.get("BERGER_AGENT", ""), len(consigne)]) + "\n")
if os.environ.get("FAUX_MUET") == nom: sys.exit(3)
texte = f"Réponse de {nom}.\nENGAGEMENTS:\n- relire le texte\n"
if nom == "codex": open(sys.argv[sys.argv.index("-o") + 1], "w").write(texte)
else: print(texte)
'''

# La ligne de commande, dans le processus : l'API Herdr du cœur (herdr_api, la remise agent.prompt) est doublée et tracée, des deux côtés
# (un vrai socket Unix n'est pas permis dans tous les bacs) ; `refus` dans le fichier d'état = la remise est refusée, comme le vrai serveur.
LANCEUR = r'''
import json, os, sys
src = sys.argv[1]; g = {"__name__": "essai", "__file__": src}
exec(compile(open(src).read(), src, "exec"), g)
def api(methode, params, strict=False):
    with open(os.environ["FAUX_TRACE"], "a") as f: f.write(json.dumps(["api", methode, params], ensure_ascii=False) + "\n")
    try: refus = json.loads(open(os.environ["FAUX_ETAT"]).read()).get("refus")
    except (OSError, ValueError): refus = False
    if refus and strict: raise ValueError("remise Herdr impossible (API indisponible ou message refusé)")
    return {}
g["herdr_api"] = api
g["main"](sys.argv[2:])
'''

# Le courtier, appelé directement (comme tests/equivalence-missions.py) ; attend la fin de ses fils (la délégation, puis son suivi).
APPEL = r'''
import json, runpy, sys, threading, time
g = runpy.run_path(sys.argv[1], run_name="essai")
agent, req = sys.argv[2], json.loads(sys.argv[3])
d = g["AGENTS"] / agent / "courrier"; (d / "encours").mkdir(parents=True, exist_ok=True)
f = d / "encours" / "1.json"; f.write_text(json.dumps(req))
g["traiter"](agent, f, {})
for _ in range(900):
    r = d / "reponses" / "1.json"
    if r.exists(): print(r.read_text()); r.unlink(); break
    time.sleep(0.1)
for th in threading.enumerate():
    if th is not threading.main_thread(): th.join(120)
'''

AGENTS = {
    "emetteur": "moteur = claude\nmur = ouvert\noutils = ecrire:cible, deleguer:cible\n",
    "cible": "moteur = claude\nmur = ouvert\n",
    "gardien": "moteur = claude\nmur = ouvert\n",
    "coord": "moteur = claude\nmur = ouvert\n",
    "outille": "moteur = claude\nmur = ouvert\noutils = essai\n",
    "intrus": "moteur = claude\nmur = ouvert\n",
}


def normaliser(texte, t):
    texte = str(texte).replace(str(t), "<T>")
    texte = re.sub(r"\d{8}-\d{6}-\d{6}", "<HORODATAGE>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}[T _]\d{2}:?\d{2}(:\d{2})?", "<DATE-HEURE>", texte)
    texte = re.sub(r"\d{4}-\d{2}-\d{2}", "<DATE>", texte)
    texte = re.sub(r"\b\d{2}:\d{2}(:\d{2})?\b", "<HEURE>", texte)
    texte = re.sub(r"\(used \d+ kB\)", "(used <N> kB)", texte)              # la pile mesurée par la RecursionError de json.loads varie d'une exécution à l'autre
    return re.sub(r"line \d+", "line <N>", texte)


def contenu(f, t):
    """Le texte normalisé d'un fichier ; les consignes régénérées (longues, du cœur des deux côtés) : leur empreinte."""
    x = normaliser(f.read_text(errors="replace"), t)
    if f.name in ("AGENTS.md", "BERGER.md", "CLAUDE.md", ".consigne-systeme.md", ".reglages-claude.json"):
        return "sha256:" + hashlib.sha256(x.encode()).hexdigest()[:16]
    return x


def fichiers(t):
    """Ce que les verbes des messages et des besoins écrivent : dossiers d'agents (files de messages, TODO, journal, consignes), échanges, besoins, débits.
    Une file de messages (noms horodatés, que la normalisation rend identiques) : la liste ordonnée de ses fichiers, chacun gardé, leur nombre avec
    (renvoi n° 89). Deux autres fichiers au même nom normalisé : une erreur, jamais l'un écrasé par l'autre."""
    out = {}
    for a in sorted(AGENTS):
        d = t / "agents" / a
        for f in sorted(d.rglob("*")):
            r = f.relative_to(d)
            if f.is_file() and r.parts[0] in ("messages", "TODO.md", "memory", "AGENTS.md", "BERGER.md", "CLAUDE.md", ".consigne-systeme.md", ".reglages-claude.json"):
                val = None if f.name == ".verrou" else contenu(f, t)
                if r.parts[0] == "messages":
                    out.setdefault(normaliser(f"{a}/{r.parent}/", t), []).append([normaliser(f.name, t), val]); continue
                cle = normaliser(f"{a}/{r}", t)
                if cle in out: raise RuntimeError(f"instantané : deux fichiers au même nom normalisé ({cle})")
                out[cle] = val
    for nom in ("courtier/echanges.jsonl", "sortie.txt"):
        e = t / nom; out[nom] = normaliser(e.read_text(), t) if e.exists() else None
    b = t / "courtier/besoins"
    for f in sorted(b.glob("*.json")) if b.is_dir() else []: out[f"courtier/besoins/{f.name}"] = normaliser(f.read_text(), t)
    for nom in ("courtier/ecrire-debit.json", "courtier/besoin-debit.json"):
        e = t / nom
        try: out[nom] = {k: len(v) for k, v in json.loads(e.read_text()).items()}
        except (OSError, ValueError): out[nom] = None
    s = t / "courtier/sollicitations"
    out["courtier/sollicitations"] = sorted(x.name for x in s.iterdir()) if s.is_dir() else []
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
    """Renvoi n° 89 : l'instantané garde CHAQUE fichier, même quand la normalisation rend leurs noms identiques (messages horodatés d'une file) ;
    un message antérieur modifié ou supprimé fait un écart. → la liste des défauts (vide = l'instantané voit tout)."""
    defauts = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td); q = t / "agents/cible/messages/attente"; q.mkdir(parents=True)
        for a in AGENTS: (t / "agents" / a).mkdir(parents=True, exist_ok=True)
        (q / "20261029-100000-000001.json").write_text('{"texte": "premier"}'); (q / "20261029-100000-000002.json").write_text('{"texte": "second"}')
        depart = fichiers(t)
        (q / "20261029-100000-000001.json").write_text('{"texte": "premier, modifié"}')
        if fichiers(t) == depart: defauts.append("un message antérieur modifié ne fait pas d'écart")
        (q / "20261029-100000-000001.json").unlink()
        if fichiers(t) == depart: defauts.append("un message antérieur supprimé ne fait pas d'écart")
    return defauts


def mesurer(src):
    src = Path(src).resolve(); resultats = []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        _produit.copier(src, t, ("bin", "courtier", "commun"))
        (t / "coffre.json").write_text("{}")
        (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n\n[outils.essai]\ntype = "essai"\n\n'
                                       f'[outils.admin]\ntype = "commandes"\ndossier = "{t}"\n[outils.admin.lecture]\netat = "true"\n'
                                       f'[outils.admin.actions]\ninstaller = "true"\n\n'
                                       f'[equipes.b]\nchef_projet = "gardien"\ncoordinateur = "gardien"\ndepot = "{t}/depot"\nprefixe = "b/"\n'
                                       f'fusion_par = "proprietaire"\ninstaller_outil = "admin installer"\n')
        for a, c in AGENTS.items():
            d = t / "agents" / a; (d / "memory").mkdir(parents=True); (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nheures = aucune\n{c}")
        (t / "faux").mkdir()
        for nom, texte in (("herdr", FAUX_HERDR), ("claude", FAUX_MOTEUR), ("codex", FAUX_MOTEUR), ("notify-send", "#!/bin/sh\nexit 0\n")):
            (t / "faux" / nom).write_text(texte); (t / "faux" / nom).chmod(0o755)
        trace, etat = t / "faux/trace.jsonl", t / "faux/etat.json"
        etat.write_text(json.dumps({"vivants": []}))
        env = dict(os.environ, BERGER_DIR=str(t), HOME=str(t), PATH=f"{t}/faux:{os.environ['PATH']}", BERGER_NOTIFY_SEND=str(t / "faux/notify-send"),
                   BERGER_HERDR=str(t / "faux/herdr"), FAUX_ETAT=str(etat), FAUX_TRACE=str(trace))
        for k in ("BERGER_AGENT", "AGENT_PANNE", "FAUX_MUET"): env.pop(k, None)
        avant = {"fichiers": fichiers(t)}

        def noter(nom, r):
            appels = [normaliser(l, t) for l in trace.read_text().splitlines()] if trace.exists() else []
            trace.unlink(missing_ok=True)
            apres = fichiers(t)
            ecrits = {k: v for k, v in apres.items() if avant["fichiers"].get(k, "∅") != v}
            if "courtier/echanges.jsonl" in ecrits: ecrits["courtier/echanges.jsonl"] = ajouts(avant["fichiers"].get("courtier/echanges.jsonl"), apres["courtier/echanges.jsonl"])   # les lignes ajoutées
            ecrits.update({k: "(supprimé)" for k in avant["fichiers"] if k not in apres})
            avant["fichiers"] = apres
            err = [l for l in r.stderr.splitlines() if l.strip()]
            fin = err[0] if err and err[0].startswith("commande inconnue : ") else (err[-1] if err else "")
            resultats.append({"scenario": nom, "code": r.returncode, "stdout": normaliser(r.stdout, t),
                              "stderr_fin": normaliser(fin, t), "fichiers_ecrits": ecrits, "herdr_et_moteurs": appels})

        def cli(nom, *argv, stdin=None, plus=None):
            r = subprocess.run([sys.executable, "-c", LANCEUR, str(t / "bin/berger"), *argv], input=stdin, env={**env, **(plus or {})}, capture_output=True, timeout=120)
            r.stdout, r.stderr = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace"); noter(nom, r)

        def courtier(nom, agent, outil, verbe, *args):
            req = json.dumps({"outil": outil, "verbe": verbe, "args": list(args)})
            r = subprocess.run([sys.executable, "-c", APPEL, str(t / "courtier/courtier"), agent, req], env=env, capture_output=True, text=True, timeout=300)
            try: rep = json.loads(r.stdout)
            except ValueError: rep = {"illisible": r.stdout[-200:]}
            r.stdout = json.dumps(rep, ensure_ascii=False, sort_keys=True); noter(nom, r)

        def vivants(*noms, refus=False): etat.write_text(json.dumps({"vivants": [f"{n}-claude" for n in noms], "refus": refus}))
        prive = lambda *v: json.dumps(list(v)).encode()
        b = lambda s: s.encode()

        # 1. message-deposer (transport privé obligatoire) et message-remettre
        cli("message-deposer en texte positionnel", "message-deposer", "emetteur", "cible", "bonjour")
        cli("message-deposer sans texte ni cible (--stdin)", "--stdin", stdin=prive("message-deposer", "emetteur"))
        cli("message-deposer vers un agent inconnu (--stdin)", "--stdin", stdin=prive("message-deposer", "emetteur", "fantome", "bonjour"))
        cli("message-deposer, cible endormie (--stdin)", "--stdin", stdin=prive("message-deposer", "emetteur", "cible", "Premier message."))
        cli("message-deposer, du propriétaire (--stdin)", "--stdin", stdin=prive("message-deposer", "Proprio", "cible", "Deuxième", "en deux mots."))
        cli("message-remettre sans agent", "message-remettre")
        cli("message-remettre, cible endormie", "message-remettre", "cible")
        (t / "agents/cible/.herdr.json").write_text(json.dumps({"workspace": "ws-cible", "agents": {"claude": "pe-cible"}}))
        vivants("cible", refus=True)
        cli("message-remettre, remise refusée par Herdr", "message-remettre", "cible")
        vivants("cible")
        cli("message-remettre, cible vivante (file vidée dans l'ordre)", "message-remettre", "cible")
        cli("message-deposer, cible vivante : remis (--stdin)", "--stdin", stdin=prive("message-deposer", "emetteur", "cible", "Remis tout de suite."))
        cli("transport : JSON invalide", "--stdin", stdin=b"[message-deposer")
        cli("transport : verbe privé imbriqué", "--stdin", stdin=prive("--stdin", "message-deposer"))
        cli("transport : UTF-8 requis", "--stdin", stdin=b'["message-deposer", "emetteur", "cible", "\xff"]')
        cli("transport : plus d'un Mio", "--stdin", stdin=b"[" + b" " * (1024 * 1024) + b"]")
        # 2. delegation-suivi et echange (usage interne du courtier)
        cli("delegation-suivi sans cible", "delegation-suivi", "emetteur", stdin=b"{}")
        cli("delegation-suivi, JSON invalide", "delegation-suivi", "emetteur", "cible", stdin=b"pas du json")
        cli("delegation-suivi, JSON qui n'est pas un objet", "delegation-suivi", "emetteur", "cible", stdin=b"[1, 2]")
        cli("delegation-suivi, engagements inscrits (TODO.md, résumé remis)", "delegation-suivi", "emetteur", "cible",
            stdin=b(json.dumps({"question": "Combien ?", "reponse": "Trois.", "engagements": ["vérifier", "recompter"], "en_trop": 1, "secrets": 1})))
        vivants()
        cli("delegation-suivi, aucun engagement (cible endormie)", "delegation-suivi", "emetteur", "cible",
            stdin=b(json.dumps({"question": "Q", "reponse": "", "engagements": [], "en_trop": 0, "secrets": 0})))
        cli("delegation-suivi, champs absents", "delegation-suivi", "emetteur", "cible", stdin=b(json.dumps({"question": "Q", "reponse": ""})))
        # renvoi n° 89 : json.loads ne lève pas que JSONDecodeError ; l'entrée illisible sort telle qu'avant, sans écarter la famille messages
        cli("delegation-suivi, entier de 5 000 chiffres (ValueError)", "delegation-suivi", "emetteur", "cible", stdin=b('{"en_trop": ' + "7" * 5000 + "}"))
        cli("delegation-suivi, imbrication trop profonde (RecursionError)", "delegation-suivi", "emetteur", "cible", stdin=b("[" * 100000 + "]" * 100000))
        cli("delegation-suivi, entrée non UTF-8", "delegation-suivi", "emetteur", "cible", stdin=b'{"question": "\xff"}')
        cli("echange sans texte", "echange", "emetteur", "cible")
        cli("echange, texte en arguments", "echange", "emetteur", "cible", "message", "texte", "en", "mots")
        cli("echange, texte sur stdin", "echange", "emetteur", "cible", "question", "--stdin", stdin=b"  texte\nsur deux lignes  ")
        cli("echange, stdin non UTF-8", "echange", "emetteur", "cible", "question", "--stdin", stdin=b"\xff\xfe")
        # 3. parler (transport privé par --stdin) et parler-interactif
        cli("parler en texte positionnel", "parler", "cible", "bonjour")
        cli("parler sans agent", "parler")
        cli("parler, option inconnue", "parler", "cible", "--stdin", "--vite", "x", stdin=b"x")
        cli("parler, option en double", "parler", "cible", "--stdin", "--de", "a", "--de", "b", stdin=b"x")
        cli("parler, option sans valeur", "parler", "cible", "--stdin", "--moteur", stdin=b"x")
        cli("parler, entrée non UTF-8", "parler", "cible", "--stdin", stdin=b"\xff\xfe")
        cli("parler, agent sans panneau", "parler", "emetteur", "--stdin", stdin=b"bonjour")
        vivants("cible", refus=True)
        cli("parler, remise refusée par Herdr", "parler", "cible", "--stdin", stdin=b"bonjour")
        vivants("cible")
        cli("parler, envoyé (échange tracé)", "parler", "cible", "--stdin", stdin=b"Bonjour toi.")
        cli("parler, --de et --moteur", "parler", "cible", "--stdin", "--de", "emetteur", "--moteur", "claude", stdin=b"De la part de.")
        cli("parler, --sans-echange", "parler", "cible", "--stdin", "--sans-echange", stdin=b"Service.")
        cli("parler-interactif : envoyé", "parler-interactif", stdin=b"1\nUn mot.\n")
        cli("parler-interactif : agent sans panneau", "parler-interactif", stdin=b"2\nUn mot.\n")
        cli("parler-interactif : message vide", "parler-interactif", stdin=b"2\n\n")
        cli("parler-interactif : numéro invalide", "parler-interactif", stdin=b"abc\n")
        cli("parler-interactif : hors liste", "parler-interactif", stdin=b"99\n")
        cli("parler-interactif : fin de l'entrée", "parler-interactif", stdin=b"")
        # 4. demander (transport privé par --stdin, bascule de moteur)
        cli("demander sans agent", "demander")
        cli("demander en texte positionnel", "demander", "cible", "question")
        cli("demander, options invalides", "demander", "cible", "--stdin", "--vite", "x", stdin=b"q")
        cli("demander, option sans valeur", "demander", "cible", "--stdin", "--moteur", stdin=b"q")
        cli("demander, entrée non UTF-8", "demander", "cible", "--stdin", stdin=b"\xff")
        cli("demander, agent inconnu", "demander", "fantome", "--stdin", stdin=b"q")
        cli("demander, moteur de l'agent (claude)", "demander", "cible", "--stdin", stdin=b"Une question ?")
        cli("demander, bascule : claude en panne simulée", "demander", "cible", "--stdin", stdin=b"Une question ?", plus={"AGENT_PANNE": "claude"})
        cli("demander, --moteur codex et --sortie", "demander", "cible", "--stdin", "--moteur", "codex", "--sortie", str(t / "sortie.txt"), stdin=b"Q ?")
        cli("demander, bascule : codex muet, claude répond", "demander", "cible", "--stdin", "--moteur", "codex", stdin=b"Q ?", plus={"FAUX_MUET": "codex"})
        cli("demander, les deux en échec", "demander", "cible", "--stdin", stdin=b"Q ?", plus={"AGENT_PANNE": "claude", "FAUX_MUET": "codex"})
        # 5. besoins : lecture, rangement, clôture
        cli("besoin liste, aucun", "besoin")
        cli("besoin liste --json, aucun", "besoin", "liste", "--json")
        cli("besoin, forme inconnue", "besoin", "autre")
        cli("besoin-ranger sans texte", "besoin-ranger", "emetteur")
        cli("besoin-ranger d'un agent inconnu", "besoin-ranger", "fantome", "outil", "x")
        cli("besoin-ranger : rangé, déposé au gardien", "besoin-ranger", "emetteur", "outil", "un", "outil", "de", "lecture")
        vivants("gardien")
        (t / "agents/gardien/.herdr.json").write_text(json.dumps({"workspace": "ws-gardien", "agents": {"claude": "pe-gardien"}}))
        cli("besoin-ranger : remis au gardien vivant", "besoin-ranger", "cible", "defaut", "un défaut")
        cli("besoin liste (texte)", "besoin", "liste")
        cli("besoin liste --json", "besoin", "--json")
        cli("besoin clore, état inconnu", "besoin", "clore", "1", "peut-etre", "x")
        cli("besoin clore, par un autre que le gardien", "besoin", "clore", "1", "fait", "x", "--par", "intrus")
        cli("besoin clore, introuvable", "besoin", "clore", "9", "fait", "x")
        cli("besoin clore, trop court (forme inconnue)", "besoin", "clore", "1")
        cli("besoin clore par le propriétaire (l'émetteur reçoit la suite)", "besoin", "clore", "1", "fait", "c'est", "fait")
        cli("besoin clore par le gardien (--par)", "besoin", "clore", "2", "refuse", "pas", "maintenant", "--par", "gardien")
        cli("besoin clore, déjà clos", "besoin", "clore", "1", "fait")
        # 6. annonce-outil
        cli("annonce-outil sans outil", "annonce-outil")
        cli("annonce-outil, aucune consigne rangée", "annonce-outil", "essai")
        (t / "courtier/consignes").mkdir(parents=True, exist_ok=True)
        (t / "courtier/consignes/essai.json").write_text(json.dumps({"outil": "essai", "version": "2", "empreinte": "e2", "aide": "lire : lit\nchercher : cherche", "texte": "Consigne d'essai."}))
        cli("annonce-outil --premiere (consignes écrites, aucun message)", "annonce-outil", "essai", "--premiere")
        cli("annonce-outil (message de service à chaque agent qui a l'outil)", "annonce-outil", "essai")
        # 7. le courtier : droits entre agents, débit d'ecrire, délégation (demander + suivi), besoin
        vivants()
        courtier("courtier : ecrire sans droit", "intrus", "ecrire", "cible", "bonjour")
        courtier("courtier : ecrire, droit déclaré (ecrire:cible)", "emetteur", "ecrire", "cible", "Message", "par", "le", "courtier.")
        courtier("courtier : ecrire, message vide", "emetteur", "ecrire", "cible", " ")
        (t / "courtier/ecrire-debit.json").write_text(json.dumps({"emetteur>cible": [time.time()] * 5}))   # cinq déjà acceptés dans l'heure
        courtier("courtier : ecrire, débit dépassé (5 par heure)", "emetteur", "ecrire", "cible", "Un de trop.")
        courtier("courtier : deleguer sans droit", "intrus", "deleguer", "cible", "Combien ?")
        courtier("courtier : deleguer vers un agent inconnu", "emetteur", "deleguer", "fantome", "Combien ?")
        courtier("courtier : deleguer, droit déclaré (demander puis suivi)", "emetteur", "deleguer", "cible", "Combien", "font", "deux", "et", "deux ?")
        courtier("courtier : besoin d'un agent (rangé, au gardien)", "emetteur", "besoin", "droit", "lire", "le", "dossier", "commun")
        courtier("courtier : besoin liste, pas le gardien", "emetteur", "besoin", "liste")
        courtier("courtier : besoin liste, le gardien", "gardien", "besoin", "liste")
        courtier("courtier : besoin clore par le gardien", "gardien", "besoin", "clore", "3", "transmis", "au", "propriétaire")
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
