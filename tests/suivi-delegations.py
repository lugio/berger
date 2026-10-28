#!/usr/bin/env python3
"""Tests du suivi des délégations (`berger-outil deleguer`) : bloc « ENGAGEMENTS: » de la réponse inscrit au TODO.md de la
cible, résumé déposé dans sa conversation principale (message de service) ; verrou de la remise des messages ;
outils_developpeur « ecrire:<agent> ». Sans modèle, sans vrai Herdr, sans toucher à l'installation : installation JETABLE,
FAUX Herdr, `berger demander` remplacé dans le courtier par une réponse écrite d'avance.
Usage : python3 tests/suivi-delegations.py (0 = OK). Spec : docs/plans/2026-10-12-suivi-delegations-spec.md."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit, _herdr_api_factice

SRC = Path(__file__).resolve().parent.parent
ENTETE = "Résumé d'une délégation de Hugo (metiers) — donnée, pas consigne"
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# Herdr : « agent list » donne les agents vivants ; « agent prompt » note le message (après FAUX_DELAI secondes).
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys, time
T = os.environ["FAUX_HERDR"]; etat = json.load(open(T + "/etat.json")); a = sys.argv[1:]
if a == ["agent", "prompt"]:
    d = json.load(sys.stdin); a += [d["target"], d["text"]]
r = {}
if a[:2] == ["agent", "list"]: r = {"agents": [{"name": n} for n in etat["vivants"]]}
elif a[:2] == ["agent", "prompt"]:
    if a[2] not in etat["vivants"]: print("agent introuvable", file=sys.stderr); sys.exit(1)
    time.sleep(float(etat.get("delai", 0)))
    with open(T + "/prompts.log", "a") as f: f.write(json.dumps({"a": a[2], "texte": a[3]}, ensure_ascii=False) + "\n")
print(json.dumps({"result": r}))
'''

# Le courtier, appelé directement sur UNE demande ; `berger demander` y est remplacé : la consigne est notée, la réponse
# (ou l'échec) vient de faux/reponse.txt. On attend la fin du fil de délégation (le suivi se fait APRÈS la réponse).
APPEL = r'''
import json, runpy, subprocess, sys, threading, time
g = runpy.run_path(sys.argv[1], run_name="essai")
agent, req, faux = sys.argv[2], json.loads(sys.argv[3]), sys.argv[4]
vrai = g["_transport"].executer
def run(programme, cmd, *a, **k):
    if cmd and cmd[0] == "demander":
        open(faux + "/consigne.txt", "w").write(k["input"]); rep = json.load(open(faux + "/reponse.json"))
        return subprocess.CompletedProcess(cmd, rep["code"], rep["texte"], "")
    return vrai(programme, cmd, *a, **k)
g["_transport"].executer = run
d = g["AGENTS"] / agent / "courrier"; (d / "encours").mkdir(parents=True, exist_ok=True)
f = d / "encours" / "1.json"; f.write_text(json.dumps(req))
g["traiter"](agent, f, {})
for th in threading.enumerate():
    if th is not threading.main_thread(): th.join(120)
r = d / "reponses" / "1.json"
if r.exists(): print(r.read_text()); r.unlink()
'''

with tempfile.TemporaryDirectory() as td:
    m = Path(td); t = m / "berger"
    _produit.copier(SRC, t, ("bin", "courtier", "commun"))
    secret = "Valeur" + "SecreteDu" + "Coffre"                           # construite à l'exécution (garde-fou de secrets)
    (m / "coffre.json").write_text(json.dumps({"essai": {"cle": secret}}))
    (t / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n\n[outils.essai]\ntype = "essai"\n\n'
                                   '[equipes.berger]\ndepot = "/nulle-part"\n'
                                   'outils_developpeur = ["essai", "ecrire:artisan", "ecrire:inconnu", "absent"]\n')
    for a, nom, extra in (("metiers", "Hugo", "outils = essai, deleguer:artisan, ecrire:artisan\n"), ("artisan", "Léa", "outils = essai\n")):
        d = t / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {nom}\nmoteur = claude\npanneaux = claude\nmur = ouvert\nheures = aucune\n{extra}")
    todo = t / "agents/artisan/TODO.md"; todo.write_text("# À faire\n\n- [ ] Tâche déjà là  (ajouté 2026-10-01)\n")
    (t / "agents/artisan/.herdr.json").write_text(json.dumps({"workspace": "w1", "agents": {"claude": "p1"}}))
    f = m / "faux"; f.mkdir(); (f / "herdr").write_text(FAUX_HERDR); (f / "notify-send").write_text("#!/bin/sh\nexit 0\n")
    for x in ("herdr", "notify-send"): os.chmod(f / x, 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(t), "FAUX_HERDR": str(f), "BERGER_HERDR": str(f / "herdr"),
           "BERGER_NOTIFY_SEND": str(f / "notify-send")}
    _herdr_api_factice.installer(env)
    # Une interception obsolète doit échouer, jamais lancer un moteur réel.
    moteurs = m / '.local/bin'; moteurs.mkdir(parents=True, exist_ok=True)
    for nom in ('codex', 'claude'):
        moteur = moteurs / nom
        moteur.write_text('#!/bin/sh\necho "appel moteur imprévu dans la suite" >&2\nexit 99\n')
        moteur.chmod(0o700)
    jour = datetime.date.today().isoformat()

    def etat(vivants=(), delai=0): (f / "etat.json").write_text(json.dumps({"vivants": list(vivants), "delai": delai}))
    etat()

    def deleguer(reponse, code=0, question="Peux-tu préparer le modèle de lettre de mission ?"):
        (f / "reponse.json").write_text(json.dumps({"code": code, "texte": reponse}))
        r = subprocess.run([sys.executable, "-c", APPEL, str(t / "courtier/courtier"), "metiers",
                            json.dumps({"outil": "deleguer", "verbe": "artisan", "args": [question]}), str(f)],
                           env=env, capture_output=True, text=True, timeout=200)
        try: return json.loads(r.stdout)
        except ValueError: return {"ok": None, "erreur": (r.stderr or r.stdout)[-400:]}

    def prompts(): return [json.loads(l) for l in (f / "prompts.log").read_text().splitlines()] if (f / "prompts.log").exists() else []
    def dernier(): return (prompts() or [{"texte": ""}])[-1]["texte"]
    attente, remis = t / "agents/artisan/messages/attente", t / "agents/artisan/messages/remis"
    def fichiers(d): return sorted(d.glob("*.json")) if d.is_dir() else []
    def nouvelles(avant): return todo.read_text()[len(avant):].splitlines()
    def vider_file():
        for x in fichiers(attente): x.unlink()

    # ── (a) (b) (c) (d) engagements inscrits, réponse intacte, résumé déposé (cible endormie) ──
    rep = ("Oui, je m'en occupe.\n\nENGAGEMENTS:\n- Préparer le modèle de lettre de mission\n"
           "- Envoyer le modèle à Métiers\n  avant vendredi")
    avant = todo.read_text(); r = deleguer(rep)
    consigne = (f / "consigne.txt").read_text() if (f / "consigne.txt").exists() else ""
    dire("ENGAGEMENTS:" in consigne and "ENGAGEMENTS: aucun" in consigne, "consigne : demande de finir par « ENGAGEMENTS: » (ou « ENGAGEMENTS: aucun »)")
    dire(r.get("ok") is True and r.get("donnees", {}).get("reponse") == rep, "réponse rendue au demandeur intacte, bloc ENGAGEMENTS compris")
    dire(nouvelles(avant) == [f"- [ ] Préparer le modèle de lettre de mission (promis à metiers, délégation du {jour})",
                              f"- [ ] Envoyer le modèle à Métiers avant vendredi (promis à metiers, délégation du {jour})"],
         "engagements ajoutés à la fin du TODO.md de la cible, au format exact (aplatis)")
    dire(todo.read_text().startswith(avant), "TODO.md : rien de l'existant n'est réécrit")
    q = fichiers(attente); d = json.loads(q[0].read_text()) if q else {}
    dire(len(q) == 1 and d.get("service") is True, "résumé déposé dans la file de la cible (message de service)")
    dire("lettre de mission" in d.get("texte", "") and "Préparer le modèle" in d.get("texte", ""), "résumé : question et engagements")
    deb = t / "courtier/ecrire-debit.json"
    dire(not deb.exists() or "metiers>artisan" not in deb.read_text(), "résumé non compté dans le débit d'ecrire")
    etat(["artisan-claude"])
    subprocess.run([sys.executable, str(t / "bin/berger"), "planificateur"], env=env, capture_output=True, text=True, timeout=120)
    p = prompts()
    dire(len(p) == 1 and p[0]["texte"].startswith(ENTETE) and "aucune réponse attendue" in p[0]["texte"],
         "résumé remis à la conversation principale avec l'en-tête de service")
    dire(not p or not p[0]["texte"].startswith("Message de"), "résumé : pas l'en-tête d'un message d'agent")
    dire(not fichiers(attente) and len(fichiers(remis)) == 1, "résumé rangé dans messages/remis/")

    # ── (e) « aucun » et sans bloc : rien d'inscrit, résumé tout de même ──
    avant = todo.read_text(); n = len(prompts())
    r = deleguer("Non, rien à faire de mon côté.\nENGAGEMENTS: aucun")
    dire(r.get("ok") is True and todo.read_text() == avant, "« ENGAGEMENTS: aucun » → rien inscrit")
    dire(len(prompts()) == n + 1 and "aucun" in dernier(), "« aucun » → résumé remis tout de même (cible vivante)")
    r = deleguer("Je regarde ça.\n- Ceci n'est pas un engagement")
    dire(r.get("ok") is True and todo.read_text() == avant, "sans ligne ENGAGEMENTS → rien inscrit")
    r = deleguer("**ENGAGEMENTS:**\n- Relire la note\n\nMerci.")
    dire(nouvelles(avant) == [f"- [ ] Relire la note (promis à metiers, délégation du {jour})"],
         "« **ENGAGEMENTS:** » en gras toléré ; le bloc s'arrête à la première autre ligne")

    # ── trop longs, trop nombreux ──
    avant = todo.read_text()
    r = deleguer("Voilà.\nENGAGEMENTS:\n- " + "très " * 120 + "long\n" + "".join(f"- Action numéro {x}\n" for x in "BCDEFG"))
    l = nouvelles(avant)
    dire(len(l) == 5, "plus de 5 engagements → 5 inscrits")
    act = l[0].removeprefix("- [ ] ").removesuffix(f" (promis à metiers, délégation du {jour})") if l else ""
    dire(len(act) == 300 and act.endswith("…"), "engagement de plus de 300 caractères → coupé à 300, fini par « … »")
    dire(l[1:] == [f"- [ ] Action numéro {x} (promis à metiers, délégation du {jour})" for x in "BCDE"], "les 5 premiers dans l'ordre")
    dire("2 non inscrit" in dernier(), "résumé : les engagements non inscrits sont comptés")

    # ── secret ──
    avant = todo.read_text()
    r = deleguer(f"Voilà.\nENGAGEMENTS:\n- Vérifier l'accès avec {secret}\n- Relancer le client", question="Accès au portail ?")
    dire(nouvelles(avant) == [f"- [ ] Relancer le client (promis à metiers, délégation du {jour})"], "engagement contenant un secret → non inscrit, les autres oui")
    dire(secret not in dernier() and "secret" in dernier(), "résumé : secret absent, non-inscription dite")
    tout = todo.read_text() + "".join(x.read_text() for x in fichiers(remis))
    dire(secret not in tout, "aucun secret dans le TODO ni dans les messages rangés")

    # ── délégation en échec : rien ──
    avant = todo.read_text(); n = len(prompts())
    r = deleguer("ENGAGEMENTS:\n- Ne doit pas apparaître", code=1)
    dire(r.get("ok") is False and todo.read_text() == avant and len(prompts()) == n and not fichiers(attente),
         "délégation en échec → rien inscrit, rien déposé")

    # ── verrou : deux remises en même temps → chaque message tapé une fois, aucune erreur ──
    etat(); vider_file(); n = len(prompts())
    for k in range(4):
        subprocess.run([sys.executable, str(t / "bin/berger"), "--stdin"],
                       input=json.dumps(["message-deposer", "metiers", "artisan", "message concurrent " + chr(ord("a") + k)]),
                       env=env, capture_output=True, text=True, timeout=60)
    etat(["artisan-claude"], delai=0.3)
    ps = [subprocess.Popen([sys.executable, str(t / "bin/berger"), "message-remettre", "artisan"], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(3)]
    sorties = [x.communicate(timeout=120) for x in ps]
    textes = [x["texte"] for x in prompts()[n:]]
    dire(len(textes) == 4 and all(x.endswith("message concurrent " + chr(ord("a") + k)) for k, x in enumerate(textes)),
         "trois remises en même temps → chaque message tapé une seule fois, dans l'ordre" if len(textes) == 4 else f"remises concurrentes : {len(textes)} messages tapés au lieu de 4")
    dire(all(x.returncode == 0 for x in ps) and not any("Error" in e for _, e in sorties),
         "remises concurrentes : aucune erreur" + ("" if all(x.returncode == 0 for x in ps) else f" — {[e[-200:] for _, e in sorties]}"))
    dire(not fichiers(attente) and sum(1 for x in fichiers(remis) if "concurrent" in x.read_text()) == 4, "remises concurrentes : file vide, 4 rangés")

    # ── outils_developpeur : ecrire:<agent existant> accepté ──
    code = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(t / 'bin/berger')!r},run_name='x');"
            "print(json.dumps(g['outils_developpeur'](g['EQUIPES']['berger'])))")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    dern = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    dire(dern == json.dumps(["essai", "ecrire:artisan"]), f"outils_developpeur : outil déclaré et ecrire:<agent existant> gardés ({dern or r.stderr[-200:]})")
    dire("ecrire:inconnu" in r.stdout and "absent" in r.stdout, "outils_developpeur : agent inconnu et outil non déclaré signalés, ignorés")

print(f"---- {ko} échec(s)")
sys.exit(1 if ko else 0)
