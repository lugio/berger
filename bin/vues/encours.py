# Vue « En cours » de Berger : berger panneau encours. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → encours.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "En cours"
ICONE = None
ONGLET = "agent"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 23


def donnees(a=None):
    """Le travail en cours (checklist), les écritures qui attendent, la liste à faire et les lignes horodatées du jour."""
    d = dossier(a)
    jour = [{"heure": m.group(1), "texte": m.group(2)} for m in
            (re.match(r"^- (\d\d:\d\d) — (.*)$", l) for l in lire(d / "memory" / f"{aujourdhui()}.md").splitlines()) if m]
    return {"agent": agent_court(a), "checklist": checklist_donnees(checklist(a)), "validations": [validation_donnees(x) for x in en_attente(a)],
            "a_faire": [lib for fait, lib in cases(lire(d / "TODO.md")) if not fait], "aujourdhui": jour}


def rendu_texte(d, w, h):
    """À CÔTÉ DE LA CONVERSATION : le travail en cours (checklist), ce qui attend, la liste, et la journée."""
    out = [mini_entete(d["agent"], "en cours", w)]
    ck = d["checklist"]
    if ck and not ck["fini"]:
        out += [""] + titre_section(f"EN COURS  {plat(ck['titre'])[:w - 20]}  {ck['faites']}/{ck['total']}", BLEU, w)
        for e in ck["etapes"]:
            lib = e["libelle"]
            sym = f"{VERT}✔{R}" if e["fait"] else (f"{BLEU}⟳{R}" if lib == ck["en_cours"] or "← en cours" in lib else f"{PALE}·{R}")
            out += plier(plat(lib.replace("← en cours", "").strip()), w, f"  {sym} ", "    ")
        if ck["bloque"]: out += plier(plat(ck["bloque"]), w, f"  {JAUNE}{GRAS}⚠ bloqué :{R} ", "    ")
    else: out += ["", PALE + "  rien en cours" + R]
    att = d["validations"]
    if att:
        out += [""] + titre_section(f"ATTEND UNE VALIDATION ({len(att)})", JAUNE, w)
        for x in att: out += plier(f"n° {'?' if x['n'] is None else x['n']} : {x['apercu']}", w, "  ", "    ")
    todo = d["a_faire"]
    out += [""] + titre_section(f"À FAIRE ({len(todo)})", CYAN, w)
    for lib in todo[:6]: out += plier(plat(lib), w, "  · ", "    ")
    if not todo: out.append(PALE + "  rien" + R)
    if len(todo) > 6: out.append(PALE + f"  … et {len(todo) - 6} autres" + R)
    jour = []
    for l in d["aujourdhui"]: jour += plier(plat(l["texte"]), w, CYAN + l["heure"] + R + "  ", "       ")
    place = max(3, h - len(out) - 4)
    out += [""] + titre_section("AUJOURD'HUI", VERT, w)
    out += (([PALE + "  …" + R] + jour[-(place - 1):]) if len(jour) > place else jour) or [PALE + "  rien encore" + R]
    return out


def vue_encours(a, w, h):
    return rendu_texte(donnees(a), w, h)


def rendre(w, h, a=None):
    return vue_encours(a, w, h)
