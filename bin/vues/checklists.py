# Vue « Checklists » de Berger : berger panneau checklists. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → checklists.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Checklists"
ICONE = '✅'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 5


def donnees(a=None):
    """Chaque liste Markdown cochable du dossier déclaré (config.toml : checklists.dossier) : avancement et cases restantes,
    avec leur section. `a` : un filtre « mot,mot » (seulement les listes dont le nom de fichier contient l'un des mots)."""
    filtre = a.split(",") if a else None
    d = dossier_checklists(); listes = sorted(d.glob("*.md")) if d.is_dir() else []
    if filtre: listes = [f for f in listes if any(m and m.lower() in f.stem.lower() for m in filtre)]
    out = []
    for f in listes:
        t = lire(f); c = cases(t); faites = sum(x for x, _ in c)
        restantes = []; section = None
        for l in t.splitlines():
            if re.match(r"^#{2,4}\s", l): section = l.lstrip("# "); continue
            m = re.match(r"^\s*-\s*\[( )\]\s*(.+)$", l)
            if m: restantes.append({"section": section, "libelle": m.group(2)})
        out.append({"fichier": f.name, "titre": next((l.lstrip("# ").strip() for l in t.splitlines() if l.startswith("# ")), f.stem),
                    "faites": faites, "total": len(c), "termine": bool(c) and faites == len(c), "restantes": restantes})
    return {"dossier": str(d), "listes": out}


def rendu_texte(d, w, h):
    """CHECKLISTS : avancement, puis seulement ce qui reste à faire, rangé sous son titre de section. On coche dans le fichier."""
    out = [INV + GRAS + pad(f" ✅ CHECKLISTS  ·  {len(d['listes'])} liste(s)", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R]
    if not d["listes"]: return out + ["", PALE + '  aucune liste · ajoute une checklist Markdown.' + R, PALE + '  Exemple : - [ ] Préparer le rapport' + R]
    for x in d["listes"]:
        faites, total = x["faites"], x["total"]
        plein = round(20 * faites / total) if total else 0
        out += [""] + titre_section(couper(plat(x["titre"]), w), CYAN, w)
        out.append(couper(f"  {VERT}{'█' * plein}{PALE}{'░' * (20 - plein)}{R}  {faites}/{total}" + (f"  {VERT}✔ terminé{R}" if x["termine"] else ""), w))
        montree = None
        for r in x["restantes"]:
            section = plat(r["section"]) if r["section"] is not None else None
            if section and section != montree: out.append(couper(f"  {GRAS}{section}{R}", w)); montree = section
            out += plier(plat(r["libelle"]), w - 2, "    ☐ ", "      ")
    out += ["", couper(PALE + f"  lecture seule — dossier {d['dossier']}" + R, w)]
    return out


def vue_checklists(w, h, filtre=None):
    return rendu_texte(donnees(",".join(filtre) if filtre else None), w, h)


def rendre(w, h, a=None):
    return vue_checklists(w, h, a.split(",") if a else None)
