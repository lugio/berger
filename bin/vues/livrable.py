# Vue d'objet « Livrable » de Berger (spec interface §6.1 et §6.1 bis) : berger vue livrable <id>, id des vues livrables et
# documents (empreinte, jamais un chemin) — la SEULE ouverture des deux. Un .md donne son texte (200 Ko au plus) ; les autres
# genres n'en donnent pas : l'interface les ouvre par `berger livrable <id> --brut <genre>` (.html dans un cadre isolé, pdf
# dans un onglet, image affichée, le reste téléchargé).
TITRE = "Livrable"
ICONE = None
ONGLET = "objet"
ORDRE = 33
TEXTE_MAX = 200_000


def donnees(a=None):
    if not re.fullmatch(r"[0-9a-f]{16}", str(a or "")): raise ValueError(f"livrable inconnu : {a} (berger vue livrable <id>, id de la vue livrables)")
    x = next((x for x in documents() if x["id"] == a), None)
    if x is None: raise ValueError(f"livrable inconnu : {a}")
    t = x["lire"]().decode("utf-8", "replace") if x["genre"] == "md" else None
    return {"id": a, "titre": x["titre"], "auteur": agent_court(x["auteur"]) if x["auteur"] else None, "origine": x["origine"],
            "projet": x["projet"], "branche": x["branche"], "chemin": x["chemin"], "genre": x["genre"], "taille": x["taille"],
            "date": quand_iso(x["date"]), "texte": t[:TEXTE_MAX] if t is not None else None, "tronque": t is not None and len(t) > TEXTE_MAX}


def rendu_texte(d, w, h):
    qui = f"{d['auteur']['icone']} {d['auteur']['nom']}".strip() if d["auteur"] else "📌 commun"
    ou = (f"{d['projet']} · {d['branche']} · " if d["branche"] else "") + d["chemin"]
    out = [INV + GRAS + pad(f" 📐 {d['titre']}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R,
           PALE + f"  {qui} · {datetime.datetime.fromisoformat(d['date']):%d/%m %H:%M} · {ou} · {d['taille']} octets" + R, ""]
    if d["texte"] is not None:
        out += rendre_markdown(d["texte"], w)
        if d["tronque"]: out += ["", JAUNE + f"  … coupé à {TEXTE_MAX // 1000} Ko" + R]
    else: out.append(PALE + {"html": "  maquette HTML : ouvre-la dans l'interface web (cadre isolé)", "pdf": "  PDF : ouvre-le depuis l'interface web"}.get(
        d["genre"], "  image : affichée dans l'interface web" if d["genre"] in ("png", "jpeg", "gif", "webp") else "  fichier à télécharger depuis l'interface web") + R)
    return out


def rendre(w, h, a=None):
    return rendu_texte(donnees(a), w, h)
