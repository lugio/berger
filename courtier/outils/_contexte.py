# -*- coding: utf-8 -*-
"""Le contexte d'un outil du courtier (qui demande, son dossier) appartient à l'APPEL, pas à l'objet outil — pas un type d'outil en soi.

Vécu le 12/10/2026 : le courtier traite chaque demande dans son propre fil, mais posait le contexte sur l'objet outil,
UNIQUE et partagé par tous les fils ; un appel long (demander-fusion : fetch, verify) relisait self.contexte après qu'un
autre agent l'avait réécrit → demandes de fusion au nom du mauvais développeur, commandes dans la copie d'un autre.

Usage, au niveau de la classe : `contexte = ContexteDeLAppel({})` (ou None). `o.contexte = {...}` (le courtier, un test)
range la valeur pour le SEUL fil qui la pose ; `o.contexte` rend celle de ce fil, sinon la valeur par défaut."""
import copy, threading


class ContexteDeLAppel:
    def __init__(self, defaut=None):
        self.defaut = defaut

    def __set_name__(self, cls, nom):
        self.cle = f"_{nom}_par_fil"

    def _fils(self, o):
        return o.__dict__.setdefault(self.cle, threading.local())       # setdefault : atomique, un seul local par objet

    def __get__(self, o, cls=None):
        if o is None: return self
        return getattr(self._fils(o), "valeur", copy.copy(self.defaut))  # copie : un fil ne modifie jamais la valeur par défaut

    def __set__(self, o, valeur):
        self._fils(o).valeur = valeur
