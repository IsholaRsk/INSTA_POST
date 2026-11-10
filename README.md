# INSTA_POST

Bot qui publie des videos sur Instagram pour plusieurs comptes a partir d'un
`session.json` par compte.

## Fonctionnement

- Chaque compte Instagram est associe a un dossier de la bibliotheque (ex. `accounts/<nom>/`).
- Chaque compte possede son propre `session.json`, son dossier de videos et ses propres heures de publication.
- A chaque heure programmee, le bot se "reveille", publie le contenu suivant (dans l'ordre
  alphabétique des fichiers), puis **supprime le fichier du repertoire** une fois publie.
- Trois types de contenu sont supportes : `video`, `reel` et `story`.

## Types de contenu

| Type | Description | Legende | Lien |
|------|-------------|---------|------|
| `video` | Publication classique sur le fil | Oui | Non |
| `reel` | Publication en Reel | Oui | Non |
| `story` | Story Instagram | Non | Oui (`story_link`) |

Plusieurs heures peuvent etre declarees par compte dans `posting_times`, ce qui permet
de publier plusieurs reels ou stories par jour.

## Installation

```bash
# 1. Cloner le depot
git clone <url-du-depot>
cd INSTA_POST

# 2. Creer l'environnement virtuel et installer les dependances
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configurer les comptes
cp config.example.json config.json
# Editer config.json avec tes comptes, dossiers et heures de publication
```

## Structure des comptes

Chaque compte dans `config.json` doit declarer :
- `name` : identifiant du compte
- `folder` : chemin vers le dossier du compte (contient `session.json` et le dossier de videos)
- `session_file` : nom du fichier de session (par defaut `session.json`)
- `videos_folder` : nom du dossier contenant les videos (par defaut `videos`)
- `posting_times` : liste d'heures au format `"HH:MM"` (plusieurs heures = plusieurs publications par jour)
- `timezone` : (optionnel) fuseau horaire du compte
- `caption_prefix` / `caption_suffix` : texte ajoute a la legende (video / reel uniquement)
- `content_type` : `"video"`, `"reel"` ou `"story"` (par defaut `"video"`)
- `story_link` : URL du sticker de lien pour les stories (uniquement `content_type: "story"`)
- `max_duration` : (optionnel) duree max en secondes

Exemple :

```json
{
  "timezone": "Europe/Paris",
  "accounts": [
    {
      "name": "compte_vacances",
      "folder": "accounts/compte_vacances",
      "content_type": "video",
      "posting_times": ["09:00", "17:00"],
      "caption_suffix": "#vacances #ete"
    },
    {
      "name": "compte_business",
      "folder": "accounts/compte_business",
      "content_type": "reel",
      "posting_times": ["10:30", "14:30", "20:00"],
      "caption_suffix": "#business"
    },
    {
      "name": "compte_promo",
      "folder": "accounts/compte_promo",
      "content_type": "story",
      "posting_times": ["12:00", "18:00"],
      "story_link": "https://monsite.com/promo"
    }
  ]
}
```

## Demarrer le bot

```bash
source .venv/bin/activate
python main.py
```

Le bot tourne en boucle et publie automatiquement a chaque heure programmee.

Pour tester sans attendre (publie un contenu par compte immediatement) :

```bash
python main.py --once
```

## Generation d'une session.json

Il faut se connecter au moins une fois a Instagram pour obtenir un `session.json` valide
pour chaque compte. Le fichier `session.json` contient les cookies/jetons de connexion
et doit etre place dans le dossier de chaque compte.

Les fichiers `session.json` et le contenu des dossiers de videos ne sont pas
commits dans Git (voir `.gitignore`).
