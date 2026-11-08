#!/usr/bin/env python3
"""Lot 1 de la spec 2026-10-28-modeles : la table [modeles], la règle par type de travail et la trace de la mission (ligne 2 de
MISSION.md). Installation JETABLE, sans modèle ni Herdr. Usage : python3 tests/modeles-table.py (0 = OK).
Garde : sur la branche du lot, aucun fichier sous courtier/ dans le diff (sinon le lot passe cas 1 et attend son go)."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import inspect, json, os, re, subprocess, sys, tempfile, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0
TYPES = {"spec": "gros", "relecture": "gros", "securite": "gros", "courtier": "gros", "mur": "gros", "decision": "gros",
         "code": "moyen", "deplacement": "moyen", "tests": "moyen", "docs": "leger", "resume": "leger", "surveillance": "leger"}   # figés ici


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# 1. config.exemple.toml : le bloc [modeles] décommenté charge, avec les 12 types figés
ex = (SRC / "config.exemple.toml").read_text().splitlines()
debut = next(i for i, l in enumerate(ex) if l.startswith("# [modeles.claude]"))
fin = next(i for i, l in enumerate(ex) if l.startswith("# surveillance"))
bloc = [re.sub(r"^# ?", "", l) for l in ex[debut:fin + 1] if re.match(r"# (\[modeles|[a-z]+ += )", l)]
cfg = tomllib.loads("\n".join(bloc))["modeles"]
dire(set(cfg["types"].items()) == set(TYPES.items()), "config.exemple.toml : [modeles.types] = les 12 types figés du lot")
dire(all(set(cfg[m]) == {"gros", "moyen", "leger"} for m in ("claude", "codex")), "config.exemple.toml : trois niveaux par moteur")

# 2. noyau/modeles.py : aucun nom de moteur ; le cœur ne teste pas un moteur par son nom
mod = (SRC / "bin/noyau/modeles.py").read_text()
dire(not re.search(r"claude|codex", mod, re.I), "bin/noyau/modeles.py ne nomme aucun moteur")

with tempfile.TemporaryDirectory() as td:
    t = Path(td); _produit.copier(SRC, t)
    (t / "bin/moteurs/zz_essai.py").write_text(
        "NOM = 'essai'\nORDRE = 9\nefforts_permis = ('bas', 'haut')\ndef executable(): return None\ndef version(): return '1'\n"
        "def verdict(): return None\ndef args(a, interactif=True): return ['--base']\n"
        "def args_modele(modele, effort=None): return ['--mod', modele] + (['--eff', effort] if effort else [])\n"
        "def lecteur_conso(): return lambda index: []\n")
    TABLE = ('[modeles.claude]\ngros = [{modele = "opus"}]\nmoyen = [{modele = "sonnet"}]\nleger = [{modele = "haiku"}]\n'
             '[modeles.codex]\ngros = [{modele = "g-gros", effort = "high"}]\nmoyen = [{modele = "g-moyen", effort = "medium"}]\n'
             'leger = [{modele = "g-leger", effort = "low"}]\n'
             '[modeles.essai]\ngros = [{modele = "e-gros", effort = "haut"}]\nmoyen = [{modele = "e-moyen"}]\nleger = [{modele = "e-leger"}]\n'
             '[modeles.types]\n' + "".join(f'{k} = "{v}"\n' for k, v in TYPES.items()))
    (t / "config.toml").write_text('proprietaire = "Essai"\n[missions]\nmodeles_claude = ["haiku"]\n' + TABLE)
    ag = t / "agents/dev"; (ag / "memory").mkdir(parents=True)
    (ag / "agent.conf").write_text("nom = dev\nmoteur = claude\nheures = aucune\noutils =\n")
    PROG = r'''
import json, runpy, sys, types
sys.argv = ["berger"]
g = runpy.run_path(%r, run_name="essai")
m = g["moteurs"]; out = {"charges": m.MOTEURS, "ecartes": m.MOTEURS_REFUSES}
def essai(*a, **k):
    try: return list(m.decider_mission(*a, **k))
    except SystemExit as e: return "REFUS " + str(e.code)
out["types"] = {tp: essai("claude", None, "Fais ça.\nType : " + tp + "\nMerci.", "chef") for tp in %r}
out["sans_type"] = essai("claude", None, "Fais ça.", "chef")
out["niveau_agent"] = essai("claude", None, "Fais ça.", "chef", "leger")
out["type_inconnu"] = essai("claude", None, "Type : zzz", "chef")
out["deux_types"] = essai("claude", None, "Type : spec\nType : code", "chef")
out["memes_types"] = essai("claude", None, "Type : code\ntype: CODE", "chef")
out["niveau_agent_inconnu"] = essai("claude", None, "Fais ça.", "chef", "enorme")
out["niveau_agent_type"] = essai("claude", None, "Fais ça.", "chef", 3)
out["explicite"] = essai("claude", "sonnet", "Type : spec", "chef")
out["modele_inconnu"] = essai("claude", "opus-9", "Type : spec", "chef")
out["moteur_inconnu"] = essai("zzz", None, "Type : spec", "chef")
out["essai_effort"] = essai("essai", None, "Type : spec", "chef")
out["essai_moyen"] = essai("essai", None, "Type : code", "chef")
out["verifier"] = {mt: m.noyau.modeles.verifier(mt, m.module(mt).efforts_permis) for mt in m.MOTEURS}
out["args"] = m.args_moteur("dev", "essai")
def lancement(ligne1, ligne2=""):
    open(%r, "w").write(ligne1 + "\n" + ligne2 + "\n\nTexte\n")
    try: return m.args_moteur("dev", "essai")
    except SystemExit as e: return "REFUS " + str(e.code)
out["lance_aide"] = lancement("moteur : essai · modèle : --help")
out["lance_effort"] = lancement("moteur : essai · modèle : e-gros", "niveau : gros · raison : x · effort : turbo")
out["lance_effort_autre_moteur"] = lancement("moteur : essai · modèle : e-gros", "niveau : gros · raison : x · effort : max")
out["lance_espace"] = lancement("moteur : essai · modèle : safe model", "niveau : gros · raison : x · effort : bas")
out["lance_effort_espace"] = lancement("moteur : essai · modèle : e-gros", "niveau : gros · raison : x · effort : very high")
out["lance_effort_seul"] = lancement("moteur : essai", "niveau : gros · raison : x · effort : very high")
out["lance_modele_vide"] = lancement("moteur : essai · modèle : ", "niveau : gros · raison : x")
out["lance_niveau_ligne"] = lancement("moteur : essai · modèle : e-gros", "niveau : gros x · raison : r · effort : turbo")
out["lance_sans_champ"] = lancement("moteur : essai", "niveau : gros · raison : x")
out["lance_bon"] = lancement("moteur : essai · modèle : e-gros", "niveau : gros · raison : x · effort : bas")
open(%r, "w").write("moteur : essai · modèle : e-gros\nniveau : gros · raison : type spec (règle) · effort : haut\n\nTexte\n")
out["args_mission"] = m.args_moteur("dev", "essai"); out["reglages"] = g["reglages_mission"]("dev")
out["trace"] = m.noyau.modeles.trace_mission("dev")
out["src_args"] = __import__("inspect").getsource(m.args_moteur) + __import__("inspect").getsource(m.decider_mission)
# mission() : ligne 2 écrite, ligne 1 intacte, suivi la rend
(g["dossier"]("dev") / "MISSION.md").unlink()
G = g["mission"].__globals__      # le vrai espace du cœur (run_path en rend une copie)
G["echange"] = lambda *a, **k: None; G["parler"] = lambda *a, **k: None; G["agent_vivant"] = lambda a: True
G["time"] = types.SimpleNamespace(sleep=lambda s: None)
g["mission"]("dev", "Fais ça.\nType : tests", "chef")
out["fichier"] = (g["dossier"]("dev") / "MISSION.md").read_text(); out["reglages2"] = g["reglages_mission"]("dev")
vm = dict(G); exec(open(%r).read(), vm); out["vue"] = vm["donnees"](G["hote_mission"]("dev"))["missions"]
out["vue_texte"] = "\n".join(vm["rendu_texte"](vm["donnees"](G["hote_mission"]("dev")), 140, 20))
s = g["suivi"]("dev"); out["suivi"] = {k: s.get(k, "ABSENT") for k in ("moteur", "modele", "niveau", "raison", "effort")}
print("\n@@" + json.dumps(out))
''' % (str(t / "bin/berger"), list(TYPES), str(ag / "MISSION.md"), str(ag / "MISSION.md"), str(t / "bin/vues/missions.py"))
    env = {**os.environ, "BERGER_DIR": str(t), "HOME": str(t)}
    r = subprocess.run([sys.executable, "-c", PROG], env=env, capture_output=True, text=True)
    try: o = json.loads(r.stdout.split("@@")[-1])
    except ValueError: o = None; print(r.stdout[-1500:], r.stderr[-2500:])
    dire(o is not None, "le programme d'essai tourne dans l'installation jetable")
    if o:
        dire("essai" in o["charges"] and "claude" in o["charges"], f"un moteur posé dans bin/moteurs/ (zz_essai.py) entre dans la liste sans toucher bin/berger ({o['charges']})")
        for tp, niv in TYPES.items():
            r_ = o["types"][tp]
            dire(isinstance(r_, list) and f"niveau : {niv} · raison : type {tp} (règle)" in r_[2], f"type {tp} → niveau {niv}")
        dire(o["types"]["spec"][1] == "opus" and o["types"]["code"][1] == "sonnet" and o["types"]["docs"][1] == "haiku", "le modèle vient de la table (opus / sonnet / haiku)")
        dire("type de travail manquant" in o["sans_type"] and "Type : spec" in o["sans_type"], "refus : type manquant sans « niveau = » (nommé)")
        dire(isinstance(o["niveau_agent"], list) and "niveau : leger · raison : niveau de l'agent" in o["niveau_agent"][2], "type absent : le niveau de agent.conf s'applique")
        dire("type de travail inconnu : zzz" in o["type_inconnu"] and "spec" in o["type_inconnu"], "refus : type inconnu (nommé, avec la liste)")
        dire("deux lignes" in o["deux_types"], "refus : deux lignes « Type : » différentes")
        dire(isinstance(o["memes_types"], list) and o["memes_types"][2] == "\nniveau : moyen · raison : type code (règle)", f"deux lignes identiques (casse comprise) : une seule règle ({o['memes_types']})")
        dire(isinstance(o["niveau_agent_inconnu"], str) and o["niveau_agent_inconnu"].startswith("REFUS niveau inconnu : enorme"), f"refus : niveau de agent.conf inconnu ({o['niveau_agent_inconnu']})")
        dire(isinstance(o["niveau_agent_type"], str) and o["niveau_agent_type"].startswith("REFUS niveau inconnu : 3"), f"refus : niveau de agent.conf qui n'est pas une chaîne ({o['niveau_agent_type']})")
        dire(isinstance(o["explicite"], list) and o["explicite"][1] == "sonnet" and "niveau : moyen · raison : choix explicite de chef" in o["explicite"][2],
             "modèle explicite de la table : accepté, niveau de la table, raison « choix explicite »")
        dire("modèle opus-9 inconnu pour claude" in o["modele_inconnu"] and "[modeles.claude]" in o["modele_inconnu"], "refus : modèle hors table, avec son nom")
        dire(o["moteur_inconnu"].startswith("REFUS moteur inconnu : zzz"), "refus : moteur inconnu (nommé)")
        dire(o["essai_effort"][1] == "e-gros" and o["essai_effort"][2].endswith("· effort : haut"), "l'effort de la table est inscrit (ligne 2)")
        dire(o["essai_moyen"][2] == "\nniveau : moyen · raison : type code (règle)", "sans effort : pas de « effort : » dans la ligne 2")
        dire(all(v == [] for v in o["verifier"].values()), f"chaque moteur chargé a ses trois niveaux, efforts permis ({o['verifier']})")
        dire(o["args"] == ["--base"], "args_moteur : sans mission, rien n'est ajouté")
        dire(o["args_mission"] == ["--base", "--mod", "e-gros", "--eff", "haut"], f"args_moteur : appelle args_modele du moteur ({o['args_mission']})")
        dire(o["reglages"] == ["essai", "e-gros"] and o["reglages2"][0] == "claude", "reglages_mission lit toujours la ligne 1 (ligne 2 présente)")
        dire(isinstance(o["lance_aide"], str) and "lancement refusé pour dev" in o["lance_aide"] and "--help" in o["lance_aide"], f"lancement : modèle « --help » refusé, nommé ({o['lance_aide']})")
        dire(isinstance(o["lance_effort"], str) and "effort" in o["lance_effort"] and "turbo" in o["lance_effort"], f"lancement : effort lu dans MISSION.md hors des efforts permis refusé, nommé ({o['lance_effort']})")
        dire(isinstance(o["lance_espace"], str) and "lancement refusé pour dev" in o["lance_espace"] and "safe model" in o["lance_espace"], f"lancement : « modèle : safe model » (espace) refusé, nommé, jamais lancé sans modèle ({o['lance_espace']})")
        dire(isinstance(o["lance_effort_espace"], str) and "very high" in o["lance_effort_espace"], f"lancement : « effort : very high » refusé, nommé, jamais lancé sans effort ({o['lance_effort_espace']})")
        dire(isinstance(o["lance_effort_seul"], str) and "very high" in o["lance_effort_seul"], "lancement : effort invalide refusé même sans modèle")
        dire(isinstance(o["lance_modele_vide"], str) and "modèle invalide" in o["lance_modele_vide"], f"lancement : « modèle : » vide (présent, invalide) refusé ({o['lance_modele_vide']})")
        dire(isinstance(o["lance_niveau_ligne"], str) and "turbo" in o["lance_niveau_ligne"], "lancement : ligne 2 à niveau étrange : l'effort est tout de même lu et refusé")
        dire(o["lance_sans_champ"] == ["--base"], f"lancement : champs vraiment absents : rien n'est ajouté ({o['lance_sans_champ']})")
        dire(isinstance(o["lance_effort_autre_moteur"], str) and "max" in o["lance_effort_autre_moteur"], "lancement : effort d'un autre moteur refusé")
        dire(o["lance_bon"] == ["--base", "--mod", "e-gros", "--eff", "bas"], f"lancement : modèle et effort valides acceptés ({o['lance_bon']})")
        vue = o["vue"][0] if o["vue"] else {}
        dire((vue.get("niveau"), vue.get("raison"), vue.get("effort")) == ("moyen", "type tests (règle)", None), f"vue Missions : niveau, raison, effort collectés ({vue})")
        dire("moyen — type tests (règle)" in o["vue_texte"], "vue Missions : niveau et raison affichés")
        dire(o["trace"][:1] == ["gros"] and o["trace"][2] == "haut", "trace_mission lit la ligne 2")
        dire(not re.search(r"""[=!]=\s*["'](claude|codex)["']""", o["src_args"]), "ni args_moteur ni decider_mission ne testent un moteur par son nom")
        dire(o["fichier"].splitlines()[1] == "moteur : claude · modèle : sonnet" and o["fichier"].splitlines()[2] == "niveau : moyen · raison : type tests (règle)",
             f"mission() : ligne 1 intacte, ligne 2 = niveau · raison ({o['fichier'].splitlines()[1:3]})")
        dire(o["suivi"] == {"moteur": "claude", "modele": "sonnet", "niveau": "moyen", "raison": "type tests (règle)", "effort": None}, f"suivi rend les cinq champs ({o['suivi']})")

    # Défauts de la table : niveau inconnu, effort hors efforts_permis, moteur sans section (module noyau lu directement)
    os.environ["BERGER_DIR"] = str(t); sys.path.insert(0, str(t / "bin"))
    from noyau import modeles as M
    dire(M.verifier("x", (), {})[0].startswith("moteur x sans section [modeles.x]"), "refus : moteur sans section (nommé)")
    base = {"x": {"gros": [{"modele": "a"}], "moyen": [{"modele": "b"}], "leger": [{"modele": "c"}]}}
    dire(M.verifier("x", (), base) == [], "table complète : aucun défaut")
    dire(any("niveau inconnu pour x : enorme" in p for p in M.verifier("x", (), {"x": {**base["x"], "enorme": [{"modele": "d"}]}})), "refus : niveau inconnu (nommé)")
    dire(any("niveau leger absent" in p for p in M.verifier("x", (), {"x": {k: v for k, v in base["x"].items() if k != "leger"}})), "refus : niveau manquant (nommé)")
    dire(any("effort turbo hors des efforts permis" in p for p in M.verifier("x", ("bas",), {"x": {**base["x"], "gros": [{"modele": "a", "effort": "turbo"}]}})), "refus : effort hors de efforts_permis")
    dire(any("effort" in p for p in M.verifier("x", (), {"x": {**base["x"], "gros": [{"modele": "a", "effort": "bas"}]}})), "refus : un effort pour un moteur qui n'en a pas")

    # Cas malveillants et types TOML (la config est une entrée) : refus nommés, jamais d'exception
    def mauvais(entree, efforts=("bas",), attendu=""):
        pb = M.verifier("x", efforts, {"x": {**base["x"], "gros": [entree] if not isinstance(entree, list) else entree}})
        return bool(pb) and attendu in pb[0]
    for nom_, v in (("saut de ligne", "safe\nniveau : gros · raison : x · effort : turbo"), ("--help", "--help"), ("espace", "a b"), ("tiret initial", "-m"),
                    ("vide", ""), ("65 signes", "a" * 65), ("chiffre", 7), ("liste", ["a"]), ("fin de ligne", "a\n")):
        dire(mauvais({"modele": v}, attendu="modèle invalide"), f"refus : modèle {nom_} (nommé)")
    for nom_, v in (("saut de ligne", "bas\nx"), ("espace", "ba s"), ("tiret initial", "--x"), ("chiffre", 3)):
        dire(mauvais({"modele": "a", "effort": v}, attendu="effort invalide"), f"refus : effort {nom_} (nommé)")
    dire(M.nom_sur("claude-opus-4.5") and M.nom_sur("gpt_5") and not M.nom_sur(None), "nom sûr : lettres, chiffres, . _ -")
    for nom_, v in (("entier", 1), ("chaîne", "opus"), ("table", {"modele": "a"})):
        dire(M.verifier("x", (), {"x": {**base["x"], "moyen": v}}) != [] and True, f"types TOML : niveau moyen = {nom_} : refus sans exception")
    dire(any("une liste d'entrées" in p for p in M.verifier("x", (), {"x": {**base["x"], "moyen": 1}})), "types TOML : moyen = 1 refusé, nommé")
    dire(any("une table {modele" in p for p in M.verifier("x", (), {"x": {**base["x"], "moyen": ["opus", 2]}})), "types TOML : entrées qui ne sont pas des tables refusées")
    dire(any("niveau moyen absent" in p for p in M.verifier("x", (), {"x": {**base["x"], "moyen": []}})), "types TOML : liste vide = niveau absent")
    dire(M.verifier_types({"types": []})[0].startswith("[modeles.types] doit être une table"), "types TOML : [modeles.types] qui n'est pas une table refusé")
    dire(any("code : niveau inconnu 5" in p for p in M.verifier_types({"types": {"code": 5}})), "types TOML : niveau d'un type qui n'est pas une chaîne")
    dire(any("code : niveau inconnu 'enorme'" in p for p in M.verifier_types({"types": {"code": "enorme"}})), "types TOML : niveau d'un type inconnu")
    for tt in ({"types": {"code": 5}}, {"types": {"code": "enorme"}}, {"types": 3}):
        try: M.decider("x", None, "Type : code", "chef", None, (), {"x": base["x"], **tt}); r_ = "pas de refus"
        except ValueError as e_: r_ = str(e_)
        dire(r_.startswith("[modeles.types]"), f"decider : types invalides {tt['types']!r} refusés, nommés ({r_[:70]})")
    try: M.decider("x", None, "Type : code", "chef", None, (), {"x": {**base["x"], "moyen": 1}, "types": {"code": "moyen"}}); r_ = "pas de refus"
    except ValueError as e_: r_ = str(e_)
    dire("une liste d'entrées" in r_, f"decider : niveau mal typé refusé sans TypeError ({r_[:70]})")

    # Le type de la racine [modeles] est vérifié AVANT le test d'absence
    for nom_, v in (("entier", 1), ("liste vide", []), ("faux", False), ("chaîne", "x"), ("zéro", 0)):
        try: M.table(v); r_ = "pas de refus"
        except ValueError as e_: r_ = str(e_)
        dire(r_.startswith("[modeles] doit être une table") and type(v).__name__ in r_, f"racine [modeles] = {nom_} : refus nommé ({r_[:70]})")
    dire(M.table({}) == {} and M.table({"types": {}}) == {"types": {}}, "racine [modeles] : table (même vide) acceptée")
    for tt in (1, [], False):
        try: M.sections(tt); r_ = "pas de refus"
        except ValueError as e_: r_ = str(e_)
        dire(r_.startswith("[modeles] doit être une table"), f"sections() refuse une racine {tt!r} sans AttributeError")

    # La table absente : rien ne change (repli nommé sur [missions] modeles_<moteur>)
    (t / "config.toml").write_text('proprietaire = "Essai"\n[missions]\nmodeles_claude = ["haiku"]\n')
    prog2 = ("import runpy, sys\nsys.argv = ['berger']\nm = runpy.run_path(%r, run_name='essai')['moteurs']\n"
             "for a in (('claude','haiku','Fais ça.','chef'), ('claude','opus','Fais ça.','chef'), ('claude',None,'Fais ça.','chef')):\n"
             "    try: print('OK', m.decider_mission(*a))\n"
             "    except SystemExit as e: print('REFUS', e.code)\n") % str(t / "bin/berger")
    for brut in ("modeles = 1", "modeles = []", "modeles = false"):
        (t / "config.toml").write_text('proprietaire = "Essai"\n' + brut + '\n')
        r2 = subprocess.run([sys.executable, "-c", prog2], env=env, capture_output=True, text=True)
        sortie2 = r2.stdout.splitlines()
        dire(len(sortie2) == 3 and all(x.startswith("REFUS [modeles] doit être une table") and "rien n'a été créé" in x for x in sortie2) and "Traceback" not in r2.stderr,
             f"decider_mission : « {brut} » refusé en le nommant, la règle n'est pas désactivée en silence ({sortie2[:1]} {r2.stderr[-100:]})")
    (t / "config.toml").write_text('proprietaire = "Essai"\n[missions]\nmodeles_claude = ["haiku"]\n')
    sortie = subprocess.run([sys.executable, "-c", prog2], env=env, capture_output=True, text=True).stdout.splitlines()
    dire(sortie[:1] == ["OK ('claude', 'haiku', '')"] and sortie[2:] == ["OK ('claude', None, '')"], f"table absente : aucun type exigé, aucune ligne 2 ({sortie})")
    dire(len(sortie) == 3 and "modèle non permis pour claude : opus (permis : haiku)" in sortie[1], "table absente : l'ancienne liste [missions] reste lue (repli nommé)")

# 3. « Type : » n'est pas un mot de la règle de go (courtier/outils/_portes.py inchangé)
portes = (SRC / "courtier/outils/_portes.py").read_text()
mots = re.search(r"GO_MOTS = \((.*?)\)\n", portes, re.S).group(1)
dire(not any(f'"{k}"' in mots for k in TYPES), "aucun type de travail n'est un mot de la règle de go (GO_MOTS)")
mg = {}; exec(compile(re.search(r"def mots_go.*?\n\n\n", portes, re.S).group(0), "mots_go", "exec"), {"re": re, "GO_MOTS": tuple(re.findall(r'"([^"]+)"', mots))}, mg)
dire(mg["mots_go"]("Fais ça.\nType : securite\nType : courtier\nType : mur") == [], "une ligne « Type : securite » ne marque pas le sujet « règle de go »")

# 4. Garde : sur la branche du lot, aucun fichier sous courtier/ dans le diff
br = subprocess.run(["git", "-C", str(SRC), "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
if br == "berger/modeles-lot1":
    base = next((b for b in ("origin/main", "main") if subprocess.run(["git", "-C", str(SRC), "rev-parse", "--verify", "-q", b], capture_output=True).returncode == 0), None)
    mb = subprocess.run(["git", "-C", str(SRC), "merge-base", "HEAD", base], capture_output=True, text=True).stdout.strip() if base else ""
    fichiers = subprocess.run(["git", "-C", str(SRC), "diff", "--name-only", mb], capture_output=True, text=True).stdout.split() if mb else None
    if fichiers is None: print("non mesuré : pas de branche principale pour comparer le diff du lot")
    else: dire(not [f for f in fichiers if f.startswith("courtier/")], f"le diff du lot ne touche aucun fichier sous courtier/ ({[f for f in fichiers if f.startswith('courtier/')] or 'aucun'})")
sys.exit(1 if ko else 0)
