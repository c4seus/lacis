---
title: Exporter une enquête
description: "Exporter une enquête entière ou la vue filtrée du graphe en rapport Markdown, lisible sans Lacis, en fichier JSON qui garde la provenance de chaque fait, en coffre Obsidian de notes liées, en graphe pour Gephi et Maltego, ou en page HTML à explorer sans Lacis."
---

Un export sort votre enquête de Lacis pour la transmettre, l'archiver ou la traiter avec d'autres outils. Il ne modifie jamais l'enquête : vous pouvez exporter aussi souvent que vous le voulez.

## Ouvrir la fenêtre d'export

Ouvrez l'enquête, puis choisissez **Fichier › Exporter**, et le format voulu : **Rapport Markdown…**, **Rapport PDF…**, **JSON…**, **Obsidian…**, **Gephi…**, **Maltego…** ou **Format HTML…**. La fenêtre « Exporter l'enquête » s'ouvre, avec trois choix :

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
- **les réserves** : ce que le rapport ne peut pas garantir, comme les requêtes qui ont échoué ou les entités qui n'ont pas été étendues ;
- **l'annexe de preuves** : chaque réponse des sources sur laquelle repose un constat ou un signal, avec sa source, son adresse, sa date de collecte et son empreinte SHA-256.

Chaque constat et chaque signal renvoie à ses preuves par des références comme [R1], qui mènent à l'annexe. Un lecteur peut ainsi retrouver la réponse d'origine, et l'empreinte lui permet de vérifier, depuis l'enquête, qu'elle n'a pas été modifiée depuis sa collecte.

Lacis enregistre les extensions depuis la version 1.0.0. Pour une enquête plus ancienne, la méthode indique seulement combien d'entités ont été étendues.


## Le rapport PDF

L'export **Rapport PDF** met en page le même rapport que l'export Markdown, avec les polices et les couleurs de Lacis, prêt à être envoyé. Chaque page rappelle en haut le nom de l'enquête et la date du rapport, et en bas son numéro sur le nombre total de pages. Les références comme R1 sont des liens vers l'annexe de preuves.

Le PDF est balisé : ses titres, ses paragraphes, ses listes et ses tableaux sont décrits dans le fichier, ce qui permet aux lecteurs d'écran de le lire dans l'ordre et d'y naviguer par titres. Le texte de vos notes y apparaît tel que vous l'avez écrit : une image ou un code HTML qu'elles contiendraient n'est ni affiché ni chargé.

L'export PDF s'appuie sur WeasyPrint et sur la bibliothèque Pango, installés avec les paquets de Lacis pour Debian, Ubuntu, Fedora et Arch Linux. L'installateur Windows ne les contient pas encore : sous Windows, Lacis signale que l'export PDF n'est pas disponible, et l'export Markdown reste possible.
## Le coffre Obsidian

Le coffre Obsidian transforme l'enquête en notes liées, à relire et à compléter dans [Obsidian](https://obsidian.md/). Ouvrez le dossier exporté avec **Ouvrir un dossier comme coffre**. Il contient :

- **une note d'index**, « Enquête » suivie du nom de l'enquête, avec la question, les signaux et la liste des entités ;
- **une note par entité**, rangée dans un dossier par type : Entreprises, Personnes, Adresses, Établissements, Entreprises étrangères.

Chaque note d'entité garde ses faits en propriétés (identifiant, type, verdict, tags, attributs et dates de collecte), puis décrit l'entité : ses liens vers les autres notes, ses signaux, votre note, ses annonces BODACC et ses sources. Les liens sont des liens Obsidian entre notes : la vue graphique du coffre reprend donc le graphe de l'enquête. Lacis la règle pour colorer chaque type d'entité et masquer la note d'index, qui sinon serait reliée à tout.

Deux entités qui portent le même nom, comme deux homonymes, reçoivent des notes distinctes : Lacis ajoute à leur nom un fait qui les distingue, comme le mois de naissance ou le SIRET.

## Le graphe HTML

L'export **Format HTML** écrit une page autonome : un seul fichier, à ouvrir dans n'importe quel navigateur, pour explorer le graphe sans installer Lacis. Envoyez-la à une personne qui doit relire l'enquête, ou gardez-la avec vos archives.

La page reprend le graphe tel que Lacis le dessine, avec ses formes, ses couleurs et les signaux autour des entités. Vous pouvez la déplacer à la souris, zoomer avec la molette ou les boutons, et **Tout afficher** recentre le graphe. Choisissez une entité dans le graphe ou dans la liste, qui se filtre par nom, SIREN ou ville : ses détails s'affichent à côté, avec ses faits, son verdict, ses tags, ses liens, ses signaux, votre note, ses annonces BODACC et ses sources. Un lien mène à l'entité voisine.

La page suit le thème clair ou sombre de votre système, et le bouton du thème permet d'en changer.

Elle fonctionne hors ligne, depuis le disque : ses styles et son script sont inclus dans le fichier, et elle interdit au navigateur de charger quoi que ce soit depuis Internet. Seuls les liens vers les annonces et les réponses des sources ouvrent une page en ligne, quand vous cliquez dessus.

## Le graphe pour Gephi

L'export **Gephi** écrit le graphe au format GEXF, que [Gephi](https://gephi.org/) ouvre directement pour analyser un grand réseau : mesures de centralité, détection de communautés, mises en page avancées. Chaque entité devient un nœud, coloré comme dans Lacis, avec ses attributs :

- son type, son identifiant et ses faits ;
- son verdict et ses tags ;
- si elle est fermée ;
- le nombre de signaux qui la concernent, leurs titres, la plus forte gravité et le meilleur score ;
- sa provenance : les sources des réponses dont elle vient, leurs dates de collecte, leurs adresses et leurs empreintes SHA-256.

Chaque lien devient une arête orientée, nommée par son rôle : « Président », « Siège social », « Établissement de »… Elle garde la même provenance que les nœuds. Un lien « Même personne » ne vient d'aucune réponse : sa source indique « Décision de l'enquêteur ».

Dans Gephi, le **Laboratoire de données** liste tous ces attributs, dans l'onglet des nœuds comme dans celui des arêtes. Quand un fait vient de plusieurs réponses, chaque colonne de provenance les liste dans le même ordre, séparées par un point-virgule : la deuxième adresse correspond à la deuxième date et à la deuxième empreinte. La fenêtre **Apparence** peut aussi se servir des attributs pour colorer ou dimensionner les nœuds, par exemple selon leur score.

## Le tableau pour Maltego

L'export **Maltego** écrit un fichier CSV à importer dans [Maltego](https://www.maltego.com/) avec **Import › Import a 3rd Party Table**. Chaque ligne décrit un lien : ses deux entités, chacune dans la colonne de son type et suivie d'une colonne avec les adresses des réponses dont elle vient, puis le rôle du lien et ses propres réponses dans les deux dernières colonnes. Une entité sans lien a sa propre ligne.

Dans l'assistant d'import :

1. Indiquez que la première ligne contient les types (**Row is Types**) : les entreprises deviennent des `maltego.Company`, les personnes des `maltego.Person`, les adresses et les établissements des `maltego.Location`.
2. Pour garder la provenance, sélectionnez chaque colonne d'entité avec la colonne sans type qui la suit, avant de l'associer à son type : la seconde devient une propriété de l'entité, qui garde ainsi les adresses de ses réponses.
3. Choisissez la connexion **Meshed** : chaque ligne relie alors ses deux entités.
4. Dans l'étape des liens, associez les deux dernières colonnes aux liens pour garder leur rôle et leurs réponses.

L'import de Maltego ne garde que les adresses des réponses, sans leurs dates ni leurs empreintes : pour la provenance complète, utilisez l'export JSON, le coffre Obsidian ou le graphe HTML. Une colonne d'adresses que vous n'associez à aucune entité est simplement ignorée.

Deux homonymes restent deux entités : Lacis ajoute à leur nom un fait qui les distingue, comme le mois de naissance, pour que Maltego ne les fusionne pas.

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
