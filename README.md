# Alertes CROUS sur Telegram

GitHub Actions vérifie les logements toutes les cinq minutes, jour et nuit, même lorsque votre ordinateur est éteint. Le bot détecte la campagne CROUS active et conserve la zone géographique de la recherche d'origine.

## Activation

Dans **Settings → Secrets and variables → Actions → New repository secret**, ajouter :

- `TELEGRAM_BOT_TOKEN` : le jeton du bot fourni par BotFather.
- `TELEGRAM_CHAT_ID` : l'identifiant de la conversation destinataire. Ouvrir d'abord le bot sur Telegram et lui envoyer `/start`.

Saisir ces valeurs uniquement dans les secrets GitHub, jamais dans le code.

Ensuite, ouvrir **Actions → Alertes CROUS → Run workflow** pour lancer une première vérification. La planification prend ensuite le relais. Le workflow s'exécute depuis `main`.

Le lancement manuel propose aussi une case pour vérifier le site sans envoyer de message Telegram. Ce mode fonctionne avant l'ajout des secrets.

## Fonctionnement

- Le script effectue une seule vérification et termine. Les disponibilités doivent être explicitement confirmées par les données CROUS.
- Il parcourt les pages de résultats et signale les erreurs réseau, les pages inconnues et les résultats incomplets dans les logs Actions.
- Au premier lancement, tous les logements disponibles dans la zone sont envoyés.
- Après chaque envoi Telegram réussi, son URL est enregistrée dans `.state/sent_apartments.json`. Le workflow sauvegarde les changements dans le dépôt, y compris après un échec partiel. Une URL déjà enregistrée n'est plus signalée, même si le logement revient en stock. L'historique ne contient aucun secret ; il est public comme le dépôt.
- Les exécutions sont sérialisées pour limiter les doublons. Un arrêt brutal entre l'envoi et la sauvegarde distante peut toutefois entraîner un nouvel envoi.
- Le jeton automatique GitHub dispose de `contents: write` pour sauvegarder cet historique. Si une règle de protection interdit les mises à jour de `main`, la sauvegarde échouera et cette règle devra être adaptée avant de poursuivre.

## Limites du service gratuit

Les runners standards GitHub Actions sont gratuits pour ce dépôt public. La planification toutes les cinq minutes n'est pas une garantie de délai : GitHub peut retarder ou omettre certaines exécutions. Les workflows planifiés peuvent être désactivés après 60 jours sans activité du dépôt : surveiller les notifications GitHub et réactiver le workflow si nécessaire.

Sources : [gratuité](https://docs.github.com/en/actions/concepts/billing-and-usage), [planification et inactivité](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Utilisation locale

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py --dry-run
```

`--dry-run` consulte le site sans envoyer de message ni modifier l'historique. Pour envoyer les alertes, définir les variables d'environnement Telegram puis exécuter `python main.py`.

Options d'environnement : `STATE_PATH` pour déplacer l'historique et `CROUS_SEARCH_URL` pour remplacer l'URL de recherche complète (campagne, limites géographiques et filtres).
