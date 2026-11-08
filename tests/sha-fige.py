#!/usr/bin/env python3
"""Tests du SHA figé (spec docs/plans/2026-10-29-sha-fige-spec.md) — sans modèle : forge, dépôt du chef, copie jetable.
1. aperçu A, nouvelle demande B sous le même sujet → la validation (A) est refusée, main intact ;
2. aperçu A, branche repoussée sur B sans nouvelle demande → refus « la branche a bougé », main intact ;
3. aperçu A, rien ne bouge → A fusionné ;
4. validation sans SHA (ancienne forme) refusée ; 2e argument de l'agent refusé ; SHA mal formé refusé ; le courtier range
   les arguments FIGÉS par l'aperçu (jamais ceux de l'agent) ;
5. les portes distantes (<porte>_outil) reçoivent un SHA de 40 caractères, jamais une branche (chef et développeur) ;
6. une porte distante verte sans « commit testé : <sha> » (ou avec un autre SHA, ou avec PLUSIEURS lignes d'attestation)
   est rouge, et le message nomme le défaut ; un aperçu dont le commit est mal formé est refusé avant tout git.
Usage : python3 tests/sha-fige.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.machinery, importlib.util, json, os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
OUTILS = SRC / "courtier/outils"
SHA = re.compile(r"[0-9a-f]{40}")
ko = 0


def charger(t):
    spec = importlib.util.spec_from_file_location(f"outil_{t}", OUTILS / f"{t}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def git(d, *a):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-C", str(d), *a], capture_output=True, text=True)


def erreur(f, args):
    try: f(args); return ""
    except (ValueError, RuntimeError, PermissionError) as e: return str(e)


with tempfile.TemporaryDirectory() as t:
    t = Path(t); forge, depot, dem = t / "forge.git", t / "depot", t / "demandes"
    (t / "config.toml").write_text('proprietaire = "Test"\n'); os.environ["BERGER_DIR"] = str(t)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)])
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], capture_output=True)
    (depot / "doc.md").write_text("départ\n"); git(depot, "add", "-A"); git(depot, "commit", "-qm", "départ"); git(depot, "push", "-q", "origin", "main")
    forge_main = lambda: git(forge, "rev-parse", "main").stdout.strip()

    appels, mode = [], {"v": "atteste"}
    def faux_controle(args):                     # le verbe de lecture d'un outil distant : rend {code, sortie}
        appels.append(list(args)); sha = (args or [""])[0]
        ligne = {"atteste": f"commit testé : {sha}", "sans": "contrôles faits", "autre": f"commit testé : {'0' * 40}",
                 "double": f"commit testé : {sha}\ncommit testé : {'0' * 40}", "deux": f"commit testé : {sha}\n  commit testé : {sha}"}[mode["v"]]
        return {"code": 0, "sortie": f"{ligne}\nok contrôles"}

    REGLES = {"principale": "main", "demandes": str(dem), "pret_outil": "distant controler"}

    def developpeur(sujet):
        copie, agent = t / f"copie-{sujet}", t / f"agent-{sujet}"
        subprocess.run(["git", "clone", "-q", str(forge), str(copie)], capture_output=True); git(copie, "switch", "-q", "-c", f"equipe/{sujet}")
        git(copie, "config", "user.name", "t"); git(copie, "config", "user.email", "t@t.invalid")
        agent.mkdir(); (agent / "agent.conf").write_text(f"projet = p\nsujet = {sujet}\ncopie = {copie}\nbranche = equipe/{sujet}\nport = 0\n")
        d = charger("equipe_dev").Outil(dict(REGLES), None, None)
        d.portes_par = {"pret": faux_controle}; d.contexte = {"agent": f"p-{sujet}", "dossier": str(agent)}
        return d, copie

    def livrer(d, copie, fichier, texte, demander=True):
        (copie / fichier).write_text(texte); git(copie, "add", fichier); git(copie, "commit", "-qm", f"docs: {fichier}"); d.verbes["pousser"]([])
        if demander: d.verbes["demander-fusion"]([f"livré : {fichier} modifié, portes jouées"])
        return git(copie, "rev-parse", "HEAD").stdout.strip()

    chef = charger("equipe_chef").Outil({**REGLES, "depot": str(depot), "valide_par": None, "travail": str(t / "integration")}, None, None)
    chef.portes_par = {"pret": faux_controle}
    apercu, fusionner = chef.ecritures["fusionner"]

    # ── 1. aperçu A, nouvelle demande B sous le même sujet ──
    a, ca = developpeur("un"); A = livrer(a, ca, "un.md", "A\n")
    ap = apercu(["un"])
    dire(isinstance(ap, dict) and ap.get("args") == ["un", A] and A in ap.get("apercu", ""),
         "aperçu : les arguments figés sont [sujet, SHA complet], le texte montre le SHA complet")
    B = livrer(a, ca, "un.md", "B\n"); avant = forge_main()
    e = erreur(fusionner, ap["args"] if isinstance(ap, dict) else ["un", A])
    dire("a changé depuis l'aperçu" in e and forge_main() == avant, f"1. nouvelle demande B après l'aperçu de A : refus, main intact ({e[:90]})")

    # ── 2. aperçu A, branche repoussée sur B sans nouvelle demande ──
    b, cb = developpeur("deux"); A2 = livrer(b, cb, "deux.md", "A\n")
    ap = apercu(["deux"]); livrer(b, cb, "deux.md", "B\n", demander=False); avant = forge_main()
    e = erreur(fusionner, ap["args"] if isinstance(ap, dict) else ["deux", A2])
    dire("a bougé depuis l'aperçu" in e and forge_main() == avant, f"2. branche repoussée après l'aperçu : refus, main intact ({e[:90]})")

    # ── 4. formes refusées ──
    c, cc = developpeur("trois"); A3 = livrer(c, cc, "trois.md", "A\n")
    dire("antérieure au SHA figé" in erreur(fusionner, ["trois"]), "4. validation sans SHA (ancienne forme) : refus clair")
    dire("figé par le courtier" in erreur(apercu, ["trois", A3]), "4. un 2e argument de l'agent à l'aperçu : refus")
    dire("mal formé" in erreur(fusionner, ["trois", "main"]), "4. SHA mal formé (un nom de branche) : refus avant tout git")

    # ── 3. aperçu A, rien ne bouge → A fusionné ; 5. pret_outil reçoit le SHA ──
    ap = apercu(["trois"]); appels.clear()
    r = fusionner(ap["args"] if isinstance(ap, dict) else ["trois", A3])
    dire(forge_main() == A3 and "fusionnée" in str(r), "3. aperçu A, rien ne bouge : A fusionné en avance rapide")
    dire(appels == [[A3]], f"5. chef, fusion en avance rapide : pret_outil reçoit le SHA contrôlé ({appels})")

    # ── 5. rejouer, développeur (verbe seul et demande), mise à jour automatique ──
    d_, cd = developpeur("quatre"); appels.clear(); A4 = livrer(d_, cd, "quatre.md", "A\n")
    dire(appels == [[A4]], f"5. développeur, demander-fusion : l'outil reçoit le commit demandé ({appels})")
    appels.clear(); d_.verbes["pret"]([])
    dire(appels == [[A4]], f"5. développeur, verbe pret seul : l'outil reçoit le SHA poussé ({appels})")
    appels.clear(); chef.verbes["rejouer"](["quatre"])
    dire(appels == [[A4]], f"5. chef, rejouer : l'outil reçoit le commit demandé ({appels})")
    autre = t / "autre"; subprocess.run(["git", "clone", "-q", str(forge), str(autre)], capture_output=True)
    (autre / "ailleurs.md").write_text("x\n"); git(autre, "add", "-A"); git(autre, "commit", "-qm", "main avance"); git(autre, "push", "-q", "origin", "main")
    ap = apercu(["quatre"]); appels.clear()
    fusionner(ap["args"] if isinstance(ap, dict) else ["quatre", A4])
    cible = json.loads((dem / "quatre.json").read_text()).get("commit_fusion")
    dire(cible and forge_main() == cible and appels and all(x == [cible] for x in appels),
         f"5. chef, mise à jour automatique : l'outil reçoit le commit de mise à jour ({appels})")
    dire(all(len(x) == 1 and SHA.fullmatch(x[0]) for x in appels) and not git(forge, "branch", "--list", "integration/*").stdout.strip(),
         "5. jamais un nom de branche ; integration/<sujet> effacée")

    # ── 6. attestation du SHA testé ──
    e_, ce = developpeur("cinq"); livrer(e_, ce, "cinq.md", "A\n", demander=False)
    for m, quoi in (("sans", "sans la ligne « commit testé »"), ("autre", "avec un autre SHA")):
        mode["v"] = m
        r = e_.verbes["pret"]([])
        dire(r.get("code") != 0 and "n'a pas prouvé" in r.get("sortie", ""), f"6. porte distante verte {quoi} : rouge (verbe seul)")
        dire("pret : rouge" in erreur(e_.verbes["demander-fusion"], ["livré : cinq.md modifié, portes jouées"]), f"6. {quoi} : pas de demande")
    for m, quoi, motif in (("double", "avec le bon SHA ET un autre", "0" * 40), ("deux", "avec deux lignes d'attestation", "plusieurs")):
        mode["v"] = m
        r = e_.verbes["pret"]([])
        dire(r.get("code") != 0 and motif in r.get("sortie", "").splitlines()[-1], f"6. porte distante verte {quoi} : rouge, le message le nomme")
        dire("pret : rouge" in erreur(e_.verbes["demander-fusion"], ["livré : cinq.md modifié, portes jouées"]), f"6. {quoi} : pas de demande")
    mode["v"] = "autre"; r = e_.verbes["pret"]([])
    dire("0" * 40 in r.get("sortie", "").splitlines()[-1], "6. attestation d'un autre SHA : le message nomme ce SHA")
    mode["v"] = "sans"; git(depot, "fetch", "-q", "origin", "equipe/cinq")      # le chef rejoue un commit qu'il a récupéré
    res, _ = chef.jouer_portes(git(ce, "rev-parse", "HEAD").stdout.strip(), seules={"pret"})
    dire(res["pret"]["etat"] != "vert", "6. chef : porte distante sans attestation → pas verte")
    mode["v"] = "atteste"

    # ── 6. un commit figé mal formé est refusé à l'aperçu, avant tout git ──
    (dem / "six.json").write_text(json.dumps({"sujet": "six", "branche": "equipe/six", "commit": "main", "etat": "à relire",
                                              "resume": "livré : six.md modifié, portes jouées", "portes": {}}))
    gits, vrai_git = [], chef.git
    chef.git = lambda *a, **k: (gits.append(a), vrai_git(*a, **k))[1]
    e = erreur(apercu, ["six"]); chef.git = vrai_git
    dire("mal formé" in e and not gits, f"6. aperçu d'une demande au commit mal formé : refus avant tout git ({len(gits)} git, {e[:70]})")

# ── 4. le courtier range les arguments FIGÉS par l'aperçu ──
with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (i / "config.toml").write_text('proprietaire = "Proprio"\nmasques = []\n')
    os.environ.update(HOME=str(m), BERGER_DIR=str(i))
    loader = importlib.machinery.SourceFileLoader("courtier_sha", str(i / "courtier/courtier"))
    spec = importlib.util.spec_from_loader("courtier_sha", loader); C = importlib.util.module_from_spec(spec); loader.exec_module(C)
    C.contexte = lambda *a, **k: None; C.echange = lambda *a, **k: None; C.notifier_proprietaire = lambda *a, **k: None
    C.ECRITURES["essai"] = {"fige": (lambda a: {"apercu": "fusionner s (" + "a" * 40 + ")", "args": [a[0], "a" * 40]}, lambda a: a),
                            "texte": (lambda a: "texte seul", lambda a: a)}
    n, texte = C.demander_validation("chef", "essai", "fige", ["s"])
    v = json.loads((C.VALIDATIONS / f"{n}.json").read_text())
    dire(v["args"] == ["s", "a" * 40] and v["apercu"] == texte == "fusionner s (" + "a" * 40 + ")", "4. courtier : la validation range les arguments figés par l'aperçu")
    n, texte = C.demander_validation("chef", "essai", "texte", ["x"])
    dire(json.loads((C.VALIDATIONS / f"{n}.json").read_text())["args"] == ["x"] and texte == "texte seul", "4. courtier : un aperçu texte garde les arguments de l'agent")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
