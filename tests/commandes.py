#!/usr/bin/env python3
"""Tests des commandes qui n'en avaient aucun (audit du 08/10/2026) : reveil, tache, planificateur, relancer, fin-mission,
restaurer — sans modèle, sans toucher aux vrais agents ni au vrai trousseau : une installation Berger JETABLE dans un
dossier personnel JETABLE, un FAUX Herdr qui note ce qu'on lui demande, de FAUX moteurs (claude, codex) et un FAUX
secret-tool. Berger met ~/.local/bin en tête du PATH : les faux y sont posés, et le test s'arrête s'ils ne sont pas pris.
Usage : python3 tests/commandes.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


# Herdr à état : « ctrl+c » sur un panneau arrête l'agent qui y tourne (sauf panneau « tenace ») ; « agent start » l'y remet.
FAUX_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
T = os.environ["FAUX_HERDR"]; etat = json.load(open(T + "/etat.json")); a = sys.argv[1:]
with open(T + "/appels.log", "a") as f: f.write(json.dumps(a) + "\n")
r = {}
if a[:2] == ["agent", "list"]: r = {"agents": [{"name": n, "pane_id": p} for n, p in etat["agents"].items()]}
elif a[:2] == ["workspace", "list"]: r = {"workspaces": [{"workspace_id": w} for w in etat["espaces"]]}
elif a[:2] == ["pane", "get"]: r = {"pane": {"pane_id": a[2], "agent_status": "idle"}}
elif a[:2] == ["pane", "send-keys"] and a[3] == "ctrl+c" and a[2] not in etat.get("tenaces", []):
    etat["agents"] = {n: p for n, p in etat["agents"].items() if p != a[2]}
elif a[:2] == ["agent", "start"]: etat["agents"][a[2]] = a[a.index("--pane") + 1]; r = {"agent": a[2]}
elif a[:2] == ["workspace", "close"]: etat["espaces"] = [w for w in etat["espaces"] if w != a[2]]
json.dump(etat, open(T + "/etat.json", "w")); print(json.dumps({"result": r}))
'''
# Moteur : note séparément arguments et stdin ; répond le contenu factice (vide = panne).
FAUX_MOTEUR = "#!" + sys.executable + "\n" + r'''import json, os, sys
from pathlib import Path
racine = Path(os.environ["FAUX_HERDR"])
with open(racine / "moteurs.log", "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "texte": sys.stdin.read()}, ensure_ascii=False) + "\n")
r = (racine / "reponse").read_text() if (racine / "reponse").exists() else ""
if not r: sys.exit(1)
if "-o" in sys.argv: Path(sys.argv[sys.argv.index("-o") + 1]).write_text(r)
else: print(r)
'''

PHRASE = "phrase-de-test-jetable-0123456789"


def installation(m):
    i = m / "berger"; _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text('{"essai": {"cle": "valeur-secrete-du-test"}}')
    # Pas de [sauvegarde] : le planificateur tenterait l'envoi WebDAV ; la phrase de `restaurer` vient du FAUX secret-tool.
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    for a, heures in (("garde", "0-23"), ("veille", "aucune"), ("mission", "aucune")):
        d = i / "agents" / a; (d / "memory").mkdir(parents=True); (d / "taches").mkdir()
        (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nmoteur = claude\npanneaux = claude\nmur = ouvert\nheures = {heures}\n")
    f = m / "faux"; f.mkdir(); b = m / ".local/bin"; b.mkdir(parents=True)
    (f / "herdr").write_text(FAUX_HERDR); (f / "notify-send").write_text("#!/bin/sh\nexit 0\n")
    for x in ("claude", "codex"): (b / x).write_text(FAUX_MOTEUR)
    (b / "secret-tool").write_text(f"#!/bin/sh\n[ \"$1\" = lookup ] && echo {PHRASE}\nexit 0\n")
    for x in (f / "herdr", f / "notify-send", b / "claude", b / "codex", b / "secret-tool"): os.chmod(x, 0o755)
    (f / "etat.json").write_text(json.dumps({"agents": {}, "espaces": []}))
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "FAUX_HERDR": str(f), "BERGER_HERDR": str(f / "herdr"),
           "BERGER_NOTIFY_SEND": str(f / "notify-send"), "GARDE_TEST": "1", "GNUPGHOME": str(m / ".gnupg")}
    env.pop("AGENT_PANNE", None)
    return i, f, env


def berger(i, env, *args, timeout=120):
    return subprocess.run([sys.executable, str(i / "bin/berger"), *args], env=env, capture_output=True, text=True, timeout=timeout)


def repondre(f, texte): (f / "reponse").write_text(texte)
def appels(f): return [json.loads(l) for l in (f / "appels.log").read_text().splitlines()] if (f / "appels.log").exists() else []
def moteurs(f): return (f / "moteurs.log").read_text().splitlines() if (f / "moteurs.log").exists() else []
def remise(f):
    for x in ("appels.log", "moteurs.log"): (f / x).unlink(missing_ok=True)


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i, f, env = installation(m)
    # SÉCURITÉ DU TEST : Berger doit prendre les FAUX (Herdr, moteurs, trousseau) — sinon on s'arrête tout de suite.
    sonde = subprocess.run([sys.executable, "-c", f"import runpy,shutil,sys;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},"
                            "run_name='x');print(g['HERDR']);print(shutil.which('claude'));print(shutil.which('codex'));print(shutil.which('secret-tool'))"],
                           env=env, capture_output=True, text=True)
    attendu = [str(f / "herdr"), str(m / ".local/bin/claude"), str(m / ".local/bin/codex"), str(m / ".local/bin/secret-tool")]
    if sonde.stdout.split() != attendu: sys.exit(f"ARRÊT : Berger ne prendrait pas les faux ({sonde.stdout.split() or sonde.stderr[-300:]})")
    jour = datetime.date.today().isoformat(); hb = i / "agents/garde/heartbeat" / f"{jour}.md"

    # ── reveil ──
    berger(i, env, "reveil", "veille", "--force")
    dire(not (i / "agents/veille/heartbeat" / f"{jour}.md").exists() and not moteurs(f), "reveil : agent « heures = aucune » jamais réveillé, même forcé")
    berger(i, env, "reveil", "garde")
    dire("RAS (pré-contrôle, sans modèle)" in hb.read_text() and not moteurs(f), "reveil : rien à vérifier → RAS sans appeler le modèle")
    repondre(f, "RAS"); berger(i, env, "reveil", "garde", "--force")
    dire("RAS (claude)" in hb.read_text() and len(moteurs(f)) == 1, "reveil --force : le modèle répond RAS → noté RAS, un seul appel")
    repondre(f, "Disque presque plein sur le serveur"); berger(i, env, "reveil", "garde", "--force")
    notes = (i / "courtier/notifications.log").read_text() if (i / "courtier/notifications.log").exists() else ""
    dire("À SIGNALER (claude)" in hb.read_text() and "Disque presque plein" in notes, "reveil : un point à signaler → noté et notifié")
    repondre(f, ""); berger(i, env, "reveil", "garde", "--force")
    notes = (i / "courtier/notifications.log").read_text()
    dire("ÉCHEC du réveil (aucun moteur)" in hb.read_text() and "URGENT" in notes, "reveil : les deux moteurs en panne → échec noté, notification urgente")
    remise(f)

    # ── tache ──
    (i / "agents/garde/taches/rapport.md").write_text("quand: tous-les-jours 23:59\nnotifier: oui\n---\nFais le rapport.\n")
    r = berger(i, env, "tache", "garde", "inconnue")
    dire(r.returncode != 0 and "tâche inconnue" in r.stdout + r.stderr, "tache : une tâche inconnue est refusée, nommée")
    repondre(f, "[RIEN] tout va bien"); berger(i, env, "tache", "garde", "rapport")
    sorties = sorted((i / "agents/garde/sorties/rapport").glob("*.md"))
    j = (i / "agents/garde/memory" / f"{jour}.md").read_text()
    dire(len(sorties) == 1 and "> moteur : claude" in sorties[0].read_text() and "rien à signaler" in j,
         "tache : résultat rangé dans sorties/, moteur noté, « rien à signaler » au journal")
    tout = "\n".join(moteurs(f))                                      # la consigne tient sur plusieurs lignes
    dire("Tâche planifiée « rapport »" in tout and "Fais le rapport." in tout, "tache : la consigne de la tâche est donnée au modèle")
    captures = [json.loads(l) for l in moteurs(f)]
    dire(all("Fais le rapport." not in str(c["argv"]) for c in captures)
         and any("Fais le rapport." in c["texte"] for c in captures), "tache : texte sur stdin, absent des arguments")
    avant = (i / "courtier/notifications.log").read_text()
    time.sleep(61 - datetime.datetime.now().second if datetime.datetime.now().second > 55 else 0)   # deux sorties dans la même minute = même fichier
    repondre(f, "Facture en retard trouvée"); berger(i, env, "tache", "garde", "rapport")
    dire("Facture en retard" in (i / "courtier/notifications.log").read_text()[len(avant):], "tache : un résultat avec « notifier: oui » → notifié")
    remise(f)

    # ── planificateur ──
    (i / "agents/garde/CHECKLIST.md").write_text("# Ranger le garage\n- [x] trier\n- [x] jeter\n\nTerminé le 08/10\n")
    repondre(f, "[RIEN]")
    for _ in range(2):                                                # la minute peut tourner entre l'écriture et le passage
        hm = f"{datetime.datetime.now():%H:%M}"
        (i / "agents/garde/taches/minute.md").write_text(f"quand: tous-les-jours {hm}\n---\nTâche de la minute.\n")
        berger(i, env, "planificateur")
        if any("Tâche de la minute." in l for l in moteurs(f)): break
    dire(any("Tâche de la minute." in l for l in moteurs(f)), "planificateur : la tâche dont l'heure est venue est lancée")
    dire(not any("Fais le rapport." in l for l in moteurs(f)), "planificateur : une tâche d'une autre heure n'est pas lancée")
    dire(not (i / "agents/garde/CHECKLIST.md").exists() and any((i / "agents/garde/historique").glob("*ranger-le-garage*.md")),
         "planificateur : une checklist « Terminé » est rangée dans historique/")
    dire((i / "courtier/dernier-audit.txt").exists(), "planificateur : l'audit quotidien des secrets est passé")
    (i / "agents/garde/taches/minute.md").unlink(); remise(f)
    # Une sauvegarde en échec ([sauvegarde] incomplète → exception) ne doit plus emporter l'audit des secrets (09/10).
    conf_avant = (i / "config.toml").read_text(); (i / "config.toml").write_text(conf_avant + '\n[sauvegarde]\ndossier = "x"\n')
    (i / "courtier/dernier-audit.txt").unlink()
    r = berger(i, env, "planificateur")
    dire((i / "courtier/dernier-audit.txt").exists() and "sauvegarde :" in r.stderr,
         "planificateur : une sauvegarde en échec est nommée et n'empêche PAS l'audit des secrets")
    (i / "config.toml").write_text(conf_avant)

    # ── relancer ──
    d = i / "agents/veille"; (d / ".herdr.json").write_text(json.dumps({"workspace": "w1", "agents": {"claude": "p1"}}))
    conv = m / ".claude/projects" / __import__("re").sub(r"[^A-Za-z0-9]", "-", str(d)); conv.mkdir(parents=True)
    (conv / "conv-1.jsonl").write_text('{"entrypoint":"cli"}\n'); (d / ".conversation-claude").write_text("conv-1\n")
    (f / "etat.json").write_text(json.dumps({"agents": {"veille-claude": "p1"}, "espaces": ["w1"]}))
    r = berger(i, env, "relancer", "veille", "claude")
    a = appels(f); arret = next((n for n, x in enumerate(a) if x[:2] == ["pane", "send-keys"]), 99)
    depart = next((x for x in a if x[:2] == ["agent", "start"]), [])
    dire(r.returncode == 0 and "relancé dans p1" in r.stdout and arret < a.index(depart) if depart else False,
         "relancer : l'agent est arrêté PUIS redémarré dans le même panneau")
    dire(depart[2:3] == ["veille-claude"] and "--resume" in depart and depart[depart.index("--resume") + 1] == "conv-1",
         "relancer : il reprend SA conversation (--resume), pas une neuve")
    remise(f)
    (f / "etat.json").write_text(json.dumps({"agents": {"veille-claude": "p1"}, "espaces": ["w1"], "tenaces": ["p1"]}))
    r = berger(i, env, "relancer", "veille", "claude", timeout=180)
    dire(r.returncode != 0 and "rien relancé" in r.stdout + r.stderr and not any(x[:2] == ["agent", "start"] for x in appels(f)),
         "relancer : un agent qui ne s'arrête pas n'est PAS relancé par-dessus (rien tapé chez lui)")
    remise(f)

    # ── fin-mission ──
    r = berger(i, env, "fin-mission", "veille")
    dire(r.returncode != 0 and "pas de mission" in r.stdout + r.stderr, "fin-mission : sans mission en cours → refus, rien touché")
    d = i / "agents/mission"; (d / "MISSION.md").write_text("# Mission confiée par Proprio — essai\n\nfaire x\n")
    (d / ".herdr.json").write_text(json.dumps({"workspace": "w2", "agents": {"claude": "p2"}}))
    (f / "etat.json").write_text(json.dumps({"agents": {"mission-claude": "p2"}, "espaces": ["w2"]}))
    r = berger(i, env, "fin-mission", "mission", timeout=180)
    a = appels(f); ids = json.loads((d / ".herdr.json").read_text())
    dire(r.returncode == 0 and not (d / "MISSION.md").exists() and any((d / "historique").glob("mission-*.md")),
         "fin-mission : MISSION.md rangée dans historique/")
    dire("mission terminée par" in (d / "memory" / f"{jour}.md").read_text(), "fin-mission : notée au journal de l'agent")
    dire(["workspace", "close", "w2"] in a and ids.get("agents") == {}, "fin-mission : agent arrêté, espace fermé, panneau oublié")
    remise(f)

    # ── restaurer ──
    src = m / "donnees"; (src / "agents/garde").mkdir(parents=True)
    (src / "agents/garde/MEMORY.md").write_text("souvenir précieux\n"); (src / "config.toml").write_text("proprietaire = \"X\"\n")
    subprocess.run(["tar", "-czf", str(m / "d.tar.gz"), "-C", str(src), "."], check=True)
    gpg = lambda phrase, sortie: subprocess.run(["gpg", "--batch", "--yes", "--pinentry-mode", "loopback", "--passphrase-fd", "0", "--symmetric",
                                                 "--cipher-algo", "AES256", "-o", str(sortie), str(m / "d.tar.gz")],
                                                input=phrase, text=True, capture_output=True, env=env)
    gpg(PHRASE, m / "bonne.tar.gz.gpg"); gpg("une-autre-phrase", m / "mauvaise.tar.gz.gpg")
    r = berger(i, env, "restaurer", str(m / "bonne.tar.gz.gpg"), str(m / "restaure"))
    dire(r.returncode == 0 and (m / "restaure/agents/garde/MEMORY.md").read_text() == "souvenir précieux\n"
         and (m / "restaure/config.toml").exists() and not (m / "restaure/donnees.tar.gz").exists(),
         "restaurer : l'archive chiffrée revient à l'identique, sans fichier intermédiaire laissé")
    r = berger(i, env, "restaurer", str(m / "mauvaise.tar.gz.gpg"), str(m / "restaure2"))
    dire(r.returncode != 0 and not (m / "restaure2/agents").exists(), "restaurer : une archive d'une autre phrase est refusée, rien d'écrit")
    subprocess.run(["gpgconf", "--kill", "all"], env=env, capture_output=True)

sys.exit(1 if ko else 0)
