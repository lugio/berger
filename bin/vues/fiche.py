# Vue « Fiche » de Berger : berger panneau fiche. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → fiche.schema.json (une fonction de données par rubrique
# du cœur, RUBRIQUES_FICHE) ; rendu_texte() ne lit que ces données.
TITRE = "Fiche"
ICONE = None
ONGLET = "agent"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 22


def donnees(a=None):
    return {"agent": agent_court(a), "statuts": statuts_donnees(a), **{cle: f(a) for cle, _, f, _ in RUBRIQUES_FICHE}}


def rendu_texte(d, w, h):
    """FICHE d'une seule page lisible (06/10/2026 : remplace la grille de 6 petites cases) — mêmes rubriques."""
    out = [entete(d["agent"], "fiche", w, statuts_texte(d["statuts"]))]
    for cle, libelle, _, texte in RUBRIQUES_FICHE:
        lignes = texte(d[cle], d["agent"]["id"], w)
        while lignes and not lignes[0].strip(): lignes.pop(0)
        out += [""] + titre_section(libelle.upper(), BLEU, w) + lignes
    return out


def vue_fiche_page(a, w, h):
    return rendu_texte(donnees(a), w, h)


def rendre(w, h, a=None):
    return vue_fiche_page(a, w, h)
