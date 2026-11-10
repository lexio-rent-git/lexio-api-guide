# Guide Python de l'API Lexio Rent

Guide pratique, en français, pour intégrer l'API v1 de [Lexio Rent](https://lexio.rent/logiciel-location-voiture), logiciel de gestion de location de véhicules, depuis Python.

**Lire le guide : [docs.page/lexio-rent-git/lexio-api-guide](https://docs.page/lexio-rent-git/lexio-api-guide)**

| Page | Contenu |
|---|---|
| [Premier appel](docs/premier-appel.mdx) | session `requests`, en-têtes, `GET /organization`, pagination par curseur |
| [Disponibilités et devis](docs/disponibilites-devis.mdx) | dates locales sans décalage, montants en unités majeures, `GET /availability`, `POST /quotes` |
| [Synchroniser les locations](docs/synchronisation.mdx) | flux `GET /events` sans webhook, curseur, reprise après arrêt |
| [Erreurs et reprises](docs/erreurs-reprises.mdx) | RFC 9457, `Idempotency-Key`, `Retry-After`, ce qu'il ne faut pas renvoyer |

## Exemple prêt à l'emploi

[`exemples/sync_locations.py`](exemples/sync_locations.py) garde une copie SQLite des locations d'une agence, à jour en continu. Lecture seule (scope `rentals.read`).

```bash
python -m pip install requests
export LEXIO_API_KEY="lck_..."
python exemples/sync_locations.py --db locations.sqlite
```

## Accès à l'API

L'API fait partie du plan Business de Lexio : chaque loueur crée sa clé (`lck_…`) dans *Paramètres → Développeur → Tokens API*. Il n'y a pas de bac à sable public ; pour essayer, demandez une organisation de démonstration à contact@lexio.rent.

- Référence complète : [docs.lexio.rent](https://docs.lexio.rent)
- Spécification OpenAPI 3.1 : [docs.lexio.rent/openapi.json](https://docs.lexio.rent/openapi.json)
- Skill pour assistants de code : [lexio-rent-git/lexio-api-skill](https://github.com/lexio-rent-git/lexio-api-skill)

## Licence

MIT, voir [LICENSE](LICENSE). Maintenu par [Lexio Rent](https://lexio.rent).
