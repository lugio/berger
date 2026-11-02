# L4b — transports restants

Le go de la mission couvre ce sujet et le cœur du courtier. L4a est fusionné et installé ; main a été intégré sans conflit. Herdr reste inchangé jusqu’à la recette du propriétaire.

Premier changement : `berger-outil outil verbe --stdin` lit un tableau JSON UTF-8 de cinq textes au plus, borné à un Mio. Le repli `--fichier .transport/requete.json` consomme un fichier exclusif 600 dans un dossier 700, relatif et neutre, sans suivre de lien, puis le supprime même si le JSON est invalide. Les arguments positionnels supplémentaires sont refusés. Les droits, validations, limites et le traitement du courtier restent identiques. Les demandes sont déposées exclusivement en 600 dans les dossiers de courrier 700, sans suivre de lien ; lecture des réponses bornée et sans suivre de lien. Les fichiers du client sont nettoyés au succès, à l'erreur et à l'interruption ; une demande déjà prise en charge reste la responsabilité du courtier, sans annulation implicite d'une action.

Tests rouges puis verts : transmission exacte, absence du témoin dans cmdline, refus de l'ancien transport, limites, permissions, liens et nettoyage. Toutes les valeurs nouvelles d'essai sont en minuscules sans chiffre.

Étapes suivantes : journal sur stdin, wrappers imbriqués, corps curl, instructions système, chemins privés et transport Herdr. Le schéma embarqué Herdr documente agent.prompt sur socket ; sa recette réelle reste à mesurer. Aucune admission globale déduite des seuls moteurs factices.

Avant la prochaine demande de fusion : verify, tests, pret, puis verifier-depot avec la configuration réelle, sans chercher à lire le coffre depuis le bac de l'agent.

Revue prioritaire : trois rouges reproduits. Les instructions du mur ouvert passent par un profil Codex généré 600, persistant comme configuration et remplacé atomiquement ; aucun texte dans argv. La vraie CLI `debug prompt-input` charge ce profil. La capture de cmdline utilise les vraies fonctions args_moteur et _args_moteur ; demander sans argument affiche un usage. Le chemin -C et les fichiers Claude restent dans l’inventaire des chemins privés, sans admission globale.

Appels imbriqués : lancement Python à code fixe ; chemin du programme, tableau d’arguments et entrée métier dans une enveloppe JSON sur stdin, bornée à un Mio. Les contrôles métier et autorisations restent dans les fonctions habituelles. Le marqueur interne de transport ne constitue aucune autorisation. Les CLI publiques mission, equipe, projet et message-deposer refusent l’ancien transport ; `berger --stdin` lit leur tableau JSON.

Scripts : fichier anonyme 600 créé dans un dossier 700, détaché immédiatement ; stdin reste indépendant. Pour le bac existant, montage du script en lecture seule sous un nom neutre dans son /dev ; espaces de noms, masques, réseau et réglages git inchangés. Les fichiers et descripteurs sont fermés même en exception ; le noyau ferme les fichiers anonymes en interruption.

Couverture : CLI complète sans fonctions remplacées ; dépôt, mission, équipe, délégation, notification et renvoi ; commandes, copie, pile et crochet ; transmission et droits. Le fichier système Claude généré rejoint un dossier 700 et un fichier 600 atomique. Les chemins privés restants des moteurs, services et Herdr sont inventoriés sans admission globale dans cette livraison.

Revue indépendante : trois rouges supplémentaires couvrent le dossier de profil préexistant trop ouvert, le dossier symbolique et le profil symbolique. Le profil Codex utilise le même écrivain privé que Claude : ouverture du dossier sans lien, propriétaire contrôlé, mode 700 rétabli, fichier exclusif 600 et remplacement par descripteur. Le nettoyage en échec préserve la configuration précédente.

Conservation des réglages utilisateur : une sonde réelle a montré qu’une surcharge vide du profil écrasait les instructions de base. Test rouge via la CLI complète puis correction : sans instruction ajoutée par Berger, le champ est omis et le profil hérite de la configuration de base, comme avant. La sonde réelle `codex debug prompt-input` contrôle aussi cet héritage sans appel modèle.
