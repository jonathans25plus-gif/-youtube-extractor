
# 🚀 Instructions pour publier et activer (Auto-Update)

Tout est prêt ! L'application contient maintenant le manuel d'utilisation et le système de mise à jour.
Le fichier exécutable final est ici : `dist\YouTubeExtractor.exe`.

## Étape 1 : Envoyer le code sur GitHub

Ouvrez un terminal (PowerShell ou CMD) dans ce dossier et tapez :

```bash
git push -u origin main
```

*(Si on vous demande vos identifiants, entrez votre nom d'utilisateur et votre mot de passe/token GitHub).*

## Étape 2 : Créer la Release (Important pour la mise à jour auto !)

1. Allez sur votre repo : https://github.com/jonathans25plus-gif/-youtube-extractor
2. Cliquez sur **"Releases"** (à droite) puis **"Draft a new release"**.
3. **Choose a tag** : Tapez `v1.0.0` et cliquez sur "Create new tag".
4. **Release title** : `Version 1.0.0`
5. **Description** :
   ```
   Première version officielle !
   - Téléchargement Audio/Vidéo
   - File d'attente
   - Recherche paginée
   - Mise à jour automatique
   ```
6. **IMPORTANT** : Glissez-déposez le fichier `dist\YouTubeExtractor.exe` dans la zone "Attach binaries by dropping them here".
7. Cliquez sur **Target** > `main` (pour être sûr).
8. Cliquez sur **Publish release**.

## C'est fini !

Désormais, quand vous sortirez la version `v1.0.1` :
1. Changez `APP_VERSION = '1.0.1'` dans `app.py`.
2. Refaites le build (`build.bat` ou la commande PyInstaller).
3. Créez une nouvelle release `v1.0.1` sur GitHub avec le nouveau `.exe`.
4. Tous les utilisateurs de la v1.0.0 recevront une notification et pourront mettre à jour en un clic ! 🎉
