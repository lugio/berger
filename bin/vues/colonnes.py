# Vue « Tableau » de Berger : berger panneau colonnes. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → colonnes.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Tableau"
ICONE = '📋'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 1


def donnees(a=None):
    """Les colonnes (clé, libellé, ton) et les cartes de cartes_donnees() : chaque ligne d'une carte en morceaux (texte, ton)."""
    return {"colonnes": [{"cle": cle, "libelle": lib, "ton": ton} for cle, lib, ton in COLONNES_TONS], "cartes": cartes_donnees()}


def rendu_texte(d, w, h):
    """TABLEAU EN COLONNES, même présentation que le Tableau du 113 (Supervision › Tableau) : une carte par agent, validation,
    lecture ou demande de fusion, rangée par ce qu'elle attend. Colonnes côte à côte si chacune a 26 colonnes, sinon empilées."""
    out = [INV + GRAS + pad(" 📋 TABLEAU  ·  agents · validations · fusions", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    cartes = d["cartes"]; n = len(d["colonnes"])
    corps = lambda x: [ligne_texte(l) for l in x["lignes"]]
    larg = (w - (n - 1)) // n
    if larg >= 26:
        cols = []
        for c in d["colonnes"]:
            coul = TONS[c["ton"]]; mes = [x for x in cartes if x["colonne"] == c["cle"]]
            col = [coul + GRAS + couper(f"{c['libelle']} ({len(mes)})", larg) + R, coul + "━" * larg + R]
            cartes_rendues = [carte_colonne(x['titre'], corps(x), larg, x['vif']) for x in mes]
            if sum(map(len, cartes_rendues)) + 4 > h:
                col += [couper(x['titre'] + ' · ' + ' · '.join(corps(x)), larg) for x in mes]
            else:
                for carte in cartes_rendues: col += carte
            if not mes: col.append(PALE + "  —" + R)
            cols.append(col)
        for i in range(max(map(len, cols))):
            out.append(" ".join(pad(c[i] if i < len(c) else "", larg) for c in cols))
        return out
    # Étroit : les sections vides tiennent sur une ligne ; si les cartes dépassent l'écran,
    # une ligne par carte garde les livraisons visibles avant les détails.
    necessaire = len(out) + sum(1 if not any(x['colonne'] == c['cle'] for x in cartes) else
                              3 + sum(len(carte_colonne(x['titre'], corps(x), w, x['vif'])) for x in cartes if x['colonne'] == c['cle']) for c in d['colonnes'])
    compact = necessaire > h
    ordre = sorted(d['colonnes'], key=lambda c: c['cle'] != 'livre') if compact else d['colonnes']
    for numero, c in enumerate(ordre):
        mes = [x for x in cartes if x["colonne"] == c["cle"]]
        if not mes:
            out.append(couper(PALE + f"{c['libelle']} (0) · rien" + R, w))
            continue
        if compact:
            out.append(couper(TONS[c['ton']] + GRAS + f"{c['libelle']} ({len(mes)})" + R, w))
            budget = max(0, h - len(out) - (len(ordre) - numero - 1))
            visibles = min(len(mes), budget) if len(mes) <= budget else max(0, budget - 1)
            for x in mes[:visibles]:
                out.append(couper(f"  {x['titre']} · " + ' · '.join(corps(x)), w))
            if len(mes) > visibles and budget:
                out.append(couper(f"  … {len(mes) - visibles} autre{'s' if len(mes) - visibles > 1 else ''} carte{'s' if len(mes) - visibles > 1 else ''} · détail dans les espaces", w))
            continue
        out += titre_section(f"{c['libelle']} ({len(mes)})", TONS[c["ton"]], w)
        for x in mes: out += carte_colonne(x["titre"], corps(x), w, x["vif"])
        out.append("")
    return out


def vue_colonnes(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_colonnes(w, h)
