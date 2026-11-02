# -*- coding: utf-8 -*-
"""Formes connues de clés, pour attraper une clé qui ne serait PAS dans le coffre (détection même sans valeur connue du coffre).
Une seule définition, lue par le courtier (contient_secret, ses journaux) et par la connexion visible du propriétaire
(_web_connexion.py, son journal des refus) : déplacée ici depuis courtier/courtier au renvoi n° 99, jamais recopiée."""
import re

MOTIFS_CLES = re.compile(r"sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
                         r"|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|(?i:bearer)\s+[A-Za-z0-9._~+/=-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.")
