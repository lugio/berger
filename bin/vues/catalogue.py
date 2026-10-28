# Vue « Catalogue » de Berger : berger panneau catalogue. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → catalogue.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Catalogue"
ICONE = '📚'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 9


def donnees(a=None):
    """Tout ce qui existe (outils du courtier, modules, méthodes, garde-fous, réveils) et QUI y a droit, avec le dernier usage
    (jours écoulés depuis le dernier appel ACCEPTÉ). Aucune valeur secrète : des noms seulement."""
    droits = droits_agents(); usages = derniers_usages(); outils = CONFIG.get("outils", {}); maint = datetime.datetime.now()
    usage = lambda q: {"dernier_usage": q.isoformat(timespec="seconds") if q else None, "jours": (maint - q).days if q else None}
    out_outils = []
    for o in sorted(outils):
        lec, ecr = verbes_outil(o)
        out_outils.append({"nom": o, "type": str(outils[o].get("type", "?")), "lecture": lec, "ecriture": ecr,
                           "droits": [{"agent": agent_court(x), **usage(usages.get((x, o)))} for x, d in droits.items() if o in d]})
    catalogue = sorted(p.parent.name for p in dossier_skills().glob("*/SKILL.md")) if dossier_skills().is_dir() else []
    skill = lambda x: {"nom": x, "absente": not (methode(x) / "SKILL.md").is_file()}   # comme regenerer : produit, puis catalogue
    return {"outils": out_outils,
            "autres_droits": [{"droit": x, "agents": [agent_court(y) for y, d in droits.items() if x in d]}
                              for x in sorted({x for d in droits.values() for x in d if x not in outils})],
            "modules": [{"nom": m, "utilise": m in {r_.get("type") for r_ in outils.values()}}
                        for m in sorted(p.stem for p in (BERGER / "courtier/outils").glob("*.py") if not p.stem.startswith("_") and p.stem != "essai")],
            "skills": {"partagees": sorted(p.parent.name for p in (HOME / ".claude/skills").glob("*/SKILL.md")) if (HOME / ".claude/skills").is_dir() else [],
                       "dossier_catalogue": str(dossier_skills()), "catalogue": catalogue,
                       "par_agent": [{"agent": agent_court(x), "skills": [skill(s) for s in skills_demandees(x)]} for x in agents() if skills_demandees(x)],
                       "par_equipe": [{"projet": p_, "skills": [skill(s) for s in e_["skills"]]} for p_, e_ in EQUIPES.items() if e_.get("skills")],
                       "orphelines": [x for x in catalogue if not any(x in skills_demandees(y) for y in agents())
                                      and not any(x in e_.get("skills", []) for e_ in EQUIPES.values())],
                       "propres": [{"agent": agent_court(x), "skills": l} for x, l in
                                   [(x, sorted(p.parent.name for p in (AGENTS / x / "skills-agent").glob("*/SKILL.md"))) for x in agents()] if l]},
            "gardes": [{"moment": str(g.get("moment", "?")), "outils": str(g.get("outils", "tous")), "script": Path(g["commande"].split()[-1]).name} for g in GARDES],
            "reveils": [{"agent": agent_court(x), "heures": conf(x).get("heures", "—"),
                         "taches": len(list((AGENTS / x / "taches").glob("*.md"))) if (AGENTS / x / "taches").is_dir() else 0} for x in agents()]}


def rendu_texte(d, w, h):
    """CATALOGUE : tout ce qui existe et QUI y a droit, avec le dernier usage — pour retirer un droit qui ne sert pas.
    Lecture seule : les droits se changent dans agent.conf / config.toml."""
    out = [INV + GRAS + pad(" CATALOGUE  ·  ce qui existe et qui y a droit", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    nom = lambda ag: f"{ag['icone']} {ag['nom']}"
    def il_y_a_(j):
        if j is None: return PALE + "jamais" + R
        return "aujourd'hui" if j == 0 else "hier" if j == 1 else f"il y a {j} j" if j < 31 else JAUNE + f"il y a {j} j" + R
    out += titre_section("OUTILS DU COURTIER (les clés restent dans le courtier)", BLEU, w)
    for o in d["outils"]:
        out += plier(f"{GRAS}{o['nom']}{R}  {PALE}{o['type']}{R}  lecture : {', '.join(o['lecture']) or '—'}"
                     + (f"  {JAUNE}écriture (validée par toi) : {', '.join(o['ecriture'])}{R}" if o["ecriture"] else ""), w, "  ", "    ")
        if o["droits"]:
            for x in o["droits"]: out.append(f"      → {nom(x['agent'])}  {PALE}dernier usage{R} {il_y_a_(x['jours'])}")
        else: out.append(f"      → {JAUNE}personne{R}  {PALE}(attribué à aucun agent){R}")
    if not d["outils"]: out.append(PALE + "  aucun outil" + R)
    if d["autres_droits"]:
        out += ["", f"  {PALE}autres droits{R}"]
        for x in d["autres_droits"]: out.append(f"  {x['droit']}  → " + ", ".join(nom(y) for y in x["agents"]))
    out += ["", f"  {PALE}modules d'outils{R}  " + " · ".join((GRAS + m["nom"] + R) if m["utilise"] else m["nom"] for m in d["modules"])
            + f"   {PALE}(en gras : utilisés){R}", ""]
    out += titre_section("MÉTHODES (skills)", CYAN, w)
    s = d["skills"]
    out += plier(f"partagées (tous les agents) : {', '.join(s['partagees']) if s['partagees'] else PALE + 'aucune' + R}", w, "  ", "    ")
    liste = lambda l: ", ".join(x["nom"] if not x["absente"] else f"{ROUGE}{x['nom']} (absente){R}" for x in l)
    if s["catalogue"]:
        out += plier(f"catalogue des rôles ({s['dossier_catalogue']}) : {', '.join(s['catalogue'])}", w, "  ", "    ")
        for x in s["par_agent"]: out += plier(f"{nom(x['agent'])} : " + liste(x["skills"]), w, "    ", "      ")
        for x in s["par_equipe"]: out += plier(f"équipe {x['projet']} (chaque développeur) : " + liste(x["skills"]), w, "    ", "      ")
        if s["orphelines"]: out += plier(f"{JAUNE}données à personne{R} : {', '.join(s['orphelines'])}", w, "    ", "      ")
    for x in s["propres"]: out += plier(f"{nom(x['agent'])} : {', '.join(x['skills'])}", w, "  ", "    ")
    if not s["propres"]: out.append(f"  propres à un agent : {PALE}aucune{R}")
    out += [""] + titre_section("GARDE-FOUS (tous les agents)", ROUGE, w)
    for g in d["gardes"]: out.append(f"  {g['moment']:<6} {PALE}{g['outils']}{R}  {g['script']}")
    if not d["gardes"]: out.append(PALE + "  aucun" + R)
    out += [""] + titre_section("RÉVEILS ET TÂCHES", VERT, w)
    for x in d["reveils"]: out.append(f"  {nom(x['agent']):<16} heures : {x['heures']}  ·  tâches : {x['taches']}")
    if not d["reveils"]: out.append(PALE + "  aucun agent" + R)
    return out


def vue_catalogue(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_catalogue(w, h)
