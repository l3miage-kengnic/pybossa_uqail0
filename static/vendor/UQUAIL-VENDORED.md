# Bibliothèques rapatriées pour U-QUAIL

Ces bibliothèques étaient chargées par le thème depuis des CDN tiers (cdnjs, jsDelivr,
code.jquery.com, maxcdn). Elles sont servies ici par l'instance elle-même, pour qu'aucune
visite ne révèle l'adresse IP de l'utilisateur à un tiers (RGPD, minimisation).
Fichiers téléchargés tels quels, sans modification, le 2026-10-21.

| Dossier | Version | Source | Licence | Utilisé par |
|---|---|---|---|---|
| `font-awesome-4.5.0/` | 4.5.0 | cdnjs.cloudflare.com/ajax/libs/font-awesome/4.5.0 | Police : SIL OFL 1.1 ; CSS : MIT | toutes les pages (`templates/base.html`) |
| `chartist-0.11.4/` | 0.11.4 | cdnjs.cloudflare.com/ajax/libs/chartist/0.11.4 | MIT / WTFPL | tableaux de bord admin (`templates/admin/*dashboard.html`) |
| `moment-2.22.1/` | 2.22.1 | cdnjs.cloudflare.com/ajax/libs/moment.js/2.22.1 | MIT | `templates/account/register.html` |
| `tingle-0.13.2/` | 0.13.2 | cdnjs.cloudflare.com/ajax/libs/tingle/0.13.2 | MIT | `templates/account/register.html` |
| `jquery-ui-1.12.1/` | 1.12.1 (thème "base", CSS + icônes) | code.jquery.com/ui/1.12.1/themes/base | MIT | parcours des tâches (`templates/projects/tasks_browse.webpack.ejs`) |

Le thème chargeait Chartist en version « latest » non épinglée : la version 0.11.4 est la
dernière de la branche 0.x, compatible avec l'API utilisée par les tableaux de bord.
