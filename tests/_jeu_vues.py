# -*- coding: utf-8 -*-
"""Jeu de données des vues (spec docs/plans/2026-10-13-interface-spec.md, §3) : une installation JETABLE, un faux Herdr, un
faux systemctl (courtier « inactive »), et une HEURE FIXE — de quoi rendre chaque vue deux fois à l'identique. Il remplit
les branches des vues : agent bloqué / en cours / fini, validation au propriétaire et déléguée, document lu et non lu,
échanges, appels du courtier, checklist de Berger, équipe avec un développeur et une demande de fusion.

construire(t) → (installation, env) ; executer(i, env, code) lance `code` dans un processus où bin/berger est chargé
(`g` = son espace de noms) à l'heure fixe ; le code écrit sa réponse en JSON sur la dernière ligne."""
import datetime, json, os, subprocess, sys
from pathlib import Path

import _produit

SRC = Path(__file__).resolve().parent.parent
FIXE = datetime.datetime(2026, 10, 13, 10, 0, 0)                        # l'heure de tous les rendus
TS = FIXE.timestamp()

# Heure fixe dans le processus qui charge bin/berger : datetime.now, date.today et time.time (le cœur et les vues
# importent les mêmes modules).
HORLOGE = f"""
import datetime as _D, time as _T
_TS = {TS!r}
class _DT(_D.datetime):
    @classmethod
    def now(cls, tz=None): return cls.fromtimestamp(_TS, tz)
class _DD(_D.date):
    @classmethod
    def today(cls): return cls.fromtimestamp(_TS)
_D.datetime = _DT; _D.date = _DD; _T.time = lambda: _TS
"""


def ecrire(f, texte, il_y_a_min=0):
    """Écrit un fichier, daté de FIXE moins `il_y_a_min` minutes (dates de fichier = données des vues)."""
    f = Path(f); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(texte)
    ns = int((TS - 60 * il_y_a_min) * 1e9); os.utime(f, ns=(ns, ns))
    return f


def construire(t, marquages=False, courtier_actif=False):
    """`marquages` : le jeu de données du COMPORTEMENT NOUVEAU (lot 1a : marquages ⚠ Go attendu, ❓ Question, Décision
    attendue ; demande de fusion avec portes signées, rejeu et dépôt git ; écriture décidée) — jamais utilisé pour la référence
    figée, qui reste le jeu d'avant (le code d'avant ne connaît pas ces marquages)."""
    t = Path(t); m = t / "maison"; i = m / "berger"; m.mkdir(parents=True)
    _produit.copier(SRC, i, ("bin", "courtier", "commun")); _produit.admettre_moteurs(i)
    # Parents protégés explicites : la référence historique connaît les mêmes masques que le code actuel.
    (m / "prive").mkdir(mode=0o700); (m / "prive/coffre.json").write_text("{}")
    (i / "courtier/mcp").mkdir(mode=0o700, exist_ok=True)
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = ["prive", "berger/courtier/mcp"]\ncoffre = "{m}/prive/coffre.json"\n'
                                   f'[equipes.demo]\ndepot = "{m}/projets/demo"\nchef_projet = "vigie"\ncoordinateur = "vigie"\nprincipale = "main"\nprefixe = "demo/"\nskills = ["revue", "inconnue"]\n'
                                   '[sauvegarde]\nurl = "https://sauvegarde.exemple.invalid/"\n'
                                   '[panneaux.alertes]\ntitre = "Alertes"\noutil = "lecture"\nverbe = "alertes"\ncadence = 300\nrouge = ["critique"]\n'
                                   '[panneaux.casse]\noutil = "lecture"\nverbe = "casse"\n'
                                   '[panneaux.vieux]\ntitre = "Vieux"\noutil = "lecture"\nverbe = "vieux"\ncadence = 60\n'
                                   '[panneaux.jamais]\noutil = "lecture"\nverbe = "jamais"\n'
                                   f'[outils.lecture]\ntype = "scripts"\ndossier = "{m}/scripts"\nautorises = ["alertes.py"]\n'
                                   f'[outils.admin]\ntype = "commandes"\ndossier = "{m}/scripts"\n[outils.admin.lecture]\netat = "true"\n'
                                   '[outils.admin.actions]\nredemarrer = "true"\n'
                                   '[[gardes]]\nmoment = "avant"\noutils = "Bash"\ncommande = "python3 ~/gardes/garde.py"\n')
    (m / "scripts").mkdir(); (m / "scripts/alertes.py").write_text('print("rien")\n')
    # faux Herdr : statut de chaque panneau d'agent (au travail, au repos, arrêté sur une question)
    (t / "herdr").write_text("#!/usr/bin/env python3\nimport json, sys\na = sys.argv[1:]\n"
                             "st = {'p-demo': 'working', 'p-scribe': 'idle', 'p-vigie': 'blocked'}\n"
                             "if a[:2] == ['pane', 'get'] and len(a) > 2 and a[2] in st:\n"
                             "    print(json.dumps({'result': {'pane': {'pane_id': a[2], 'agent_status': st[a[2]]}}}))\n"
                             "else: print(json.dumps({'result': {}}))\n"); os.chmod(t / "herdr", 0o755)
    fb = m / ".local/bin"; fb.mkdir(parents=True)
    (fb / "systemctl").write_text('#!/bin/sh\necho ' + ('active' if courtier_actif else 'inactive') + '\n'); os.chmod(fb / "systemctl", 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(t / "herdr")}
    env.pop("BERGER_HERDR_SOCKET", None)                                 # aucun socket de l'installation appelante
    for a, n in (("vigie", "Vigie"), ("scribe", "Scribe"), ("demo-ecran", "Demo ecran")):
        subprocess.run([sys.executable, str(i / "bin/berger"), "nouveau", a, n], env=env, capture_output=True, text=True, timeout=60)
    ag = i / "agents"
    with open(ag / "demo-ecran/agent.conf", "a") as f: f.write("projet = demo\nsujet = ecran\nbranche = demo/ecran\nport = 5491\n")
    # vigie : travail en cours, bloqué, à faire, journal du jour
    ecrire(ag / "vigie/CHECKLIST.md", "# Inventaire des sauvegardes\n- [x] Lister les tâches\n- [ ] Vérifier les rétentions   ← en cours\n"
           "- [ ] Rapport\n⚠ Bloqué : il manque l'accès en lecture au serveur de sauvegarde\n", 30)
    ecrire(ag / "vigie/TODO.md", "# À faire\n- [ ] Relire les alertes  (ajouté 2026-10-12)\n- [x] Ranger le journal  (fait 2026-10-12)\n", 60)
    ecrire(ag / "vigie/memory/2026-10-13.md", "- 08:15 — début de l'inventaire\n- 09:40 — liste des tâches faite\n", 20)
    # scribe : travail fini, historique, deux documents à lire (un lu, un non lu)
    ecrire(ag / "scribe/CHECKLIST.md", "# Compte rendu de la réunion\n- [x] Notes\n- [x] Mise au propre\nTerminé 2026-10-13 09:30\n", 30)
    ecrire(ag / "scribe/historique/2026-10-12_1630_note-de-service.md", "# Note de service\n- [x] Écrire\n", 1100)
    ecrire(ag / "scribe/a-lire/2026-10-13_compte-rendu.md", "# Compte rendu de la réunion\n\nTexte.\n", 25)
    lu = ecrire(ag / "scribe/a-lire/2026-10-12_note.md", "# Note de service\n\nTexte.\n", 1000)
    ecrire(i / "a-lire/2026-10-13_commun.md", "# Document commun\n", 90)
    (i / ".lectures.json").write_text(json.dumps([f"{lu}:{lu.stat().st_mtime_ns}"]))
    # demo-ecran : développeur de l'équipe demo, demande de fusion à relire
    ecrire(ag / "demo-ecran/CHECKLIST.md", "# Écran de connexion\n- [x] Maquette\n- [ ] Tests   ← en cours\n⚠ Bloqué : la base de test ne répond pas\n", 15)
    ecrire(ag / "demo-ecran/memory/2026-10-13.md", "- 09:10 — maquette faite\n", 50)
    ecrire(ag / "demo-ecran/MISSION.md", "# Mission confiée par vigie — 2026-10-13 08:00\nmoteur : claude · modèle : opus\n\nL'écran de connexion.\n", 120)
    ecrire(ag / "demo-ecran/.herdr.json", json.dumps({"agents": {"claude": "p-demo"}, "mission": {"hote": "vigie"}}), 120)
    ecrire(i / "equipes/demo/demandes/ecran.json", json.dumps({"sujet": "ecran", "branche": "demo/ecran", "commit": "abcdef1234",
                                                              "resume": "écran de connexion", "agent": "demo-ecran", "portes": {"verify": {"etat": "vert"}, "pret": {"etat": "rouge"}}, "renvois": 1,
                                                              "etat": "à relire", "demande": "2026-10-13T09:20"}), 40)
    # courtier : deux écritures en attente (au propriétaire, déléguée), appels du jour
    v = i / "courtier/validations"
    ecrire(v / "1.json", json.dumps({"n": 1, "agent": "vigie", "outil": "berger-admin", "verbe": "espace", "args": ["vigie"],
                                     "apercu": "recréer l'espace de vigie", "valideur": None, "demande": "2026-10-13T09:00"}), 60)
    ecrire(v / "2.json", json.dumps({"n": 2, "agent": "demo-ecran", "outil": "projet", "verbe": "ouvrir", "args": ["demo", "x"],
                                     "apercu": "ouvrir le projet x", "valideur": "scribe", "demande": "2026-10-13T09:10"}), 50)
    ecrire(v / "3.json", json.dumps({"n": 3, "agent": "vigie", "outil": "demo-chef", "verbe": "fusionner", "args": ["menu"],
                                     "apercu": "fusionner menu", "valideur": None, "demande": "2026-10-13T09:30"}), 30)
    ecrire(i / "equipes/demo/demandes/menu.json", json.dumps({"sujet": "menu", "branche": "demo/menu", "etat": "à relire", "agent": "demo-ecran"}), 35)
    ecrire(i / "equipes/demo/demandes/pied.json", json.dumps({"sujet": "pied", "branche": "demo/pied", "etat": "fusionnée", "agent": "demo-ecran"}), 300)
    ecrire(i / "courtier/appels.log", "2026-10-13 08:00:00\tvigie\tberger-admin\tetat\t\taccepté\tok\n"
                                      "2026-10-13 08:05:00\tscribe\tlecture\tmauvais\t\tREFUSÉ\tverbe inconnu\n"
                                      "2026-10-13 08:10:00\tvigie\tberger-admin\tsuivi\tdemo-ecran\taccepté\tok\n"
                                      "2026-10-11 07:00:00\tvigie\tlecture\talertes.py\t\taccepté\tok\n", 5)
    ecrire(i / "courtier/echanges.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in (
        {"quand": "2026-10-13T08:30:00", "de": "Proprio", "a": "vigie", "genre": "mission", "texte": "Inventaire des sauvegardes"},
        {"quand": "2026-10-13T09:00:00", "de": "vigie", "a": "Proprio", "genre": "validation demandée", "texte": "n° 1 : recréer l'espace"},
        {"quand": "2026-10-13T09:20:00", "de": "demo-ecran", "a": "vigie", "genre": "demande de fusion", "texte": "ecran : écran de connexion"})), 5)
    ecrire(ag / "vigie/.herdr.json", json.dumps({"agents": {"claude": "p-vigie"}}), 120)
    ecrire(ag / "scribe/.herdr.json", json.dumps({"agents": {"claude": "p-scribe", "codex": "p-scribe-codex"}}), 120)
    # sources relues par le courtier : à jour (rouge, jaune, neutre, couleur d'outil), en échec, figée ; « jamais » : rien
    p = i / "courtier/panneaux"
    ecrire(p / "alertes.json", json.dumps({"ok": True, "quand": (FIXE - datetime.timedelta(minutes=2)).isoformat(timespec="seconds"), "duree": 1.2,
                                           "lignes": ["2 alerte(s)", "  ✗ disque critique · srv1", "  ⚠ lenteur · srv2", "  \x1b[32mtout va bien\x1b[0m"]}), 2)
    ecrire(p / "casse.json", json.dumps({"ok": False, "quand": (FIXE - datetime.timedelta(minutes=3)).isoformat(timespec="seconds"), "code": 2,
                                         "lignes": ["demi-résultat"]}), 3)
    ecrire(p / "vieux.json", json.dumps({"ok": True, "quand": (FIXE - datetime.timedelta(hours=2)).isoformat(timespec="seconds"), "duree": 0.4,
                                         "lignes": ["rien de neuf"]}), 120)
    ecrire(i / "courtier/dernier-audit.txt", "2026-10-13 06:00 : aucune fuite (12 valeurs cherchées)\n", 240)
    ecrire(i / "courtier/derniere-sauvegarde.txt", "2026-10-13 02:00 : archive envoyée (14 Mo)\n", 480)
    # fiche, tableau et journal de l'agent : réglages, âme, mémoire, proposition, réveils, sorties, méthodes, historique
    ecrire(ag / "vigie/agent.conf", "nom = Vigie\nicone = 🛡\nmoteur = claude\npanneaux = claude\nheures = 8-19\n"
           "outils = lecture, admin, deleguer:scribe\nskills = revue, absente\nrc = vigie-distante\necrire_aussi = ~/partage-vigie\n", 500)
    ecrire(ag / "scribe/agent.conf", f"nom = Scribe\nmoteur = codex\npanneaux = codex\nheures = aucune\nlecture_seule = oui\n"
           f"superviseur = oui\ndossier = {m}/travail-scribe\nmemoire = memoire\noutils = equipe:demo\n", 500)
    (m / "travail-scribe").mkdir(exist_ok=True)
    ecrire(ag / "vigie/SOUL.md", "# Vigie\n\n## Ton\n\n- Direct et bref.\n- Toujours la source.\n\n## Ce que tu sais faire\n\n"
           "- **Inventaire** : liste les sauvegardes et leurs rétentions. Puis compare.\n- **Rapport** (hebdomadaire) : un document À lire.\n\n"
           "Ce que tu ne peux PAS faire ici : modifier une sauvegarde ; supprimer un fichier.\n\n"
           "## Tes limites\n\n- **Lecture seule** : jamais d'écriture sur les serveurs.\n\n## Règles\n\n- Une ligne par fait au journal.\n", 500)
    ecrire(ag / "vigie/MEMORY.md", "# Mémoire longue\n\n- [2026-10-12] Le serveur de sauvegarde est le premier de la baie.\n"
           "- [2026-10-10] Méthode : voir [la fiche des rétentions](retentions.md).\n", 300)
    ecrire(ag / "vigie/pending/2026-10-13_retention.md", "type: memoire\npourquoi: utile le mois prochain\n---\n- [2026-10-13] Rétention de 30 jours.\n", 40)
    ecrire(ag / "vigie/memory/2026-10-13.md", "- 08:15 — début de l'inventaire\n- 09:40 — liste des tâches faite\nnote sans heure\n", 20)
    ecrire(ag / "vigie/heartbeat/2026-10-13.md", "- 08:00 — RAS\n- 09:00 — SIGNALER : disque presque plein\n    disque presque plein sur le serveur 1\n"
           "- 09:30 — ÉCHEC : délai dépassé\n", 30)
    ecrire(ag / "vigie/sorties/rangement/2026-10-13_0700.md", "fait\n", 180)
    ecrire(ag / "vigie/historique/2026-10-12_1600_inventaire-des-postes.md", "# Inventaire des postes\n- [x] a\n- [x] b\n", 1080)
    ecrire(ag / "vigie/skills-agent/maison/SKILL.md", "---\nname: maison\n---\nMéthode de la maison.\n", 600)
    ecrire(m / ".claude/skills/partagee/SKILL.md", "---\nname: partagee\n---\nPour tous.\n", 600)
    for s in ("revue", "orpheline"): ecrire(i / f"skills/{s}/SKILL.md", f"---\nname: {s}\n---\nMéthode {s}.\n", 600)
    ecrire(ag / "scribe/memoire/MEMORY.md", "# Index\n- [2026-10-11] Réunions : [fiche](reunions.md)\n", 600)
    ecrire(ag / "scribe/memoire/reunions.md", "# Réunions\nLe lundi.\n", 600)
    (ag / "vigie/.claude/skills").mkdir(parents=True, exist_ok=True)
    if not (ag / "vigie/.claude/skills/revue").exists(): os.symlink(i / "skills/revue", ag / "vigie/.claude/skills/revue")   # méthode de son rôle
    ecrire(i / "tests/dernier-resultat.txt", "ok : 52 suites, 0 échec\n", 300)
    # consommation de tokens (journal déjà relevé) et quotas des abonnements
    c = m / ".cache/berger/conso"
    ecrire(c / "reponses.jsonl", "".join(json.dumps(e) + "\n" for e in (
        {"t": TS - 600, "a": "vigie", "m": "claude", "mod": "modele-a", "lus": 120000, "ecr": 3000, "ctx": 600000, "id": "r1"},
        {"t": TS - 3 * 86400, "a": "vigie", "m": "claude", "mod": "modele-a", "lus": 2500000, "ecr": 40000, "ctx": 90000, "id": "r2"},
        {"t": TS - 7200, "a": "scribe", "m": "codex", "mod": "modele-b", "lus": 900, "ecr": 50, "ctx": 900, "id": "r3"})), 10)
    ecrire(c / "index.json", "{}", 10)
    ecrire(c / "quota-claude.json", json.dumps({"t": TS - 300, "rate_limits": {"five_hour": {"used_percentage": 42, "resets_at": TS + 3600},
                                                                               "seven_day": {"used_percentage": 85, "resets_at": TS + 3 * 86400}}}), 5)
    ecrire(c / "quota-codex.json", json.dumps({"t": TS - 600, "rate_limits": {"primary": {"used_percent": 96, "window_minutes": 300, "resets_in_seconds": 1800}}}), 10)
    # checklists de Berger (onglet Checklists)
    ecrire(i / "checklists/mise-en-route.md", "# Mise en route\n## Réseau\n- [x] Pare-feu\n- [ ] Bornes\n## Comptes\n- [ ] Annuaire\n", 300)
    if marquages: ajouter_marquages(i, m)
    return i, env


def ajouter_marquages(i, m):
    ag = i / "agents"
    ecrire(ag / "demo-ecran/CHECKLIST.md", "# Écran de connexion\n- [x] Maquette\n- [ ] Tests   ← en cours\n"
           "⚠ Go attendu : passer l'écran en production — rapport dans À lire\n❓ Question : faut-il garder l'ancien écran ?\n", 15)
    ecrire(ag / "scribe/a-lire/2026-10-13_retention.md", "# Rétention des sauvegardes\n\nDécision attendue : choisir 30 ou 90 jours\n\n"
           "## Contexte\n- **30 jours** : moins de place.\n- `90 jours` : plus sûr.\n", 12)
    # « À lire » qui se vide (§6 quinquies, point 3) : des notes liées, par un agent Claude (vigie) et un agent Codex (scribe)
    ecrire(ag / "vigie/a-lire/2026-10-13_go-redemarrage.md", "# Il faut ton go pour redémarrer\n\nLié à : validation 4\n\nDécision attendue : redémarrer\n", 11)
    ecrire(ag / "vigie/a-lire/2026-10-13_espace.md", "# L'espace de vigie attend ta décision\n\nLié à : validation 1\n", 10)
    ecrire(ag / "scribe/a-lire/2026-10-13_pied.md", "# Le pied de page attend la fusion\n\nLié à : demande demo,pied\n", 9)
    ecrire(ag / "scribe/a-lire/2026-10-13_menu.md", "# Le menu attend la relecture\n\nLié à : demande demo,menu\n", 8)
    ecrire(i / "courtier/validations/4.fait.json", json.dumps({"n": 4, "agent": "vigie", "outil": "admin", "verbe": "redemarrer", "args": [],
                                                           "apercu": "redémarrer le service d'essai", "valideur": None, "demande": "2026-10-13T08:40",
                                                           "etat": "validé et exécuté", "decide": "2026-10-13T08:45", "par": "Proprio", "resultat": "fait"}), 70)
    # le dépôt du chef de l'équipe demo : une forge locale, la branche du développeur poussée, un commit qui touche 2 fichiers
    # livrables (spec §6.1) : la bibliothèque d'un agent (sous-dossier, maquette avec script, fichier à télécharger), un lien et un
    # fichier caché ignorés ; puis les docs/plans et docs/apercu ajoutés sur la branche du développeur (ci-dessous)
    tr = i / "bibliotheque/agents/vigie/travail"
    ecrire(tr / "ecran/maquette.html", "<!doctype html><html><head><title>Maquette de l'écran</title></head><body><p id=x></p>"
           "<script>document.getElementById('x').textContent = 'rendu par son script'</script></body></html>\n", 25)
    ecrire(tr / "ecran/notes.md", "# Notes de maquette\n\n- **deux** variantes\n", 26)
    ecrire(tr / "capture.bin", "octets", 27); ecrire(tr / ".cache", "caché", 28)
    (tr / "lien.md").symlink_to(i / "config.toml")
    # documents (spec §6.1 bis) : commun (un vrai pdf, un « .pdf » qui est du HTML, une image, un .svg, un sous-dossier), un
    # projet d'équipe, ses archives (ignorées), un dossier caché et un lien de dossier (ignorés)
    bi = i / "bibliotheque"
    ecrire(bi / "commun/guide.pdf", "%PDF-1.4\n% guide d'essai\n", 30); ecrire(bi / "commun/piege.pdf", "<html><script>alert(1)</script></html>", 31)
    (bi / "commun/logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 16); os.utime(bi / "commun/logo.png", ns=(int((TS - 1920) * 1e9),) * 2)
    ecrire(bi / "commun/dessin.svg", "<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", 33)
    ecrire(bi / "commun/procedures/sauvegarde.md", "# Procédure de sauvegarde\n\nChaque nuit.\n", 34)
    ecrire(bi / "commun/.prive/cache.md", "# caché\n", 35); (bi / "commun/raccourci").symlink_to(i / "agents")
    ecrire(bi / "equipes/demo/projets/site/plan.md", "# Plan du site\n", 36); ecrire(bi / "equipes/demo/archives/vieux/ancien.md", "# Ancien\n", 37)
    forge = m / "projets/demo.git"; depot = m / "projets/demo"
    g = lambda d, *x: subprocess.run(["git", "-C", str(d), "-c", "user.name=Essai", "-c", "user.email=essai@exemple.invalid", *x],
                                     capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(forge)], check=True)
    subprocess.run(["git", "clone", "-q", str(forge), str(depot)], check=True, capture_output=True)
    (depot / "lisezmoi.md").write_text("projet\n"); g(depot, "add", "-A"); g(depot, "commit", "-qm", "départ"); g(depot, "push", "-q", "origin", "HEAD:main")
    (depot / "docs/plans").mkdir(parents=True); (depot / "docs/plans/ancienne-spec.md").write_text("# Ancienne spec, déjà sur main\n")
    g(depot, "add", "-A"); g(depot, "commit", "-qm", "spec d'avant"); g(depot, "push", "-q", "origin", "HEAD:main")
    g(depot, "checkout", "-qb", "demo/ecran"); (depot / "ecran.py").write_text("print(1)\nprint(2)\n"); (depot / "lisezmoi.md").write_text("projet\nécran\n")
    (depot / "docs/apercu").mkdir(parents=True); (depot / "docs/plans/ecran-spec.md").write_text("# Spec de l'écran de connexion\n\nUn champ, un bouton.\n")
    (depot / "docs/apercu/ecran.html").write_text("<!doctype html><title>Aperçu de l'écran</title><p>écran</p>\n")
    g(depot, "add", "-A"); g(depot, "commit", "-qm", "écran de connexion"); g(depot, "push", "-q", "origin", "demo/ecran")
    commit = g(depot, "rev-parse", "HEAD"); g(depot, "checkout", "-q", "main"); g(depot, "fetch", "-q", "origin")
    signe = lambda e, par, q: {"etat": e, "code": 0 if e == "vert" else 1, "bilan": "---- 0 échec(s)" if e == "vert" else "1 échec", "joue_par": par, "joue_le": q}
    ecrire(i / "equipes/demo/demandes/ecran.json", json.dumps({
        "sujet": "ecran", "branche": "demo/ecran", "commit": commit, "agent": "demo-ecran", "etat": "à relire", "demande": "2026-10-13T09:20",
        "resume": "Écran de connexion.\nTests joués : verify, tests.\nPoint d'attention : la base de test.", "tronque": True, "renvois": 1,
        "motif": "porte pret rouge", "portes": {"verify": signe("vert", "demo-ecran", "2026-10-13T09:18"), "pret": signe("rouge", "demo-ecran", "2026-10-13T09:19")},
        "rejeux": [{"par": "vigie", "quand": "2026-10-13T09:40", "recompte": "ÉCART avec l'annonce : pret",
                    "portes": {"verify": signe("vert", "vigie", "2026-10-13T09:39")}}]}), 40)


def objets(i, env):
    """Les objets du jeu pour les vues d'objet : {vue: [argument…]} (l'id d'un document se lit dans la vue alire, celui d'un
    document (Livrables ou Documents) dans la vue documents)."""
    r = commande(i, env, "vue", "alire", "--json")
    ids = [x["id"] for x in json.loads(r.stdout)["donnees"]["documents"]]
    r = commande(i, env, "vue", "documents", "--json")                  # Livrables en est un filtre : mêmes ids
    livr = [x["id"] for x in json.loads(r.stdout)["donnees"]["documents"]]
    return {"validation": ["1", "2", "3", "4"], "demande": ["demo,ecran", "demo,menu"], "document": ids, "livrable": livr}


def commande(i, env, *args, timeout=180):
    """`berger <args>` à l'heure fixe (comme l'appellerait l'interface) : → subprocess.CompletedProcess."""
    prog = HORLOGE + ("import io, json, runpy, sys\n"
                      "d = json.loads(sys.stdin.read())\n"
                      "sys.argv = ['berger', '--stdin']\n"
                      "sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(d['arguments']).encode('utf-8')))\n"
                      "runpy.run_path(d['programme'], run_name='__main__')\n")
    return subprocess.run([sys.executable, "-c", prog],
                          input=json.dumps({'programme': str(i / 'bin/berger'), 'arguments': list(args)}),
                          env=env, capture_output=True, text=True, timeout=timeout)


def executer(i, env, code):
    """Lance `code` après le chargement de bin/berger à l'heure fixe ; rend la dernière ligne de sortie, lue en JSON."""
    prog = HORLOGE + f"import runpy, json, sys\nsys.argv = ['berger']\ng = runpy.run_path({str(i / 'bin/berger')!r}, run_name='essai')\n" + code
    r = subprocess.run([sys.executable, "-c", prog], env=env, capture_output=True, text=True, timeout=180)
    try: return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): sys.exit(f"ARRÊT : le cœur ne charge pas — {r.stderr[-800:]}")


COMMANDES = ("etat", "validations")                                    # commandes texte qui reçoivent aussi --json


def sorties(i, env):
    """{commande: [lignes]} : ce qu'affichent `berger etat` et `berger validations` à l'heure fixe."""
    out = executer(i, env, "import io, contextlib\nout = {}\nfor c in " + repr(COMMANDES) + ":\n"
                           "    f = io.StringIO()\n    with contextlib.redirect_stdout(f): g[c]()\n    out[c] = f.getvalue()\n"
                           "print(json.dumps(out, ensure_ascii=False))")
    return {n: x.replace(str(i), "<installation>").replace(str(i.parent), "<maison>").split("\n") for n, x in out.items()}


AGENTS_JEU = ("vigie", "scribe", "demo-ecran")                        # une vue d'agent est rendue pour chacun


def rendus(i, env, w=100, h=40):
    """{vue: [lignes]} : chaque vue rendue à l'heure fixe — une vue d'agent pour chaque agent du jeu (« tableau.vigie »),
    le dossier jetable remplacé par <installation> (il change à chaque essai)."""
    out = executer(i, env, f"out = {{}}\nfor n, v in sorted(g['VUES'].items()):\n"
                           f"  if getattr(v, 'ONGLET', '') == 'objet': continue\n"   # vue d'objet : rendue avec ses objets (objets())
                           f"  for a in ({AGENTS_JEU!r} if v.ONGLET == 'agent' else (None,)):\n"
                           f"    k = n + ('.' + a if a else '')\n"
                           f"    try: out[k] = v.rendre({w}, {h}, a)\n"
                           f"    except Exception as e: out[k] = ['ERREUR ' + type(e).__name__ + ': ' + str(e)]\n"
                           "print(json.dumps(out, ensure_ascii=False))")
    return {n: [x.replace(str(i), "<installation>").replace(str(i.parent), "<maison>") for x in l] for n, l in out.items()}
