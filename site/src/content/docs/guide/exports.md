---
title: Exporter une enquête
description: "Exporter une enquête entière ou la vue filtrée du graphe en rapport Markdown, lisible sans Lacis, en fichier JSON qui garde la provenance de chaque fait, ou en coffre Obsidian de notes liées."
---

Un export sort votre enquête de Lacis pour la transmettre, l'archiver ou la traiter avec d'autres outils. Il ne modifie jamais l'enquête : vous pouvez exporter aussi souvent que vous le voulez.

## Ouvrir la fenêtre d'export

Ouvrez l'enquête, puis choisissez **Fichier › Exporter**, et le format voulu : **Rapport Markdown…**, **JSON…** ou **Obsidian…**. La fenêtre « Exporter l'enquête » s'ouvre, avec trois choix :

- **Format** : le format du fichier, que vous pouvez encore changer ;
- **Contenu** : toute l'enquête, ou seulement la vue filtrée ;
- **Destination** : le fichier à écrire.

Le bouton **Exporter** écrit le fichier, et Lacis confirme l'export par une notification qui donne son nom.

## Choisir le contenu

**Toute l'enquête** exporte chaque entité, chaque lien et chaque signal, même ceux que les filtres du graphe cachent.

**La vue filtrée** n'exporte que les entités que le graphe montre, avec les liens dont les deux bouts sont montrés et les signaux de ces entités. Elle suit tous les filtres : types d'entités, entités signalées seulement, tag et verdict. Le choix indique combien d'entités chacun exporte. Sans filtre actif, la vue filtrée est grisée, puisqu'elle serait identique à l'enquête entière.

## Choisir la destination

Lacis propose un fichier au nom de l'enquête dans votre dossier Documents. Modifiez le chemin dans le champ, ou choisissez le fichier avec le bouton **Choisir…**.

Le bouton **Exporter** reste grisé tant que la destination ne peut pas être écrite : un chemin vide, un dossier qui n'existe pas, ou un dossier à la place d'un fichier. Si le fichier existe déjà, Lacis prévient qu'il sera remplacé.

Le coffre Obsidian est un dossier, et non un fichier : Lacis propose un dossier au nom de l'enquête, qu'il crée au moment de l'export. Vous pouvez aussi choisir un dossier existant, à condition qu'il soit vide, pour ne jamais mêler l'export à d'autres notes.

## Le rapport Markdown

Le rapport raconte ce que l'enquête a trouvé, comment, et avec quelles réserves. Il se lit sans Lacis : transmettez-le tel quel, ou ouvrez-le dans un éditeur Markdown pour le compléter. Il contient, dans l'ordre :

- **la question** de l'enquête, la date du rapport et ce qu'il couvre ;
- **une synthèse** : le nombre de constats par verdict, de signaux et de notes ;
- **la méthode** : les sources interrogées, avec le nombre de requêtes, d'échecs et de réponses conservées, et la période de collecte ; les entités ajoutées depuis la recherche et chaque extension, avec sa date, sa profondeur et le nombre d'entités qu'elle a ajoutées ; la date du calcul des signaux ;
- **les constats** : les entités qui ont un [verdict](/lacis/guide/notes/), rangées de « Confirmé » à « Écarté », avec la raison du verdict et les tags ;
- **les signaux**, du plus grave au moins grave, avec leur explication et les entités en cause ;
- **les notes**, citées sous le nom de leur entité ;
- **les réserves** : ce que le rapport ne peut pas garantir, comme les requêtes qui ont échoué ou les entités qui n'ont pas été étendues.

Lacis enregistre les extensions depuis la version 1.0.0. Pour une enquête plus ancienne, la méthode indique seulement combien d'entités ont été étendues.

## Le coffre Obsidian

Le coffre Obsidian transforme l'enquête en notes liées, à relire et à compléter dans [Obsidian](https://obsidian.md/). Ouvrez le dossier exporté avec **Ouvrir un dossier comme coffre**. Il contient :

- **une note d'index**, « Enquête » suivie du nom de l'enquête, avec la question, les signaux et la liste des entités ;
- **une note par entité**, rangée dans un dossier par type : Entreprises, Personnes, Adresses, Établissements, Entreprises étrangères.

Chaque note d'entité garde ses faits en propriétés (identifiant, type, verdict, tags, attributs et dates de collecte), puis décrit l'entité : ses liens vers les autres notes, ses signaux, votre note, ses annonces BODACC et ses sources. Les liens sont des liens Obsidian entre notes : la vue graphique du coffre reprend donc le graphe de l'enquête. Lacis la règle pour colorer chaque type d'entité et masquer la note d'index, qui sinon serait reliée à tout.

Deux entités qui portent le même nom, comme deux homonymes, reçoivent des notes distinctes : Lacis ajoute à leur nom un fait qui les distingue, comme le mois de naissance ou le SIRET.

## Le format JSON

L'export JSON est complet et sans perte. Il contient :

- l'enquête : son nom, sa question et sa date de création ;
- les entités : leur type, leur nom, leurs attributs, leurs dates de collecte, leurs tags, leur note, leur verdict avec sa raison, et pour les entreprises leurs annonces BODACC ;
- les liens entre entités, avec leur rôle et leurs dates ;
- les signaux d'alerte, avec leur règle, leur sévérité et leur explication ;
- vos décisions d'homonymie ;
- les réponses des sources, avec leur adresse, leurs paramètres, leur date de collecte et leur empreinte SHA-256.

Chaque entité, chaque lien et chaque annonce cite les réponses dont il vient : la [provenance](/lacis/guide/preuves/) reste vérifiable hors de Lacis.

Le fichier suit un schéma publié, [investigation-1.schema.json](https://c4seus.github.io/lacis/schemas/investigation-1.schema.json), au format JSON Schema. Un outil peut s'en servir pour valider l'export avant de le lire. Le champ `format_version` change si la structure du fichier change.

Un export contient les données personnelles de l'enquête : rangez-le et partagez-le avec les mêmes précautions que l'enquête elle-même. La page [Usage responsable](/lacis/guide/usage-responsable/) rappelle les règles à suivre.
