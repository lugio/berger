# Vue « Missions » de Berger : berger panneau missions. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → missions.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Missions"
ICONE = None
ONGLET = "agent"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 24


def donnees(hote=None):
    """Les missions hébergées dans l'onglet Missions de `hote` (son équipe s'il en est le chef de projet), et le compte de
    toutes les missions en cours dans Berger."""
    attente = en_attente(); missions = []
    for x in [x for x in agents() if hote_mission(x) == hote and (dossier(x) / "MISSION.md").is_file()]:
        c = conf(x); mm, modele = reglages_mission(x)
        f = BERGER / "equipes" / str(c.get("projet")) / "demandes" / f"{c.get('sujet')}.json"
        missions.append({"agent": agent_court(x), "moteur": mm, "modele": modele, "statuts": statuts_donnees(x),
                         "checklist": checklist_donnees(checklist(x)), "validations": sum(1 for d in attente if d.get("agent") == x),
                         "demande_fusion": str(json.loads(f.read_text()).get("etat")) if c.get("sujet") and f.is_file() else None})
    return {"hote": agent_court(hote), "projet": next((p for p, e in EQUIPES.items() if e.get("chef_projet") == hote), None),
            "en_cours": sum(1 for x in agents() if (dossier(x) / "MISSION.md").is_file()), "max": MISSIONS.get("max", 3), "missions": missions}


def rendu_texte(d, w, h):
    projet = d["projet"]; nom = d["hote"]["nom"]
    titre = f"ÉQUIPE {projet.upper()}  ·  chef de projet {nom}" if projet else f"MISSIONS de {nom}"
    out = [INV + GRAS + pad(f" {titre}  ·  {d['en_cours']}/{d['max']} missions en cours dans Berger", w) + R]
    if not d["missions"]: return out + ["", PALE + "  aucune mission en cours ici" + R]
    for x in d["missions"]:
        ag = x["agent"]; ck = x["checklist"]; modele = x["modele"]
        st = " ".join(STATUTS.get(s["etat"], ("?", PALE))[1] + STATUTS.get(s["etat"], ("?", PALE))[0] + R for s in x["statuts"])
        av = f"{ck['faites']}/{ck['total']}" if ck else "pas de checklist"
        ligne = f" {ag['icone']} {GRAS}{ag['nom']}{R}  {PALE}{x['moteur']}{' · ' + modele if modele else ''}{R}  {st}  {av}"
        if ck and ck.get("fini"): ligne += f"  {VERT}terminée — à clôturer{R}"
        elif ck and ck.get("en_cours"): ligne += f"  {PALE}›{R} {plat(ck['en_cours'])}"
        if ck and ck.get("bloque"): ligne += f"  {ROUGE}⚠ {plat(ck['bloque'])}{R}"
        if x["validations"]: ligne += f"  {JAUNE}{x['validations']} validation(s) en attente{R}"
        if x["demande_fusion"] is not None: ligne += f"  {CYAN}demande de fusion : {x['demande_fusion']}{R}"
        out.append(ligne)
    return out


def vue_missions(hote, w, h):
    return rendu_texte(donnees(hote), w, h)


def rendre(w, h, a=None):
    return vue_missions(a, w, h)
