---
title: Dépannage
description: "Les réponses aux problèmes fréquents de Lacis, de l'installation à l'ouverture d'une enquête, et le journal à joindre pour signaler un bug."
---

Cette page rassemble les problèmes les plus fréquents et leur solution. Les messages entre guillemets sont ceux que Lacis affiche. Si votre problème n'y figure pas, [signalez-le](#signaler-un-bug) avec le journal de l'application.

## Installer et lancer Lacis

### Windows affiche « Windows a protégé votre ordinateur »

L'installateur de Lacis n'est pas encore signé, et Windows SmartScreen se méfie des programmes qu'il ne connaît pas. [Vérifiez d'abord votre téléchargement](/lacis/guide/installation/#vérifier-le-téléchargement), puis choisissez **Informations complémentaires**, et **Exécuter quand même**.

### Lacis ne démarre pas

Sous Linux, lancez `lacis` depuis un terminal : le message d'erreur s'y affiche. `lacis --version` vérifie que Lacis est bien installé et donne sa version.

Sous Linux comme sous Windows, ouvrez ensuite le [journal de l'application](#trouver-le-journal) : si Lacis a eu le temps de démarrer, l'erreur y est notée.

### Je ne trouve pas Lacis dans le menu de mon bureau

Installé avec pipx, Lacis n'a pas d'entrée dans le menu : lancez-le avec la commande `lacis`. Les paquets pour Debian, Fedora, Arch Linux et l'installateur Windows, eux, en ajoutent une.

## Chercher et étendre

### « Saisissez au moins 3 caractères pour rechercher. »

La recherche part à partir de trois caractères. Pour un numéro SIREN ou SIRET, saisissez-le en entier : 9 ou 14 chiffres, avec ou sans espaces.

### L'entreprise que je cherche n'apparaît pas

La liste n'affiche que les 25 premiers résultats. Précisez la recherche, avec la dénomination complète, la ville, ou mieux, le numéro SIREN. Une entreprise créée très récemment peut aussi ne pas encore figurer dans le registre.

### « Le service … ne répond pas. Vérifiez votre connexion à Internet, puis réessayez. »

Lacis n'a pas pu joindre le registre ou le BODACC. Vérifiez votre connexion, et le pare-feu ou le proxy de votre réseau : Lacis doit pouvoir joindre `recherche-entreprises.api.gouv.fr` et `bodacc-datadila.opendatasoft.com`.

### « Le service … limite le nombre de requêtes. » ou « … est momentanément indisponible »

Lacis espace déjà ses requêtes pour respecter les limites de chaque service, et réessaie de lui-même après une erreur passagère. Si le message s'affiche malgré tout, le service est surchargé ou en maintenance : patientez quelques minutes, puis relancez la recherche ou l'extension. Ce que Lacis avait déjà collecté est conservé.

### Une entreprise n'a pas de dirigeant ou pas d'adresse

Si elle vient d'être ajoutée, elle n'est pas encore étendue : choisissez **Étendre** sur sa fiche. Si elle l'est déjà, ses dirigeants ou son adresse sont sans doute non diffusibles : certaines personnes ont demandé que leurs informations ne soient pas publiées, et Lacis respecte ce choix. Sa fiche donne alors le nombre de dirigeants non diffusibles, par exemple « 1 dirigeant non diffusible », sans rien dire d'eux.

### Une extension s'est arrêtée avant la fin

Une extension n'ajoute jamais plus de 500 nouvelles entités, et le signale : « Extension arrêtée à 500 nouvelles entités, la limite fixée. » Étendez ensuite une à une les pistes qui vous intéressent, dans la colonne « À examiner ».

### « Seuls les 100 premiers résultats sur … ont été lus »

Une personne ou une adresse compte plus de 100 résultats dans le registre : un nom très répandu, ou une adresse de domiciliation. Lacis n'en lit que les 100 premiers, et les mandats ou les entreprises au-delà manquent au graphe. L'entité reste parmi les pistes, dans la colonne « À examiner », pour vous le rappeler. Dans cette version, une nouvelle extension relit les mêmes résultats.

### Les informations semblent dépassées

Lacis garde chaque réponse 24 heures en cache, pour ménager les services publics. Pour une réponse fraîche, choisissez **Étendre à nouveau** sur la fiche de l'entité, ou **Rafraîchir** sur ses annonces BODACC.

### J'ai confirmé un homonyme par erreur

Tant que l'enquête est ouverte, **Édition › Annuler la décision d'homonyme**, ou <kbd>Ctrl</kbd>+<kbd>Z</kbd>, défait la décision. Une fois l'enquête fermée, la décision est acquise : cette version de Lacis ne permet plus de l'annuler.

### Le graphe est illisible

Choisissez **Réorganiser le graphe**, <kbd>Ctrl</kbd>+<kbd>Maj</kbd>+<kbd>R</kbd>, puis **Ajuster le graphe à la fenêtre**, <kbd>Ctrl</kbd>+<kbd>0</kbd>. Le bouton **Filtres** masque les types d'entités dont vous n'avez pas besoin, ou ne garde que les entités signalées.

## Signaux d'alerte

### La colonne « À examiner » affiche « Signaux indisponibles »

Votre fichier `signals.toml` contient une erreur. Le message qui suit donne le fichier, le réglage en cause et ce qui est attendu. Corrigez-le en vous aidant de la page sur les [signaux d'alerte](/lacis/guide/signaux/#régler-les-seuils), ou renommez le fichier pour revenir aux réglages par défaut, puis fermez et rouvrez l'enquête.

## Enquêtes

### « L'enquête … a été enregistrée par une version plus récente de Lacis »

L'enquête vient d'un ordinateur où Lacis est plus récent. [Mettez Lacis à jour](/lacis/guide/installation/#mettre-à-jour) pour l'ouvrir : la nouvelle version lit toutes les enquêtes des versions précédentes.

### « La base de données de cette enquête est illisible. »

Le fichier de l'enquête est endommagé, par exemple après une copie faite pendant que Lacis l'utilisait, ou un disque plein. Restaurez votre dernière [sauvegarde](/lacis/guide/donnees/#sauvegarder-une-enquête). Sans sauvegarde, [signalez le problème](#signaler-un-bug) sans joindre le fichier, qui contient des données personnelles.

### « Lacis n'a pas pu écrire dans le dossier des enquêtes »

Lacis n'a pas pu créer ou modifier une enquête. La raison suit, entre parenthèses : le plus souvent, un disque plein ou un dossier en lecture seule. Libérez de la place, ou vérifiez les droits sur le [dossier des enquêtes](/lacis/guide/donnees/#où-lacis-range-ce-quil-écrit).

### « Impossible de supprimer l'enquête »

Lacis place les enquêtes supprimées dans la corbeille du système, et ce système n'en a pas. Fermez Lacis et supprimez vous-même le [dossier de l'enquête](/lacis/guide/donnees/#supprimer-une-enquête).

### Mes enquêtes du mode démo ont disparu

C'est voulu : le mode démo travaille dans un dossier temporaire, supprimé à la fermeture de Lacis. Pour garder une enquête, lancez Lacis sans `--demo`.

## « Erreur inattendue »

Lacis a rencontré une erreur qu'il ne sait pas traiter. L'action en cours n'a pas abouti, mais vous pouvez continuer à travailler : vos enquêtes ne sont pas touchées. La fenêtre donne le chemin du journal où l'erreur est détaillée, et son bouton **Ouvrir le dossier du journal** l'ouvre. Signalez cette erreur : c'est un bug.

## Trouver le journal

Lacis tient un journal, `lacis.log`, qui note son démarrage, les avertissements et les erreurs :

- sous Linux : `~/.local/state/Lacis/Lacis/logs/lacis.log` ;
- sous Windows : `%LOCALAPPDATA%\Lacis\Lacis\State\logs\lacis.log`.

Les fichiers `lacis.log.1` à `lacis.log.3`, à côté, sont les journaux précédents.

## Signaler un bug

**Aide › Signaler un problème…** ouvre la page des signalements de Lacis sur GitHub. Le formulaire, en anglais, demande :

- ce qui s'est passé, et ce que vous attendiez ;
- les étapes pour reproduire le problème ;
- la version de Lacis, donnée par **Aide › À propos de Lacis** ;
- votre système et la façon dont vous avez installé Lacis.

Joignez les dernières lignes du journal, celles qui entourent l'erreur. Relisez-les avant de les publier : un signalement est public. Retirez-en les données personnelles, comme votre nom d'utilisateur dans les chemins de fichiers, ou le nom d'une entreprise ou d'une personne de votre enquête. Ne joignez jamais le fichier d'une enquête.

Si le problème se reproduit avec le [mode démo](/lacis/guide/demonstration/), décrivez-le avec ses entreprises fictives : c'est le signalement le plus facile à suivre.
