#!/usr/bin/env python3
"""Admission automatique d'une version ÉQUIVALENTE d'un moteur (go n° 136, docs/plans/2026-11-02-admission-auto-spec.md) — sans
moteur ni réseau, installation JETABLE.
Une version sans liste fermée est ADMISE par le contrat (tests/contrat-moteur.py › admettre_par_equivalence) seulement si la
seule ligne rouge est (12) « pas de liste fermée », si (13) est verte sous Codex, et si, jugée avec la liste de référence (la
plus récente du dépôt pour ce moteur, bien formée), (12) serait verte : aucun outil inconnu ni web, témoin complet. Aucune liste
n'est écrite : le verdict nomme la référence et son empreinte ; verdict_moteur ne l'accepte que si cette liste existe encore avec
la même empreinte (sinon « à rejouer »). Alerte JAUNE « admis par équivalence… liste à ajouter au dépôt » tant que la liste exacte
manque ; alerte JAUNE « version installée sans verdict : contrat à jouer ».
Les six cas de la spec : 1. équivalence admise ; 2. outil nouveau, web ou témoin incomplet refusés ; 3. Codex (13) rouge refusé ;
4. référence modifiée ou retirée → à rejouer ; 5. liste exacte ajoutée → l'alerte disparaît, verdict valable ; 6. version sans
verdict → alerte jaune. Usage : python3 tests/admission-equivalence.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import hashlib, importlib.util, json, os, re, runpy, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


sp = importlib.util.spec_from_file_location("contrat", SRC / "tests/contrat-moteur.py"); C = importlib.util.module_from_spec(sp); sp.loader.exec_module(C)
QUAND = "2026-11-03"
REF_CLAUDE = json.loads((SRC / "tests/outils-connus/claude-2.1.316.json").read_text())
REF_CODEX = json.loads((SRC / "tests/outils-connus/codex-0.165.0.json").read_text())
AUTRES = ["✓ témoin : un serveur canari déclaré explicitement au moteur est bien lancé", "✓ (1) outils vus (init) : aucun mcp__*",
          "✓ (2) aucun serveur lancé", "✓ (5) écriture par l'agent de .mcp.json : refusee", "✓ (6) connect() AF_UNIX : refusé"]


def poser(d, m, v, contenu):
    f = Path(d) / f"{m}-{v}.json"; f.write_text(json.dumps({**contenu, "version": v}, ensure_ascii=False, indent=2)); return f


def sha(f): return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def contrat_claude(d, init, temoin, autres=AUTRES, v="9.9.9"):
    """Les lignes d'un contrat Claude sur la version `v` (sans liste), jugé avec les listes du dossier `d` : (lignes, connus)."""
    connus = C.charger_connus("claude", v, d); lignes = list(autres)
    C.conditions_web_claude(lambda b, t: lignes.append(("✓ " if b else "✗ ") + t), {"tools": init}, {"tools": temoin}, connus, set())
    return lignes, connus


OUTILS = REF_CLAUDE["outils"]; TEMOIN = OUTILS + REF_CLAUDE["web"]

with tempfile.TemporaryDirectory() as t:
    t = Path(t); d = t / "outils-connus"; d.mkdir()
    ref = poser(d, "claude", "9.9.8", REF_CLAUDE); poser(d, "claude", "9.9.1", REF_CLAUDE)

    # ── 1. équivalence admise : sans liste pour 9.9.9, outils inclus dans la liste de référence (la plus récente : 9.9.8) ──
    lignes, connus = contrat_claude(d, OUTILS, TEMOIN)
    dire(any(l.startswith("✗ (12) liste fermée") and "pas de liste fermée" in l for l in lignes),
         "1. contrat sans liste exacte : (12) d'abord rouge « pas de liste fermée » (rien ne change dans la mesure)")
    r = C.admettre_par_equivalence("claude", lignes, connus, None, QUAND)
    ok12 = [l for l in (r or []) if l.startswith("✓ (12) liste fermée : admis par équivalence avec claude 9.9.8")]
    dire(r is not None and len(ok12) == 1 and f"(sha256 {sha(ref)[:8]})" in ok12[0] and f"contrat du {QUAND}" in ok12[0]
         and not any(l.startswith("✗ ") for l in r),
         f"1. équivalence admise : (12) verte « admis par équivalence avec claude 9.9.8 (sha256 <8>), contrat du <date> » — {ok12}")
    dire(r is not None and f"équivalence : claude 9.9.8 sha256 {sha(ref)}" in r,
         "1. le verdict nomme la référence et son empreinte complète (ligne « équivalence : »)")
    dire(r is not None and any(l.startswith("✓ témoin (12) ") for l in r), "1. le témoin (12) reste dans le verdict (contrôle complet)")
    dire(sorted(p.name for p in d.iterdir()) == ["claude-9.9.1.json", "claude-9.9.8.json"], "1. aucune liste écrite par le contrat")

    # ── 2. outil nouveau, outil web, témoin incomplet : NON ADMIS, outils nommés ──
    for init, temoin, quoi, nomme in ((OUTILS + ["Glob"], TEMOIN, "outil nouveau", "Glob"), (OUTILS + ["WebFetch"], TEMOIN, "outil web", "WebFetch"),
                                      (OUTILS, OUTILS + ["WebFetch"], "témoin incomplet", "WebSearch")):
        lignes, connus = contrat_claude(d, init, temoin)
        dire(C.admettre_par_equivalence("claude", lignes, connus, None, QUAND) is None and any(nomme in l for l in lignes if l.startswith("✗ ")),
             f"2. {quoi} : NON ADMIS, {nomme} nommé")
    lignes, connus = contrat_claude(d, OUTILS, TEMOIN, autres=AUTRES[:-1] + ["✗ (6) connect() AF_UNIX : CONNECTÉ"])
    dire(C.admettre_par_equivalence("claude", lignes, connus, None, QUAND) is None, "2. une autre condition rouge : pas d'équivalence")
    lignes, connus = contrat_claude(d, OUTILS, TEMOIN, autres=AUTRES + ["✗ (3) serveur d'essai : non mesurable"])
    dire(C.admettre_par_equivalence("claude", lignes, connus, None, QUAND) is None, "2. une condition non mesurable : pas d'équivalence")
    lignes, connus = contrat_claude(d, OUTILS, TEMOIN, v="9.9.8")
    dire(C.admettre_par_equivalence("claude", lignes, connus, None, QUAND) is None and connus["exacte"],
         "2. liste exacte présente : le contrat ordinaire s'applique, jamais d'équivalence")
    with tempfile.TemporaryDirectory() as e:
        e = Path(e); poser(e, "claude", "9.9.8", REF_CLAUDE); (e / "claude-9.9.9a.json").write_text("{")
        poser(e, "claude", "9.9.10", {**REF_CLAUDE, "outils": "Bash"})          # la plus récente : mal formée
        lignes, connus = contrat_claude(e, OUTILS, TEMOIN, v="9.9.11")
        dire(C.admettre_par_equivalence("claude", lignes, connus, None, QUAND) is None,
             "2. liste de référence la plus récente mal formée : pas d'équivalence (jamais un repli sur une plus ancienne)")
    with tempfile.TemporaryDirectory() as e:
        e = Path(e); poser(e, "claude", "9.9.8", {**REF_CLAUDE, "moteur": "codex"})
        lignes, connus = contrat_claude(e, OUTILS, TEMOIN)
        dire(C.admettre_par_equivalence("claude", lignes, connus, None, QUAND) is None, "2. liste d'un autre moteur : pas d'équivalence")
    lignes, connus = contrat_claude(d, OUTILS, TEMOIN)
    dire(C.admettre_par_equivalence("claude", [l for l in lignes if not l.startswith("✗ ")], connus, None, QUAND) is None,
         "2. aucune ligne rouge à convertir : rien n'est rendu (le contrat vert s'applique tel quel)")

    # ── 3. Codex : (13) rouge = NON ADMIS même avec des outils identiques ; (13) verte = admis par équivalence ──
    poser(d, "codex", "9.9.8", REF_CODEX)
    def contrat_codex(sous_agents, treize):
        connus = C.charger_connus("codex", "9.9.9", d); lignes = list(AUTRES) + [treize]
        out = lambda b, x: lignes.append(("✓ " if b else "✗ ") + x)
        out(True, "témoin (12) : sans le réglage de Berger, Codex envoie son outil de recherche web au modèle — vu")
        vus = list(connus["outils"]) + (list(connus["si_13"]) if sous_agents else [])
        C.verdict_liste(out, "outils de la requête de Codex au modèle", vus,
                        lambda c: c in connus["outils"] or (sous_agents and c in connus["si_13"]), connus, True, affiche=C.affiche_codex)
        return lignes, connus
    lignes, connus = contrat_codex(True, "✓ (13) évasion : lecture, depuis l'outil du sous-agent — refusée")
    r = C.admettre_par_equivalence("codex", lignes, connus, True, QUAND)
    dire(r is not None and any(l.startswith("✓ (12) liste fermée : admis par équivalence avec codex 9.9.8") for l in r),
         "3. Codex, (13) verte, outils identiques à la référence : admis par équivalence")
    lignes, connus = contrat_codex(False, "✗ (13) sous-agents : évasion : lecture ; collaboration refusé")
    dire(C.admettre_par_equivalence("codex", lignes, connus, False, QUAND) is None, "3. Codex, (13) rouge : NON ADMIS, même avec des outils identiques")
    lignes, connus = contrat_codex(True, "✓ (13) évasion : lecture — refusée")
    dire(C.admettre_par_equivalence("codex", lignes, connus, False, QUAND) is None, "3. Codex, (13) non prouvée verte (sous_agents faux) : NON ADMIS")
    dire(C.admettre_par_equivalence("codex", lignes, connus, None, QUAND) is None, "3. Codex, (13) non jouée : NON ADMIS")

# ── Côté Berger : verdict_moteur et alertes, installation JETABLE ──
with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre-essai.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre-essai.json"\n')
    for a, moteur in (("strict-essai", "claude"), ("essai-codex", "codex")):
        dd = i / "agents" / a; (dd / "memory").mkdir(parents=True)
        (dd / "agent.conf").write_text(f"nom = {a}\nmoteur = {moteur}\npanneaux = {moteur}\nmur = strict\nheures = aucune\noutils =\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false", "BERGER_TMP_AGENTS": str(m / "bt")}
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "regenerer"], env=env, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0, "regenerer réussit" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-200:]}"))
    os.environ.update({k: env[k] for k in ("HOME", "BERGER_DIR", "BERGER_HERDR", "BERGER_TMP_AGENTS")})
    sys.argv = ["berger"]; g = runpy.run_path(str(i / "bin/berger"), run_name="essai")["lancer"].__globals__
    M = g["moteurs"]; M.CONTRATS = m / "contrats"; M.CONTRATS.mkdir()
    L = M.LISTES = i / "tests/outils-connus"; L.mkdir(parents=True)
    versions = {"claude": "9.9.9", "codex": "9.9.9"}; M.version_moteur = lambda mo: versions[mo]
    ref = poser(L, "claude", "9.9.8", REF_CLAUDE)
    lignes, connus = contrat_claude(L, OUTILS, TEMOIN)
    eq = C.admettre_par_equivalence("claude", lignes, connus, None, QUAND)
    def verdict(mo, corps, v="9.9.9"):
        (M.CONTRATS / f"{mo}-{v}.txt").write_text("\n".join(["ADMIS", f"moteur : {mo} {v}", "agent : strict-essai", f"quand : {QUAND} 12:00", *corps]) + "\n")
    verdict("claude", eq or ["✗ aucune équivalence rendue"])
    verdict("codex", ["✓ témoin (12) : vu", "✓ (12) liste fermée : outils tous connus"])
    e, v, raison = M.verdict_moteur("claude")
    dire(e == "admis", f"1. verdict d'équivalence, référence intacte : admis — {e} {raison}")
    al = [x for c, _, x in M.alertes_moteurs() if c == "jaune"]
    dire(any("claude 9.9.9 admis par équivalence avec claude 9.9.8 : liste à ajouter au dépôt" in x for x in al),
         f"1. alerte JAUNE « admis par équivalence avec … : liste à ajouter au dépôt » — {al}")
    dire(not any(c == "rouge" for c, _, _ in M.alertes_moteurs()), "1. aucune alerte rouge pour une version admise par équivalence")

    # ── 4. référence modifiée ou retirée après le verdict : « à rejouer » ──
    texte = ref.read_text(); ref.write_text(texte.replace('"Bash"', '"Bash", "Glob"', 1))
    e, v, raison = M.verdict_moteur("claude")
    dire(e == "à rejouer" and "claude 9.9.8" in raison, f"4. liste de référence modifiée : à rejouer — {raison}")
    dire(any("claude 9.9.9" in x and "rejoué" in x for c, _, x in M.alertes_moteurs() if c == "jaune"), "4. Synthèse : à rejouer en jaune")
    ref.write_text(texte); dire(M.verdict_moteur("claude")[0] == "admis", "4. liste remise à l'identique : admis de nouveau (même empreinte)")
    ref.unlink(); e, v, raison = M.verdict_moteur("claude")
    dire(e == "à rejouer" and "claude 9.9.8" in raison, f"4. liste de référence retirée : à rejouer — {raison}")
    ref.write_text(texte)
    corps = list(eq or []); verdict("claude", [l for l in corps if not l.startswith("équivalence : ")])
    dire(M.verdict_moteur("claude")[0] == "à rejouer", "4. « admis par équivalence » sans la ligne de référence : à rejouer (jamais admis)")
    verdict("claude", [re.sub(r"sha256 [0-9a-f]{64}", "sha256 " + "0" * 64, l) for l in corps])
    dire(M.verdict_moteur("claude")[0] == "à rejouer", "4. empreinte de référence fausse : à rejouer")
    verdict("claude", [l.replace("équivalence : claude 9.9.8", "équivalence : codex 9.9.8") for l in corps])
    dire(M.verdict_moteur("claude")[0] == "à rejouer", "4. référence d'un autre moteur : à rejouer")
    verdict("claude", [l.replace("équivalence : claude 9.9.8", "équivalence : claude ../9.9.8") for l in corps])
    dire(M.verdict_moteur("claude")[0] == "à rejouer", "4. référence au nom piégé (..) : à rejouer")
    # une équivalence ne sert jamais de référence : un verdict qui renvoie à une version sans liste du dépôt est à rejouer
    verdict("claude", [l.replace("claude 9.9.8", "claude 9.9.7") for l in corps])
    dire(M.verdict_moteur("claude")[0] == "à rejouer", "4. référence à une version sans liste dans le dépôt (une autre équivalence) : à rejouer")
    verdict("claude", corps)

    # ── 5. liste exacte ajoutée au dépôt : l'alerte jaune disparaît, le verdict reste valable ──
    poser(L, "claude", "9.9.9", REF_CLAUDE)
    dire(M.verdict_moteur("claude")[0] == "admis", "5. liste exacte ajoutée : le verdict d'équivalence reste valable")
    dire(not any("équivalence" in x for _, _, x in M.alertes_moteurs()), "5. liste exacte ajoutée : l'alerte jaune disparaît")

    # ── 6. version installée sans verdict : alerte jaune « contrat à jouer », calculée en local ──
    versions["codex"] = "9.9.10"
    al = [(c, x) for c, _, x in M.alertes_moteurs() if "codex" in x]
    dire(any(c == "jaune" and "codex 9.9.10" in x and "version installée sans verdict : contrat à jouer" in x for c, x in al),
         f"6. version installée sans verdict : alerte jaune « contrat à jouer » — {al}")
    dire(M.verdict_moteur("codex")[0] == "jamais vu", "6. sans verdict : « jamais vu » (contrat joué avant le premier lancement, inchangé)")

sys.exit(1 if ko else 0)
