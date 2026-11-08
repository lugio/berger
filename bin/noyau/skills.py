"""Les méthodes (skills) d'un agent : liens .claude/skills et .agents/skills, refus d'une méthode qui cite le coffre ou un motif interdit.

Code déplacé de bin/berger (extensions, lot 1). Puis : une skill d'extension (extensions/skill/<nom>/actuelle) se donne comme une méthode
du catalogue (`skills =`) ; une méthode propre (skills-agent/) passe le même contrôle que le catalogue. Fonctions du CŒUR (regenerer les appelle) : hors de l'API, jamais données à
une vue, une famille ou un moteur. Dépendances nommées, aucun `import *`."""
import re
from noyau.config import BERGER, CONFIG, COFFRE, HOME
from noyau.agents import dossier
from noyau.lectures import dossier_skills, methode, skills_demandees
from noyau.extensions import skill_installee


def homonyme_ignore(nom):
    """Copie du catalogue masquée par la méthode du produit du même nom (signalée par regenerer), sinon None."""
    c = dossier_skills() / nom
    return c if methode(nom) != c and (c / "SKILL.md").is_file() else None


def motif_refus_skill(s):
    """Une méthode du catalogue ne doit citer ni le coffre ni un motif interdit (config.toml : skills.interdits, regex) :
    elle est lue par le modèle, et un agent en mur strict n'a pas à savoir où sont les secrets. -> motif ou None."""
    v = CONFIG.get("skills"); motifs = [(m, m) for m in (v.get("interdits", []) if isinstance(v, dict) else [])]
    motifs.append((re.escape(COFFRE.name), COFFRE.name))
    for f in sorted(p for p in s.rglob("*") if p.is_file()):
        try: t = f.read_text(errors="ignore")                                # un binaire (image) se lit aussi : rien n'y échappe
        except OSError: continue
        for m, nom_ in motifs:
            if re.search(m, t, re.I): return f"{f.relative_to(s)} cite « {nom_} »"
    return None


def lier_skills(a):
    d = dossier(a)
    for sous in (".claude/skills", ".agents/skills"):
        (d / sous).mkdir(parents=True, exist_ok=True)
        for l in (d / sous).iterdir():
            if l.is_symlink(): l.unlink()                                   # on ne supprime que des LIENS
    # ~/.claude/skills : partagé avec TOUS les agents, sauf `[skills] partager_utilisateur = false`. Claude ne le charge PAS
    # de lui-même chez un agent strict (--setting-sources project,local, mesuré le 08/10) : ce partage vient de ces liens.
    v = CONFIG.get("skills"); partager = not (isinstance(v, dict) and v.get("partager_utilisateur") is False)
    utilisateur = HOME / ".claude/skills"                                   # absent sur une installation neuve : aucun skill à partager
    for s in sorted(utilisateur.iterdir()) if partager and utilisateur.is_dir() else []:
        if (s / "SKILL.md").is_file(): (d / ".claude/skills" / s.name).symlink_to(s.resolve())
    for nom in skills_demandees(a):                                         # catalogue : seulement celles de SON rôle
        s = methode(nom)
        if re.fullmatch(r"[\w.-]+", nom) and not (s / "SKILL.md").is_file() and skill_installee(nom): s = skill_installee(nom)   # extension (extensions/skill/)
        if not re.fullmatch(r"[\w.-]+", nom) or not (s / "SKILL.md").is_file():
            print(f"⚠ {a} : méthode « {nom} » absente du catalogue {dossier_skills()} — non donnée"); continue
        ignore = homonyme_ignore(nom)
        if ignore and not (d / "skills-agent" / nom / "SKILL.md").is_file():  # sa méthode à soi prime de toute façon
            print(f"⚠ {a} : méthode « {nom} » — celle du produit ({s.relative_to(BERGER)}) prime ; homonyme du catalogue ignoré : {ignore}")
        motif = motif_refus_skill(s)
        if motif:
            print(f"⚠ {a} : méthode « {nom} » refusée ({motif}) — non donnée"); continue
        for sous in (".claude/skills", ".agents/skills"):
            cible = d / sous / nom
            if cible.is_symlink(): cible.unlink()
            cible.symlink_to(s.resolve())
    for s in sorted((d / "skills-agent").glob("*/SKILL.md")):
        motif = motif_refus_skill(s.parent)                                 # extensions lot 1 : contrôlée comme le catalogue (passait sans bruit)
        if motif:
            print(f"⚠ {a} : méthode propre « {s.parent.name} » (skills-agent/) refusée ({motif}) — non donnée"); continue
        for sous in (".claude/skills", ".agents/skills"):
            cible = d / sous / s.parent.name
            if cible.is_symlink(): cible.unlink()
            cible.symlink_to(s.parent)


__all__ = ('homonyme_ignore', 'motif_refus_skill', 'lier_skills')
