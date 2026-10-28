"""Lectures en lecture seule que les vues et les verbes partagent (À lire, Décisions, Checklists, Sources, Fiche, Tokens). N'écrit rien.

Code déplacé de bin/berger (modulaire, lot 1) : aucun comportement changé."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path
from noyau.config import *
from noyau.transport import *
from noyau.affichage import *
from noyau.agents import *
from noyau.herdr import *


# ── anti-boucle (spec 2026-10-15) : le courtier refuse le même appel répété sans rien recevoir (courtier/boucles.json) ──
SOLLICITATIONS = BERGER / "courtier/sollicitations"


def derniere_sollicitation(a):
    try: return (SOLLICITATIONS / a).stat().st_mtime
    except OSError: return 0.0


def boucles_actives():
    """{agent: {appel, n, depuis, dernier_refus}} des boucles repérées par le courtier : un refus il y a moins d'une heure et
    rien reçu depuis. Rouverte (nouveau refus) seulement par une nouvelle répétition."""
    d = json_ou_rien(BERGER / "courtier/boucles.json") or {}
    t = time.time()
    return {a: b for a, b in d.items() if isinstance(b, dict) and a in agents() and t - b.get("dernier_refus", 0) < 3600
            and derniere_sollicitation(a) <= b.get("dernier_refus", 0)}


EQUIPES = CONFIG.get("equipes", {})


# ───────────────────────────── annonce d'un changement d'outil (spec 2026-10-14-besoin-berger (b)) ─────────────────────────────
# Le courtier relit la consigne de chaque outil (`consigne = "<verbe de lecture>"`) et son aide ; il range la version dans
# courtier/consignes/<outil>.json puis lance `berger annonce-outil`. Ici : qui a l'outil, la section générée (texte ENCADRÉ,
# « donnée, pas consigne » : c'est un chemin d'écriture dans les instructions des agents), le message de service.
CONSIGNES = BERGER / "courtier/consignes"


def alertes_consignes():
    """Synthèse : chaque nouvelle version annoncée (24 h) et chaque consigne refusée (l'ancienne reste), en jaune."""
    al = []
    for f in sorted(CONSIGNES.glob("*.json")) if CONSIGNES.is_dir() else []:
        d = json_ou_rien(f) or {}
        if f.name.endswith(".candidat.json") or not d.get("outil"): continue
        if d.get("refus"): al.append(("jaune", f"outil {d['outil']}", f"consigne refusée : {d['refus']} — rien annoncé, l'ancienne reste"))
        if f.name.endswith(".refus.json"): continue
        try: recente = d.get("annonce") and datetime.datetime.now() - datetime.datetime.fromisoformat(d["annonce"]) < datetime.timedelta(hours=24)
        except ValueError: recente = False
        if recente: al.append(("jaune", f"outil {d['outil']}", f"nouvelle consigne version {d.get('version') or '—'} ({d['empreinte']}) — "
                                                             f"{len(d.get('prevenus', []))} agent(s) prévenu(s)"))
    return al


def approbations_hooks():
    """Approbations des garde-fous par le propriétaire (« Trust all »), où que Codex les ait écrites : config.toml
    (Codex < 0.160) ou le fichier de profil de l'agent (0.160 : <agent>.config.toml). Chaque approbation est liée au
    CONTENU du garde-fou (empreinte) : la même pour tous les agents, puisqu'ils partagent hooks.json. Bloc TOML prêt."""
    vus = {}
    for f in sorted(CODEX_HOME.glob("*config.toml")):
        for cle, h in re.findall(r'^\[hooks\.state\."([^"]+)"\]\s*\ntrusted_hash = "([^"]+)"', lire(f), re.M): vus[cle] = h
    return ("[hooks.state]\n\n" + "".join(f'[hooks.state."{k}"]\ntrusted_hash = "{v}"\n\n' for k, v in sorted(vus.items()))) if vus else ""


def dossier_skills():
    """Catalogue de méthodes de l'installation (config.toml : skills.dossier ; défaut : skills/, ignoré par git). Une méthode
    du catalogue n'est donnée qu'aux agents qui la nomment (agent.conf : `skills = a, b`), selon leur rôle — à la différence
    de ~/.claude/skills, que Berger lie chez TOUS les agents (sauf `[skills] partager_utilisateur = false`)."""
    v = CONFIG.get("skills"); v = v.get("dossier") if isinstance(v, dict) else None
    return Path(os.path.expanduser(v)) if v else BERGER / "skills"


SKILLS_PRODUIT = COMMUN / "skills"   # méthodes du PRODUIT (versionnées, ex. `berger`) : en lecture seule pour les agents (commun/)


def methode(nom):
    """Dossier d'une méthode nommée dans `skills =` : celle du PRODUIT (versionnée), sinon le catalogue de l'installation.
    14/10 : le catalogue passait d'abord — une vieille copie `berger` (08/10) y masquait commun/skills/berger sans un mot."""
    p = SKILLS_PRODUIT / nom
    return p if (p / "SKILL.md").is_file() else dossier_skills() / nom


def developpeur(a):
    """Projet de l'équipe dont `a` est un développeur (ouvert par berger equipe ouvrir : projet + sujet), sinon None."""
    c = conf(a); p = c.get("projet")
    return p if p and c.get("sujet") and p in EQUIPES else None


def skills_demandees(a):
    """Méthodes du catalogue pour `a` : celles de son agent.conf, plus — pour un développeur d'équipe — celles de son
    équipe ([equipes.<projet>] skills), sans qu'on ait à les recopier dans chaque développeur jetable."""
    l = [x.strip() for x in conf(a).get("skills", "").split(",") if x.strip()]
    p = developpeur(a)
    for x in (EQUIPES[p].get("skills", []) if p else []):
        if x not in l: l.append(x)
    return l


def conversation_claude(a):
    """La conversation de l'agent dans son panneau. D'abord l'id noté par demarrer_agent (.conversation-claude) ; sinon
    (agent lancé avant) la dernière conversation INTERACTIVE du dossier : Claude range ~/.claude/projects/<dossier, chaque
    caractère non alphanumérique remplacé par « - »>/<id>.jsonl, et marque « "entrypoint":"cli" » une conversation ouverte
    dans un terminal (« sdk-cli » pour un appel claude -p du planificateur, qu'il ne faut PAS reprendre). None sinon."""
    d = HOME / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(travail(a)))
    note = lire(dossier(a) / ".conversation-claude").strip()
    if note and (d / f"{note}.jsonl").is_file(): return note
    for f in sorted(d.glob("*.jsonl") if d.is_dir() else [], key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(f, errors="replace") as h: tete = h.read(20000)
        except OSError: continue
        if '"entrypoint":"cli"' in tete: return f.stem
    return None


# ───────────────────────────── besoin Berger (berger-outil besoin) ─────────────────────────────
# Le courtier a vérifié l'émetteur, la chaîne d'équipe, le texte, le secret et le débit ; ici : le rangement numéroté dans
# courtier/besoins/, la trace Échanges, la remise au gardien, la clôture. Spec : docs/plans/2026-10-14-besoin-berger-spec.md (a).
BESOINS = BERGER / "courtier/besoins"


def gardien():
    """Le chef de projet de l'équipe dont la fusion EST l'installation (`installer_outil`) ; None sinon (même règle que le courtier)."""
    return next((e.get("chef_projet") for e in EQUIPES.values() if e.get("installer_outil") and e.get("chef_projet")), None)


def besoins(ouverts=True):
    """Les besoins ouverts (n.json), ou clos (n.clos.json), dans l'ordre des numéros."""
    motif = "*.json" if ouverts else "*.clos.json"
    fs = [f for f in BESOINS.glob(motif) if (f.stem.isdigit() if ouverts else f.name.split(".")[0].isdigit())] if BESOINS.is_dir() else []
    return [d for d in (json_ou_rien(f) for f in sorted(fs, key=lambda f: int(f.name.split(".")[0]))) if d]


def hote_mission(a):
    """L'agent qui héberge la mission de `a` dans son onglet Missions (None : mission dans l'espace de `a`)."""
    return herdr_ids(a).get("mission", {}).get("hote")


MISSIONS = CONFIG.get("missions", {})       # max = missions simultanées ; modeles_claude / modeles_codex = modèles permis


def reglages_mission(a):
    """(moteur, modèle) de la mission en cours de l'agent, lus dans l'en-tête de MISSION.md ; (None, None) sinon."""
    r = re.search(r"^moteur : (\w+)(?: · modèle : ([\w.-]+))?$", lire(dossier(a) / "MISSION.md"), re.M)
    return (r.group(1), r.group(2)) if r else (None, None)


def json_ou_rien(f):
    """Un fichier JSON écrit par un autre processus peut être lu à moitié écrit : rien plutôt qu'une exception."""
    try: d = json.loads(f.read_text())
    except (OSError, ValueError): return None
    return d if isinstance(d, dict) else None


def en_attente(agent=None):
    v = BERGER / "courtier/validations"
    out = [json_ou_rien(f) for f in sorted(v.glob("*.json"), key=lambda x: int(x.stem) if x.stem.isdigit() else 0)
           if f.stem.isdigit()] if v.is_dir() else []
    out = [{"n": "?", "agent": "?", "apercu": "", **d} for d in out if d]
    return [d for d in out if agent is None or d["agent"] == agent]


def validation_donnees(d):
    """Une écriture en attente dans les données des vues (Validation de bin/schemas/communs.schema.json) : jamais ses
    arguments (son détail, avec filtre, est une autre vue)."""
    return {"n": int(d["n"]) if str(d.get("n")).isdigit() else None, "agent": agent_court(str(d.get("agent", "?"))),
            "outil": str(d.get("outil", "?")), "verbe": str(d.get("verbe", "?")), "apercu": str(d.get("apercu", "")),
            "demande": str(d.get("demande", "")), "valideur": agent_court(d["valideur"]) if d.get("valideur") else None,
            "fusion": str((d.get("args") or [""])[0]) if d.get("verbe") == "fusionner" else None}


def reglage_tache(f):
    entete = lire(f).split("\n---", 1)[0]
    return {k.strip().lower(): v.split("#")[0].strip() for k, v in
            (l.split(":", 1) for l in entete.splitlines() if ":" in l)}


def tableau_donnees(a):
    """Les données du Tableau de l'agent (vue tableau, tableau.schema.json) : travail en cours, ce qui attend le propriétaire
    (blocage, écritures, propositions, signalements du jour), à faire, fait (5 dernières lignes cochées) et historique (4)."""
    d = dossier(a); ck = checklist(a); todo = cases(lire(d / "TODO.md")); attend = []
    attend = [{"genre": x["genre"], "n": x["n"], "texte": x["detail"]}
              for x in decisions() if x["pour"] == "toi" and x["agent"] == a]
    ligne = lambda lib: dict(zip(("libelle", "date"), date_fin(plat(lib))))
    historique = []
    for h in sorted((d / "historique").glob("*.md"))[-4:]:
        historique.append({"titre": next((x[1:].strip() for x in lire(h).splitlines() if x.startswith("#")), h.stem), "date": f"{h.stem[8:10]}/{h.stem[5:7]}"})
    return {"agent": agent_court(a), "statuts": statuts_donnees(a), "en_cours": checklist_donnees(ck) if ck and not ck["fini"] else None,
            "attend": attend, "a_faire": [ligne(lib) for fait, lib in todo if not fait],
            "fait": [ligne(lib) for fait, lib in [x for x in todo if x[0]][-5:]], "historique": historique}


# ─── Fiche d'un agent : une fonction de DONNÉES par rubrique (fiche.schema.json), un rendu texte qui ne lit qu'elles ───
def identite_donnees(a):
    d = dossier(a); c = conf(a)
    codex = "codex" in (c["moteur"], *[m.strip() for m in c["panneaux"].split(",")]); approuves = approbations_hooks().count("trusted_hash") >= 3
    return {"statuts": statuts_donnees(a), "moteur": c["moteur"], "panneaux": c["panneaux"], "mur_ouvert": c.get("mur") == "ouvert",
            "rc": c.get("rc") or None, "travaille_dans": str(travail(a)) if externe(a) else None, "dossier": f"~/berger/agents/{a}",
            "outils": next((l.split("=", 1)[1].split("#")[0].strip() for l in lire(d / "agent.conf").splitlines() if l.split("=")[0].strip() == "outils"), ""),
            "ton": [t for _, t in puces(section(lire(d / "SOUL.md"), "Ton"))],
            "protections": {"garde_fous": len(GARDES), "codex": codex, "approuves": approuves, "ok": approuves or not codex, "ouvert": ouvert(a),
                            "illisibles": None if ouvert(a) else len(masques(a)) + 1,
                            "ecrit_en_plus": [] if ouvert(a) else [x.replace(str(HOME), "~") for x in ecritures_en_plus(a)]}}


def identite_texte(d, a, w):
    out = [f"  {PALE}statut{R}            {statuts_texte(d['statuts']) or PALE + 'pas d’espace Herdr' + R}"]
    out.append(f"  {PALE}moteur par défaut{R} {GRAS}{d['moteur']}{R}   {PALE}(bascule sur l'autre si panne){R}")
    out.append(f"  {PALE}panneaux ouverts{R}  {d['panneaux']}")
    out.append(f"  {PALE}sécurité{R}          " + (f"{JAUNE}ouverte{R} {PALE}(réseau, SSH, coffre ; garde-fous seulement){R}" if d["mur_ouvert"]
               else f"{VERT}stricte{R} {PALE}(bac à sable : ni réseau ni coffre){R}") + (f"   {PALE}Remote Control{R} {d['rc']}" if d["rc"] else ""))
    if d["travaille_dans"]: out.append(f"  {PALE}travaille dans{R}    {d['travaille_dans']}")
    out.append(f"  {PALE}dossier{R}           {d['dossier']}")
    out.append(f"  {PALE}outils (courtier){R}  {d['outils'] or 'aucun'}    {PALE}parler : berger parler {a} --stdin · Ctrl+Espace a{R}"); out.append("")
    if d["ton"]:
        out += titre_section("TON", CYAN, w)
        for t in d["ton"]: out += plier(t, w, "  • ", "    ")
    p = d["protections"]
    out += titre_section("PROTECTIONS", VERT, w)
    texte = f"{p['garde_fous']} garde-fous" + ((" (approuvés sous Codex)" if p["approuves"] else " (NON approuvés sous Codex)") if p["codex"] else "")
    if p["ouvert"]: texte += " · mur ouvert : accès de l'utilisateur, réseau compris"
    else:
        ecrit = "son dossier" + "".join(f" + {x}" for x in p["ecrit_en_plus"])
        texte += f" · {p['illisibles']} emplacements illisibles · écrit seulement dans {ecrit} · pas de réseau"
    out += plier(texte, w, (VERT if p["ok"] else ROUGE) + "  ✓ " + R, "    ")
    return out


def capacites_donnees(a):
    d = dossier(a); cap = []
    for lab, desc in puces(section(lire(d / "SOUL.md"), "Ce que tu sais faire")):
        if not lab: continue
        reste = re.sub(r"^\(.*?\)\s*:?\s*", "", desc).strip(" .:;")
        desc = reste or re.sub(r"^\((.*?)\).*$", r"\1", desc)
        cap.append({"titre": lab, "texte": desc.split(". ")[0].rstrip(".")})
    perso = sorted(p.parent.name for p in (d / "skills-agent").glob("*/SKILL.md"))
    liens = [p for p in (d / ".claude/skills").iterdir() if p.is_symlink()] if (d / ".claude/skills").is_dir() else []
    role = sorted(p.name for p in liens if p.name not in perso and p.resolve().parent in (dossier_skills().resolve(), SKILLS_PRODUIT.resolve()))
    return {"capacites": cap, "skills": {"partagees": len([p for p in liens if p.name not in perso and p.name not in role]), "role": role, "propres": perso}}


def capacites_texte(d, w):
    out = []
    for x in d["capacites"]:
        lignes = plier(f"{x['titre']} — {x['texte']}", w, "  • ", "    ")
        lignes[0] = lignes[0].replace(x["titre"], GRAS + x["titre"] + R, 1); out += lignes
    s = d["skills"]; role, perso = s["role"], s["propres"]
    out += ["", f"  {PALE}méthodes (skills){R}  {s['partagees']} partagées" + (f"  ·  {GRAS}{len(role)} de son rôle{R} : {', '.join(role)}" if role else "")
            + (f"  ·  {GRAS}{len(perso)} à lui{R} : {', '.join(perso)}" if perso else "  ·  aucune à lui")]
    return out


def verbes_outil(o):
    """(lectures, écritures) d'un outil du courtier, lues dans le module de l'outil lui-même (sans réseau, sans secret)."""
    r_ = CONFIG.get("outils", {}).get(o)
    if not r_: return [], []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(f"outil_{r_['type']}", BERGER / "courtier/outils" / f"{r_['type']}.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        x = mod.Outil(r_, lambda cle: "", lambda cle, url: None)
        return list(getattr(x, "verbes", {})), list(getattr(x, "ecritures", {}))
    except Exception:
        return [], []


def ecritures_outil(o):
    """Verbes d'ÉCRITURE (soumis à validation) d'un outil du courtier."""
    return verbes_outil(o)[1]


def limites_donnees(a):
    d = dossier(a); c = conf(a); soul = lire(d / "SOUL.md")
    lim = re.search(r"ne peux PAS faire ici[^:]*:\s*(.+?)(?:\.\s|\.$|$)", " ".join(section(soul, "Ce que tu sais faire").split()))
    lecture_seule = c.get("lecture_seule", "").lower() in ("oui", "yes", "true", "1")
    valid = [f"{o} : {v}" for o in [x.strip() for x in c.get("outils", "").split(",") if x.strip()] for v in ecritures_outil(o)]
    return {"impossible": [m.strip() for m in plat(lim.group(1)).split(";")] if lim else [], "lecture_seule": lecture_seule,
            "superviseur": superviseur(a), "a_valider": [] if lecture_seule else valid,
            "regles": [(f"{lab} — {t}" if lab else t) for titre in ("Tes limites", "Règles") for lab, t in puces(section(soul, titre))]}


def limites_texte(d, w):
    out = []
    if d["impossible"]:
        out += titre_section("IMPOSSIBLE ICI (bloqué par le système)", ROUGE, w)
        for morceau in d["impossible"]: out += plier(morceau, w, ROUGE + "  ✗ " + R, "    ")
    if d["lecture_seule"]:
        out += [""] + titre_section("LECTURE SEULE (tenue par le courtier)", ROUGE, w)
        out += plier("aucune écriture, même soumise à validation ; ni mission, ni délégation, ni décision", w, ROUGE + "  ✗ " + R, "    ")
    if d["superviseur"]:
        out += [""] + titre_section("SUPERVISEUR (lit tout Berger, n'écrit que chez lui)", JAUNE, w)
        out += plier("lit les autres agents, leur bibliothèque et les projets ; jamais le coffre ni les sources des outils", w, JAUNE + "  👁 " + R, "    ")
    if d["a_valider"]:
        out += [""] + titre_section("SOUMIS À VALIDATION (berger valider <n°>)", JAUNE, w)
        for t in d["a_valider"]: out += plier(t, w, JAUNE + "  ? " + R, "    ")
    if d["regles"]:
        out += [""] + titre_section("SES RÈGLES", CYAN, w)
        for t in d["regles"]: out += plier(t, w, CYAN + "  • " + R, "    ")
    return out


def memoire_donnees(a):
    d = dossier(a); mem = lire(fichier_memoire(a)); md = memoire_dossier(a); lignes = []
    for l in [l for l in mem.splitlines() if l.startswith("- ")]:
        m = re.match(r"^- \[(\d{4})-(\d\d)-(\d\d)\]\s*(.*)$", l)
        lignes.append({"date": f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None,
                       "texte": re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", m.group(4) if m else l[2:])})     # [Titre](fiche.md) → Titre
    return {"dossier": str(md).replace(str(HOME), "~") if md else None,
            "fiches": len([x for x in md.glob("*.md") if x.name != "MEMORY.md"]) if md else None,
            "taille": len(mem), "max": 3000, "lignes": lignes,
            "propositions": [{"nom": x[:-3], "texte": lire(d / "pending" / x).split("\n---", 1)[-1].strip()} for x in pendants(a)]}


def memoire_texte(d, w):
    out = []
    if d["dossier"]: out.append(f"  {PALE}index + {d['fiches']} fiches dans{R} {d['dossier']}")
    else: out.append(f"  {jauge(d['taille'], d['max'], min(30, w - 20), VERT)}  {d['taille']}/{d['max']} caractères")
    out.append("")
    for l in d["lignes"]:
        out += plier(plat(l["texte"]), w, f"  {PALE}{l['date'][8:10]}/{l['date'][5:7]}{R}  " if l["date"] else "  ", "         ")
    if not d["lignes"]: out.append(PALE + "  vide" + R)
    p = d["propositions"]
    out += [""] + titre_section(f"PROPOSITIONS À VALIDER ({len(p)})", JAUNE, w)
    for x in p: out += plier(plat(x["texte"].lstrip("- ")), w, f"  {JAUNE}?{R} {GRAS}{x['nom']}{R} — ", "    ")
    if not p: out.append(PALE + "  aucune" + R)
    return out


def veille_donnees(a):
    d = dossier(a); c = conf(a); taches = []
    hb = [x[2:] for x in lire(d / "heartbeat" / f"{aujourdhui()}.md").splitlines() if x.startswith("- ")]
    for f in sorted((d / "taches").glob("*.md")):
        r_ = reglage_tache(f); mo = r_.get("moteur", ""); der = sorted((d / "sorties" / f.stem).glob("*.md"))
        taches.append({"nom": f.stem, "quand": str(r_.get("quand", "?")), "moteur": c["moteur"] if mo in ("", "defaut") else mo,
                       "notifier": str(r_.get("notifier", "non")), "prochaine": prochaine(r_.get("quand")),
                       "derniere": der[-1].stem.replace("_", " ") if der else None})
    return {"heures": c["heures"], "reveils": len(hb), "ras": sum("RAS" in x for x in hb), "signalements": sum("SIGNALER" in x for x in hb),
            "echecs": sum("ÉCHEC" in x or "échec" in x for x in hb), "dernier": hb[-1] if hb else None, "taches": taches}


def veille_texte(d, w):
    out = []
    if "-" in d["heures"]:
        debut, fin = d["heures"].split("-")
        out.append(f"  {PALE}battement de cœur{R}  chaque heure pile, de {debut} h à {fin} h")
    else: out.append(f"  {PALE}battement de cœur{R}  aucun : agent à la demande (il ne vit que pendant ses missions)")
    sig, ech = d["signalements"], d["echecs"]
    out.append(f"  {PALE}aujourd'hui{R}        {d['reveils']} réveils · {d['ras']} RAS · "
               + (f"{JAUNE}{sig} signalements{R}" if sig else "0 signalement") + " · " + (f"{ROUGE}{ech} échecs{R}" if ech else "0 échec"))
    if d["dernier"] is not None: out += plier(plat(d["dernier"]), w, f"  {PALE}dernier{R}            ", "                     ")
    out += [""] + titre_section("TÂCHES PLANIFIÉES", CYAN, w)
    for t in d["taches"]:
        out.append(f"  {GRAS}{t['nom']}{R}  {PALE}·{R} {t['quand']}  {PALE}· {t['moteur']} · notification {t['notifier']}{R}")
        out.append(f"      {PALE}prochaine{R} {t['prochaine']}    {PALE}dernière{R} " + (t["derniere"] or "jamais"))
    if not d["taches"]: out.append(PALE + "  aucune" + R)
    return out


AUTO_TEST_NUIT = HOME / ".config/systemd/user/timers.target.wants/berger-tests.timer"   # minuterie de nuit activée


def alertes_auto_test(maintenant=None):
    """Suite complète (tests/tout.sh) : un échec → ROUGE, avec le nom des contrôles en échec (3 au plus) ; minuterie de
    nuit activée mais aucun passage depuis 26 h (ou jamais) → ROUGE : un auto-test qui ne tourne plus ne prouve rien."""
    f = BERGER / "tests/dernier-resultat.txt"; lignes = lire(f).strip().splitlines()
    al = []
    if lignes and "échec" in lignes[0]:
        noms = [l[2:] for l in lignes[1:] if l.startswith("- ")]
        al.append(("rouge", "auto-test", f"dernier auto-test : {lignes[0]}" + (" — " + " · ".join(noms[:3]) if noms else "")
                   + (f" (+{len(noms) - 3})" if len(noms) > 3 else "")))
    if AUTO_TEST_NUIT.exists() and (not lignes or (maintenant or time.time()) - f.stat().st_mtime > 26 * 3600):
        al.append(("rouge", "auto-test", "auto-test de nuit : aucun passage depuis plus de 26 h" if lignes else "auto-test de nuit : jamais passé"))
    return al


def activite_donnees(a):
    d = dossier(a); todo = cases(lire(d / "TODO.md")); jours = sorted((d / "memory").glob("*.md")); ck = checklist(a); termines = []
    for x in sorted((d / "historique").glob("*.md"))[-8:][::-1]:
        t = lire(x); k = cases(t)
        termines.append({"titre": next((l[1:].strip() for l in t.splitlines() if l.startswith("#")), x.stem), "quand": x.stem[:15],
                         "faites": sum(f for f, _ in k), "total": len(k)})
    return {"a_faire": sum(not f for f, _ in todo), "fait": sum(f for f, _ in todo), "jours": len(jours),
            "premier_jour": jours[0].stem if jours else None,
            "en_cours": {"titre": ck["titre"], "faites": ck["faites"], "total": ck["total"]} if ck and not ck["fini"] else None,
            "auto_test": (lire(BERGER / "tests" / "dernier-resultat.txt").strip().splitlines() or [""])[0], "termines": termines}


def activite_texte(d, w):
    j = d["premier_jour"]
    out = [f"  {PALE}à faire{R} {d['a_faire']}   {PALE}fait{R} {d['fait']}   "
           f"{PALE}jours de journal{R} {d['jours']}" + (f"  {PALE}(depuis le {j[8:]}/{j[5:7]}){R}" if j is not None else "")]
    ck = d["en_cours"]
    out.append(f"  {PALE}travail en cours{R}  " + (f"{GRAS}{plat(ck['titre'])}{R} {ck['faites']}/{ck['total']}" if ck else "aucun"))
    out.append(f"  {PALE}dernier auto-test{R} " + (d["auto_test"] or "jamais lancé"))
    out += [""] + titre_section("TRAVAUX TERMINÉS", VERT, w)
    for x in d["termines"]:
        q = x["quand"]
        out += plier(f"{plat(x['titre'])}  {PALE}{x['faites']}/{x['total']} étapes{R}", w,
                     f"  {VERT}✓{R} {PALE}{q[8:10]}/{q[5:7]} {q[11:13]}h{q[13:15]}{R}  ", "                 ")
    if not d["termines"]: out.append(PALE + "  aucun pour l'instant" + R)
    return out


# Les mêmes rubriques en (clé, libellé, données(a), texte(données, a, w)) : la vue fiche et son schéma en viennent.
RUBRIQUES_FICHE = [("identite", "Identité", identite_donnees, identite_texte),
                   ("capacites", "Capacités", capacites_donnees, lambda d, a, w: capacites_texte(d, w)),
                   ("limites", "Limites", limites_donnees, lambda d, a, w: limites_texte(d, w)),
                   ("memoire", "Mémoire", memoire_donnees, lambda d, a, w: memoire_texte(d, w)),
                   ("veille", "Réveils", veille_donnees, lambda d, a, w: veille_texte(d, w)),
                   ("activite", "Activité", activite_donnees, lambda d, a, w: activite_texte(d, w))]


def courtier_actif():
    return subprocess.run(["systemctl", "--user", "is-active", "berger-courtier"], capture_output=True, text=True).stdout.strip() == "active"


def droits_agents():
    """{agent: [droits]} lus dans le réglage « outils » de chaque agent.conf (outils du courtier et droits spéciaux)."""
    return {a: [x.strip() for x in conf(a).get("outils", "").split(",") if x.strip()] for a in agents()}


def derniers_usages():
    """{(agent, outil): date du dernier appel ACCEPTÉ} d'après courtier/appels.log (aucune valeur : noms seulement)."""
    u = {}
    for l in lire(BERGER / "courtier/appels.log").splitlines():
        c = l.split("\t")
        if len(c) < 6 or c[5] != "accepté": continue
        try: u[(c[1], c[2])] = datetime.datetime.strptime(c[0], "%Y-%m-%d %H:%M:%S")
        except ValueError: pass
    return u


# ─────────────── consommation de tokens : un LECTEUR par moteur (Berger est multi-moteur) ───────────────
# Chaque lecteur lit les journaux LOCAUX de son moteur, en avançant (octet déjà lu retenu), et rend des réponses :
# {t, a(gent), m(oteur), mod(èle), lus (entrée + cache), ecr(its), ctx (contexte relu à ce tour), id}. Rien n'est envoyé.
# Ajouter un moteur = déposer bin/moteurs/<moteur>.py (son lecteur est rangé dans LECTEURS_CONSO au chargement) ; sa source de quota va à quota_moteurs.
CONSO = HOME / ".cache/berger/conso"


GARDE_CONSO = 7 * 86400

# Sources d'alertes de la Synthèse posées par des paquets chargés au démarrage : {nom: fonction() -> [(ton, source, texte)]}.
SOURCES_ALERTES = {}


def agent_du_dossier(chemin):
    """Agent dont le dossier de travail contient `chemin` (le plus précis gagne), sinon None."""
    chemin = str(chemin or ""); meilleur = None
    for a in agents():
        t = str(travail(a))
        if (chemin == t or chemin.startswith(t + "/")) and (meilleur is None or len(t) > len(str(travail(meilleur)))): meilleur = a
    return meilleur


def lignes_neuves(f, index):
    """Lignes complètes ajoutées à f depuis le dernier passage (index : {fichier: octet lu})."""
    try: st = f.stat()
    except OSError: return []
    pos = index.get(str(f), 0)
    if st.st_size < pos: pos = 0                                          # fichier réécrit
    if st.st_size == pos or time.time() - st.st_mtime > GARDE_CONSO: index[str(f)] = st.st_size; return []
    out = []
    with open(f, "rb") as h:
        h.seek(pos)
        for brut in h:
            if not brut.endswith(b"\n"): break                          # ligne en cours d'écriture : au prochain passage
            pos += len(brut); out.append(brut)
    index[str(f)] = pos
    return out


# Rempli par moteurs/ (lot 2) : un lecteur par moteur CHARGÉ (moteurs/<moteur>.py, lecteur_conso()) ; un moteur écarté n'y est pas.
LECTEURS_CONSO = {}


def collecter_conso():
    """Réponses des 7 derniers jours, tous moteurs, sans doublon (une réponse peut s'écrire sur plusieurs lignes)."""
    try: CONSO.mkdir(parents=True, exist_ok=True)
    except OSError: pass
    try: index = json.loads((CONSO / "index.json").read_text())
    except (OSError, ValueError): index = {}
    try: evts = [json.loads(l) for l in (CONSO / "reponses.jsonl").read_text().splitlines()]
    except (OSError, ValueError): evts = []
    vus = {e["id"] for e in evts}
    for lire_moteur in LECTEURS_CONSO.values():
        for e in lire_moteur(index):
            if e["id"] not in vus: vus.add(e["id"]); evts.append(e)
    maint = time.time(); evts = [e for e in evts if maint - e["t"] < GARDE_CONSO]
    try:                                                                   # cache de lecture : s'il n'est pas inscriptible (lecture
        (CONSO / "reponses.jsonl.tmp").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evts))   # seule, autre
        os.replace(CONSO / "reponses.jsonl.tmp", CONSO / "reponses.jsonl")   # utilisateur), les données sont rendues quand même
        (CONSO / "index.json.tmp").write_text(json.dumps(index)); os.replace(CONSO / "index.json.tmp", CONSO / "index.json")
    except OSError: pass
    return evts


def quand_remise(ts):
    try: r = datetime.datetime.fromtimestamp(float(ts))
    except (TypeError, ValueError): return "?"
    return f"{r:%H:%M}" if r.date() == datetime.date.today() else f"{('lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.')[r.weekday()]} {r:%H:%M}"


def quota_moteurs():
    """{moteur: (mesures [(nom, %, remise)], âge en s) ou None}. Claude : relevé par `berger statusline` (rate_limits de
    la barre d'état, abonnement seulement, absent si une passerelle ne relaie pas les en-têtes) ; Codex : ses journaux."""
    q = {}
    try:
        d = json.loads((CONSO / "quota-claude.json").read_text()); rl = d.get("rate_limits") or {}
        q["claude"] = ([(n, rl[k]["used_percentage"], rl[k].get("resets_at")) for k, n in (("five_hour", "5 h"), ("seven_day", "7 j"))
                        if (rl.get(k) or {}).get("used_percentage") is not None], time.time() - d["t"])
    except (OSError, ValueError, KeyError): q["claude"] = None
    try:
        d = json.loads((CONSO / "quota-codex.json").read_text()); rl = d.get("rate_limits") or {}; mes = []
        for k in ("primary", "secondary"):
            v = rl.get(k) or {}
            if v.get("used_percent") is None: continue
            fen = v.get("window_minutes"); nom = f"{fen // 60} h" if fen and fen < 1440 else f"{fen // 1440} j" if fen else k
            remise = v.get("resets_at") or (d["t"] + v["resets_in_seconds"] if v.get("resets_in_seconds") is not None else None)
            mes.append((nom, v["used_percent"], remise))
        q["codex"] = (mes, time.time() - d["t"])
    except (OSError, ValueError, KeyError): q["codex"] = None
    return q


def kilo(n):
    return f"{n / 1e9:.1f} G" if n >= 1e9 else f"{n / 1e6:.1f} M" if n >= 1e6 else f"{n / 1e3:.0f} k" if n >= 1e3 else str(n)


def derniere_action(a):
    l = [x for x in lire(dossier(a) / "memory" / f"{aujourdhui()}.md").splitlines() if x.startswith("- ")]
    return l[-1][2:] if l else ""


# ─────────────── À lire : les documents produits pour le propriétaire (rapports, inventaires, comptes rendus) ───────────────
# Un agent dépose un document dans agents/<agent>/a-lire/ (son dossier : il y écrit) ; le propriétaire ou un outil peut en déposer
# dans <BERGER>/a-lire/. L'onglet « À lire » les liste et les ouvre mis en forme ; ce qui est lu est retenu (.lectures.json, une
# empreinte « chemin + date de modification » : un document modifié redevient non lu).
LECTURES = BERGER / ".lectures.json"


LIE_A = re.compile(r"^Lié à\s*:\s*(?:validation\s+n?°?\s*(\d{1,6})|demande\s+([\w.-]+)\s*,\s*([\w.-]+))\s*$", re.M | re.I)


def lien_regle(texte):
    """« À lire » qui se vide (spec interface §6 quinquies, point 3) : une note qui déclare dans ses 15 premières lignes
    `Lié à : validation <n>` ou `Lié à : demande <projet>,<sujet>` est réglée quand l'écriture est décidée (<n>.fait.json)
    ou la demande fusionnée → le motif (texte), sinon None. Rien n'est supprimé : la note compte alors comme lue."""
    m = LIE_A.search("\n".join(texte.splitlines()[:15]))
    if not m: return None
    if m.group(1):
        f = BERGER / "courtier" / "validations" / f"{int(m.group(1))}.fait.json"
        try: return f"écriture n° {int(m.group(1))} {json.loads(f.read_text()).get('etat', 'décidée')}" if f.is_file() else None
        except (OSError, ValueError): return f"écriture n° {int(m.group(1))} décidée"
    try: d = json.loads((BERGER / "equipes" / m.group(2) / "demandes" / f"{m.group(3)}.json").read_text())
    except (OSError, ValueError): return None
    return f"demande {m.group(2)},{m.group(3)} fusionnée" if d.get("etat") == "fusionnée" else None


def documents_a_lire():
    docs = []
    for auteur, dos in [(a, AGENTS / a / "a-lire") for a in agents()] + [("", BERGER / "a-lire")]:
        for f in (sorted(dos.glob("*.md")) if dos.is_dir() else []):
            if not f.is_file() or f.is_symlink(): continue
            st = f.stat(); t = lire(f); titre = next((l.lstrip("# ").strip() for l in t.splitlines() if l.strip()), f.stem)
            docs.append({"chemin": f, "auteur": auteur, "titre": titre[:120], "date": st.st_mtime, "cle": f"{f}:{st.st_mtime_ns}",
                         "regle": lien_regle(t)})
    return sorted(docs, key=lambda d: d["date"], reverse=True)


def lus():
    """Les documents lus : marqués à la main (berger lire, l'interface au lot 2) ET ceux dont l'objet lié est réglé."""
    try: vus = set(json.loads(LECTURES.read_text()))
    except (OSError, ValueError): vus = set()
    return vus | {d["cle"] for d in documents_a_lire() if d["regle"]}


DOCUMENTS_MAX = 2000                                                       # les plus récents (schéma documents : maxItems)


LIVRABLES_MAX = 200                                                        # les plus récents (schéma livrables : maxItems)


BRANCHE_SURE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")            # nom de branche lu dans la config ou une demande : jamais un tiret initial


# Genre d'un fichier : son EXTENSION (table fermée) ; un pdf ou une image ne garde ce genre que si ses premiers octets portent
# la signature attendue — sinon « autre » (téléchargé, jamais affiché : un .pdf qui est du HTML ne s'ouvre pas).
EXTENSIONS = {".md": "md", ".html": "html", ".htm": "html", ".pdf": "pdf", ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg",
              ".gif": "gif", ".webp": "webp"}


SIGNATURES = {"pdf": (b"%PDF-",), "png": (b"\x89PNG\r\n\x1a\n",), "jpeg": (b"\xff\xd8\xff",), "gif": (b"GIF87a", b"GIF89a"),
              "webp": (b"RIFF",)}


LIVRABLES_GENRES = ("md", "html", "pdf")                                     # specs, maquettes, rapports


LIVRABLES_ORIGINES = ("travail", "a_lire", "branche")


def genre_document(nom, debut=b""):
    g = EXTENSIONS.get(os.path.splitext(nom)[1].lower(), "autre")
    if g in SIGNATURES and not (debut.startswith(SIGNATURES[g]) and (g != "webp" or debut[8:12] == b"WEBP")): return "autre"
    return g


def titre_document(nom, debut):
    """Le titre d'un document : 1re ligne d'un .md, <title> d'un .html, sinon le nom du fichier."""
    import html as _html
    t = debut.decode("utf-8", "replace"); g = genre_document(nom, debut)
    if g == "md": t = next((l.lstrip("# ").strip() for l in t.splitlines() if l.strip()), "")
    elif g == "html":
        m = re.search(r"<title[^>]*>([^<]*)</title>", t, re.I); t = _html.unescape(m.group(1)).strip() if m else ""
    else: t = ""
    return (t or nom.rsplit("/", 1)[-1])[:120]


def documents():
    """Le SEUL lister de fichiers de l'interface (spec interface §6.1 et §6.1 bis), racines fixes et rien d'autre :
    bibliothèque — commun/ (origine commun), equipes/<équipe>/projets/<projet>/ (projet ; jamais archives/),
    agents/<agent>/travail/ (travail) — ; les À lire (a_lire, documents_a_lire) ; les fichiers ajoutés ou modifiés sous les
    dossiers `livrables` de [equipes.<p>] (défaut docs/plans et docs/apercu) sur les branches en cours (branche : développeurs
    ouverts, demandes non fusionnées), lus dans le dépôt du chef SANS fetch. Aucun lien suivi (os.walk ; lien de fichier ou de
    dossier ignoré), aucun fichier ni dossier caché, fichier résolu hors de sa racine ignoré.
    → les plus récents d'abord, chacun avec `lire()` (son contenu) ; l'`id` est une empreinte de l'origine et du chemin (jamais le chemin lui-même) : STABLE quand le fichier est modifié."""
    import hashlib
    out = []
    def ajouter(origine, cle, nom, debut, **x):
        out.append({"id": hashlib.sha256(f"{origine}\0{cle}".encode()).hexdigest()[:16], "origine": origine,
                    "titre": titre_document(nom, debut), "genre": genre_document(nom, debut), **x})
    def parcourir(racine, origine, prefixe, auteur=None, projet=None):
        if racine.is_symlink() or not racine.is_dir(): return
        base = racine.resolve()
        for dos, sous, fichiers in os.walk(racine):                         # os.walk ne suit pas les liens de dossier
            sous[:] = sorted(s for s in sous if not s.startswith(".") and not (Path(dos) / s).is_symlink())
            for nom in sorted(fichiers):
                f = Path(dos) / nom
                if nom.startswith(".") or f.is_symlink() or not f.is_file() or base not in f.resolve().parents: continue
                st = f.stat()
                with open(f, "rb") as h: debut = h.read(65536)
                ajouter(origine, str(f), nom, debut, auteur=auteur, projet=projet, branche=None,
                        chemin=prefixe + str(f.relative_to(racine)), taille=st.st_size, date=st.st_mtime, lu=None, lire=lambda f=f: f.read_bytes())
    parcourir(BIBLIO_COMMUN, "commun", "commun/")
    for e in (sorted(BIBLIO_EQUIPES.iterdir()) if BIBLIO_EQUIPES.is_dir() and not BIBLIO_EQUIPES.is_symlink() else []):
        pj = e / "projets"
        if e.name.startswith(".") or e.is_symlink() or pj.is_symlink() or not pj.is_dir(): continue
        for p in sorted(pj.iterdir()):
            if not p.name.startswith("."): parcourir(p, "projet", "", projet=f"{e.name}/{p.name}")
    racine = BIBLIOTHEQUE / "agents"
    for d in (sorted(racine.iterdir()) if racine.is_dir() else []):
        if not d.name.startswith(".") and not d.is_symlink(): parcourir(d / "travail", "travail", "travail/", auteur=d.name)
    vus = lus()
    for x in documents_a_lire():
        f = x["chemin"]
        with open(f, "rb") as h: debut = h.read(65536)
        ajouter("a_lire", str(f), f.name, debut, auteur=x["auteur"] or None, projet=None, branche=None, chemin=f"a-lire/{f.name}",
                taille=f.stat().st_size, date=x["date"], lu=x["cle"] in vus, lire=lambda f=f: f.read_bytes())
        out[-1]["titre"] = x["titre"]
    for p, e in EQUIPES.items():
        depot = Path(os.path.expanduser(e["depot"])) if e.get("depot") else None
        if not depot or not (depot / ".git").exists(): continue
        git = lambda *x, entree=None, depot=depot: subprocess.run(["git", "-C", str(depot), *x], capture_output=True, input=entree, timeout=20)
        principale = e.get("principale", "main"); dossiers = e.get("livrables", ["docs/plans", "docs/apercu"])
        base = f"origin/{principale}" if git("rev-parse", "--verify", "--quiet", f"origin/{principale}").returncode == 0 else principale
        branches = {}
        for a in agents():
            c = conf(a)
            if c.get("projet") == p and c.get("branche"): branches.setdefault(c["branche"], a)
        dem = BERGER / "equipes" / p / "demandes"
        for f in (sorted(dem.glob("*.json")) if dem.is_dir() else []):
            try: d = json.loads(f.read_text())
            except (OSError, ValueError): continue
            if d.get("branche") and d.get("etat") != "fusionnée": branches.setdefault(d["branche"], d.get("agent"))
        for b, auteur in sorted(branches.items()):
            if not BRANCHE_SURE.fullmatch(b) or ".." in b: continue
            ref = f"origin/{b}"
            if git("rev-parse", "--verify", "--quiet", ref).returncode: continue
            quand = int(git("log", "-1", "--format=%ct", ref).stdout.strip() or 0)
            noms = [n for n in git("diff", "--name-only", "--diff-filter=AM", "-z", f"{base}...{ref}", "--", *dossiers).stdout.decode().split("\0") if n]
            if not noms: continue
            arbre = [l.split(b"\t", 1) for l in git("ls-tree", "-l", "-z", ref, "--", *noms).stdout.split(b"\0") if b"\t" in l]
            for meta, nom in arbre:
                mode, type_, sha, taille = meta.split()
                nom = nom.decode(); sha = sha.decode()
                if type_ != b"blob" or mode == b"120000" or any(x.startswith(".") for x in nom.split("/")): continue   # lien, caché : ignorés
                ajouter("branche", f"{p}\0{b}\0{nom}", nom, git("cat-file", "blob", sha).stdout[:65536], auteur=auteur, projet=p, branche=b,
                        chemin=nom, taille=int(taille), date=quand, lu=None, lire=lambda sha=sha, git=git: git("cat-file", "blob", sha).stdout)
    return sorted(out, key=lambda x: x["date"], reverse=True)[:DOCUMENTS_MAX]


def livrables():
    """Les livrables (spec §6.1) : un FILTRE de documents() — specs, maquettes, rapports (md, html, pdf) des dossiers de
    travail, des À lire et des branches en cours."""
    return [x for x in documents() if x["origine"] in LIVRABLES_ORIGINES and x["genre"] in LIVRABLES_GENRES][:LIVRABLES_MAX]


def rendre_markdown(texte, w=100):
    """Mise en forme simple pour le terminal : titres, gras, code, listes, citations, tableaux laissés alignés."""
    out = []; bloc = False
    for l in texte.splitlines():
        if l.startswith("```"): bloc = not bloc; out.append(PALE + "─" * min(w, 60) + R); continue
        if bloc: out.append(CYAN + l + R); continue
        m = re.match(r"^(#{1,6})\s+(.*)", l)
        if m:
            niveau, t = len(m.group(1)), m.group(2)
            out += ([""] if out else []) + [GRAS + (INV + " " + t + " " + R if niveau == 1 else (BLEU if niveau == 2 else CYAN) + t + R)]
            if niveau == 2: out.append(BLEU + PALE + "─" * min(w, max(len(t), 12)) + R)
            continue
        l = re.sub(r"\*\*(.+?)\*\*", GRAS + r"\1" + R, l)
        l = re.sub(r"`([^`]+)`", CYAN + r"\1" + R, l)
        l = re.sub(r"^(\s*)[-*] ", r"\1• ", l)
        if l.startswith(">"): l = JAUNE + "▌" + R + l[1:]
        out.append(l)
    return out


def carte_colonne(titre, lignes, larg, vif=False):
    """Une carte comme sur le Tableau du 113 : ╭─ titre ─╮, corps │ … │ coupé à la largeur, ╰─╯ ; cadre en gras si vif."""
    g = GRAS if vif else ""; dedans = larg - 4
    haut = couper(f"╭─ {titre} ", larg - 1); haut = g + haut + g + "─" * max(0, larg - 1 - vlen(haut)) + "╮" + R
    corps = []
    for l in lignes:                                                       # texte simple : 2 lignes au plus, comme sur le 113
        if ANSI.search(l): corps.append(l); continue
        pli = textwrap.wrap(l, dedans, break_on_hyphens=False) or [""]
        corps += pli[:1] + ([pli[1] + (" " + " ".join(pli[2:]) if len(pli) > 2 else "")] if len(pli) > 1 else [])
    return [haut] + [g + "│" + R + " " + pad(l, dedans) + " " + g + "│" + R for l in corps] + [g + "╰" + "─" * (larg - 2) + "╯" + R]


TONS = {"rouge": ROUGE, "jaune": JAUNE, "vert": VERT, "bleu": BLEU, "cyan": CYAN, "pale": PALE}   # tons des données → couleurs du terminal


def seg(texte, ton=None):
    """Un morceau de ligne dans les données : son texte et son ton (couleur sémantique ; None = texte normal)."""
    return {"texte": texte, "ton": ton}


def ligne_texte(l):
    """Une ligne de données (liste de morceaux) → texte de panneau : la couleur du ton autour de chaque morceau coloré."""
    return "".join((TONS[s["ton"]] + s["texte"] + R) if s["ton"] else s["texte"] for s in l)


def cartes_donnees():
    """Les cartes du Tableau : {colonne, titre, lignes, vif}, chaque ligne une liste de morceaux (seg). Sources = celles de
    l'Accueil, rien de plus : statut Herdr de chaque agent, sa checklist, sa dernière action, les validations, les documents
    à lire, les demandes de fusion."""
    out = []; jour = datetime.datetime.now() - datetime.timedelta(hours=24)
    carte = lambda col, titre, lignes, vif=False: out.append({"colonne": col, "titre": titre, "lignes": lignes, "vif": vif})
    for a in agents():
        c = conf(a); ck = checklist(a); dern = derniere_action(a)
        st = {statut_herdr(p) for p in herdr_ids(a).get("agents", {}).values()}
        titre = f"{c['icone']} {c['nom']}" if not c.get("sujet") else f"🔧 {c['sujet']}"
        corps = []
        if ck and not ck["fini"]:
            corps += [[seg(plat(ck["titre"]))], [seg(f"{ck['faites']}/{ck['total']}", "bleu"), seg(f" · {plat(ck['en_cours']) or '—'}")]]
        if "blocked" in st:
            col, ligne = "proprio", [seg("▲ attend une réponse dans son terminal", "jaune")]
        elif ck and ck["bloque"] and not ck["fini"]:
            col, ligne = "proprio", [seg("⚠ bloqué :", "jaune"), seg(f" {plat(ck['bloque'])}")]
        elif "working" in st:
            col, ligne = "cours", [seg("● au travail", "vert")]
        elif not st or st <= {"unknown", "?"}:
            col, ligne = "repos", [seg("○ pas d'agent ouvert", "pale")]
        else:
            col, ligne = "repos", [seg("· au repos" + (f" · en pause {ck['faites']}/{ck['total']}" if ck and not ck["fini"] else ""), "pale")]
        corps.append(ligne)
        if dern: corps.append([seg(f"↳ {plat(dern)}", "pale")])
        carte(col, titre, corps, col == "cours")
        if ck and ck["fini"] and (dossier(a) / "CHECKLIST.md").stat().st_mtime > jour.timestamp():
            carte("livre", titre, [[seg(plat(ck["titre"]))], [seg(f"✔ {ck['faites']}/{ck['total']}", "vert")]])
    nom_de = lambda x: conf(x)["nom"] if x in agents() else x
    attente = en_attente(); en_validation = {str((d.get("args") or [""])[0]) for d in attente if d.get("verbe") == "fusionner"}
    for d in attente:
        nom = nom_de(d["agent"])
        if d.get("valideur"):
            carte("agent", f"validation n° {d['n']}", [[seg(f"{nom} : {d['apercu']}")], [seg(f"▲ attend {nom_de(d['valideur'])}", "jaune")]])
        else:
            carte("proprio", f"validation n° {d['n']}", [[seg(f"{nom} : {d['apercu']}")], [seg(f"berger valider {d['n']} / refuser {d['n']}", "pale")]], True)
    vus = lus(); a_lire = [x for x in documents_a_lire() if x["cle"] not in vus]
    if a_lire:
        carte("proprio", f"📖 à lire ({len(a_lire)})", [[seg(x["titre"])] for x in a_lire[:3]] + [[seg("→ onglet À lire", "pale")]])
    for p_ in EQUIPES:
        for f in sorted((BERGER / "equipes" / p_ / "demandes").glob("*.json")):
            d = json_ou_rien(f); e = (d or {}).get("etat") or "?"
            if not d or d.get("sujet") in en_validation: continue           # illisible, ou déjà dans une carte « validation »
            if e == "fusionnée":
                if f.stat().st_mtime > jour.timestamp(): carte("livre", f"fusion {p_}", [[seg(d.get("sujet", "?"))], [seg("✔ fusionnée", "vert")]])
            else:
                qui_ = EQUIPES[p_].get("chef_projet") if e in ("à relire", "en attente") else d.get("agent")
                carte("agent", f"fusion {p_}", [[seg(d.get("sujet", "?"))], [seg(f"▲ {e}", "jaune")] + ([seg(f" · {nom_de(qui_)}")] if qui_ else [])])
    return out


COLONNES_TONS = (("cours", "EN COURS", "vert"), ("proprio", "ATTEND " + str(CONFIG.get("proprietaire", "le propriétaire")).upper(), "jaune"),
                 ("agent", "ATTEND UN AGENT", "jaune"), ("repos", "AU REPOS", "pale"), ("livre", "LIVRÉ · 24 h", "bleu"))


# ─── Sources et Synthèse : le résultat d'un outil du courtier, relu sans jamais toucher un secret ───
# Un panneau de source se déclare dans config.toml ([panneaux.<nom>] : outil, verbe, args, cadence, rouge, jaune). C'est le
# COURTIER qui lance le verbe de lecture à la cadence dite et range le résultat, filtré comme toute réponse, dans
# courtier/panneaux/<nom>.json ; le panneau ne fait que relire ce fichier.
PANNEAUX_SOURCES = {n: p for n, p in CONFIG.get("panneaux", {}).items() if isinstance(p, dict)}


SYNTHESE_VU = BERGER / ".synthese-vu.json"


def propre(t):
    """Une ligne venue d'un outil : couleurs gardées, tout autre code de terminal retiré (un outil ne pilote pas l'écran)."""
    t = re.sub(r"\033(?!\[[0-9;]*m)", "", str(t).replace("\t", "  "))           # ESC hors couleur : neutralisé
    return "".join(c for c in t if c == "\033" or (c >= " " and c != "\x7f" and not "\x80" <= c <= "\x9f"))


def gravite(ligne, p):
    """« rouge », « jaune » ou None : ✗/❌ et les motifs `rouge` de la déclaration ; ⚠ et les motifs `jaune`. Une ligne qui
    répond à un motif `ignorer` n'a pas de couleur : un fait CONNU et voulu (ex. option FortiGuard non souscrite)."""
    t = ANSI.sub("", ligne)
    if any(re.search(m, t) for m in p.get("ignorer", [])): return None
    if "✗" in t or "❌" in t or any(re.search(m, t) for m in p.get("rouge", [])): return "rouge"
    if "⚠" in t or any(re.search(m, t) for m in p.get("jaune", [])): return "jaune"
    return None


def etat_source(nom, p):
    """(état, résultat) : « attente » (jamais collecté), « echec », « fige » (plus de 3 cadences sans collecte), « ok ».
    Une déclaration fautive (cadence, motif) est un échec NOMMÉ, pas un panneau cassé."""
    try:
        cadence = max(60, int(p.get("cadence", 300)))
        for m in p.get("rouge", []) + p.get("jaune", []) + p.get("ignorer", []): re.compile(m)
    except (TypeError, ValueError, re.error) as e: return "echec", {"erreur": f"déclaration [panneaux.{nom}] fautive : {e}"}
    r = json_ou_rien(RESULTATS / f"{nom}.json")
    if r is None: return "attente", {}
    try: age = time.time() - datetime.datetime.fromisoformat(r["quand"]).timestamp()
    except (KeyError, TypeError, ValueError): return "echec", {**r, "erreur": r.get("erreur") or "résultat illisible"}
    if not r.get("ok"): return "echec", r
    return ("fige" if age > 3 * cadence + 60 else "ok"), r


def alertes_synthese():
    """Tout ce qui est ROUGE ou JAUNE, rien d'autre : (couleur, domaine, texte). Berger lui-même (courtier, audit,
    sauvegarde, auto-test, validations, agents bloqués), puis chaque source déclarée."""
    al = []
    if not courtier_actif(): al.append(("rouge", "courtier", "courtier ARRÊTÉ : aucun outil ni aucune source ne répond"))
    audit = lire(BERGER / "courtier/dernier-audit.txt").strip(); fa = BERGER / "courtier/dernier-audit.txt"
    if audit and "aucune fuite" not in audit: al.append(("rouge", "secrets", f"audit des secrets : {audit}"))
    elif not audit or time.time() - fa.stat().st_mtime > 2 * 86400: al.append(("jaune", "secrets", "audit des secrets pas lancé depuis plus de 2 jours"))
    fs = BERGER / "courtier/derniere-sauvegarde.txt"
    if CONFIG.get("sauvegarde") and (not fs.exists() or time.time() - fs.stat().st_mtime > 2 * 86400):
        al.append(("jaune", "sauvegarde", "sauvegarde de Berger : aucune depuis plus de 2 jours"))
    al += alertes_auto_test()
    al += alertes_consignes()
    for source in SOURCES_ALERTES.values(): al += source()   # alertes branchées par un paquet chargé (moteurs/ : alertes_moteurs)
    for d in en_attente():
        qui = d.get("valideur") or PROPRIETAIRE
        al.append(("jaune", "validation", f"n° {d['n']} attend {qui} : {conf(d['agent'])['nom'] if d.get('agent') in agents() else d.get('agent')} — {d.get('apercu', '')}"))
    for a in agents():
        ck = checklist(a) or {}
        if ck.get("bloque"): al.append(("jaune", conf(a)["nom"], f"bloqué : {plat(ck['bloque'])}"))
    for a, b in boucles_actives().items():
        al.append(("jaune", conf(a)["nom"], f"boucle : « {b['appel']} » refait {b['n']} fois en une heure sans rien recevoir "
                                            f"(depuis {datetime.datetime.fromtimestamp(b['depuis']):%H:%M}) — refusé par le courtier"))
    for nom, p in PANNEAUX_SOURCES.items():
        etat_, r = etat_source(nom, p); titre = p.get("titre", nom)
        if etat_ == "echec": al.append(("rouge", titre, f"○ collecte en échec — {r.get('erreur') or 'code ' + str(r.get('code'))}"))
        elif etat_ == "fige": al.append(("jaune", titre, f"○ figé : dernière collecte à {str(r.get('quand', ''))[11:16]}"))
        elif etat_ == "attente": al.append(("jaune", titre, "○ pas encore collecté"))
        for l in r.get("lignes", []) if etat_ != "echec" else []:
            g = gravite(propre(l), p)
            if g: al.append((g, titre, ANSI.sub("", propre(l)).strip()))
    return al


def depuis(al):
    """Première apparition de chaque alerte (mémo .synthese-vu.json ; une alerte disparue est oubliée). Les chiffres sont
    ignorés dans la clé : « (30 h) » qui devient « (31 h) » reste la même alerte."""
    vu = json_ou_rien(SYNTHESE_VU) or {}; maintenant = datetime.datetime.now().isoformat(timespec="minutes")
    cles = [f"{g}|{dom}|{re.sub(r'[0-9]+', '#', t)}" for g, dom, t in al]
    neuf = {k: vu.get(k, maintenant) for k in cles}
    if neuf != vu:
        try: tmp = SYNTHESE_VU.with_suffix(".tmp"); tmp.write_text(json.dumps(neuf)); tmp.replace(SYNTHESE_VU)
        except OSError: pass
    return [neuf[k] for k in cles]


# ─── Décisions et Checklists ───
def question_en_attente(a, maxi_h=48):
    """(question, quand) quand le dernier message de l'agent Claude, postérieur au dernier message humain, pose une
    question (« ? » hors code et adresse) ; None sinon, ou au-delà de 48 h (abandonnée). Lit la fin de sa conversation."""
    if "claude" not in [m.strip() for m in conf(a).get("panneaux", "").split(",")] + [conf(a).get("moteur")]: return None
    cid = conversation_claude(a)
    f = HOME / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(travail(a))) / f"{cid}.jsonl"
    if not cid or not f.is_file(): return None
    try:
        with open(f, "rb") as h:
            h.seek(max(0, f.stat().st_size - 400_000)); fin = h.read().decode("utf-8", "replace").splitlines()
    except OSError: return None
    for ligne in reversed(fin):
        try: e = json.loads(ligne)
        except ValueError: continue
        c = (e.get("message") or {}).get("content")
        if e.get("type") == "user" and not e.get("isMeta"):
            if isinstance(c, str) or (isinstance(c, list) and any(x.get("type") == "text" for x in c if isinstance(x, dict))
                                      and not any(x.get("type") == "tool_result" for x in c if isinstance(x, dict))):
                return None                                                  # un humain a parlé en dernier
        if e.get("type") == "assistant" and isinstance(c, list):
            texte = "\n".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text").strip()
            if not texte: continue
            try: quand = datetime.datetime.fromisoformat(str(e.get("timestamp", "")).replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
            except ValueError: quand = datetime.datetime.now()
            if datetime.datetime.now() - quand > datetime.timedelta(hours=maxi_h): return None
            nu = re.sub(r"`[^`]*`", "", re.sub(r"```.*?```", "", texte, flags=re.S))
            nu = re.sub(r"https?://\S+", "", nu)
            q = [l.strip() for l in nu.splitlines() if "?" in l]
            return (plat(q[-1]).lstrip("#>*- ").strip(), quand) if q else None
    return None


DECISION_ATTENDUE = re.compile(r"^\s*Décision attendue\s*:\s*(.+)$", re.M | re.I)   # en tête d'un document À lire (15 lignes)


def decision_document_resolue(texte):
    """État explicite ou lien stable vers l'objet décidé ; jamais une déduction à partir d'un rapport plus récent.
    Lecture seule, sans modifier une validation ni les règles qui l'exécutent. Un lien absent/inconnu reste ouvert."""
    if re.search(r"^Décision résolue\s*:\s*\S", texte, re.M | re.I): return True
    m = re.search(r"^Décision liée\s*:\s*validation:([0-9]+)\s*$", texte, re.M | re.I)
    if m:
        d = json_ou_rien(BERGER / "courtier/validations" / f"{m[1]}.fait.json")
        return bool(d and d.get("etat") in ("validé et exécuté", "refusé"))
    m = re.search(r"^Décision liée\s*:\s*fusion:([\w-]+)/([\w-]+)\s*$", texte, re.M | re.I)
    if m and m[1] in EQUIPES:
        d = json_ou_rien(BERGER / "equipes" / m[1] / "demandes" / f"{m[2]}.json")
        return bool(d and d.get("etat") == "fusionnée")
    return False


def propositions_decidables(a):
    """Propositions utilisateur seulement : les artefacts techniques sans type et les sondes ne sont pas des attentes."""
    for p in pendants(a):
        nom = re.sub(r"^\d{4}-\d\d-\d\d_", "", p)
        if re.match(r"(?:piege|sonde|test)(?:[-_.]|$)", nom, re.I): continue
        t = lire(dossier(a) / "pending" / p)
        entete = t.split("\n---", 1)[0]
        if not re.search(r"^type:\s*(memoire|skill)\s*(?:#.*)?$", entete, re.M): continue
        if re.search(r"^(?:test|sonde):\s*(?:oui|true)\s*$", entete, re.M | re.I): continue
        yield p


def decisions():
    """Ce qui attend un geste (spec interface §6.3) : {pour (« toi » | « agent »), genre, titre, detail, quand, agent, n,
    projet, sujet, document, commande, lien}. Genres : validation (courtier), terminal (agent arrêté sur une permission),
    bloque / go / question (marquages de la checklist), question (fin de conversation, Claude : repli), a_lire (documents non
    lus), a_decider (document À lire qui porte « Décision attendue : »), fusion (demande sans agent qui en réponde),
    besoin (besoin Berger ouvert, adressé au gardien : berger-outil besoin)."""
    nom_de = lambda x: conf(x)["nom"] if x in agents() else x; out = []
    def item(pour, genre, titre, detail, quand="", **plus):
        out.append({"pour": pour, "genre": genre, "titre": titre, "detail": detail, "quand": quand, "agent": None, "n": None,
                    "projet": None, "sujet": None, "document": None, "commande": None, "lien": None, **plus})
    for d in en_attente():
        quand = str(d.get("demande", ""))[:16].replace("T", " "); n = validation_donnees(d)["n"]
        lien = {"vue": "validation", "a": str(n)} if n is not None else None
        if d.get("valideur"): item("agent", "validation", f"validation n° {d['n']} · attend {nom_de(d['valideur'])}", f"{nom_de(d['agent'])} : {d['apercu']}",
                                   quand, agent=d.get("agent"), n=n, lien=lien)
        else: item("toi", "validation", f"validation n° {d['n']} · {nom_de(d['agent'])}", f"{d['apercu']}  →  berger valider {d['n']} / refuser {d['n']}",
                   quand, agent=d.get("agent"), n=n, commande=f"berger valider {d['n']} / berger refuser {d['n']}", lien=lien)
    for a in agents():
        c = conf(a); qui = f"{c['icone']} {c['nom']}"
        for p in propositions_decidables(a):
            lib = re.sub(r"^\d{4}-\d\d-\d\d_", "", p[:-3]).replace("_", " ").replace("-", " ")
            item("toi", "proposition", f"{qui} · proposition", lib, agent=a)
        for signal in signale_aujourdhui(a): item("toi", "signalement", f"{qui} · signalement", plat(signal), agent=a)
        if "blocked" in {statut_herdr(p) for p in herdr_ids(a).get("agents", {}).values()}:
            item("toi", "terminal", qui, "attend une réponse dans son terminal (permission ou choix)", agent=a)
            continue
        ck = checklist(a) or {}
        if ck.get("bloque") and not ck.get("fini"):
            if ck.get("go"): item("toi", "go", qui, f"go attendu : {plat(ck['bloque'])}", agent=a)
            else: item("toi", "bloque", qui, f"bloqué : {plat(ck['bloque'])}", agent=a)
        if ck.get("question") and not ck.get("fini"): item("toi", "question", qui, f"« {plat(ck['question'])} »", agent=a)
        else:
            q = question_en_attente(a)
            if q: item("toi", "question", qui, f"« {q[0]} »", f"{q[1]:%d/%m %H:%M}", agent=a)
    for b in besoins():                                                   # besoin Berger ouvert : adressé au gardien, montré au propriétaire
        item("toi", "besoin", f"besoin n° {b['n']} · {nom_de(b['de'])} → {nom_de(b.get('a') or gardien() or '?')}", f"{b['genre']} — {b['texte']}",
             str(b.get("quand", ""))[:16].replace("T", " "), agent=b["de"], n=b["n"],
             commande=f"berger besoin clore {b['n']} fait|refuse|transmis \"<suite>\"")
    vus = lus(); docs = documents_a_lire(); a_lire = [x for x in docs if x["cle"] not in vus]
    for x in a_lire:
        item("toi", "a_lire", "📖 1 document à lire", x["titre"] + "  →  onglet À lire", agent=x["auteur"] or None,
             document=id_document(x), lien={"vue": "document", "a": id_document(x)})
    for x in docs:
        if x["regle"]: continue                                             # l'objet lié est réglé : plus rien à décider
        texte = "\n".join(lire(x["chemin"]).splitlines()[:15]); m = DECISION_ATTENDUE.search(texte)
        if m and not decision_document_resolue(texte): item("toi", "a_decider", f"📝 {nom_de(x['auteur']) if x['auteur'] else 'commun'} · décision attendue", f"{plat(m.group(1))} — {x['titre']}",
                   f"{datetime.datetime.fromtimestamp(x['date']):%d/%m %H:%M}", agent=x["auteur"] or None, document=id_document(x),
                   lien={"vue": "document", "a": id_document(x)})
    en_validation = {str((d.get("args") or [""])[0]) for d in en_attente() if d.get("verbe") == "fusionner"}
    for p_ in EQUIPES:
        for f in sorted((BERGER / "equipes" / p_ / "demandes").glob("*.json")):
            d = json_ou_rien(f); e = (d or {}).get("etat")
            if not d or e in (None, "fusionnée") or d.get("sujet") in en_validation: continue
            qui_ = EQUIPES[p_].get("chef_projet") if e in ("à relire", "en attente") else d.get("agent")
            item("agent" if qui_ else "toi", "fusion", f"fusion {p_} · {e}" + (f" · attend {nom_de(qui_)}" if qui_ else ""), d.get("sujet", "?"),
                 f"{datetime.datetime.fromtimestamp(f.stat().st_mtime):%d/%m %H:%M}", agent=qui_ or None, projet=p_, sujet=d.get("sujet"),
                 lien={"vue": "demande", "a": f"{p_},{d.get('sujet')}"} if d.get("sujet") else None)
    return out


def dossier_checklists():
    v = CONFIG.get("checklists"); v = v.get("dossier") if isinstance(v, dict) else v
    return Path(os.path.expanduser(v)) if v else BERGER / "checklists"


def agent_court(a):
    """Un agent dans les données (Agent) : identifiant, nom, icône ; un nom qui n'est pas un agent reste tel quel."""
    if a not in agents(): return {"id": str(a), "nom": str(a), "icone": ""}
    c = conf(a); return {"id": a, "nom": c["nom"], "icone": c["icone"]}


def statuts_donnees(a):
    return [{"moteur": m, "etat": e, "libelle": STATUTS.get(e, ("?",))[0]} for m, e in ((m, statut_herdr(p)) for m, p in herdr_ids(a).get("agents", {}).items())]


def checklist_donnees(ck):
    if not ck: return None
    return {**{k: ck[k] for k in ("titre", "faites", "total", "en_cours", "bloque", "fini", "go", "question")},
            "etapes": [{"fait": fait, "libelle": lib} for fait, lib in ck["etapes"]]}


def quand_iso(ts): return datetime.datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def id_document(doc):
    """Identifiant opaque d'un document à lire : empreinte de sa clé de lecture (jamais son chemin)."""
    import hashlib
    return hashlib.sha256(doc["cle"].encode()).hexdigest()[:16]


def masques(a):
    """Branchée par bin/berger au démarrage (le calcul du mur reste au cœur jusqu'au lot 4, cas 1)."""
    raise RuntimeError("masques non branchée : bin/berger la pose dans noyau.lectures au démarrage")


def cloisons(a):
    """Branchée par bin/berger au démarrage (le calcul du mur reste au cœur jusqu'au lot 4, cas 1)."""
    raise RuntimeError("cloisons non branchée : bin/berger la pose dans noyau.lectures au démarrage")


__all__ = ('SOURCES_ALERTES', 'masques', 'cloisons', 'AUTO_TEST_NUIT', 'BESOINS', 'BRANCHE_SURE', 'COLONNES_TONS', 'CONSIGNES', 'CONSO', 'DECISION_ATTENDUE', 'DOCUMENTS_MAX', 'EQUIPES', 'EXTENSIONS', 'GARDE_CONSO', 'LECTEURS_CONSO', 'LECTURES', 'LIE_A', 'LIVRABLES_GENRES', 'LIVRABLES_MAX', 'LIVRABLES_ORIGINES', 'MISSIONS', 'PANNEAUX_SOURCES', 'RUBRIQUES_FICHE', 'SIGNATURES', 'SKILLS_PRODUIT', 'SOLLICITATIONS', 'SYNTHESE_VU', 'TONS', 'activite_donnees', 'activite_texte', 'agent_court', 'agent_du_dossier', 'alertes_auto_test', 'alertes_consignes', 'alertes_synthese', 'approbations_hooks', 'besoins', 'boucles_actives', 'capacites_donnees', 'capacites_texte', 'carte_colonne', 'cartes_donnees', 'checklist_donnees', 'collecter_conso', 'conversation_claude', 'courtier_actif', 'decision_document_resolue', 'decisions', 'depuis', 'derniere_action', 'derniere_sollicitation', 'derniers_usages', 'developpeur', 'documents', 'documents_a_lire', 'dossier_checklists', 'dossier_skills', 'droits_agents', 'ecritures_outil', 'en_attente', 'etat_source', 'gardien', 'genre_document', 'gravite', 'hote_mission', 'id_document', 'identite_donnees', 'identite_texte', 'json_ou_rien', 'kilo', 'lien_regle', 'ligne_texte', 'lignes_neuves', 'limites_donnees', 'limites_texte', 'livrables', 'lus', 'memoire_donnees', 'memoire_texte', 'methode', 'propositions_decidables', 'propre', 'quand_iso', 'quand_remise', 'question_en_attente', 'quota_moteurs', 'reglage_tache', 'reglages_mission', 'rendre_markdown', 'seg', 'skills_demandees', 'statuts_donnees', 'tableau_donnees', 'titre_document', 'validation_donnees', 'veille_donnees', 'veille_texte', 'verbes_outil',)
