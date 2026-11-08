"""Lecture d'un texte d'agent.conf, partagée par bin/berger (noyau.agents) et le courtier (outils/_portes.py : chemins de consigne)."""


def conf_texte(texte):
    """Les réglages `cle = valeur` d'un texte d'agent.conf (`#` = commentaire), sans les défauts."""
    c = {}
    for ligne in texte.splitlines():
        if "=" in ligne and not ligne.lstrip().startswith("#"):
            k, v = ligne.split("=", 1); c[k.strip()] = v.split("#")[0].strip()
    return c
