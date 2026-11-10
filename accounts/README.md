# Repertoire des comptes Instagram

Chaque sous-dossier represente un compte Instagram et doit contenir :

- un fichier `session.json` (session Instagram de ce compte, generee auprealable)
- un dossier de videos (ex: `videos/`, `contenu/` ou `stories/`) contenant les videos a publier

Exemple d'arborescence :

    accounts/
    ├── compte_vacances/
    │   ├── session.json
    │   └── videos/
    │       ├── video_01.mp4
    │   └── video_02.mp4
    ├── compte_business/
    │   ├── session.json
    │   └── contenu/
    │       └── clip_01.mp4
    └── compte_promo/
        ├── session.json
        └── stories/
            └── story_01.mp4

Les heures de publication, le dossier de videos, le type de contenu et le lien de story
se declarent dans `config.json` (voir `config.example.json` et `README.md`).

Les fichiers `session.json` et le contenu des dossiers de videos ne sont pas
commits dans Git (voir `.gitignore`).
