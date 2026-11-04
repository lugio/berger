#!/usr/bin/env python3
"""Tests des projets d'équipe de la bibliothèque (lot 4, 08/10/2026) — sans modèle, sans Herdr, installation JETABLE, avec le
VRAI courtier (chargé comme module) : ouverture demandée par le chef de projet → validation → dossier + registre + réglages ;
refus (pas chef ni coordinateur, membre hors équipe, nom invalide) ; droits Claude ET Codex (membre : écriture ; non-membre :
masqué) ; règles ; partage d'un fichier propre, refus d'un fichier à secret, d'un non-membre, d'un chemin hors du dossier de
travail, et d'un lien piégé posé dans le projet ; journal ; fermeture → archives (rien supprimé), droits retirés, archives
masquées ; `projet_par = "coordinateur"` → le coordinateur décide. L'effet réel du mur (disque) : tests/tout.sh (sonde-mur).
Usage : python3 tests/bibliotheque-projets.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.machinery, importlib.util, json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    V = "VALEUR-" + "DU-COFFRE-" + str(123456)        # valeur d'ESSAI, construite à l'exécution (jamais écrite en clair)
    (m / "coffre-essai.json").write_text(json.dumps({"x": {"to" + "ken": V}}))
    (m / "depot").mkdir()
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n'
                                   f'[equipes.eq]\ndepot = "{m}/depot"\nchef_projet = "chef"\ncoordinateur = "coord"\n')
    agents = {"chef": ("claude", True, ""), "coord": ("claude", False, ""), "dev1": ("codex", False, "projet = eq\nsujet = x\n"),
              "autre": ("claude", True, "")}
    for a, (moteur, inscrit, plus) in agents.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\npanneaux = {moteur}\nheures = aucune\noutils =\n{plus}"
                                      + ("bibliotheque = oui\n" if inscrit else ""))
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    os.environ.update(HOME=str(m), BERGER_DIR=str(i))
    def berger(*a): return subprocess.run([sys.executable, str(i / "bin/berger"), "--stdin"], input=json.dumps(list(a)), env=env, capture_output=True, text=True, timeout=120)
    r = berger("regenerer"); dire(r.returncode == 0, "regenerer réussit (équipe, deux inscrits, un développeur Codex)")

    # ── refus par la commande ──
    dire(berger("projet", "ouvrir", "eq", "lot6", "chef,dev1", "--par", "autre").returncode != 0, "refus : ni chef de projet ni coordinateur")
    dire(berger("projet", "ouvrir", "eq", "lot6", "chef,autre", "--par", "chef").returncode != 0, "refus : membre hors de l'équipe")
    dire(berger("projet", "ouvrir", "eq", "Lot_6", "chef", "--par", "chef").returncode != 0, "refus : nom de projet invalide")
    dire(berger("projet", "ouvrir", "zz", "lot6", "chef", "--par", "chef").returncode != 0, "refus : équipe inconnue")

    # ── le vrai courtier ──
    loader = importlib.machinery.SourceFileLoader("courtier_essai", str(i / "courtier/courtier"))
    spec = importlib.util.spec_from_loader("courtier_essai", loader); C = importlib.util.module_from_spec(spec); loader.exec_module(C)
    def demande(agent, verbe, *args):
        enc = i / "agents" / agent / "courrier/encours"; enc.mkdir(parents=True, exist_ok=True)
        f = enc / f"{verbe}-{len(list(enc.parent.rglob('*.json')))}.json"
        f.write_text(json.dumps({"outil": "projet", "verbe": verbe, "args": list(args)})); C.traiter(agent, f, {})
        return json.loads((f.parent.parent / "reponses" / f.name).read_text())
    def decider(n, decision="valider"):
        (C.VALIDATIONS / f"{n}.decision").write_text(decision + "\n"); C.traiter_decisions()
        return json.loads((C.VALIDATIONS / f"{n}.fait.json").read_text())

    dire("projet" in C.OUTILS, "courtier : l'outil « projet » existe d'office (il y a une équipe)")
    dire(not demande("autre", "ouvrir", "eq", "lot6", "chef,dev1")["ok"], "courtier : un agent qui ne pilote pas l'équipe ne peut pas demander l'ouverture")
    r = demande("chef", "ouvrir", "eq", "lot6", "chef,dev1")
    dire(r.get("ok") and r.get("en_attente"), "courtier : le chef de projet DEMANDE l'ouverture → validation en attente, rien d'ouvert")
    P = i / "bibliotheque/equipes/eq/projets/lot6"
    dire(not P.exists(), "rien n'est créé avant la décision")
    n = r["en_attente"]; v = json.loads((C.VALIDATIONS / f"{n}.json").read_text())
    dire(v.get("valideur") is None, "projet_par par défaut : le propriétaire décide (aucun agent valideur)")
    d = decider(n); dire(d["etat"] == "validé et exécuté" and P.is_dir(), "validé : dossier du projet créé")
    reg = json.loads((i / "equipes/eq/projets.json").read_text())
    dire(reg.get("lot6", {}).get("membres") == ["chef", "dev1"], "registre (hors bibliothèque) : membres chef, dev1")
    dire(not demande("chef", "ouvrir", "eq", "lot6", "chef")["ok"], "refus : projet déjà ouvert")

    # ── droits générés ──
    def reglages(a): return json.loads((i / "agents" / a / ".claude/settings.json").read_text())
    def lecture_refusee(s, p): return f"Read(~/{p.relative_to(m)}/**)" in s["permissions"]["deny"]
    s = reglages("chef")
    dire(str(P) in s["sandbox"]["filesystem"].get("allowWrite", []) and not lecture_refusee(s, P), "Claude, membre : lit et écrit le projet")
    for a in ("autre", "coord"):
        s = reglages(a)
        dire(lecture_refusee(s, P) and str(P) not in s["sandbox"]["filesystem"].get("allowWrite", []), f"Claude, non-membre ({a}) : projet masqué, aucune écriture")
    cx = (i / ".codex/config.toml").read_text()
    def profil(a): return cx.split(f"[permissions.{a}.filesystem]", 1)[1].split("\n[", 1)[0]
    dire(f'"{P}" = "write"' in profil("dev1"), "Codex, membre (développeur) : « write » sur le projet")
    dire(f'"{P}" = "none"' in profil("autre") and f'"{P}" = "none"' in profil("coord"), "Codex, non-membres : projet « none »")
    dire(f'"{P}" = "none"' not in profil("dev1"), "Codex, membre : le projet n'est pas masqué")

    # ── règles ──
    rc, ra, rco = [(i / "agents" / a / "AGENTS.md").read_text() for a in ("chef", "autre", "coord")]
    dire(f"`{P}/`" in rc and "{projets_bibliotheque}" not in rc, "règles du membre : son projet nommé")
    dire("Projets d'équipe" not in ra, "règles d'un agent hors équipe : pas de section projets")
    dire("Projets d'équipe" in rco and "(aucun pour l'instant)" in rco, "règles du coordinateur (non membre) : la section, sans projet")

    # ── partager ──
    T = i / "bibliotheque/agents/chef/travail"
    (T / "note.md").write_text("Plan du lot 6.\n"); r = demande("chef", "partager", "eq", "lot6", "note.md")
    dire(r.get("ok") and (P / "note.md").read_text() == "Plan du lot 6.\n", "partager : fichier propre copié dans le projet")
    (T / "fuite.md").write_text("jeton : " + V + "\n")
    dire(not demande("chef", "partager", "eq", "lot6", "fuite.md")["ok"] and not (P / "fuite.md").exists(), "partager : fichier contenant une valeur du coffre REFUSÉ")
    (T / "cle.md").write_text("ghp_" + "A" * 36 + "\n")
    dire(not demande("chef", "partager", "eq", "lot6", "cle.md")["ok"], "partager : fichier contenant une forme de clé REFUSÉ")
    (i / "bibliotheque/agents/autre/travail/x.md").write_text("x")
    dire(not demande("autre", "partager", "eq", "lot6", "x.md")["ok"], "partager : un non-membre est refusé")
    (m / "dehors.md").write_text("x")
    dire(not demande("chef", "partager", "eq", "lot6", "../../../../dehors.md")["ok"], "partager : chemin hors de son dossier de travail refusé")
    # relecture du 08/10 (TOCTOU) : le courtier lit HORS bac à sable — un lien posé par l'agent dans SON travail/ ne doit
    # jamais lui faire lire le coffre (fichier remplacé par un lien ; lien dans un sous-dossier) ; un vrai sous-dossier passe
    avant = set(os.listdir(P))
    (T / "lien-coffre.md").symlink_to(m / "coffre-essai.json")
    dire(not demande("chef", "partager", "eq", "lot6", "lien-coffre.md")["ok"] and set(os.listdir(P)) == avant,
         "partager : un fichier remplacé par un LIEN vers le coffre est refusé, rien d'écrit")
    (T / "lien-propre.md").symlink_to(m / "dehors.md")         # cible SANS secret : seul le refus de suivre un lien peut l'arrêter
    dire(not demande("chef", "partager", "eq", "lot6", "lien-propre.md")["ok"] and set(os.listdir(P)) == avant,
         "partager : un lien vers un fichier hors du travail est refusé même sans secret (le lien n'est jamais suivi)")
    (m / "dehors-dir").mkdir(); (m / "dehors-dir/f.md").write_text((m / "coffre-essai.json").read_text()[:0] + "propre\n")
    (T / "sous").symlink_to(m / "dehors-dir")
    dire(not demande("chef", "partager", "eq", "lot6", "sous/f.md")["ok"] and set(os.listdir(P)) == avant,
         "partager : un LIEN dans un sous-dossier du chemin est refusé, rien d'écrit")
    (T / "vrai").mkdir(); (T / "vrai/ok.md").write_text("ok\n")
    dire(demande("chef", "partager", "eq", "lot6", "vrai/ok.md").get("ok") and (P / "ok.md").read_text() == "ok\n",
         "partager : un fichier d'un VRAI sous-dossier de son travail est copié")
    dire(not demande("chef", "partager", "eq", "lot6", "vrai")["ok"], "partager : un dossier (pas un fichier ordinaire) est refusé")
    os.mkfifo(T / "tube.md")                                     # sans O_NONBLOCK, l'ouverture bloquerait le courtier (08/10)
    dire(not demande("chef", "partager", "eq", "lot6", "tube.md")["ok"] and set(os.listdir(P)) - avant <= {"ok.md"},
         "partager : un tube (FIFO) est refusé SANS bloquer le courtier")
    (P / "piege.md").symlink_to(m / "cible-du-piege"); (T / "piege.md").write_text("propre\n")
    r = demande("chef", "partager", "eq", "lot6", "piege.md")
    dire(not (m / "cible-du-piege").exists() and (r.get("ok") is False or "piege-" in str(r.get("donnees"))),
         "partager : un lien piégé posé dans le projet n'emmène PAS l'écriture ailleurs")
    jl = (i / "courtier/appels.log").read_text()
    dire("projet\tpartager" in jl and "REFUSÉ" in jl, "journal du courtier : partages acceptés et refusés tracés")
    dire(V not in jl, "journal : aucune valeur du coffre")

    # ── fermer ──
    dire(not demande("dev1", "fermer", "eq", "lot6")["ok"], "fermer : un développeur ne peut pas le demander")
    r = demande("coord", "fermer", "eq", "lot6"); d = decider(r["en_attente"])
    arch = list((i / "bibliotheque/equipes/eq/archives").glob("lot6-*"))
    dire(d["etat"] == "validé et exécuté" and not P.exists() and len(arch) == 1 and (arch[0] / "note.md").is_file(),
         "fermé : dossier ARCHIVÉ avec son contenu, rien supprimé")
    dire("lot6" not in json.loads((i / "equipes/eq/projets.json").read_text()), "fermé : retiré du registre")
    s = reglages("chef"); A = i / "bibliotheque/equipes/eq/archives"
    dire(str(P) not in json.dumps(s["sandbox"]["filesystem"]) and lecture_refusee(s, A), "fermé : droits retirés au membre, archives masquées")
    cx = (i / ".codex/config.toml").read_text()
    dire(f'"{P}" = "write"' not in cx and f'"{A}" = "none"' in profil("dev1"), "fermé, Codex : plus d'écriture, archives « none »")

    # ── projet_par = coordinateur ──
    spec2 = importlib.util.spec_from_file_location("projets_essai", i / "courtier/outils/projets.py")
    mod = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(mod)
    o = mod.Outil({"berger": str(i), "racine": str(i / "bibliotheque"), "equipes": {"eq": {"coordinateur": "coord", "chef_projet": "chef", "projet_par": "coordinateur"}}}, None, None)
    dire(o.valideur("ouvrir", ["eq", "p", "chef"]) == "coord", "projet_par = coordinateur : le coordinateur décide (jamais le demandeur : le courtier y veille)")
    o2 = mod.Outil({"berger": str(i), "racine": str(i / "bibliotheque"), "equipes": {"eq": {}}}, None, None)
    o2.contexte = {"agent": "chef"}
    dire(o2.filtre_fuite("rien"), "outil seul, sans le filtre du courtier : tout partage est refusé par défaut")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
