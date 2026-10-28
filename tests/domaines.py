#!/usr/bin/env python3
"""Tests des sites permis par projet (equipes/<projet>/domaines, 12/10/2026) — sans modèle, sans Herdr, installation JETABLE,
avec le VRAI courtier (chargé comme module).
- mur généré : projet à liste → coordinateur et développeurs : allowedDomains = la liste + strictAllowlist, sans deny-all,
  fichier .reseau-claude.json passé par --settings (seul endroit où Claude lit strictAllowlist) et protégé (denyWrite +
  Edit) ; projet sans liste, liste vide, chef de projet, agent hors projet → deny-all comme avant ; Codex : aucun réseau ;
- motif strict (joker, IP, port, majuscules, localhost, nom sans point refusés) ;
- berger equipe domaine ajouter|retirer : liste réécrite, Échanges, réglages régénérés ;
- courtier : seul le coordinateur demande ; écriture en attente, rien avant la décision ; valideur = le superviseur ; superviseur
  membre du projet ou demandeur → le propriétaire.
L'effet réel du mur (un domaine listé répond, un autre est refusé) : tests/sonde-domaines.py, joué par tests/tout.sh.
Usage : python3 tests/domaines.py (0 = tout passe)"""
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
    _produit.copier(SRC, i, ("bin", "courtier", "commun")); _produit.admettre_moteurs(i)
    (m / "coffre-essai.json").write_text("{}")
    for d in ("depot-a", "depot-b", "depot-c"): (m / d).mkdir()
    (m / "role-existant").mkdir()
    (i / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n\n'
        f'[equipes.alpha]\ndepot = "{m}/depot-a"\nchef_projet = "chef"\ncoordinateur = "coord"\n\n'
        f'[equipes.beta]\ndepot = "{m}/depot-b"\ncoordinateur = "gardien"\n\n'
        f'[equipes.gamma]\ndepot = "{m}/depot-c"\ncoordinateur = "coord"\n')
    agents = {"coord": "moteur = claude\noutils = equipe:alpha, equipe:gamma\n",
              "chef": "moteur = claude\n",
              "alpha-x": "moteur = claude\nprojet = alpha\nsujet = x\n",
              "alpha-y": "moteur = codex\nprojet = alpha\nsujet = y\n",
              "gamma-z": "moteur = claude\nprojet = gamma\nsujet = z\n",
              "gardien": "moteur = claude\nsuperviseur = oui\noutils = equipe:beta\n",
              "beta-w": "moteur = claude\nprojet = beta\nsujet = w\n",
              "seul": "moteur = claude\n",
              "ext": f"moteur = claude\nprojet = alpha\nsujet = e\ndossier = {m}/role-existant\n",
              "libre": "moteur = claude\nmur = ouvert\nprojet = alpha\nsujet = l\n"}
    for a, plus in agents.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\npanneaux = claude\nheures = aucune\n{plus}" + ("" if "outils" in plus else "outils =\n"))
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    os.environ.update(HOME=str(m), BERGER_DIR=str(i))
    def berger(*a): return subprocess.run([sys.executable, str(i / "bin/berger"), "--stdin"], input=json.dumps(list(a)), env=env, capture_output=True, text=True, timeout=120)
    def reglages(a): return json.loads((i / "agents" / a / ".claude/settings.json").read_text())
    def reseau(a): return reglages(a)["sandbox"]["network"]
    def deny_all(a): return reseau(a).get("deniedDomains") == ["*"] and not reseau(a).get("allowedDomains")
    def args(a):
        r = berger("args", a, "claude", "--non-interactif")
        try: return json.loads(r.stdout)["args"]
        except (ValueError, KeyError): return ["ERREUR " + r.stderr[-200:]]
    def fichier_settings(a):
        x = args(a); return Path(x[x.index("--settings") + 1]) if "--settings" in x else None
    LISTE = i / "equipes/alpha/domaines"

    r = berger("regenerer"); dire(r.returncode == 0, f"regenerer réussit sans aucune liste ({r.stderr.strip()[-160:]})")
    dire(all(deny_all(a) for a in agents if a not in ("libre", "ext")), "sans liste : tous les agents stricts en deny-all (comme avant)")
    fe = fichier_settings("ext")
    dire(fe is not None and json.loads(fe.read_text())["sandbox"]["network"].get("deniedDomains") == ["*"], "sans liste : agent à dossier externe en deny-all")
    dire(fichier_settings("alpha-x") is None and not (i / "agents/alpha-x/.reseau-claude.json").exists(),
         "sans liste : aucun --settings réseau, aucun fichier .reseau-claude.json")

    # ── motif strict ──
    for mauvais, quoi in (("*.exemple.fr", "joker"), ("10.0.0.1", "adresse IP"), ("exemple.fr:443", "port"), ("Exemple.fr", "majuscules"),
                          ("localhost", "localhost"), ("exemple", "nom sans point"), ("exemple..fr", "label vide"),
                          ("-x.exemple.fr", "tiret initial"), ("exemple.fr.", "point final"), ("https://exemple.fr", "URL"),
                          ("a" * 64 + ".fr", "label de plus de 63 caractères"), ("ex emple.fr", "espace")):
        r = berger("equipe", "domaine", "alpha", "ajouter", mauvais, "--par", "coord")
        dire(r.returncode != 0 and not LISTE.exists(), f"motif : {quoi} refusé ({mauvais[:30]})")
    dire(berger("equipe", "domaine", "zz", "ajouter", "api.exemple.fr", "--par", "coord").returncode != 0, "projet inconnu refusé")
    dire(berger("equipe", "domaine", "alpha", "ouvrir", "api.exemple.fr", "--par", "coord").returncode != 0, "action inconnue refusée")
    r = berger("equipe", "domaine", "alpha", "ajouter", "api.exemple.fr", "--par", "coord", "--essai")
    dire(r.returncode == 0 and not LISTE.exists() and "api.exemple.fr" in r.stdout, "--essai : aperçu sans rien écrire")

    # ── ajouter : liste, Échanges, réglages ──
    r = berger("equipe", "domaine", "alpha", "ajouter", "api.exemple.fr", "--par", "coord")
    dire(r.returncode == 0, f"ajouter api.exemple.fr au projet alpha ({(r.stderr or r.stdout).strip()[-160:]})")
    berger("equipe", "domaine", "alpha", "ajouter", "depot.exemple.org", "--par", "coord")
    dire(berger("equipe", "domaine", "alpha", "ajouter", "api.exemple.fr", "--par", "coord").returncode != 0, "déjà permis : refusé")
    lignes = [x for x in LISTE.read_text().splitlines() if x and not x.startswith("#")]
    dire(lignes == ["api.exemple.fr", "depot.exemple.org"], f"liste du projet : noms exacts, triés ({lignes})")
    ech = [json.loads(x) for x in (i / "courtier/echanges.jsonl").read_text().splitlines()]
    dire(any(e["genre"] == "domaine" and "api.exemple.fr" in e["texte"] and e["de"] == "coord" for e in ech), "trace dans Échanges (genre domaine)")
    L = ["api.exemple.fr", "depot.exemple.org"]
    for a in ("coord", "alpha-x", "alpha-y"):
        n = reseau(a)
        dire(n.get("allowedDomains") == L and n.get("strictAllowlist") is True and "*" not in n.get("deniedDomains", []),
             f"{a} (coordinateur ou développeur) : allowedDomains = la liste, strictAllowlist, sans deny-all")
    f = fichier_settings("alpha-x")
    dire(f == i / "agents/alpha-x/.reseau-claude.json" and json.loads(f.read_text()) == {"sandbox": {"network": {"allowedDomains": L, "strictAllowlist": True}}},
         "--settings .reseau-claude.json : la liste stricte (le SEUL endroit où Claude lit strictAllowlist)")
    dire(".reseau-claude.json" in (SRC / "tests/tout.sh").read_text().split("claude_p()", 1)[1].split("\n}", 1)[0][:600],
         "tests/tout.sh lance Claude avec la liste stricte, comme au vrai lancement (sinon l'essai réel ne prouverait rien)")
    x = args("alpha-x"); dire(x[:2] == ["--setting-sources", "project,local"], "les réglages du projet (skills, refus) restent lus")
    s = reglages("alpha-x"); fr = str(i / "agents/alpha-x/.reseau-claude.json")
    dire(fr in s["sandbox"]["filesystem"]["denyWrite"] and f"Edit(~/{Path(fr).relative_to(m)})" in s["permissions"]["deny"],
         "le fichier réseau est protégé : denyWrite + refus d'édition (l'agent ne s'ajoute pas un site)")
    for a in ("chef", "seul", "gardien", "beta-w"):
        dire(deny_all(a) and fichier_settings(a) is None, f"{a} (hors liste : chef de projet, autre agent, autre projet sans liste) : deny-all")
    dire(reseau("gamma-z").get("deniedDomains") == ["*"], "projet gamma (même coordinateur, sans liste) : son développeur reste en deny-all")
    fe = fichier_settings("ext")
    dire(json.loads(fe.read_text())["sandbox"]["network"] == {"allowedDomains": L, "strictAllowlist": True},
         "agent à dossier externe : liste stricte dans ses réglages --settings")
    se = json.loads(fe.read_text())
    dire(str(fe) in se["sandbox"]["filesystem"]["denyWrite"], "agent à dossier externe : son .reglages-claude.json est protégé (denyWrite)")
    dire(not (i / "agents/libre/.reseau-claude.json").exists(), "mur ouvert : rien de généré (hors du sujet)")
    cx = (i / ".codex/config.toml").read_text()
    dire("network" not in cx.lower() and "api.exemple.fr" not in cx, "Codex : aucun réseau ouvert (pas de filtrage par domaine prouvé)")
    rg = (i / "agents/alpha-x/AGENTS.md").read_text()
    dire("api.exemple.fr" in rg and "Codex" in rg, "règles du développeur : les sites permis et « Codex : aucun réseau »")
    dire("api.exemple.fr" not in (i / "agents/seul/AGENTS.md").read_text(), "règles d'un agent hors projet : aucun site")

    # ── retirer : retour au deny-all ──
    for d in L: berger("equipe", "domaine", "alpha", "retirer", d, "--par", "coord")
    dire(berger("equipe", "domaine", "alpha", "retirer", "api.exemple.fr", "--par", "coord").returncode != 0, "retirer un nom absent : refusé")
    dire(deny_all("alpha-x") and deny_all("coord") and fichier_settings("alpha-x") is None and not (i / "agents/alpha-x/.reseau-claude.json").exists(),
         "liste vidée : retour au deny-all, fichier réseau retiré")
    LISTE.write_text("# rien\n\n")
    berger("regenerer"); dire(deny_all("alpha-x"), "liste vide (commentaires seuls) : deny-all")
    LISTE.write_text("*.exemple.fr\nbon.exemple.fr\n10.0.0.1\n")
    r = berger("regenerer")
    dire(reseau("alpha-x").get("allowedDomains") == ["bon.exemple.fr"] and "ignoré" in r.stdout + r.stderr,
         "liste retouchée à la main : lignes invalides ignorées et signalées, jamais un joker")
    LISTE.unlink(); berger("regenerer")

    # ── courtier : demande, valideur, exécution ──
    loader = importlib.machinery.SourceFileLoader("courtier_essai", str(i / "courtier/courtier"))
    spec = importlib.util.spec_from_loader("courtier_essai", loader); C = importlib.util.module_from_spec(spec); loader.exec_module(C)
    def demande(agent, verbe, *a):
        enc = i / "agents" / agent / "courrier/encours"; enc.mkdir(parents=True, exist_ok=True)
        f = enc / f"{verbe}-{len(list(enc.parent.rglob('*.json')))}.json"
        f.write_text(json.dumps({"outil": "equipe", "verbe": verbe, "args": list(a)})); C.traiter(agent, f, {})
        for _ in range(100):
            if (f.parent.parent / "reponses" / f.name).exists(): break
            __import__("time").sleep(0.1)
        return json.loads((f.parent.parent / "reponses" / f.name).read_text())
    def decider(n, decision="valider"):
        (C.VALIDATIONS / f"{n}.decision").write_text(decision + "\n"); C.traiter_decisions()
        return json.loads((C.VALIDATIONS / f"{n}.fait.json").read_text())

    dire(not demande("alpha-x", "domaine", "alpha", "ajouter", "api.exemple.fr")["ok"], "courtier : un développeur ne peut pas demander un site")
    dire(not demande("seul", "domaine", "alpha", "ajouter", "api.exemple.fr")["ok"], "courtier : un agent hors équipe ne peut pas demander un site")
    dire(not demande("coord", "domaine", "alpha", "ajouter", "*.exemple.fr")["ok"] and not list(C.VALIDATIONS.glob("*.json")),
         "courtier : motif invalide refusé dès la demande, aucune validation créée")
    r = demande("coord", "domaine", "alpha", "ajouter", "api.exemple.fr")
    dire(r.get("ok") and r.get("en_attente"), "courtier : le coordinateur DEMANDE → validation en attente")
    dire(not LISTE.exists() and deny_all("alpha-x"), "rien n'est ouvert avant la décision")
    v = json.loads((C.VALIDATIONS / f"{r['en_attente']}.json").read_text())
    dire(v.get("valideur") == "gardien", "valideur : le superviseur (pas le propriétaire, pas le demandeur)")
    d = decider(r["en_attente"])
    dire(d["etat"] == "validé et exécuté" and reseau("alpha-x").get("allowedDomains") == ["api.exemple.fr"],
         f"validé : liste écrite, réglages régénérés ({str(d.get('resultat'))[:120]})")
    r = demande("coord", "domaines", "alpha")
    dire(r.get("ok") and r.get("donnees") == ["api.exemple.fr"], "courtier : le coordinateur lit la liste (domaines)")
    r = demande("coord", "domaine", "alpha", "retirer", "api.exemple.fr"); d = decider(r["en_attente"], "refuser")
    dire(d["etat"] == "refusé" and reseau("alpha-x").get("allowedDomains") == ["api.exemple.fr"], "refusé : rien ne change")
    r = demande("gardien", "domaine", "beta", "ajouter", "api.exemple.fr")
    v = json.loads((C.VALIDATIONS / f"{r['en_attente']}.json").read_text())
    dire(v.get("valideur") is None, "le superviseur coordonne le projet (son mur changerait) : le propriétaire décide")
    jl = (i / "courtier/appels.log").read_text()
    dire("equipe\tdomaine" in jl and "REFUSÉ" in jl, "journal du courtier : demandes acceptées et refusées tracées")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
