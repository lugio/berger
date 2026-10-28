#!/usr/bin/env python3
"""Tests de contrat des données des vues (spec docs/plans/2026-10-13-interface-spec.md, §3) — sans modèle, faux Herdr, faux
systemctl, installation JETABLE à heure fixe (tests/_jeu_vues.py). Vérifie :
 1. une vue qui a donnees() a son schéma bin/vues/<type>.schema.json, et inversement ; les vues encore « texte seulement »
    sont exactement celles de A_SEPARER (la liste ne fait que rétrécir : lots 0b, 0c) ;
 2. `berger vue <type> --json`, `berger etat --json`, `berger validations --json` respectent leur schéma (validateur en
    Python standard, tests/_schema.py : tout champ requis, aucun champ non déclaré) ;
 3. chaque champ déclaré est réellement produit (non vide au moins une fois) par le jeu de données ;
 4. chaque champ porte x-libelle et un x-rendu connu (le vocabulaire de l'interface) ;
 6. le texte de CHAQUE vue et de etat / validations est identique, octet pour octet, à celui figé AVANT la séparation
    (tests/attendus/, une liste de lignes JSON par vue : les espaces de fin de ligne y sont des données) ; une vue née après
    la séparation (NEES_APRES) n'a pas de texte d'avant : elle est prouvée par 2, 3, 4 et 9 ;
 9. le texte d'une vue ne dépend que de ses données : rendu_texte(aller-retour JSON de donnees()) = rendre() ;
 et : une vue piégée (données sans schéma, sans rendu_texte) est écartée et nommée ; refus clairs de `berger vue`.
Usage : python3 tests/interface.py (0 = tout passe).
Refiger la référence (jeu de données enrichi) : python3 tests/interface.py --figer-depuis — la référence est produite par le
code des vues de SOURCE_FIGEE (avant toute séparation), dans une copie jetable, avec le jeu de données ACTUEL ; jamais par
le code en cours. Le refigeage est un commit à part (tests/_jeu_vues.py et tests/attendus/ seulement) qui cite cette commande."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J, _schema as S

SRC = Path(__file__).resolve().parent.parent
ATTENDUS = SRC / "tests/attendus"
SOURCE_FIGEE = "46e42ce"           # dernier commit AVANT la séparation données/rendu (correctif du Tableau de l'agent inclus)
PREMIERE_SEPARATION = "54bed8b"    # premier commit qui sépare des vues : une source qui le contient est refusée


def figer_depuis(source):
    """Fige tests/attendus/ avec le code des vues de `source` et le jeu de données actuel (deux passages identiques exigés)."""
    git = lambda *a: subprocess.run(["git", "-C", str(SRC), *a], capture_output=True, text=True)
    c = git("rev-parse", "--verify", "--quiet", source + "^{commit}").stdout.strip()
    if not c: sys.exit(f"REFUS : {source} n'est pas un commit de ce dépôt")
    if git("merge-base", "--is-ancestor", c, "HEAD").returncode: sys.exit(f"REFUS : {source} n'est pas un ancêtre de la branche")
    if git("merge-base", "--is-ancestor", PREMIERE_SEPARATION, c).returncode == 0:
        sys.exit(f"REFUS : {source} contient déjà la séparation ({PREMIERE_SEPARATION}) : la référence doit venir du code d'AVANT")
    if git("grep", "-l", "def donnees", c, "--", "bin/vues").stdout.strip():
        sys.exit(f"REFUS : des vues de {source} ont déjà donnees() : la référence doit venir du code d'AVANT la séparation")
    with tempfile.TemporaryDirectory() as w:
        copie = Path(w) / "source"; copie.mkdir()                       # copie jetable : git archive (rien n'est écrit dans .git)
        a = subprocess.run(["git", "-C", str(SRC), "archive", c], capture_output=True)
        if a.returncode or subprocess.run(["tar", "-x", "-C", str(copie)], input=a.stdout, capture_output=True).returncode:
            sys.exit("REFUS : copie jetable impossible (git archive)")
        for f in ("_jeu_vues.py", "_produit.py"): shutil.copy(SRC / "tests" / f, copie / "tests" / f)
        prog = ("import json, sys, tempfile\nsys.path.insert(0, 'tests')\nimport _jeu_vues as J\nres = []\n"
                "for _ in range(2):\n    with tempfile.TemporaryDirectory() as t:\n"
                "        i, env = J.construire(t); res.append({'vues': J.rendus(i, env), 'commandes': J.sorties(i, env)})\n"
                "print(json.dumps({'identiques': res[0] == res[1], 'figes': res[0]}, ensure_ascii=False))")
        r = subprocess.run([sys.executable, "-c", prog], cwd=copie, capture_output=True, text=True, timeout=600)
    try: x = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError): sys.exit(f"REFUS : figeage en échec — {r.stderr[-800:]}")
    if not x["identiques"]: sys.exit("REFUS : deux passages différents (jeu de données non déterministe) : rien écrit")
    erreurs = [n for n, l in x["figes"]["vues"].items() if any("ERREUR" in y for y in l)]
    if erreurs: sys.exit(f"REFUS : vues en erreur avec le code de {source} : {erreurs} — rien écrit")
    for d, l in x["figes"].items():
        for f in (ATTENDUS / d).glob("*.json"): f.unlink()                 # une vue disparue ou renommée ne laisse rien derrière
        for n, y in l.items(): (ATTENDUS / d / f"{n}.json").write_text(json.dumps(y, ensure_ascii=False, indent=0) + "\n")
    print(f"figé depuis {source} ({c[:10]}) : tests/attendus/ — commit à part, avec la commande « python3 tests/interface.py --figer-depuis »")


if "--figer-depuis" in sys.argv: figer_depuis(SOURCE_FIGEE); sys.exit(0)
# Vues pas encore séparées (texte seulement) : 0b puis 0c les retirent ; une vue NOUVELLE doit venir avec ses données.
A_SEPARER = set()
# Vues NÉES APRÈS la séparation (lot 1b et suivants) : elles n'ont pas de texte « d'avant » à figer (le code de SOURCE_FIGEE ne
# les connaît pas) ; leur texte est prouvé par le test 9 (texte = f(données)) et leurs données par les tests 2 à 4.
NEES_APRES = {"livrables", "documents"}
# Lot vues autorisé le 23/10 : les références historiques restent intactes ; nouveaux attendus séparés et relus.
VUES_REVISEES = {'accueil', 'colonnes', 'courtier', 'decisions', 'tableau', 'tokens'}
# Ce que l'interface sait afficher (spec §3, test 4) : les clés du bloc « const RENDUS = { … }; » de bin/page/app.js.
APP_JS = (SRC / "bin/page/app.js").read_text()
_bloc = re.search(r"^const RENDUS = \{\n(.*?)^\};", APP_JS, re.M | re.S)
RENDUS = set(re.findall(r'^  "?([a-z][a-z-]*)"?\s*:', _bloc.group(1), re.M)) if _bloc else set()
# Champs produits seulement quand une vue est piégée (contrôlés plus bas, avec le piège).
PRODUITS_PAR_LE_PIEGE = {"etat": ("$.vues_ecartees", "$.moteurs_ecartes", "$.commandes_ecartees")}   # moteurs_ecartes : lot 2, commandes_ecartees : lot 3 (prouvés par tests/contrat-noyau.py)
# Appels en plus d'une vue (filtre, agent) : chacun validé, et leurs données comptent pour « chaque champ est produit ».
VARIANTES = {"echanges": [["vigie"]], "sources": [["alertes,inexistante"]], "checklists": [["mise"]]}
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def vide(x): return x is None or x == "" or x == [] or x == {}


with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t)
    b = lambda *a: J.commande(i, env, *a)                                  # berger à l'heure fixe : des données qui ne vieillissent pas

    # 6. texte identique, octet pour octet, à celui figé avant la séparation — EN PREMIER : la Synthèse retient la première
    # apparition de chaque alerte (.synthese-vu.json) ; un appel à l'heure réelle avant changerait son « depuis le »
    rendus = {n: x for n, x in J.rendus(i, env).items() if n.split(".")[0] not in NEES_APRES}
    figes = {p.stem for p in (ATTENDUS / "vues").glob("*.json")}
    dire(not {n.split(".")[0] for n in figes} & NEES_APRES, f"aucune vue née après la séparation n'a de rendu figé ({sorted(NEES_APRES)})")
    dire(figes == set(rendus), f"un rendu figé par vue (et par agent du jeu pour une vue d'agent), aucun en trop (manquants : {sorted(set(rendus) - figes)} ; en trop : {sorted(figes - set(rendus))})")
    for n, x in rendus.items():
        f = ATTENDUS / ('vues-herdr' if n.split('.')[0] in VUES_REVISEES else 'vues') / f"{n}.json"
        dire(f.is_file() and x == json.loads(f.read_text()), f"vue {n} : texte identique au rendu figé (tests/attendus/vues/{n}.json)")
    for n, x in J.sorties(i, env).items():
        f = ATTENDUS / "commandes" / f"{n}.json"
        dire(f.is_file() and x == json.loads(f.read_text()), f"berger {n} : texte identique à la sortie figée (tests/attendus/commandes/{n}.json)")

    # La suite se joue sur le jeu AVEC marquages (comportement nouveau, lot 1a) : il contient tout le jeu d'avant, plus.
    i_ref, env_ref = i, env
    i, env = J.construire(Path(t) / "marquages", marquages=True); b = lambda *a: J.commande(i, env, *a)
    OBJETS = J.objets(i, env)

    # 9. le texte ne dépend que des données (vues d'agent : chaque agent ; vues d'objet : chaque objet du jeu)
    aller = J.executer(i, env, f"OBJETS = {OBJETS!r}\nout = {{}}\nfor n, v in sorted(g['VUES'].items()):\n"
                               "  if not hasattr(v, 'donnees'): continue\n"
                               f"  for a in ({J.AGENTS_JEU!r} if v.ONGLET == 'agent' else OBJETS.get(n, []) if v.ONGLET == 'objet' else (None,)):\n"
                               "    d = json.loads(json.dumps(v.donnees(a)))\n"
                               "    out[n + ('.' + a if a else '')] = v.rendu_texte(d, 100, 40) == v.rendre(100, 40, a)\n"
                               "print(json.dumps(out))")
    dire(aller and all(aller.values()), f"rendu_texte(aller-retour JSON des données) = rendre(), pour chaque vue séparée ({aller})")

    # 1. vues ↔ schémas
    r = b("vues", "--json"); lv = json.loads(r.stdout)
    vues = {v["type"]: v for v in lv["vues"]}
    avec = {n for n, v in vues.items() if v["donnees"]}; sans = set(vues) - avec
    schemas = {p.name[:-len(".schema.json")] for p in (SRC / "bin/vues").glob("*.schema.json")}
    dire(r.returncode == 0 and not lv["ecartees"], f"berger vues --json : {len(vues)} vues, aucune écartée ({lv['ecartees']})")
    dire(schemas == avec, f"un schéma par vue à données, aucun orphelin (schémas sans données : {sorted(schemas - avec)} ; données sans schéma : {sorted(avec - schemas)})")
    dire(sans == A_SEPARER, f"vues encore « texte seulement » = A_SEPARER (en trop : {sorted(sans - A_SEPARER)} ; déjà séparées, à retirer de la liste : {sorted(A_SEPARER - sans)})")

    # 2, 3, 4. données conformes, chaque champ produit, chaque champ affichable
    cibles = [(n, ["vue", n], SRC / f"bin/vues/{n}.schema.json") for n in sorted(avec)]
    cibles += [(c, [c], SRC / f"bin/schemas/{c}.schema.json") for c in J.COMMANDES]
    for nom, argv, fs in cibles:
        s = S.charger(fs); toutes = []
        onglet = vues[nom]["onglet"] if nom in vues else None
        appels = ([[a] for a in J.AGENTS_JEU] if onglet == "agent" else [[x] for x in OBJETS.get(nom, [])] if onglet == "objet"
                  else [[]] + VARIANTES.get(nom, []))
        for plus in appels:
            r = b(*argv, *plus, "--json")
            try: env_ = json.loads(r.stdout)
            except ValueError: dire(False, f"{nom} {' '.join(plus)} --json : pas du JSON (code {r.returncode}, {r.stderr.strip()[-200:]})"); continue
            dire(env_.get("vue") == nom and env_.get("version") == s.get("x-version") and isinstance(env_.get("genere"), str),
                 f"{nom} {' '.join(plus)} --json : enveloppe {{vue, version = x-version du schéma, genere, donnees}}")
            err = S.valider(env_["donnees"], s, s)
            dire(not err, f"{nom} {' '.join(plus)} --json respecte {fs.name}" + (f" — {err[:5]}" if err else ""))
            toutes.append(env_["donnees"])
        morts = [c for c, _ in S.proprietes(s, s) if all(vide(x) for d in toutes for x in S.valeurs(d, c))
                 and not c.startswith(PRODUITS_PAR_LE_PIEGE.get(nom, ("#",)))]
        dire(not morts, f"{nom} : chaque champ du schéma est produit par le jeu de données (jamais produits : {morts})")
        sans_rendu = [c for c, p in S.proprietes(s, s) if p.get("x-rendu") not in RENDUS or not p.get("x-libelle")]
        items = [c + "[]" for c, p in S.proprietes(s, s) if "$ref" in p.get("items", {}) and p["items"].get("x-rendu") not in RENDUS
                 and p.get("x-rendu") not in ("statuts", "lignes")]
        dire(not sans_rendu and not items, f"{nom} : chaque champ a x-libelle et un x-rendu connu de l'interface (fautifs : {sans_rendu + items})")

    # 4, 5. la page : son vocabulaire de rendus est complet, ses onglets viennent de berger vues, aucune vue n'y est nommée
    dire(len(RENDUS) >= 10, f"bin/page/app.js déclare ses rendus dans un bloc « const RENDUS = {{ … }}; » ({sorted(RENDUS)})")
    # les vues ne sont nommées que dans le bloc DEDIES (rendus dédiés de la maquette) ; partout ailleurs, la page est générique
    bloc_d = re.search(r"^const DEDIES = \{\n(.*?)^\};", APP_JS, re.M | re.S)
    bloc_i = re.search(r"^const ICONES = \{\n(.*?)^\};", APP_JS, re.M | re.S)       # icônes de navigation, par type de vue
    hors_bloc = APP_JS
    for b_ in (bloc_d, bloc_i):
        if b_: hors_bloc = hors_bloc.replace(b_.group(0), "")
    icones = re.findall(r"^  ([a-z][a-z-]*):", bloc_i.group(1), re.M) if bloc_i else []
    dire(set(icones) <= set(vues), f"bloc ICONES : chaque vue citée existe (inconnues : {sorted(set(icones) - set(vues))})")
    nommees = [n for n in vues if f'"{n}"' in hors_bloc or f"'{n}'" in hors_bloc or f"`{n}`" in hors_bloc]
    dire(not nommees and "/api/vues" in APP_JS, f"app.js : navigation tirée de /api/vues, aucune vue nommée hors des blocs DEDIES et ICONES (nommées : {nommees})")
    dedies = re.findall(r"^  ([a-z][a-z-]*): \{", bloc_d.group(1), re.M) if bloc_d else []
    cites = set(re.findall(r'"([a-z][a-z-]*)"', bloc_d.group(1))) if bloc_d else set()
    dire(bloc_d and dedies and set(dedies) <= avec and all(vues[x]["onglet"] != "agent" for x in dedies),
         f"bloc DEDIES : chaque rendu dédié porte sur une vue à données qui n'est pas une vue d'agent ({dedies})")
    dire(cites <= set(vues), f"bloc DEDIES : chaque vue citée existe (inconnues : {sorted(cites - set(vues))})")

    # la page elle-même, dans un faux DOM (node, s'il est présent : PAS une dépendance du projet) : chaque vue du jeu, dédiée ou
    # générique, se rend sans erreur, sans texte « undefined/null », en ne lisant QUE des champs présents dans ses données
    if not shutil.which("node"): print("NON JOUÉ essai de la page dans un faux DOM : node absent de cette machine")
    else:
        schemas_ = {p.name[:-len(".schema.json")]: json.loads(p.read_text()) for d_ in ("bin/vues", "bin/schemas") for p in (SRC / d_).glob("*.schema.json")}
        toutes = {n: json.loads(b("vue", n, "--json").stdout)["donnees"] for n in sorted(avec) if vues[n]["onglet"] == "berger"}
        jeux = []
        for n in sorted(avec):
            o = vues[n]["onglet"]
            for a in (J.AGENTS_JEU if o == "agent" else OBJETS.get(n, []) if o == "objet" else [None]):
                d_ = toutes[n] if o == "berger" else json.loads(b("vue", n, a, "--json").stdout)["donnees"]
                jeux.append({"type": n, "a": a, "dedie": n in dedies and o != "agent", "donnees": d_, "autres": toutes})
        f_ = Path(t) / "jeux-page.json"; f_.write_text(json.dumps({"schemas": schemas_, "jeux": jeux}, ensure_ascii=False))
        r = subprocess.run(["node", str(SRC / "tests/_page_essai.js"), str(SRC / "bin/page/app.js"), str(f_)], capture_output=True, text=True, timeout=120)
        try: res = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): res = {"essai": "ERREUR " + r.stderr[-300:]}
        file_ = res.pop("#file", None); cadre = res.pop("#cadre", None); rech = res.pop("#recherche", None); flux_ = res.pop("#flux", None)
        dire(file_ == "ok", f"page : une seule demande en vol à la fois, même quand une lecture échoue ({file_})")
        dire(flux_ == "ok", f"page : temps réel — flux ouvert, la boucle de 5 s se tait ; « change » → relecture ; coupure → repli à 5 s puis reprise seule ; 503 → nouvel essai à 30 s ({flux_})")
        dire(rech == "ok", f"page : Documents — la recherche par nom (sans accent ni casse) masque ce qui ne correspond pas et rend tout à vide ({rech})")
        dire(cadre == "ok", f"page : un livrable .html s'affiche dans un cadre isolé (sandbox « allow-scripts » seul, jamais allow-same-origin ; source /api/livrable/<id>/html ; sans référent) ({cadre})")
        mauvais = {k: v for k, v in res.items() if v != "ok" and not k.endswith("#compteur")} | {k: v for k, v in res.items() if k.endswith("#compteur")}
        dire(len(res) >= len(jeux) and not mauvais,
             f"page dans un faux DOM : {len(jeux)} rendus ({len([j for j in jeux if j['dedie']])} dédiés) sans erreur ni texte vide, champs lus = champs des données (fautifs : {mauvais})")

    # commandes qui rendent déjà leur JSON tel quel (sans enveloppe) : berger suivi, berger equipe liste
    BRUTES = {"suivi": ["suivi", "demo-ecran"], "equipe-liste": ["equipe", "liste", "demo"]}
    for nom, argv in BRUTES.items():
        r = b(*argv); s = S.charger(SRC / f"bin/schemas/{nom}.schema.json")
        try: d = json.loads(r.stdout)
        except ValueError: dire(False, f"berger {' '.join(argv)} : pas du JSON (code {r.returncode}, {r.stderr.strip()[-200:]})"); continue
        err = S.valider(d, s, s)
        dire(not err, f"berger {' '.join(argv)} respecte {nom}.schema.json" + (f" — {err[:5]}" if err else ""))
        morts = [c for c, _ in S.proprietes(s, s) if all(vide(x) for x in S.valeurs(d, c))]
        dire(not morts, f"{nom} : chaque champ du schéma est produit par le jeu de données (jamais produits : {morts})")
    # commandes à enveloppe qui demandent un agent : berger espace-voulu <agent> --json (le détail des règles : tests/regles-espace.py)
    PAR_AGENT = {"espace-voulu": ["espace-voulu"]}
    for nom, argv in PAR_AGENT.items():
        s = S.charger(SRC / f"bin/schemas/{nom}.schema.json")
        for a in J.AGENTS_JEU:
            r = b(*argv, a, "--json")
            try: env_ = json.loads(r.stdout)
            except ValueError: dire(False, f"berger {' '.join(argv)} {a} --json : pas du JSON (code {r.returncode}, {r.stderr.strip()[-200:]})"); continue
            err = S.valider(env_.get("donnees"), s, s)
            dire(env_.get("vue") == nom and env_.get("version") == s.get("x-version") and not err,
                 f"berger {' '.join(argv)} {a} --json : enveloppe et {nom}.schema.json respectés" + (f" — {err[:5]}" if err else ""))
        sans_rendu = [c for c, x in S.proprietes(s, s) if x.get("x-rendu") not in RENDUS or not x.get("x-libelle")]
        dire(not sans_rendu, f"{nom} : chaque champ a x-libelle et un x-rendu connu de l'interface (fautifs : {sans_rendu})")
    utilises = {"communs", *J.COMMANDES, *BRUTES, *PAR_AGENT}
    orphelins = sorted(p.name[:-len(".schema.json")] for p in (SRC / "bin/schemas").glob("*.schema.json") if p.name[:-len(".schema.json")] not in utilises)
    dire(not orphelins, f"chaque schéma de bin/schemas/ est contrôlé ici (non contrôlés : {orphelins})")

    # durée bornée (14/10 : la page disait « délai de 10 s dépassé ») : chaque vue répond vite — le délai du serveur est 10 s,
    # aucune vue ne doit approcher la moitié ; et une vue de données ne casse pas si son cache n'est pas inscriptible
    import time as _t
    lentes = {}
    for n in sorted(avec):
        o = vues[n]["onglet"]; a = (J.AGENTS_JEU[0] if o == "agent" else (OBJETS.get(n) or [None])[0] if o == "objet" else None)
        debut = _t.time(); b("vue", n, *([a] if a else []), "--json"); duree = _t.time() - debut
        if duree > 3: lentes[n] = round(duree, 1)
    dire(not lentes, f"chaque vue répond en moins de 3 s (le serveur coupe à 10 s) (lentes : {lentes})")
    cache = i.parent / ".cache/berger/conso"; os.chmod(cache, 0o500)
    for f_ in cache.iterdir(): os.chmod(f_, 0o400)
    r = b("vue", "tokens", "--json"); os.chmod(cache, 0o700)
    for f_ in cache.iterdir(): os.chmod(f_, 0o600)
    dire(r.returncode == 0 and json.loads(r.stdout or "{}").get("donnees", {}).get("par_agent"),
         f"vue tokens : cache de consommation non inscriptible → données rendues quand même, rien ne casse ({r.stderr.strip()[-120:]})")

    # refus de `berger vue`
    r = b("vue", "tableau", "--json"); dire(r.returncode != 0 and "vue d'agent" in r.stderr, "berger vue <vue d'agent> sans agent : refus clair")
    r = b("vue", sorted(A_SEPARER)[0], "--json") if A_SEPARER else None
    dire(r is None or (r.returncode != 0 and "pas encore de données" in r.stderr), "berger vue <vue texte seulement> --json : refus clair, jamais un JSON vide")
    r = b("vue", "inconnue"); dire(r.returncode != 0 and "vue inconnue" in r.stderr, "berger vue <inconnue> : refus, avec la liste des vues")
    r = b("vue", "alire"); dire(r.returncode == 0 and "À LIRE" in r.stdout, "berger vue alire (sans --json) : le texte de la vue, une fois")
    refus = [(x, b("vue", *x, "--json")) for x in (["validation", "99"], ["validation", "-1"], ["demande", "demo,inconnu"], ["demande", "x"],
                                                     ["document", "0" * 16], ["document", "../../x"])]
    dire(all(r.returncode != 0 and "inconnu" in r.stderr and not r.stdout.strip() for _, r in refus),
         f"vue d'objet sur un objet inconnu ou mal formé : refus clair, aucun JSON ({[(x, r.returncode, r.stderr.strip()[-60:]) for x, r in refus if r.returncode == 0 or 'inconnu' not in r.stderr]})")
    r = b("vue", "decisions", "--json"); genres = {x["genre"] for x in json.loads(r.stdout)["donnees"]["decisions"]}
    texte = re.sub(r"\x1b\[[0-9;]*m", "", b("vue", "decisions").stdout)
    dire({"validation", "terminal", "go", "question", "a_lire", "a_decider", "fusion"} <= genres and "go attendu : passer l'écran en production" in texte
         and "« faut-il garder l'ancien écran ? »" in texte and "décision attendue" in texte and "choisir 30 ou 90 jours" in texte,
         f"marquages ⚠ Go attendu, ❓ Question, Décision attendue : dans les données (genres {sorted(genres)}) et dans le texte de Herdr")
    r = b("vue", "document", OBJETS["document"][0], "--json"); x = json.loads(r.stdout)["donnees"]
    dire(r.returncode == 0 and x["texte"] and json.loads(b("vue", "document", OBJETS["document"][0], "--json").stdout)["donnees"]["lu"] == x["lu"],
         "berger vue document : le texte, sans marquer le document lu")

    # vues piégées : données sans schéma, données sans rendu_texte → écartées et nommées
    (i / "bin/vues/sansschema.py").write_text("TITRE = 'S'\nICONE = None\nONGLET = 'berger'\nORDRE = 97\n"
                                             "def donnees(a=None): return {}\ndef rendu_texte(d, w, h): return []\ndef rendre(w, h, a=None): return []\n")
    (i / "bin/vues/sanstexte.py").write_text("TITRE = 'T'\nICONE = None\nONGLET = 'berger'\nORDRE = 96\n"
                                            "def donnees(a=None): return {}\ndef rendre(w, h, a=None): return []\n")
    (i / "bin/vues/sanstexte.schema.json").write_text("{}")
    r = b("vues", "--json"); ec = {e["vue"]: e["cause"] for e in json.loads(r.stdout)["ecartees"]}
    dire("schéma" in ec.get("sansschema", "") and "rendu_texte" in ec.get("sanstexte", ""),
         f"vue à données sans schéma, ou sans rendu_texte : écartée et nommée ({ec})")
    r = b("etat"); dire("vue écartée : bin/vues/sansschema.py" in r.stdout, "berger etat nomme la vue écartée")
    r = b("etat", "--json"); e = json.loads(r.stdout)["donnees"]; s = S.charger(SRC / "bin/schemas/etat.schema.json")
    dire(not S.valider(e, s, s) and all(not vide(x["vue"]) and not vide(x["cause"]) for x in e["vues_ecartees"]) and len(e["vues_ecartees"]) == 2,
         "berger etat --json : les vues écartées, avec leur cause, conformes au schéma")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
