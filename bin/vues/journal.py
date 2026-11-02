# Vue « Journal de l'agent » de Berger : berger panneau journal. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → journal.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Journal de l'agent"
ICONE = None
ONGLET = "agent"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 21


def donnees(a=None):
    """Le journal du jour (une ligne « HH:MM — texte » a son heure ; une autre ligne non vide, sans heure), les 4 derniers
    réveils du jour et les 3 dernières sorties de tâches."""
    d = dossier(a); lignes = []
    for ligne in lire(d / "memory" / f"{aujourdhui()}.md").splitlines():
        m = re.match(r"^- (\d\d:\d\d) — (.*)$", ligne)
        if m: lignes.append({"heure": m.group(1), "texte": m.group(2)})
        elif ligne.strip(): lignes.append({"heure": None, "texte": ligne.lstrip("- ")})
    hb = [x[2:] for x in lire(d / "heartbeat" / f"{aujourdhui()}.md").splitlines() if x.startswith("- ")][-4:]
    return {"agent": agent_court(a), "statuts": statuts_donnees(a), "jour": datetime.date.today().isoformat(), "lignes": lignes,
            "reveils": hb, "taches": [{"tache": s.parent.name, "sortie": s.stem} for s in sorted((d / "sorties").glob("*/*.md"))[-3:]]}


def rendu_texte(d, w, h):
    out = [entete(d["agent"], f"journal du {datetime.date.fromisoformat(d['jour']):%d/%m}", w, statuts_texte(d["statuts"])), ""]
    corps = []
    for l in d["lignes"]:
        if l["heure"]: corps += plier(plat(l["texte"]), w, CYAN + l["heure"] + R + "  ", "       ")
        else: corps += plier(plat(l["texte"]), w, "       ")
    bas = titre_section("♥ RÉVEILS", ROUGE, w)
    bas += [plier(plat(x), w, "  ")[0] for x in d["reveils"]] or [PALE + "  aucun aujourd'hui" + R]
    bas += [""] + titre_section("⏱ DERNIÈRES TÂCHES", BLEU, w)
    bas += [f"  {s['tache']}  {PALE}{s['sortie'].replace('_', ' ')}{R}" for s in d["taches"]] or [PALE + "  aucune" + R]
    place = max(3, h - len(out) - len(bas) - 2)
    if len(corps) > place: corps = [PALE + f"  … {len(corps) - place + 1} lignes plus haut" + R] + corps[-(place - 1):]
    return out + (corps or [PALE + "  journal vide" + R]) + [""] + bas


def vue_journal(a, w, h):
    return rendu_texte(donnees(a), w, h)


def rendre(w, h, a=None):
    return vue_journal(a, w, h)
