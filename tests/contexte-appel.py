#!/usr/bin/env python3
"""Tests du contexte PROPRE À CHAQUE APPEL du courtier (12/10/2026) — sans modèle, sans Herdr, installation JETABLE, avec le
VRAI courtier (chargé comme module).
Vécu le 12/10 : les demandes de fusion portaient le MAUVAIS agent — le contexte (qui demande, son dossier) était écrit sur
l'objet outil, partagé par tous les fils du courtier ; un appel long le relisait après qu'un autre agent l'avait réécrit.
- deux développeurs, deux copies, deux demander-fusion CONCURRENTS (verify lent pour le premier) : chaque verify tourne
  dans SA copie et chaque demande porte SON agent ;
- chaque outil qui a un contexte (découverts dans le code : un nouvel outil n'est pas oublié) le garde PAR FIL : deux fils
  ne voient jamais le contexte l'un de l'autre, un fil qui n'a rien posé voit la valeur par défaut ;
- une collecte de panneau ne change pas le contexte d'une demande en cours.
Usage : python3 tests/contexte-appel.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast, importlib.machinery, importlib.util, json, os, re, subprocess, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True)


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"; forge = m / "forge.git"; depot = m / "depot"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre").mkdir(); (m / "coffre/coffre-essai.json").write_text("{}")   # le dossier du coffre est masqué au verify : à part
    (i / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre/coffre-essai.json"\n\n'
        f'[equipes.p]\ndepot = "{depot}"\nverify = "sh verifier.sh"\npret = "true"\n\n'
        f'[panneaux.vue]\noutil = "p-dev"\nverbe = "etat"\ncadence = 60\n')
    os.environ.update(HOME=str(m), BERGER_DIR=str(i))
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    (depot / "verifier.sh").write_text("touch verify-ici\n"); git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ")
    git(depot, "push", "-q", "origin", "main")

    def developpeur(sujet, verify):
        """Un développeur jetable : agent p-<sujet>, SA copie sur SA branche, poussée, prête à demander la fusion."""
        copie, agent = m / f"copie-{sujet}", i / "agents" / f"p-{sujet}"
        subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", f"equipe/{sujet}")
        (copie / "verifier.sh").write_text(verify); (copie / sujet).write_text(sujet)
        git(copie, "add", "-A"); git(copie, "commit", "-qm", f"feat: {sujet}"); git(copie, "push", "-q", "-u", "origin", f"equipe/{sujet}")
        (copie / ".git/info/exclude").write_text("verify-*\n")          # le verify laisse sa trace sans salir la copie
        (agent / "memory").mkdir(parents=True)
        (agent / "agent.conf").write_text(f"nom = p-{sujet}\noutils = p-dev\nprojet = p\nsujet = {sujet}\ncopie = {copie}\n"
                                          f"branche = equipe/{sujet}\nport = 0\n")
        return copie

    # le premier verify est LENT : il prévient qu'il a commencé, attend que le second appel soit FINI, puis laisse sa trace
    # (le signal est posé DANS sa copie : le bac à sable du verify ne voit qu'elle)
    lent = developpeur("lent", "touch verify-commence; for k in $(seq 300); do [ -f verify-second-fini ] && break; sleep 0.1; done; touch verify-ici\n")
    vite = developpeur("vite", "touch verify-ici\n")

    loader = importlib.machinery.SourceFileLoader("courtier_essai", str(i / "courtier/courtier"))
    spec = importlib.util.spec_from_loader("courtier_essai", loader); C = importlib.util.module_from_spec(spec); loader.exec_module(C)

    def demande(agent, outil, verbe, *a):
        enc = i / "agents" / agent / "courrier/encours"; enc.mkdir(parents=True, exist_ok=True)
        f = enc / f"{verbe}-{time.time_ns()}.json"
        f.write_text(json.dumps({"outil": outil, "verbe": verbe, "args": list(a)})); C.traiter(agent, f, {})
        return json.loads((f.parent.parent / "reponses" / f.name).read_text())

    # ── deux demander-fusion concurrents ──
    reponses = {}
    def fusion(sujet): reponses[sujet] = demande(f"p-{sujet}", "p-dev", "demander-fusion", f"livré : {sujet}, verify joué")
    fil = threading.Thread(target=fusion, args=("lent",)); fil.start()
    for _ in range(300):                                               # le premier est DANS son verify…
        if (lent / "verify-commence").exists(): break
        time.sleep(0.1)
    dire((lent / "verify-commence").exists(), "le premier verify a commencé (appel long en cours)")
    fusion("vite"); (lent / "verify-second-fini").write_text("x")              # … quand le second fait toute sa demande
    fil.join(120)
    dem = i / "equipes/p/demandes"
    lire = lambda s: json.loads((dem / f"{s}.json").read_text()) if (dem / f"{s}.json").is_file() else {}
    dire(reponses.get("vite", {}).get("ok") and reponses.get("lent", {}).get("ok"),
         f"les deux demandes sont acceptées ({str(reponses)[:200]})")
    dire(lire("vite").get("agent") == "p-vite", f"la demande « vite » porte SON agent ({lire('vite').get('agent')})")
    dire(lire("lent").get("agent") == "p-lent",
         f"la demande « lent » porte SON agent, même finie après l'autre appel ({lire('lent').get('agent')})")
    dire((lent / "verify-ici").exists() and (vite / "verify-ici").exists(), "chaque verify a tourné dans SA copie")
    dire(lire("lent").get("branche") == "equipe/lent" and lire("vite").get("branche") == "equipe/vite", "chaque demande porte SA branche")
    ech = [json.loads(l) for l in (i / "courtier/echanges.jsonl").read_text().splitlines()] if (i / "courtier/echanges.jsonl").is_file() else []
    de = {e.get("texte", "").split(" :")[0]: e.get("de") for e in ech if e.get("genre") == "demande de fusion"}
    dire(de == {"lent": "p-lent", "vite": "p-vite"}, f"Échanges : chaque demande de fusion au nom de SON agent ({de})")

    # ── chaque outil à contexte le garde PAR FIL ──
    def outils_a_contexte():
        """Les classes d'outils qui lisent self.contexte (dans le code : un nouvel outil n'est pas oublié) + SitesPermis du courtier."""
        out = {}
        for f in sorted((i / "courtier/outils").glob("*.py")):
            if f.name == "_contexte.py" or not re.search(r"self\.contexte\b", f.read_text()): continue
            sp = importlib.util.spec_from_file_location(f"essai_{f.stem}", f); mod = importlib.util.module_from_spec(sp); sp.loader.exec_module(mod)
            texte = f.read_text()
            for c in ast.walk(ast.parse(texte)):
                if isinstance(c, ast.ClassDef) and re.search(r"self\.contexte\b", ast.get_source_segment(texte, c)):
                    out[f"{f.stem}.{c.name}"] = getattr(mod, c.name)
        out["courtier.SitesPermis"] = C.SitesPermis
        return out

    trouves = outils_a_contexte()
    dire({"copie.Outil", "equipe_dev.Outil", "equipe_chef.Outil", "_commandes.Base", "scripts.Outil", "projets.Outil", "nextcloud.Outil",
          "pages_publiques.Outil"} <= set(trouves), f"outils à contexte trouvés dans le code ({', '.join(sorted(trouves))})")
    for nom, cls in sorted(trouves.items()):
        o = object.__new__(cls)                                       # sans __init__ : seul le contexte est éprouvé
        defaut = getattr(o, "contexte", "absent"); vus = {}; pose = threading.Event(); autre_a_ecrit = threading.Event()
        def premier():
            o.contexte = {"agent": "premier"}; pose.set(); autre_a_ecrit.wait(5); vus["premier"] = o.contexte
        def second():
            pose.wait(5); o.contexte = {"agent": "second"}; vus["second"] = o.contexte; autre_a_ecrit.set()
        def neuf(): vus["neuf"] = getattr(o, "contexte", "absent")
        f1, f2 = threading.Thread(target=premier), threading.Thread(target=second); f1.start(); f2.start(); f1.join(10); f2.join(10)
        f3 = threading.Thread(target=neuf); f3.start(); f3.join(10)
        dire(vus.get("premier") == {"agent": "premier"} and vus.get("second") == {"agent": "second"},
             f"{nom} : chaque fil relit SON contexte après que l'autre a écrit ({vus.get('premier')}, {vus.get('second')})")
        dire(vus.get("neuf") == defaut and defaut in (None, {}), f"{nom} : un fil neuf voit la valeur par défaut ({vus.get('neuf')!r})")

    # ── une collecte de panneau ne touche pas une demande en cours ──
    o = C.OBJETS["p-dev"]; vu = {}; pose = threading.Event(); collecte = threading.Event()
    def appel():
        C.contexte("p-dev", "p-lent"); pose.set(); collecte.wait(30); vu["agent"] = o.contexte.get("agent"); vu["copie"] = o.valeurs()["copie"]
    f1 = threading.Thread(target=appel); f1.start(); pose.wait(10)
    f2 = threading.Thread(target=C.collecter, args=("vue", C.CONFIG["panneaux"]["vue"])); f2.start(); f2.join(60); collecte.set(); f1.join(30)
    dire(vu == {"agent": "p-lent", "copie": str(lent)}, f"une collecte de panneau ne change pas le contexte d'une demande en cours ({vu})")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
