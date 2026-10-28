#!/usr/bin/env python3
"""Tests de `berger agent apercu|appliquer` (créer ou modifier un agent sur proposition, 09/10/2026) — sans modèle, sans
Herdr, installation JETABLE. Un agent écrit `propositions/<agent>.md` dans SON dossier ; l'aperçu montre les DROITS avant →
après et une empreinte ; l'application (action validée par le propriétaire) n'applique QUE ce qui a été montré : empreinte
changée = refus. Une modification sauvegarde les fichiers remplacés et ne touche ni la mémoire, ni le journal, ni TODO.
Refus, même validés : ses propres réglages, mur ouvert, superviseur, outil non déclaré, secret ou coffre cité, écriture
dans le produit ou chez un autre, fichier non prévu.
Par le COURTIER, avec les commandes exactes de config.exemple.toml : la demande d'application attend le propriétaire
(rien n'est fait avant), l'agent ne peut pas l'accepter lui-même, et une proposition retouchée entre la demande et la
décision échoue à l'exécution. (Que l'agent ne puisse pas lancer `berger agent appliquer` en direct depuis son bac à
sable — il n'écrit ni chez un autre ni dans agents/ — relève du mur : tests/tout.sh, sonde-mur.)
Usage : python3 tests/agent-appliquer.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, subprocess, sys, tempfile, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def commande_exemple(verbe):
    """La commande `verbe` de [outils.berger-admin], telle qu'écrite (commentée) dans config.exemple.toml."""
    for ligne in (SRC / "config.exemple.toml").read_text().splitlines():
        if re.match(rf"# {verbe} = ", ligne): return tomllib.loads(ligne[2:])[verbe]
    raise SystemExit(f"{verbe} absent de config.exemple.toml")


# Le courtier, appelé directement (comme tests/missions.py) : une demande de l'agent, puis sa réponse.
APPEL = r'''
import json, runpy, sys, time
g = runpy.run_path(sys.argv[1], run_name="essai")
if sys.argv[2] == "--decisions": g["traiter_decisions"](); sys.exit(0)
agent, req = sys.argv[2], json.loads(sys.argv[3])
d = g["AGENTS"] / agent / "courrier"; (d / "encours").mkdir(parents=True, exist_ok=True)
f = d / "encours" / "1.json"; f.write_text(json.dumps(req))
g["traiter"](agent, f, {})
for _ in range(100):
    r = d / "reponses" / "1.json"
    if r.exists(): print(r.read_text()); r.unlink(); break
    time.sleep(0.1)
'''


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / ".config/berger").mkdir(parents=True)
    (m / ".config/berger/coffre-essai.json").write_text(json.dumps({"erp": {"token": "Zq81-valeur-secrete-77"}}))
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = [".config/berger"]\ncoffre = "{m}/.config/berger/coffre-essai.json"\n\n'
                                   '[outils.essai]\ntype = "essai"\n\n'
                                   f'[outils.berger-admin]\ntype = "commandes"\ndossier = "{i}"\n[outils.berger-admin.lecture]\n'
                                   f'agent-apercu = {json.dumps(commande_exemple("agent-apercu"))}\n[outils.berger-admin.actions]\n'
                                   f'agent-appliquer = {json.dumps(commande_exemple("agent-appliquer"))}\n')
    for a, extra in {"master": "superviseur = oui\noutils = essai, berger-admin\n", "voisin": "outils =\n"}.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True); (d / "propositions").mkdir()
        (d / "agent.conf").write_text(f"nom = {a.capitalize()}\nmoteur = claude\npanneaux = claude\nheures = aucune\n{extra}")
        (d / "SOUL.md").write_text(f"# {a}\n\nAncienne âme.\n"); (d / "MEMORY.md").write_text("- [2026-10-01] souvenir\n")
        (d / "TODO.md").write_text("- [ ] à faire\n"); (d / "memory/2026-10-09.md").write_text("- 08:00 — journal\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i)}
    def berger(*args): return subprocess.run([sys.executable, str(i / "bin/berger"), *args], env=env, capture_output=True, text=True, timeout=120)
    berger("regenerer")
    P = i / "agents/master/propositions"
    def proposer(cible, blocs): (P / f"{cible}.md").write_text("".join(f"=== {n}\n{c}" for n, c in blocs.items()))
    def empreinte(sortie): return next((l.split("Empreinte : ")[1].strip() for l in sortie.splitlines() if "Empreinte : " in l), "")

    # ── création ──
    proposer("veilleur", {"agent.conf": "nom = Veilleur\nmoteur = claude\npanneaux = claude\nheures = aucune\noutils = essai\n",
                          "SOUL.md": "# Veilleur\n\nTu veilles.\n", "taches/sante.md": "quand: tous-les-jours 07:45\n---\nContrôle.\n"})
    r = berger("agent", "apercu", "master", "veilleur"); e = empreinte(r.stdout)
    dire(r.returncode == 0 and "CRÉATION" in r.stdout and "+essai" in r.stdout and e, "création : aperçu applicable, droits nouveaux (+essai), empreinte")
    r = berger("agent", "appliquer", "master", "veilleur.000000000000")
    dire(r.returncode != 0 and "empreinte" in (r.stdout + r.stderr) and not (i / "agents/veilleur").exists(), "création : une autre empreinte est refusée, rien n'est créé")
    r = berger("agent", "appliquer", "master", f"veilleur.{e}"); v = i / "agents/veilleur"
    dire(r.returncode == 0 and (v / "agent.conf").read_text().startswith("nom = Veilleur") and (v / "taches/sante.md").is_file()
         and "Tu veilles" in (v / "SOUL.md").read_text(), "création : agent créé avec les fichiers proposés")
    dire((v / "AGENTS.md").is_file() and (v / ".claude/settings.json").is_file(), "création : règles et réglages générés (regenerer)")
    dire(not (P / "veilleur.md").exists() and list(P.glob("veilleur.applique-*.md")), "création : la proposition est rangée (pas d'application en double)")
    dire("proposition de master" in "".join(x.read_text() for x in (v / "memory").glob("*.md"))
         and "veilleur" in "".join(x.read_text() for x in (i / "agents/master/memory").glob("*.md")), "création : une ligne au journal des deux agents")

    # ── modification ──
    w = i / "agents/voisin"
    proposer("voisin", {"agent.conf": "nom = Voisin\nmoteur = claude\npanneaux = claude\nheures = 8-19\noutils = essai\nproteges = notes.md\n", "SOUL.md": "# voisin\n\nNouvelle âme.\n"})
    r = berger("agent", "apercu", "master", "voisin"); e = empreinte(r.stdout)
    dire(r.returncode == 0 and "MODIFICATION" in r.stdout and "heures : aucune → 8-19" in r.stdout and "+essai" in r.stdout and "+notes.md" in r.stdout
         and "-Ancienne âme." in r.stdout and "+Nouvelle âme." in r.stdout, "modification : aperçu avec droits avant → après et différence")
    (P / "voisin.md").write_text((P / "voisin.md").read_text().replace("Nouvelle", "Autre"))
    r = berger("agent", "appliquer", "master", f"voisin.{e}")
    dire(r.returncode != 0 and "Ancienne" in (w / "SOUL.md").read_text(), "modification : proposition changée après l'aperçu → refusée")
    e = empreinte(berger("agent", "apercu", "master", "voisin").stdout)
    (w / "TODO.md").write_text("- [ ] changé entre-temps\n")   # l'agent bouge : TODO n'est pas proposé, l'empreinte ne change pas
    r = berger("agent", "appliquer", "master", f"voisin.{e}")
    dire(r.returncode == 0 and "Autre âme" in (w / "SOUL.md").read_text() and "outils = essai" in (w / "agent.conf").read_text(), "modification : appliquée")
    dire(len(list(w.glob("SOUL.md.avant-*"))) == 1 and len(list(w.glob("agent.conf.avant-*"))) == 1, "modification : fichiers remplacés sauvegardés (.avant-<date>)")
    dire((w / "MEMORY.md").read_text() == "- [2026-10-01] souvenir\n" and (w / "TODO.md").read_text() == "- [ ] changé entre-temps\n"
         and (w / "memory/2026-10-09.md").read_text().startswith("- 08:00 — journal\n"), "modification : mémoire, TODO et journal intacts")
    proposer("voisin", {"SOUL.md": "# voisin\n\nEncore.\n"}); e = empreinte(berger("agent", "apercu", "master", "voisin").stdout)
    (w / "SOUL.md").write_text("# voisin\n\nÉcrit par le propriétaire entre-temps.\n")
    r = berger("agent", "appliquer", "master", f"voisin.{e}")
    dire(r.returncode != 0 and "entre-temps" in (w / "SOUL.md").read_text(), "modification : l'agent a changé depuis l'aperçu → refusée")

    # ── refus, même avec la bonne empreinte ──
    base = "nom = X\nmoteur = claude\nheures = aucune\n"
    cas = [("master", {"SOUL.md": "x\n"}, "propres réglages", "ses propres réglages"),
           ("refus1", {"agent.conf": base + "mur = ouvert\n", "SOUL.md": "x\n"}, "mur", "mur ouvert"),
           ("refus2", {"agent.conf": base + "superviseur = oui\n", "SOUL.md": "x\n"}, "supervision", "superviseur"),
           ("refus3", {"agent.conf": base + "outils = ssh-partout\n", "SOUL.md": "x\n"}, "non déclaré", "outil non déclaré"),
           ("refus4", {"agent.conf": base + "outils = deleguer:master\n", "SOUL.md": "x\n"}, "lui-même", "pouvoir sur le demandeur"),
           ("refus5", {"agent.conf": base, "SOUL.md": "jeton : Zq81-valeur-secrete-77\n"}, "valeur du coffre", "valeur du coffre"),
           ("refus6", {"agent.conf": base, "SOUL.md": "lis coffre-essai.json\n"}, "cite le coffre", "nom du coffre"),
           ("refus7", {"agent.conf": base + f"ecrire_aussi = {i}/bin\n", "SOUL.md": "x\n"}, "produit", "écrire dans bin/"),
           ("refus8", {"agent.conf": base + f"ecrire_aussi = {i}/agents/voisin\n", "SOUL.md": "x\n"}, "autre agent", "écrire chez un autre"),
           ("refus9", {"agent.conf": base + f"ecrire_aussi = {m}/.bashrc\n", "SOUL.md": "x\n"}, "hors de l'installation", "écrire hors de l'installation"),
           ("refus10", {"agent.conf": base, "SOUL.md": "x\n", "MEMORY.md": "x\n"}, "seuls agent.conf", "fichier non prévu (MEMORY.md)"),
           ("refus11", {"agent.conf": base + "projet = moncab\n", "SOUL.md": "x\n"}, "equipe ouvrir", "clé d'un développeur")]
    for cible, blocs, motif, lib in cas:
        proposer(cible, blocs); r = berger("agent", "apercu", "master", cible)
        dire(r.returncode != 0 and "REFUSÉ" in r.stdout and motif in r.stdout and "Zq81" not in r.stdout + r.stderr, f"refus à l'aperçu : {lib}")
    from hashlib import sha256
    proposer("refus1", cas[1][1])
    r = berger("agent", "appliquer", "master", "refus1.abcdef123456")
    dire(r.returncode != 0 and "REFUSÉ" in r.stderr and not (i / "agents/refus1").exists(), "refus à l'application aussi (mur ouvert)")

    # ── l'empreinte est liée à la différence EXACTE ──
    proposer("exact", {"agent.conf": "nom = Exact\nmoteur = claude\nheures = aucune\n", "SOUL.md": "# Exact\n"})
    e1 = empreinte(berger("agent", "apercu", "master", "exact").stdout)
    proposer("exact", {"agent.conf": "nom = Exact\nmoteur = claude\nheures = aucune\n", "SOUL.md": "# Exact \n"})   # une espace
    e2 = empreinte(berger("agent", "apercu", "master", "exact").stdout)
    dire(e1 and e2 and e1 != e2, "empreinte : un seul caractère de plus dans la proposition la change")
    r = berger("agent", "appliquer", "master", f"exact.{e1}")
    dire(r.returncode != 0 and not (i / "agents/exact").exists(), "empreinte : l'aperçu d'AVANT la retouche ne s'applique pas")
    proposer("voisin", {"SOUL.md": "# voisin\n\nPour l'empreinte.\n"}); e3 = empreinte(berger("agent", "apercu", "master", "voisin").stdout)
    (w / "SOUL.md").write_text((w / "SOUL.md").read_text() + " ")
    dire(empreinte(berger("agent", "apercu", "master", "voisin").stdout) != e3, "empreinte : un caractère changé dans le fichier ACTUEL la change aussi")

    # ── par le courtier : la demande attend le propriétaire, l'agent ne se valide pas ──
    (m / "faux").mkdir(); (m / "faux/notify-send").write_text("#!/bin/sh\nexit 0\n"); os.chmod(m / "faux/notify-send", 0o755)
    envc = {**env, "PATH": f"{m}/faux:{os.environ['PATH']}"}
    def appel(agent, outil, verbe, *args):
        r = subprocess.run([sys.executable, "-c", APPEL, str(i / "courtier/courtier"), agent, json.dumps({"outil": outil, "verbe": verbe, "args": list(args)})],
                           env=envc, capture_output=True, text=True, timeout=120)
        try: return json.loads(r.stdout)
        except ValueError: return {"ok": None, "erreur": (r.stderr or r.stdout)[-300:]}
    def decider(n, decision):
        (i / f"courtier/validations/{n}.decision").write_text(decision + "\n")
        subprocess.run([sys.executable, "-c", APPEL, str(i / "courtier/courtier"), "--decisions"], env=envc, capture_output=True, text=True, timeout=120)
        return json.loads((i / f"courtier/validations/{n}.fait.json").read_text())
    proposer("garde", {"agent.conf": "nom = Garde\nmoteur = claude\nheures = aucune\n", "SOUL.md": "# Garde\n"})
    r = appel("master", "berger-admin", "agent-apercu", "garde"); e = empreinte(json.dumps(r, ensure_ascii=False).replace("\\n", "\n"))
    dire(r.get("ok") is True and e, "courtier : agent-apercu (lecture) répond avec l'empreinte")
    r = appel("master", "berger-admin", "agent-appliquer", f"garde.{e}"); n = r.get("en_attente")
    dire(n and not (i / "agents/garde").exists(), "courtier : agent-appliquer est MIS EN ATTENTE, rien n'est créé avant la décision")
    v = json.loads((i / f"courtier/validations/{n}.json").read_text()) if n else {}
    dire(f"garde.{e}" in v.get("apercu", "") and v.get("valideur") is None, "courtier : la demande montre l'empreinte ; le propriétaire seul décide")
    r = appel("master", "validation", "accepter", str(n))
    dire(r.get("ok") is False and (i / f"courtier/validations/{n}.json").exists() and not (i / "agents/garde").exists(),
         "courtier : l'agent ne peut pas accepter sa propre demande")
    d = decider(n, "valider")
    dire(d.get("etat") == "validé et exécuté" and (i / "agents/garde/SOUL.md").read_text() == "# Garde\n", "courtier : validée par le propriétaire → appliquée")
    proposer("garde2", {"agent.conf": "nom = Garde2\nmoteur = claude\nheures = aucune\n", "SOUL.md": "# Garde2\n"})
    e = empreinte(json.dumps(appel("master", "berger-admin", "agent-apercu", "garde2"), ensure_ascii=False).replace("\\n", "\n"))
    n = appel("master", "berger-admin", "agent-appliquer", f"garde2.{e}").get("en_attente")
    proposer("garde2", {"agent.conf": "nom = Garde2\nmoteur = claude\nheures = aucune\noutils = essai\n", "SOUL.md": "# Garde2\n"})   # retouche après la demande
    d = decider(n, "valider")
    dire(d.get("etat") == "validé mais ÉCHEC" and not (i / "agents/garde2").exists(), "courtier : proposition retouchée après la demande → échec à l'exécution, rien de créé")
    n = appel("master", "berger-admin", "agent-appliquer", "master.abcdef123456").get("en_attente")
    d = decider(n, "valider") if n else {"etat": "refusé d'avance"}
    dire(d.get("etat") in ("validé mais ÉCHEC", "refusé d'avance") and "Ancienne âme" in (i / "agents/master/SOUL.md").read_text(),
         "courtier : même validée, une proposition sur SES propres réglages échoue")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
