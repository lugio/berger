# Vue « Tableau de l'agent » de Berger : berger panneau tableau. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → tableau.schema.json (tableau_donnees du cœur) ;
# rendu_texte() ne lit que ces données (colonnes_tableau_texte).
TITRE = "Tableau de l'agent"
ICONE = None
ONGLET = "agent"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 20


def donnees(a=None):
    return tableau_donnees(a)


def rendu_texte(d, w, h):
    out = [entete(d["agent"], "tableau", w, statuts_texte(d["statuts"])), ""]
    if w >= 100:                                                           # 4 colonnes côte à côte
        cw = (w - 9) // 4; cols = colonnes_tableau_texte(d, cw)
        heads = [pad(col + GRAS + t + R, cw) for t, col, _ in cols]
        out.append(f" {PALE}│{R} ".join(heads))
        out.append(f" {PALE}│{R} ".join(pad(col + PALE + "─" * cw + R, cw) for _, col, _ in cols))
        n = max(len(l) for _, _, l in cols)
        for i in range(n):
            out.append(f" {PALE}│{R} ".join(pad(l[i] if i < len(l) else "", cw) for _, _, l in cols))
    else:                                                                  # étroit : sections empilées
        for t, col, l in colonnes_tableau_texte(d, w - 2):
            out += titre_section(t, col, w) + ["  " + x for x in l] + [""]
    return out


def vue_tableau(a, w, h):
    return rendu_texte(donnees(a), w, h)


def rendre(w, h, a=None):
    return vue_tableau(a, w, h)
