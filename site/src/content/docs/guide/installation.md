---
title: Installer Lacis
description: "Installer Lacis sous Debian, Fedora, Arch Linux ou Windows, vérifier le téléchargement, puis le mettre à jour ou le désinstaller."
---

Chaque [version publiée](https://github.com/c4seus/lacis/releases) de Lacis propose un paquet par plateforme, l'archive des sources et un fichier `SHA256SUMS`. Téléchargez le fichier de votre plateforme et `SHA256SUMS`, [vérifiez le téléchargement](#vérifier-le-téléchargement), puis installez Lacis comme indiqué ci-dessous.

| Plateforme | Fichier |
|---|---|
| Debian 13 et suivantes, et les dérivées qui fournissent PySide6 6.8 ou plus récent | `lacis_X.Y.Z_all.deb` |
| Fedora, un paquet par version maintenue | `lacis-X.Y.Z-1.fcNN.noarch.rpm` |
| Arch Linux | `lacis-X.Y.Z-1-any.pkg.tar.zst` |
| Windows 10 (version 1809 ou plus récente) et Windows 11, 64 bits | `lacis-X.Y.Z-windows-x64-setup.exe` |
| Autres plateformes | `lacis-X.Y.Z.tar.gz`, l'archive des sources |

`X.Y.Z` désigne la version de Lacis, et `NN` la version de Fedora.

## Debian et dérivées

```bash
sudo apt install ./lacis_X.Y.Z_all.deb
```

apt installe les dépendances depuis les dépôts de votre distribution, et Lacis apparaît dans le menu de votre bureau. Pour le désinstaller : `sudo apt remove lacis`.

## Fedora

Téléchargez le paquet dont le nom se termine par votre version de Fedora, par exemple `fc45` pour Fedora 45, puis installez-le avec dnf :

```bash
sudo dnf install ./lacis-X.Y.Z-1.fc45.noarch.rpm
```

dnf installe aussi les dépendances. N'utilisez pas `rpm -i` : le paquet n'est pas signé, et Fedora 45 refuse les paquets non signés avec cette commande. Pour désinstaller Lacis : `sudo dnf remove lacis`.

## Arch Linux

```bash
sudo pacman -Syu
sudo pacman -U ./lacis-X.Y.Z-1-any.pkg.tar.zst
```

Mettez d'abord le système à jour : le paquet est construit pour la version de Python fournie par Arch Linux le jour de la publication. Quand Arch Linux passe à une nouvelle version de Python, le paquet ne fonctionne plus jusqu'à la version suivante de Lacis. Pour le désinstaller : `sudo pacman -R lacis`.

## Windows

Lancez `lacis-X.Y.Z-windows-x64-setup.exe`. Par défaut, il installe Lacis pour votre compte seulement, sans droits d'administrateur, et l'ajoute au menu Démarrer. Il peut aussi installer Lacis pour tous les utilisateurs de l'ordinateur.

L'installateur n'est pas encore signé : Windows SmartScreen peut afficher « Windows a protégé votre ordinateur ». Après avoir [vérifié le téléchargement](#vérifier-le-téléchargement), choisissez **Informations complémentaires**, puis **Exécuter quand même**.

Pour désinstaller Lacis, ouvrez **Paramètres › Applications**. La désinstallation conserve vos enquêtes.

## Autres plateformes

Sur les autres distributions Linux, comme openSUSE, installez l'archive des sources avec [pipx](https://pipx.pypa.io/), qui demande Python 3.12 ou plus récent :

```bash
pipx install ./lacis-X.Y.Z.tar.gz
```

pipx installe Lacis et ses dépendances, PySide6 compris, dans un environnement séparé, et place la commande `lacis` dans votre chemin. Lacis n'a alors pas d'entrée dans le menu de votre bureau. Pour le désinstaller : `pipx uninstall lacis`.

## Mettre à jour

Téléchargez le paquet de la nouvelle version et installez-le avec la même commande que la première fois : apt, dnf et pacman remplacent la version installée, et l'installateur Windows remplace le Lacis déjà installé. Avec pipx, ajoutez `--force` :

```bash
pipx install --force ./lacis-X.Y.Z.tar.gz
```

Vos enquêtes sont conservées. `lacis --version` affiche la version installée, tout comme **Aide › À propos de Lacis**.

## Vérifier le téléchargement

`SHA256SUMS` donne l'empreinte SHA-256 de chaque fichier de la version. Placez-le dans le dossier de votre téléchargement, puis comparez les empreintes.

Sous Linux :

```bash
sha256sum --check --ignore-missing SHA256SUMS
```

La commande affiche `OK` après le nom de chaque fichier téléchargé. Toute autre réponse signifie que le téléchargement est abîmé ou modifié : supprimez-le et téléchargez-le à nouveau.

Sous Windows, dans PowerShell :

```powershell
$file = "lacis-X.Y.Z-windows-x64-setup.exe"
$expected = (Select-String -Path SHA256SUMS -SimpleMatch $file).Line.Split(" ")[0]
$actual = (Get-FileHash $file).Hash
if ($expected -and $actual -eq $expected) { "OK" } else { "Mismatch: do not install" }
```

La vérification détecte un téléchargement abîmé ou modifié, à condition que `SHA256SUMS` vienne de la page de la version.
