#!/usr/bin/env python3
"""Tests des panneaux selon le rôle de l'agent ([espaces.<agent>] de config.toml) — sans modèle, avec un FAUX Herdr (jamais le
vrai) : à droite de l'agent « en cours » puis ses panneaux a_cote, ses onglets propres (1 à 4 panneaux), les commandes reprises
après un redémarrage, les sources filtrées, les checklists filtrées, le lecteur de fichiers. Usage : python3 tests/roles.py"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import io, json, os, re, runpy, shutil, sys, tempfile, time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0
ANSI = re.compile(r"\033\[[0-9;]*m")


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; a = sys.argv[1:]
with open(T + "/appels.log", "a") as f: f.write(json.dumps(a) + "\n")
n = sum(1 for _ in open(T + "/appels.log"))
if a[:3] == ["plugin", "config-dir", "herdr-file-viewer"]: print(T + "/reglages-lecteur"); sys.exit(0)
r = {}
if a[:2] == ["tab", "create"]: r = {"tab": {"tab_id": f"w9:t{n}"}, "root_pane": {"pane_id": f"w9:p{n}"}}
elif a[:2] == ["pane", "split"]: r = {"pane": {"pane_id": f"w9:p{n}"}}
print(json.dumps({"result": r}))
'''

CONFIG = '''
lecteur_fichiers = "{t}/lecteur"
[panneaux.cluster]
titre = "Cluster"
outil = "x"
verbe = "cluster.py"
[panneaux.pbs]
titre = "Sauvegardes PBS"
outil = "x"
verbe = "machines.py"
[panneaux.veille]
titre = "Veille éditeurs"
outil = "x"
verbe = "bulletins"
[panneaux.fortiguard]
titre = "FortiGuard"
outil = "x"
verbe = "fortiguard.py"
ignorer = ["no_license"]
[checklists]
dossier = "{t}/listes"
[espaces.infra]
a_cote = ["source:cluster", "fichiers"]
[espaces.infra.onglets]
"Sauvegardes" = ["source:pbs", "source:cluster,pbs", "checklists:dev"]
"Veille" = ["source:veille"]
'''


def installation(t, config):
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    (t / "coffre.json").write_text("{}")
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{t}/coffre.json"\n' + config.replace("{t}", str(t)))
    (t / "faux").mkdir(exist_ok=True); (t / "faux/herdr").write_text(FAUX_HERDR); os.chmod(t / "faux/herdr", 0o755)
    for a in ("infra", "autre"):
        (t / "agents" / a).mkdir(parents=True); (t / "agents" / a / "agent.conf").write_text(f"nom = {a.title()}\nicone = x\npanneaux = claude\n")
    os.environ.update({"BERGER_DIR": str(t), "FAUX_HERDR": str(t / "faux"), "BERGER_HERDR": str(t / "faux/herdr"),
                       "BERGER_HERDR_SOCKET": str(t / "faux/aucun.sock")})


def charger(t):
    m = runpy.run_path(str(t / "bin/berger"), run_name="essai")
    if m["HERDR"] != str(t / "faux/herdr"): sys.exit(f"ARRÊT : Berger n'utiliserait pas le faux Herdr ({m['HERDR']})")
    return m


def appels(t):
    f = t / "faux/appels.log"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


with tempfile.TemporaryDirectory() as t:
    t = Path(t); installation(t, CONFIG); m = charger(t)

    # 1. onglet Travail : « en cours » puis les panneaux du rôle, empilés à droite de l'agent
    ids = m["colonne_travail"]("infra", "w9:p0")
    runs = {x[2]: x[3] for x in appels(t) if x[:2] == ["pane", "run"]}
    dire(list(ids) == ["encours", "cote-1", "cote-2"], f"Travail : en cours puis 2 panneaux du rôle (obtenu {list(ids)})")
    dire(runs.get(ids.get("cote-1"), "").endswith("panneau source cluster"), "Travail : 1er panneau = source cluster")
    splits = [x for x in appels(t) if x[:2] == ["pane", "split"]]
    ratios = [x[x.index("--ratio") + 1] for x in splits]
    dire(ratios == ["0.58", "0.40", "0.50"], f"Travail : parts égales sous « en cours » (ratios {ratios})")
    dire(all(x[x.index("--direction") + 1] == "down" for x in splits[1:]), "Travail : panneaux du rôle empilés sous « en cours »")

    # 2. lecteur de fichiers : absent → dit ; présent → lancé dans le dossier de l'agent avec les réglages que Herdr lui donne
    dire("lecteur de fichiers absent" in runs.get(ids.get("cote-2"), ""), "fichiers : lecteur non installé → le panneau le dit")
    (t / "lecteur/target/release").mkdir(parents=True); (t / "lecteur/target/release/herdr-file-viewer").write_text("")
    c = m["commande_element"]("infra", "fichiers")
    dire(c.startswith(f"cd {t}/agents/infra") and f"HERDR_PLUGIN_CONFIG_DIR={t}/faux/reglages-lecteur" in c and c.endswith("herdr-file-viewer"),
         "fichiers : lecteur lancé dans le dossier de l'agent, réglages du plugin donnés par Herdr")
    dire(f"GIT_CEILING_DIRECTORIES={t}/agents " in c, "fichiers : racine = dossier de l'agent (git ne remonte pas au dépôt de Berger)")

    # 3. onglets propres au rôle : libellés, 1 à 4 panneaux chacun, chaque commande lancée
    (t / "faux/appels.log").unlink()
    o = m["onglets_agent"]("w9", "infra")
    labels = [x[x.index("--label") + 1] for x in appels(t) if x[:2] == ["tab", "create"]]
    dire(labels == ["Sauvegardes", "Veille"], f"onglets du rôle : Sauvegardes · Veille (obtenu {labels})")
    dire(list(o) == ["onglet-Sauvegardes-1", "onglet-Sauvegardes-2", "onglet-Sauvegardes-3", "onglet-Veille-1"], f"onglets : 3 + 1 panneaux (obtenu {list(o)})")
    runs = {x[2]: x[3] for x in appels(t) if x[:2] == ["pane", "run"]}
    dire(runs.get(o["onglet-Sauvegardes-2"], "").endswith("panneau source cluster,pbs") and runs.get(o["onglet-Sauvegardes-3"], "").endswith("panneau checklists dev"),
         "onglets : sources groupées et checklists filtrées lancées")

    # 4. reprise : chaque panneau du rôle a sa commande (berger reprendre le relance À SA PLACE)
    cmds = m["commandes_panneaux"]("infra")
    dire(all(k in cmds for k in list(ids) + list(o)), "reprise : une commande pour chaque panneau du rôle")
    dire("cote-1" not in m["commandes_panneaux"]("autre"), "agent sans [espaces.<agent>] : ancienne disposition (aucun panneau du rôle)")

    # 5. éléments refusés : type inconnu, type de panneau douteux
    dire(m["commande_element"]("infra", "panneau:../x").startswith("echo ") and m["commande_element"]("infra", "rm -rf /").startswith("echo "),
         "élément inconnu ou douteux : un message, jamais une commande")

    # 6. Sources filtrées : seulement les sources demandées ; un nom non déclaré est DIT
    r = t / "courtier/panneaux"; r.mkdir(parents=True, exist_ok=True)
    for nom, l in (("cluster", "✗ nœud pve9 absent"), ("pbs", "tout va bien")):
        (r / f"{nom}.json").write_text(json.dumps({"titre": nom, "quand": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True, "lignes": [l]}))
    v = "\n".join(ANSI.sub("", x) for x in m["VUES"]["sources"].vue_sources(120, 40, ["cluster", "absente"]))
    dire("Cluster" in v and "pve9" in v and "Sauvegardes PBS" not in v, "source:cluster : la seule source demandée")
    dire("non déclarée" in v and "absente" in v, "source non déclarée : signalée, pas ignorée")
    v2 = "\n".join(ANSI.sub("", x) for x in m["VUES"]["sources"].vue_sources(120, 40))
    dire("Cluster" in v2 and "Sauvegardes PBS" in v2, "onglet Sources de Berger : toujours toutes les sources")
    dire(any(g == "rouge" and "pve9" in tx for g, _, tx in m["alertes_synthese"]()), "Synthèse : relit aussi les sources des espaces d'agents")
    (r / "fortiguard.json").write_text(json.dumps({"titre": "FortiGuard", "quand": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True,
                                                   "lignes": ["❌ dlp  no_license", "❌ antivirus  expired"]}))
    al = [tx for g, _, tx in m["alertes_synthese"]() if g == "rouge"]
    dire(any("expired" in x for x in al) and not any("no_license" in x for x in al), "ignorer : un fait connu et voulu sort de la Synthèse, le reste y reste")

    # 7. Checklists filtrées
    (t / "listes").mkdir(); (t / "listes/1-dev.md").write_text("# Dev\n- [ ] coder\n"); (t / "listes/2-infra.md").write_text("# Infra\n- [ ] câbler\n")
    v = "\n".join(ANSI.sub("", x) for x in m["VUES"]["checklists"].vue_checklists(100, 40, ["dev"]))
    dire("coder" in v and "câbler" not in v, "checklists:dev : seulement les listes « dev »")
    v = "\n".join(ANSI.sub("", x) for x in m["VUES"]["checklists"].vue_checklists(100, 40))
    dire("coder" in v and "câbler" in v, "checklists sans filtre : toutes les listes")

print(f"==== {ko} échec(s)"); sys.exit(1 if ko else 0)
