# Messages Herdr sans texte dans les arguments

`berger parler <agent> --stdin [--moteur m] [--de qui] [--sans-echange]` lit un texte UTF-8 borné à un Mio. Exemple : `berger parler <agent> --stdin < message.md`. La syntaxe positionnelle est refusée, y compris dans les appels internes. Les appelants internes placent le texte dans `input`, et conservent les options dans la liste d'arguments.

Cause racine : le lanceur interne protégeait le premier processus, mais `parler` et la remise du courrier reconstruisaient ensuite `herdr agent prompt TARGET TEXT`. Le texte réapparaissait dans les argv du dernier processus.

Herdr `agent prompt --help` ne propose pas stdin. Son schéma (`herdr api schema --json`, `AgentPromptParams`) expose `agent.prompt` avec `target` et `text`. Ces deux chemins utilisent désormais l'API socket existante : aucun sous-processus Herdr ne reçoit le corps. Un refus, une socket absente ou une réponse invalide ne provoquent aucun repli dans le terminal ou la CLI ; les messages restent en attente, dans leur ordre initial. Les détails d'erreur du serveur ne sont jamais reproduits.

`tests/argv-herdr.py` lance la vraie entrée Berger et capture `/proc/self/cmdline` du processus Berger et du récepteur factice. Il couvre aussi le lanceur interne et un renvoi de fusion jusqu'à la requête finale. Seule la socket est simulée dans ces tests : ce n'est pas la preuve du socket Herdr réel.

Les anciennes suites métier utilisent un serveur AF_UNIX factice (`_herdr_api_factice.py`), sans texte dans les argv de leur récepteur. Elles annoncent NON JOUÉ si le bac refuse AF_UNIX ; elles doivent être rejouées par la porte extérieure.

La sonde manuelle `tests/sonde-herdr-argv.py <agent> [moteur]`, avec `BERGER_DIR` explicite vers l'installation de test, charge le code de la copie sans l'installer. Le propriétaire doit choisir un agent réel au repos. Elle envoie un message technique, contrôle les argv du noyau du processus émetteur et vérifie l'acceptation par le vrai socket, sans afficher le témoin. Elle ne prouve pas la réponse du modèle. Pas de relance ni de création d'agent.

Après revue : le corps du courrier en attente est transmis tel quel, sans split/join ni suppression des espaces. Les tests comparent le texte intégral (en-tête compris), pour messages ordinaires et résumés de délégation : multiligne, tabulations, espaces multiples, accents et gros texte. Le même jeu vérifie parler sur stdin. Le vérificateur rejette explicitement troncature, normalisation et ajout ; aucun contenu d’essai n’est affiché, même au rouge.

Les anciens messages dont le corps JSON n’est pas une chaîne sont convertis par `str(texte or "")` avant concaténation : null devient vide, les autres valeurs non vides deviennent du texte. Cette conversion ne normalise aucun espace ni retour à la ligne des chaînes. La remise et l’archivage sont testés avec null, nombre, liste et objet.
