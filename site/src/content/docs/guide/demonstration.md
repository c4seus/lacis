---
title: Découvrir Lacis avec le mode démo
description: "Essayer Lacis sur des entreprises fictives, sans réseau et sans toucher à vos enquêtes : lancer le mode démo et parcourir son enquête d'exemple."
---

Le mode démo lance Lacis sur une fausse API qui imite le registre national des entreprises et le BODACC. Les entreprises et les personnes qu'il montre sont toutes fictives. Vous pouvez y essayer chaque fonctionnalité sans connexion, sans toucher à vos enquêtes et sans interroger les vraies API.

## Lancer le mode démo

Sous Linux, dans un terminal :

```bash
lacis --demo
```

Sous Windows, dans PowerShell, si Lacis est installé pour votre compte :

```powershell
& "$env:LOCALAPPDATA\Programs\Lacis\lacis.exe" --demo
```

S'il est installé pour tous les utilisateurs de l'ordinateur, remplacez `$env:LOCALAPPDATA\Programs` par `$env:ProgramFiles`.

La barre de titre affiche alors « Lacis — démonstration ».

## Ce qui change en mode démo

- **Aucune requête ne part vers les API publiques.** Les recherches et les extensions interrogent la fausse API, sur votre ordinateur.
- **Les enquêtes vivent dans un dossier temporaire**, effacé à la fermeture de Lacis. Vos vraies enquêtes n'apparaissent pas et restent intactes.
- **Vos réglages restent les mêmes** : le thème et la taille de la fenêtre sont ceux de votre Lacis habituel.

Les liens vers l'Annuaire des entreprises et vers bodacc.fr s'ouvrent quand même dans votre navigateur, mais ils ne mènent à rien d'utile : les entreprises de la démonstration n'existent pas dans les vrais registres.

## L'enquête d'exemple

Le registre fictif contient deux plomberies toulousaines domiciliées au 12 rue des Lilas. Cherchez cette adresse : Lacis trouve ACME PLOMBERIE et DUPONT SERVICES, ainsi qu'une boulangerie de Lyon, située dans une autre rue des Lilas. Ajoutez les deux plomberies à une enquête, puis étendez-les.

Lacis signale alors un schéma phénix : DUPONT SERVICES a fermé après une liquidation judiciaire, et ACME PLOMBERIE, qui a le même dirigeant et la même activité, a été créée deux mois plus tôt. Il vous demande aussi si Jean DUPONT et Jean Pierre DUPONT, nés le même mois, sont une seule et même personne.

[Mener une première enquête](/lacis/guide/premiere-enquete/) suit cette enquête pas à pas.
