# Vue « Décisions » de Berger : berger panneau decisions. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → decisions.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Décisions"
ICONE = '🔔'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 4


def donnees(a=None):
    return {"decisions": decisions()}


def rendu_texte(d, w, h):
    """DÉCISIONS (idée de l'etat-decisions du 113) : ce qui attend TON geste en premier, puis ce qui attend un agent."""
    out = [INV + GRAS + pad(" 🔔 DÉCISIONS  ·  ce qui attend un geste", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R]
    for cle, lib, coul in (("toi", "T'ATTEND", JAUNE), ("agent", "ATTEND UN AGENT", CYAN)):
        mes = [x for x in d["decisions"] if x["pour"] == cle]
        out += [""] + titre_section(f"{lib} ({len(mes)})", coul if mes else VERT, w)
        if not mes: out.append(PALE + ("  ✓ rien n'attend ton geste" if cle == "toi" else "  —") + R)
        for x in mes:
            out.append(couper(f"  {coul}▲{R} {GRAS}{x['titre']}{R}" + (f"{PALE}  · {x['quand']}{R}" if x["quand"] else ""), w))
            out += plier(x["detail"], w - 2, "    ", "    ")
    return out


def vue_decisions(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_decisions(w, h)
