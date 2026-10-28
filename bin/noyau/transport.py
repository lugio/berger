"""Transport privé : entrée sur stdin bornée et exécution de sous-processus sans texte d'agent en argument (courtier/outils/_transport.py).

Code déplacé de bin/berger (modulaire, lot 1) : aucun comportement changé. Les refus d'entrée de `entree_privee` lèvent `Refus` (sous-classe de ValueError : les appelants qui attrapent ValueError sont inchangés)."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path
from noyau.config import *
from noyau.ecarts import Refus


_spec_transport = importlib.util.spec_from_file_location('berger_transport', Path(__file__).resolve().parent.parent.parent / 'courtier/outils/_transport.py')
_transport = importlib.util.module_from_spec(_spec_transport); _spec_transport.loader.exec_module(_transport)



def entree_privee():
    """Consigne sur stdin uniquement, bornée ; aucune valeur dans les diagnostics."""
    maximum = 1024 * 1024
    contenu = sys.stdin.buffer.read(maximum + 1)
    if len(contenu) > maximum: raise Refus("entrée privée trop grande")
    try: return contenu.decode("utf-8")
    except UnicodeDecodeError: raise Refus("entrée privée UTF-8 requise") from None


transport = _transport                       # executer, executer_shell, lancer, ecrire_configuration (courtier/outils/_transport.py)


__all__ = ('transport', '_spec_transport', '_transport', 'entree_privee',)
