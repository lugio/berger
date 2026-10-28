# Vue d'objet « Écriture en attente » de Berger (spec interface §6.4) : berger vue validation <n>. Jamais un onglet : l'interface
# l'ouvre depuis une décision. Données : courtier/validations/<n>.json (ou <n>.fait.json une fois décidée) — l'aperçu COMPLET,
# jamais les arguments bruts (ils viendront avec le filtre de secrets mis en commun, lot 2) ; rendu_texte() ne lit qu'elles.
TITRE = "Écriture en attente"
ICONE = None
ONGLET = "objet"     # "objet" : vue d'un objet (n° d'écriture, demande, document), ouverte par un lien, sans onglet
ORDRE = 30


def donnees(a=None):
    if not re.fullmatch(r"[0-9]{1,6}", str(a or "")): raise ValueError(f"écriture inconnue : {a} (berger vue validation <n°>)")
    v = BERGER / "courtier/validations"; f = v / f"{a}.json"; fait = v / f"{a}.fait.json"
    d = json_ou_rien(f) if f.is_file() else json_ou_rien(fait)
    if d is None: raise ValueError(f"écriture inconnue : n° {a}")
    base = validation_donnees(d); projet = None
    if base["fusion"] and str(d.get("outil", "")).endswith("-chef") and d["outil"][:-5] in EQUIPES: projet = d["outil"][:-5]
    return {**base, "en_attente": f.is_file(), "etat": str(d.get("etat") or "en attente"), "decide": d.get("decide"), "par": d.get("par"),
            "resultat": None if d.get("resultat") is None else str(d.get("resultat"))[:2000],
            "lien": {"vue": "demande", "a": f"{projet},{base['fusion']}"} if projet else None}


def rendu_texte(d, w, h):
    n = "?" if d["n"] is None else d["n"]
    out = [INV + GRAS + pad(f" ÉCRITURE n° {n}  ·  {d['etat']}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    out.append(f"  {PALE}demandée par{R} {d['agent']['nom']}  {PALE}le{R} {d['demande'][:16].replace('T', ' ') or '—'}  "
               f"{PALE}outil{R} {d['outil']} {GRAS}{d['verbe']}{R}")
    out.append(f"  {PALE}décide{R} " + (d["valideur"]["nom"] if d["valideur"] else PROPRIETAIRE))
    out += [""] + titre_section("APERÇU (complet)", JAUNE, w)
    out += plier(d["apercu"], w - 2, "  ", "  ")
    if d["en_attente"]: out += ["", f"  {PALE}berger valider {n}   /   berger refuser {n}{R}"]
    else:
        out += [""] + titre_section(f"DÉCIDÉE · {d['etat']}", VERT if "ÉCHEC" not in d["etat"] and d["etat"] != "refusé" else ROUGE, w)
        out.append(f"  {PALE}par{R} {d['par'] or '?'}  {PALE}le{R} {str(d['decide'] or '?').replace('T', ' ')}")
        if d["resultat"]: out += plier(d["resultat"], w - 2, "  ", "  ")
    if d["lien"]: out += ["", f"  {PALE}détail de la demande de fusion :{R} berger vue demande {d['lien']['a']}"]
    return out


def rendre(w, h, a=None):
    return rendu_texte(donnees(a), w, h)
