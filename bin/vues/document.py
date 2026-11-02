# Vue d'objet « Document à lire » de Berger (spec interface §6) : berger vue document <id>. Jamais un onglet : l'interface
# l'ouvre depuis À lire ou une décision. L'id est celui de la vue alire (empreinte de la clé de lecture, jamais un chemin) ;
# lire ici NE marque PAS le document lu (c'est une action, lot 2). Texte limité à 200 Ko.
TITRE = "Document à lire"
ICONE = None
ONGLET = "objet"     # "objet" : vue d'un objet (n° d'écriture, demande, document), ouverte par un lien, sans onglet
ORDRE = 32
TEXTE_MAX = 200_000


def donnees(a=None):
    if not re.fullmatch(r"[0-9a-f]{16}", str(a or "")): raise ValueError(f"document inconnu : {a} (berger vue document <id>, id de la vue alire)")
    x = next((x for x in documents_a_lire() if id_document(x) == a), None)
    if x is None: raise ValueError(f"document inconnu : {a}")
    t = lire(x["chemin"])
    return {"id": a, "titre": x["titre"], "auteur": agent_court(x["auteur"]) if x["auteur"] else None, "date": quand_iso(x["date"]),
            "lu": x["cle"] in lus(), "texte": t[:TEXTE_MAX], "tronque": len(t) > TEXTE_MAX}


def rendu_texte(d, w, h):
    qui = f"{d['auteur']['icone']} {d['auteur']['nom']}" if d["auteur"] else "📌 commun"
    out = [INV + GRAS + pad(f" 📖 {d['titre']}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R,
           PALE + f"  {qui} · {datetime.datetime.fromisoformat(d['date']):%d/%m %H:%M} · " + ("lu" if d["lu"] else "non lu") + R, ""]
    out += rendre_markdown(d["texte"], w)
    if d["tronque"]: out += ["", JAUNE + f"  … document coupé à {TEXTE_MAX // 1000} Ko" + R]
    return out


def rendre(w, h, a=None):
    return rendu_texte(donnees(a), w, h)
