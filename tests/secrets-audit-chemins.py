#!/usr/bin/env python3
"""`berger secrets audit` lit les transcriptions Claude des agents QUEL QUE SOIT le chemin de l'installation (correctif de sécurité, 07/11/2026).

Claude range une transcription sous ~/.claude/projects/<chemin du dossier, chaque caractère non alphanumérique remplacé par « - »>. L'audit
cherchait sous <chemin, seuls les « / » remplacés> : une installation dont le chemin contient « _ » ou « . » n'avait pas ses transcriptions
auditées (une valeur du coffre copiée dans une conversation n'était pas vue). Installation JETABLE au chemin « ber_ger.essai », coffre fictif
(valeur construite à l'exécution). Vérifie :
 1. la transcription rangée comme Claude la range est auditée et nommée par la CLÉ, jamais la valeur ;
 2. l'audit ne perd rien : le dossier examiné jusqu'ici (seuls les « / » remplacés) l'est toujours ;
 3. une installation au chemin sans « _ » ni « . » : un seul dossier, compté une fois (pas de zone en double) ;
 4. une seule règle : noyau/lectures.py `dossier_transcriptions`, employée par l'audit et par les lectures (aucune règle recopiée).
Usage : python3 tests/secrets-audit-chemins.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import atexit, json, os, random, re, shutil, string, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


SECRET = "valeur" + "".join(random.choice(string.ascii_letters) for _ in range(24))


def audit(nom_installation):
    """Installation jetable à <tmp>/<nom_installation> ; → (code, sortie, dossier de Claude, dossier d'avant, maison)."""
    m = Path(tempfile.mkdtemp(prefix="audit")); atexit.register(shutil.rmtree, m, True); i = m / nom_installation
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text(json.dumps({"service": {"jeton": SECRET}}))
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    (i / "agents/chef/memory").mkdir(parents=True); (i / "agents/chef/agent.conf").write_text("nom = Chef\nheures = aucune\nmoteur = claude\n")
    projets = m / ".claude/projects"
    claude = projets / (re.sub(r"[^A-Za-z0-9]", "-", str(i / "agents/chef")))          # comme Claude range la conversation de l'agent
    avant = projets / (str(i / "agents/chef").replace("/", "-") + "-ancien")           # ce que l'audit examinait jusqu'ici
    for d, n in ((claude, "claude.jsonl"), (avant, "avant.jsonl")):
        d.mkdir(parents=True, exist_ok=True); (d / n).write_text(json.dumps({"texte": SECRET}) + "\n")
    env = {k: v for k, v in os.environ.items() if k != "BERGER_AGENT"}
    env.update(BERGER_DIR=str(i), HOME=str(m))
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "secrets", "audit"], env=env, capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout + r.stderr, claude, avant, m


c, o, claude, avant, m = audit("ber_ger.essai")
dire(c == 1 and "claude.jsonl" in o and "service.jeton" in o,
     "chemin avec « _ » et « . » : la transcription rangée comme Claude la range est auditée, nommée par la clé" + ("" if "claude.jsonl" in o else f" — {' '.join(o.split())[-240:]}"))
dire("avant.jsonl" in o, "l'audit ne perd rien : le dossier examiné jusqu'ici (seuls les « / » remplacés) l'est toujours")
dire(SECRET not in o, "aucune valeur du coffre dans la sortie de l'audit")

c, o, claude, avant, m = audit("installation")
z = re.search(r"\((\d+) zones\)", o)
dire(c == 1 and "claude.jsonl" in o and o.count("claude.jsonl") == 1, "chemin sans « _ » ni « . » : la transcription est auditée une seule fois")
dire(z is not None and int(z.group(1)) == 3,
     f"chemin sans « _ » ni « . » : aucune zone en double ({z.group(1) if z else '?'} zones ; attendu 3 : l'installation et ses deux dossiers de transcriptions)")

# 5. Ordre de la sortie : la même sur tous les systèmes de fichiers (correctif CI, 08/11/2026). L'audit parcourait les dossiers dans l'ordre
#    du système de fichiers (rglob) : la liste des fichiers changeait d'une machine à l'autre (runner GitHub ≠ poste) et l'équivalence
#    « deux fichiers, nommés par la clé » rendait un ordre différent de la référence. Fuites posées dans un ordre MÉLANGÉ (12 noms) :
#    la sortie doit être triée par chemin, comme la liste de « Par clé ».
m = Path(tempfile.mkdtemp(prefix="auditordre")); atexit.register(shutil.rmtree, m, True); i = m / "installation"
_produit.copier(SRC, i, ("bin", "courtier", "commun"))
(m / "coffre.json").write_text(json.dumps({"service": {"jeton": SECRET}}))
(i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
(i / "agents/chef/memory").mkdir(parents=True); (i / "agents/chef/agent.conf").write_text("nom = Chef\nheures = aucune\nmoteur = claude\n")
noms = ["k", "c", "h", "a", "l", "e", "j", "b", "i", "d", "g", "f"]               # ordre de création fixe, ni croissant ni décroissant
for n in noms: (i / f"agents/chef/memory/fuite-{n}.md").write_text(f"note : {SECRET}\n")
env = {k: v for k, v in os.environ.items() if k != "BERGER_AGENT"}; env.update(BERGER_DIR=str(i), HOME=str(m))
r = subprocess.run([sys.executable, str(i / "bin/berger"), "secrets", "audit"], env=env, capture_output=True, text=True, timeout=300)
vus = re.findall(r"fuite-([a-z])\.md", r.stdout)
dire(r.returncode == 1 and sorted(noms) == sorted(vus), f"ordre : les 12 fuites sont nommées (code {r.returncode}, {len(vus)} vues)")
dire(vus == sorted(vus), f"ordre : la liste des fichiers est triée par chemin, quel que soit l'ordre du système de fichiers ({''.join(vus)})")
dire(SECRET not in r.stdout + r.stderr, "ordre : aucune valeur du coffre dans la sortie")

lect = (SRC / "bin/noyau/lectures.py").read_text(encoding="utf-8"); coeur = (SRC / "bin/berger").read_text(encoding="utf-8")
dire("def dossier_transcriptions(" in lect, "noyau/lectures.py : une fonction dossier_transcriptions, la règle de Claude écrite une fois")
recopies = [f for f, t in (("bin/berger", coeur), ("bin/noyau/lectures.py", re.sub(r"\ndef dossier_transcriptions\(.*?\n\n", "\n", lect, flags=re.S))) for _ in re.finditer(r'\.claude/projects"\)? */ *re\.sub|glob\(re\.sub', t)]
dire(not recopies, f"aucune règle recopiée : aucun re.sub pour un dossier de transcriptions hors dossier_transcriptions ({recopies or 'aucune'})")

print(f"==== {ko} échec(s)")
sys.exit(1 if ko else 0)
