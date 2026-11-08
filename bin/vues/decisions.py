# Vue « Décisions » de Berger : berger panneau decisions. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → decisions.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Décisions"
ONGLET = None        # SANS onglet (interface web v2, 03/11/2026 : retiré du web et de Herdr, l'Accueil montre ce qui t'attend) ; `berger vue decisions` reste
ORDRE = 1


def donnees(a=None):
    return {"decisions": decisions()}


def rendu_texte(d, w, h):
    """DÉCISIONS : ce qui attend TON geste en premier (écritures à valider avec leurs deux commandes, questions et go des agents qui te
    rendent compte), les propositions repliées, puis ce qui attend un agent. Phrases de patron : sans chemin ni jargon, une ligne par élément."""
    out = [INV + GRAS + pad(" 🔔 DÉCISIONS  ·  ce qui attend un geste", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R]
    par = lambda cle: [x for x in d["decisions"] if x["pour"] == cle]
    for cle, lib, coul in (("toi", "T'ATTEND", JAUNE), ("propositions", "PROPOSITIONS", PALE), ("agent", "ATTEND UN AGENT", CYAN)):
        mes = par(cle)
        if cle == "propositions":
            if mes: out += ["", couper(f"{PALE}▸ {lib} ({len(mes)}) · repliées : " + " · ".join(phrase_patron(x["detail"], 40) for x in mes) + R, w)]
            continue
        out += [""] + titre_section(f"{lib} ({len(mes)})", coul if mes else VERT, w)
        if not mes: out.append(f"  {VERT}✅ Rien à faire, tout avance{R}" if cle == "toi" else PALE + "  —" + R)
        for x in mes:
            if x["genre"] == "validation" and cle == "toi":
                out.append(couper(f"  {coul}▲{R} {GRAS}Écriture n° {x['n']}{R} · {phrase_patron(x['titre'].split(' · ', 1)[-1], 24)} : {phrase_patron(x['detail'].split('  →', 1)[0], max(20, w - 40))}"
                                  + (f"{PALE}  · {x['quand']}{R}" if x["quand"] else ""), w))
                out += [f"      {GRAS}berger valider {x['n']}{R}", f"      {GRAS}berger refuser {x['n']}{R}"]
                continue
            out.append(couper(f"  {coul}▲{R} {GRAS}{phrase_patron(x['titre'], 60)}{R} : {phrase_patron(x['detail'], max(20, w - 30))}"
                              + (f"{PALE}  · {x['quand']}{R}" if x["quand"] else ""), w))
    return out


def vue_decisions(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_decisions(w, h)
