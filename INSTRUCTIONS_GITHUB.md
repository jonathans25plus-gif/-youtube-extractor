
# 🚀 Instructions pour publier et activer (Auto-Update)

J'ai nettoyé le projet pour retirer les gros fichiers `.exe` qui bloquaient l'envoi.

## Étape 1 : Envoyer le code source (Force)

Comme nous avons réinitialisé le dépôt pour le nettoyer, il faut forcer l'envoi une première fois.
Ouvrez votre terminal et tapez :

```bash
git push -f origin main
```

*(Cela enverra uniquement le code Python, HTML, et les fichiers de configuration, c'est très rapide).*

## Étape 2 : Créer la Release et Ajouter l'Exécutable

C'est ici que l'on met le fichier `.exe` (et non pas dans le code source).

1. Allez sur votre repo : https://github.com/jonathans25plus-gif/-youtube-extractor
2. Cliquez sur **"Releases"** (à droite) puis **"Draft a new release"**.
3. **Choose a tag** : `v1.0.0` (Create new tag).
4. **Release title** : `Version 1.0.0`
5. **Description** : Copiez le texte ci-dessous si vous voulez :
   ```
   Première version officielle !
   - Téléchargement Audio/Vidéo
   - Recherche paginée
   - Mise à jour automatique
   ```
6. **⚠️ TRÈS IMPORTANT** : Prenez le fichier `dist\YouTubeExtractor.exe` sur votre PC, et glissez-le dans la zone "Attach binaries...". C'est grâce à ça que la mise à jour fonctionnera.
7. Cliquez sur **Publish release**.

## C'est fini !
Votre application saura maintenant qu'une version 1.0.0 existe, et pourra télécharger le fichier `.exe` que vous venez d'uploader.
