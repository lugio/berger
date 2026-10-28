# Vue « Courtier » de Berger : berger panneau courtier. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → courtier.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Courtier"
ICONE = '🔐'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 7
APPELS_MAX = 200                                                           # derniers appels donnés (le texte en montre ce qui tient)


def donnees(a=None):
    audit = lire(BERGER / "courtier/dernier-audit.txt").strip(); sv = lire(BERGER / "courtier/derniere-sauvegarde.txt").strip()
    lignes = lire(BERGER / "courtier/appels.log").splitlines(); auj = [l for l in lignes if l.startswith(aujourdhui())]
    appels = []
    # Réserver la sélection aux refus du jour avant les lectures répétées (200 entrées au plus).
    refus_du_jour = [n for n, l in enumerate(lignes) if l.startswith(aujourdhui()) and '\tREFUSÉ\t' in l][-APPELS_MAX:]
    selection = set(refus_du_jour)
    for n in range(len(lignes) - 1, -1, -1):
        if len(selection) >= APPELS_MAX: break
        selection.add(n)
    for n in sorted(selection):
        l = lignes[n]
        c = (l.split("\t") + [""] * 7)[:7]
        appels.append({"quand": c[0], "agent": c[1], "outil": c[2], "verbe": c[3], "args": c[4], "ok": c[5] == "accepté", "detail": c[6]})
    return {"actif": courtier_actif(), "droits": sum(len(x) for x in droits_agents().values()),
            "audit": {"texte": audit, "ok": "aucune fuite" in audit} if audit else None,
            "validations": [validation_donnees(x) for x in en_attente()],
            "sauvegarde": {"suivie": bool(CONFIG.get("sauvegarde")), "derniere": sv or None},
            "aujourdhui": {"appels": len(auj), "refus": sum("\tREFUSÉ\t" in l for l in auj)}, "appels": appels}


def rendu_texte(d, w, h):
    etat_ = (VERT + "en service" if d["actif"] else ROUGE + GRAS + "ARRÊTÉ") + R
    out = [INV + GRAS + pad(f" COURTIER DE SECRETS  ·  {ANSI.sub('', etat_)}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    n = d["droits"]
    out += plier(f"{n} droit{'s' if n > 1 else ''} attribué{'s' if n > 1 else ''} · accès et dernier usage : Catalogue", w, "  ", "  ")
    audit = d["audit"]
    out += [""] + plier("audit des secrets : " + (audit['texte'] if audit else 'jamais lancé'), w, '  ', '    ', VERT if audit and audit['ok'] else PALE)
    att = d["validations"]
    out += [""] + titre_section(f"ÉCRITURES À VALIDER ({len(att)})", JAUNE, w)
    for x in att:
        out += plier(f"n° {x['n']} · {x['agent']['nom']} · {x['apercu']}   → berger valider {x['n']} | refuser {x['n']}", w, JAUNE + "  ✎ " + R, "    ")
    if not att: out.append(PALE + "  aucune" + R)
    sv = d["sauvegarde"]
    if sv["suivie"]:
        out += [""] + titre_section("SAUVEGARDE", CYAN, w) + plier(sv['derniere'] or 'jamais faite', w, '    ', '    ', VERT if sv['derniere'] else ROUGE)
    refus = d["aujourdhui"]["refus"]
    out += ['', f"  aujourd'hui : {d['aujourdhui']['appels']} appel{'s' if d['aujourdhui']['appels'] > 1 else ''} · {JAUNE if refus else VERT}{refus} refusé{'s' if refus > 1 else ''}{R}", '']
    out += titre_section('APPELS · REFUS DU JOUR EN PREMIER', CYAN, w)
    # Même identité et même résultat : une ligne groupée, heure du plus récent. Les refus du jour restent prioritaires.
    groupes = {}
    jour = datetime.date.today().isoformat()
    for c in sorted(d['appels'], key=lambda c: c['quand'], reverse=True):
        cle = tuple(c[k] for k in ('agent', 'outil', 'verbe', 'args', 'ok', 'detail')) + (c['quand'][:10],)
        if cle in groupes: groupes[cle][1] += 1
        else: groupes[cle] = [c, 1]
    groupes = sorted(groupes.values(), key=lambda x: not (not x[0]['ok'] and x[0]['quand'].startswith(jour)))
    place = max(0, (h - len(out)) // 2)
    for c, nombre in groupes[:place]:
        prefixe = f"  {c['quand'][11:16]} {c['agent']} · {c['outil']} {c['verbe']}" + (f" ×{nombre}" if nombre > 1 else '')
        out.append(couper(prefixe + (f" · {c['args']}" if c['args'] else ''), w))
        out.append(couper(f"    {VERT if c['ok'] else ROUGE + GRAS}{'✓' if c['ok'] else '✗'} {c['detail'] or ('accepté' if c['ok'] else 'refusé')}{R}", w))
    if len(groupes) > place and place:
        out[-1] = couper(out[-1], max(0, w - 26)) + f" {PALE}· {len(groupes) - place} groupes suivants{R}"
    if not d["appels"]: out.append(PALE + "  aucun appel" + R)
    return out


def vue_courtier(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_courtier(w, h)
