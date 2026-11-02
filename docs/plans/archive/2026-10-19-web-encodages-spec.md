# Masquage des encodages de session et environnement web MCP

Périmètre accepté : réponses de session prêtée et shell de l'enveloppe web.
Cause racine : les variantes comparées ne comprenaient ni Base64 ni hexadécimal,
ni pourcentage intégral ; le shell intermédiaire conservait SHLVL lors de exec.

Pour les valeurs connues d'au moins huit caractères, supprimer les encodages
Base64 standard et URL-safe, avec ou sans remplissage, pourcentage intégral et
hexadécimal minuscule/majuscule dans le corps et les en-têtes. Conserver le
réassemblage HTTP avant filtrage et le recalcul de Content-Length. Retirer
SHLVL via env -u après exec du shell (bash recrée SHLVL même après unset) sans étendre la liste permise du contrat (3).

Preuves : un test rouge par représentation, corps chunked et lectures fragmentées,
en-têtes, longueur recalculée ; test rouge exécutant le shell réel devant un
serveur factice qui ne rapporte que la présence de SHLVL. Les sorties de tests
ne publient aucune valeur de cookie. Aucune connexion extérieure.

Limite : pas de décodage universel d'obfuscations ; la protection réelle reste
le domaine seul, la lecture seule, l'échéance et la déconnexion.

## Contre-revue : casse mixte et pouvoir discriminant des tests

Cause racine : seules les chaînes hexadécimales tout en minuscules ou tout en
majuscules étaient générées ; les combinaisons des deux traversaient le filtre.
Les motifs hexadécimaux sont désormais comparés sans tenir compte de la casse,
après réassemblage des lectures et chunks. Le contrôle de non-reconstitution
et le filtrage des noms d'en-têtes utilisent aussi cette comparaison.

La première fixture Base64 ne garantissait ni les caractères spécifiques des
alphabets ni un remplissage. La fixture utilise maintenant une valeur connue du
stockage local, en lettres Unicode minuscules, et un cookie HTTP ASCII nommé
temoin. Chaque test Base64 exige les caractères plus, barre oblique et égal en
standard et quatre formes distinctes (deux alphabets, avec/sans remplissage).
Aucune valeur d'essai n'est publiée. Deux tests rouges ont précédé ces corrections.
