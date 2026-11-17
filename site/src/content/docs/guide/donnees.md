---
title: Vos données
description: "Où Lacis range les enquêtes, les réglages et le journal sous Linux et Windows, ce qu'il envoie sur le réseau, et comment sauvegarder, déplacer ou supprimer une enquête."
---

Lacis fonctionne entièrement sur votre ordinateur. Il n'a pas de compte, pas de serveur et ne mesure pas votre usage : vos enquêtes ne quittent jamais votre machine. Cette page dit où il écrit, et comment garder la main sur ce qu'il écrit.

## Ce que Lacis envoie sur le réseau

Lacis n'interroge que deux services publics, et seulement quand vous le lui demandez :

- l'[API Recherche d'entreprises](https://recherche-entreprises.api.gouv.fr/), pour chaque recherche et chaque extension ;
- l'API du [BODACC](https://www.bodacc.fr/), pour les annonces d'une entreprise.

Ces requêtes contiennent ce que vous cherchez : une dénomination, un numéro SIREN, une adresse, ou le nom et les prénoms d'un dirigeant que vous étendez. Elles se présentent comme venant de Lacis, avec son numéro de version, et ne contiennent rien d'autre sur vous ni sur votre enquête. Comme toute requête sur Internet, elles font connaître votre adresse IP au service interrogé.

Le mode démo n'envoie aucune requête.

Ce site, lui, mesure son audience sans cookie ni donnée personnelle : la page [Confidentialité du site](/lacis/confidentialite/) dit ce qu'il compte.

## Où Lacis range ce qu'il écrit

Sous Linux :

- les enquêtes : `~/.local/share/Lacis/Lacis/investigations/` ;
- les réglages de l'interface : `~/.config/Lacis/Lacis.ini` ;
- les seuils des signaux : `~/.config/Lacis/Lacis/signals.toml` ;
- le journal de l'application : `~/.local/state/Lacis/Lacis/logs/`.

Sous Windows :

- les enquêtes : `%LOCALAPPDATA%\Lacis\Lacis\investigations\` ;
- les réglages de l'interface : `%APPDATA%\Lacis\Lacis.ini` ;
- les seuils des signaux : `%LOCALAPPDATA%\Lacis\Lacis\signals.toml` ;
- le journal de l'application : `%LOCALAPPDATA%\Lacis\Lacis\State\logs\`.

Sous Linux, ces dossiers suivent les variables `XDG_DATA_HOME`, `XDG_CONFIG_HOME` et `XDG_STATE_HOME` quand elles sont définies. Sous Windows, collez le chemin dans la barre d'adresse de l'Explorateur de fichiers : `%LOCALAPPDATA%` et `%APPDATA%` y sont remplacés par vos dossiers.

Les **enquêtes** ont chacune leur dossier, au nom de l'enquête, avec un seul fichier : `investigation.sqlite3`. Ce fichier contient tout : la question, les entités et les liens, les réponses brutes et leurs empreintes, les annonces BODACC, le journal de collecte, les décisions sur les homonymes, les signaux calculés et la place des entités dans le graphe.

Les **réglages de l'interface** retiennent le thème, la taille et la position de la fenêtre, la largeur des colonnes et l'état de la colonne « À examiner ». Supprimer ce fichier rend à Lacis son apparence par défaut, sans toucher aux enquêtes.

Le fichier des **seuils des signaux** n'existe que si vous l'avez créé : la page sur les [signaux d'alerte](/lacis/guide/signaux/#régler-les-seuils) explique son contenu.

Le **journal de l'application**, `lacis.log`, note le démarrage de Lacis, avec sa version, votre système et le chemin du journal, ainsi que les avertissements et les erreurs inattendues. Il n'enregistre pas le contenu de vos enquêtes, mais le détail d'une erreur peut citer ce que Lacis était en train de traiter. Au-delà de 5 Mo, il passe le relais à un nouveau fichier ; Lacis garde les trois précédents, `lacis.log.1` à `lacis.log.3`.

Le **mode démo** range ses enquêtes dans un dossier temporaire, `lacis-demo-` suivi de caractères au hasard, dans le dossier temporaire du système. Lacis le supprime à sa fermeture. Le mode démo partage en revanche les réglages de l'interface et le journal.

## Sauvegarder une enquête

Pour sauvegarder une enquête, copiez son dossier, par exemple sur un disque externe. Fermez Lacis avant, pour copier un fichier que rien n'est en train d'écrire.

Une sauvegarde contient les mêmes données personnelles que l'enquête : rangez-la avec le même soin, et supprimez-la quand vous supprimez l'enquête.

## Déplacer une enquête vers un autre ordinateur

1. Fermez Lacis sur les deux ordinateurs.
2. Copiez le dossier de l'enquête dans le dossier des enquêtes de l'autre ordinateur, en gardant son nom. Si ce dossier n'existe pas encore, créez-le, ou lancez Lacis une première fois.
3. Lancez Lacis : l'enquête apparaît sur l'écran « Enquêtes ».

Une enquête s'ouvre avec la même version de Lacis ou une version plus récente, qui la met à jour à l'ouverture. Une version plus ancienne refuse de l'ouvrir et demande de mettre Lacis à jour. Le même fichier passe de Linux à Windows et inversement.

Pour la renommer, utilisez **Modifier le nom ou la question…** dans le menu **Actions** de sa carte, plutôt que de renommer le dossier à la main.

## Supprimer une enquête

Sur l'écran « Enquêtes », ouvrez le menu **Actions** de la carte de l'enquête, choisissez **Supprimer…**, puis **Placer dans la corbeille**. L'enquête rejoint la corbeille du système avec ses preuves et son journal : vous pouvez l'en sortir tant que la corbeille n'est pas vidée. Pour l'effacer pour de bon, videz la corbeille.

Si le système n'a pas de corbeille, Lacis le signale et ne supprime rien. Fermez alors Lacis et supprimez vous-même le dossier de l'enquête.

## Désinstaller Lacis

Désinstaller Lacis, avec le gestionnaire de paquets de votre distribution ou depuis **Paramètres › Applications** sous Windows, retire le programme mais garde vos enquêtes, vos réglages et le journal : vous les retrouvez si vous réinstallez Lacis.

Pour effacer toute trace de Lacis, supprimez aussi ces dossiers, après avoir sauvegardé les enquêtes que vous voulez garder :

- sous Linux : `~/.local/share/Lacis/`, `~/.config/Lacis/` et `~/.local/state/Lacis/` ;
- sous Windows : `%LOCALAPPDATA%\Lacis\` et `%APPDATA%\Lacis\`.
