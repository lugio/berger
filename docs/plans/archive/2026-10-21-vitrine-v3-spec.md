# Vitrine V3 — entrée bilingue du dépôt

Lot L7 autorisé dans la mission de refonte, à présenter après V2. Objectif : README anglais de 150 à 220 lignes, README français de même structure, lisibles sans parcourir le manuel complet.

Contenu : logo choisi par le propriétaire, accroche exacte « Your agents. Your methods. Your choice of engine. », quatre badges locaux statiques (MIT, Python 3.11+, Linux, Herdr), Quick start fondé sur les commandes existantes, tableau Features vers le manuel, Safety et limites, How it works avec schéma généré, Documentation, Removal, Contributing et License. Pas de section Screenshots, ni promesse de service ou d’installeur absent.

Le manuel français reste la référence. Les unités fournies supposent un checkout dans ~/berger et Herdr dans ~/.local/bin ; ces hypothèses sont explicites. Le retrait est manuel, avec arrêt des unités réellement activées et retrait du plugin local berger.reprise selon l’aide de la version de Herdr. Aucun verbe de désinstallation n’est inventé.

Architecture : README.md et README.fr.md partagent les mêmes sections ; docs/scripts/schema.py écrit seulement les blocs délimités du schéma dans les deux fichiers, ou les vérifie avec --check. Texte du schéma et badges locaux sans ressource distante. Les scripts et tests n’appellent aucun service.

Logo : choix explicite reçu via master : variante 03 chien couché et mouton, refaite en couleur par le propriétaire. Le SVG fourni est conservé tel quel dans docs/assets/berger.svg : 2 925 octets, SHA-256 73326d21439a849742d8f08594216bc684ffdfcddda22ef9840be45a8182005b. Le même médaillon apparaît dans les deux README en clair et en sombre, sans picture ni variante de thème. Aucun autre logo n’entre au dépôt ; aucune page ni favicon distinct n’est prévu dans ce lot.

Tests d’abord : fichiers et sections attendus, 150–220 lignes, structure bilingue, liens locaux, absence de placeholder et de section Screenshots, badges autonomes et absence de badge de sécurité, schémas égaux à la génération déterministe (deux passages identiques), mutation d’un bloc détectée, commandes citées existantes, logo SVG autonome. Une seule demande de fusion après V2, portes verify/tests/pret vertes et contrôle des marques par master.

Décision de validation : communaute.py conserve ses 30 contrôles légers mais ne rejoue plus le clone frais dans la porte locale ; clone-frais.sh reste inchangé, manuel et appelé en CI, avec un test de non-rejeu et de détection des fichiers invalides ; aucun délai ni autre contrôle retiré, blocage si la porte tests dépasse 1 300 s.

Refus : aucun bin/ ni courtier/, aucune capture, aucun réseau ou publication, aucune étiquette ni installation. Seul le fichier exact validé est intégré.
