# Vue d'objet « Demande de fusion » de Berger (spec interface §6.4) : berger vue demande <projet>,<sujet>. Jamais un onglet :
# l'interface l'ouvre depuis une décision ou une écriture « fusionner ». Données : equipes/<projet>/demandes/<sujet>.json et le
# dépôt du chef (git log / diff --numstat, en LECTURE, sans fetch) ; rendu_texte() ne lit que ces données.
TITRE = "Demande de fusion"
ICONE = None
ONGLET = "objet"     # "objet" : vue d'un objet (n° d'écriture, demande, document), ouverte par un lien, sans onglet
ORDRE = 31
FICHIERS_MAX = 300


def donnees(a=None):
    projet, _, sujet = str(a or "").partition(",")
    if projet not in EQUIPES or not re.fullmatch(r"[\w.-]+", sujet): raise ValueError(f"demande inconnue : {a} (berger vue demande <projet>,<sujet>)")
    f = BERGER / "equipes" / projet / "demandes" / f"{sujet}.json"; d = json_ou_rien(f)
    if d is None: raise ValueError(f"demande inconnue : {projet},{sujet}")
    e = EQUIPES[projet]; principale = e.get("principale", "main"); commit = str(d.get("commit") or ""); commits, fichiers, erreur = [], [], None
    depot = Path(os.path.expanduser(e["depot"])) if e.get("depot") else None
    if depot and (depot / ".git").exists() and re.fullmatch(r"[0-9a-f]{7,40}", commit):
        git = lambda *x: subprocess.run(["git", "-C", str(depot), *x], capture_output=True, text=True, timeout=20)
        base = f"origin/{principale}" if git("rev-parse", "--verify", "--quiet", f"origin/{principale}").returncode == 0 else principale
        lg = git("log", "--format=%h%x00%s", f"{base}..{commit}"); df = git("diff", "--numstat", f"{base}...{commit}")
        if lg.returncode or df.returncode: erreur = "commit absent du dépôt du chef (pas encore récupéré ?)"
        commits = [dict(zip(("id", "sujet"), l.split("\x00", 1))) for l in lg.stdout.splitlines() if "\x00" in l]
        for l in df.stdout.splitlines()[:FICHIERS_MAX]:
            plus, moins, chemin = (l.split("\t", 2) + ["", "", ""])[:3]
            fichiers.append({"chemin": chemin, "ajouts": int(plus) if plus.isdigit() else None, "retraits": int(moins) if moins.isdigit() else None})
    else: erreur = "dépôt du chef ou commit indisponible"
    porte = lambda p, r, ou: {"porte": p, "etat": str(r.get("etat", "?")), "code": r.get("code"), "bilan": r.get("bilan"),
                              "par": r.get("joue_par"), "quand": r.get("joue_le"), "ou": ou}
    return {"projet": projet, "sujet": sujet, "branche": str(d.get("branche", "")), "commit": commit, "agent": agent_court(d.get("agent") or "?"),
            "etat": str(d.get("etat", "?")), "demande": str(d.get("demande", "")), "resume": str(d.get("resume", "")), "tronque": bool(d.get("tronque")),
            "renvois": int(d.get("renvois", 0)), "motif": d.get("motif"),
            "portes": [porte(p, r, "demande") for p, r in (d.get("portes") or {}).items() if isinstance(r, dict)],
            "rejeux": [{"par": x.get("par"), "quand": x.get("quand"), "recompte": x.get("recompte"),
                        "portes": [porte(p, r, "rejeu") for p, r in (x.get("portes") or {}).items() if isinstance(r, dict)]}
                       for x in d.get("rejeux", []) if isinstance(x, dict)],
            "commits": commits, "fichiers": fichiers, "git": erreur}


def rendu_texte(d, w, h):
    out = [INV + GRAS + pad(f" DEMANDE DE FUSION  ·  {d['projet']} · {d['sujet']}  ·  {d['etat']}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    out.append(f"  {PALE}branche{R} {d['branche']}  {PALE}commit{R} {d['commit'][:10] or '—'}  {PALE}par{R} {d['agent']['nom']}  "
               f"{PALE}demandée le{R} {d['demande'][:16].replace('T', ' ') or '—'}" + (f"  {JAUNE}{d['renvois']} renvoi(s){R}" if d["renvois"] else ""))
    if d["motif"]: out += plier(f"dernier motif de renvoi : {plat(str(d['motif']))}", w - 2, f"  {JAUNE}", "    ", JAUNE)
    out += [""] + titre_section("RÉSUMÉ" + (" (coupé à l'inscription)" if d["tronque"] else ""), BLEU, w)
    for l in d["resume"].splitlines() or ["—"]: out += plier(l, w - 2, "  ", "  ")
    coul = lambda e: {"vert": VERT, "rouge": ROUGE}.get(e, PALE)
    def portes(l):
        return [f"  {coul(p['etat'])}{p['porte']:<7} {p['etat']}{R}  {PALE}{p['par'] or '?'} · {str(p['quand'] or '?')[:16].replace('T', ' ')}{R}  {p['bilan'] or ''}" for p in l]
    out += [""] + titre_section("PORTES (à la demande)", VERT, w) + (portes(d["portes"]) or [PALE + "  aucune inscrite" + R])
    for x in d["rejeux"]:
        out += [""] + titre_section(f"REJEU · {x['par'] or '?'} · {str(x['quand'] or '?')[:16].replace('T', ' ')}", CYAN, w) + portes(x["portes"])
        if x["recompte"]: out += plier(str(x["recompte"]), w - 2, "  ", "  ")
    out += [""] + titre_section(f"COMMITS ({len(d['commits'])})", CYAN, w) + [f"  {PALE}{c['id']}{R} {c['sujet']}" for c in d["commits"]]
    out += [""] + titre_section(f"FICHIERS TOUCHÉS ({len(d['fichiers'])})", CYAN, w)
    out += [f"  {VERT}+{x['ajouts'] if x['ajouts'] is not None else '?'}{R} {ROUGE}-{x['retraits'] if x['retraits'] is not None else '?'}{R}  {x['chemin']}" for x in d["fichiers"]]
    if d["git"]: out.append(f"  {JAUNE}{d['git']}{R}")
    return out


def rendre(w, h, a=None):
    return rendu_texte(donnees(a), w, h)
