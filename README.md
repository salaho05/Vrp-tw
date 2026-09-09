# VRPTW par CP + LNS — Optimisation de la livraison du dernier kilomètre à Casablanca

Ce projet résout le **Vehicle Routing Problem with Time Windows (VRPTW)** — la planification de tournées de livraison — par **Programmation par Contraintes (CP)** et **Large Neighborhood Search (LNS)** sous MiniZinc, appliqué à un cas réel de distribution urbaine à Casablanca, et comparé à l'heuristique classique de Clarke-Wright.

Projet réalisé dans le cadre du module *Statistiques et Décisions — Recherche Opérationnelle* (CP-INSEA-SDRO-2A), INSEA, année 2025-2026, encadré par le Dr Jabrane Slimani.

**Équipe :** Aya Akrich · Ilyas Meliani · Abdelhadi Bennani · Salah Eddine Masmoudi

Le rapport complet se trouve dans [`report/rapport_P5_VRPTW.pdf`](report/rapport_P5_VRPTW.pdf).

---

## Problématique

Livrer des dizaines de clients en ville avec une flotte limitée soulève une question d'optimisation difficile : dans quel ordre et avec quels véhicules effectuer les tournées pour minimiser la distance totale, tout en respectant les horaires de livraison de chaque client et la capacité de chaque véhicule ? C'est le VRPTW, un problème **NP-difficile** : le nombre de tournées possibles explose avec le nombre de clients, et aucune méthode ne peut toutes les énumérer.

Dans le contexte **réel de Casablanca**, le problème se complique encore avec trois contraintes que les modèles académiques ignorent :

- Le **trafic change selon l'heure** — traverser la ville à 8h du matin n'a rien à voir avec 23h.
- Certaines **zones sont interdites à certains véhicules** — un camion ne peut pas entrer dans la médina ou une rue piétonne.
- La **flotte est hétérogène** — des triporteurs légers, des fourgonnettes, des gros camions, chacun avec sa capacité et ses autorisations d'accès.

**Les deux questions de recherche du projet :**

1. Une approche exacte (CP) enrichie de recherche locale (LNS) peut-elle produire des solutions **meilleures** que l'heuristique rapide de Clarke-Wright, largement utilisée en pratique ?
2. **À quelle taille** le CP « pur » cesse-t-il de suffire, obligeant à passer au LNS ?

---

## Démarche en deux temps

Le travail se déroule en deux parties complémentaires.

### Partie A — Validation sur les instances de référence Solomon

Avant de s'attaquer au cas réel, les modèles sont validés sur 6 instances **Solomon** standard (les benchmarks de référence mondiaux pour le VRPTW), issues de 3 familles :

- **C101** — clients regroupés en clusters, fenêtres de temps larges
- **R101** — clients répartis aléatoirement, fenêtres étroites
- **RC101** — mélange des deux, la configuration la plus difficile

Chaque famille est testée en **25 et 50 clients**, ce qui permet de comparer nos résultats aux *Best Known Solutions* (meilleures solutions publiées) et de repérer précisément où le CP pur atteint ses limites.

### Partie B — Application au cas réel : Casablanca (50 clients)

C'est le cœur du projet. Une instance réaliste de **50 points de livraison** (commerces, pharmacies, restaurants en zone urbaine dense) est construite et enrichie des trois contraintes marocaines.

---

## La partie Casablanca en détail

### Construction des données

L'instance Casablanca n'est pas synthétique : elle est bâtie à partir de données géographiques et de trafic réelles, assemblées par le script `maroc/scripts/build_casa_database_xlsx_v2.py` dans un classeur exploitable (`maroc/data/casa_logistics.xlsx`), puis converties au format solveur `.dzn`.

**50 clients**, chacun caractérisé par :

- une **demande** (poids à livrer, de 21 à 239 kg),
- une **fenêtre de temps** `[early, late]` (heure d'ouverture / limite de livraison),
- une **durée de service** sur place (10 à 24 min).

**Une flotte hétérogène de 18 véhicules :**

| Type | Capacité | Nombre | Particularité |
|---|---|---|---|
| Triporteur | 300 kg | 8 | Seul autorisé en médina et zones piétonnes |
| Fourgonnette | 1 200 kg | 5 | Accès urbain standard |
| Camion | 5 000 kg | 5 | Grande capacité, accès restreint au centre |

**Le trafic modélisé sur 4 créneaux horaires** (matrices de temps de trajet distinctes, calibrées sur des vitesses réelles) :

| Créneau | Plage horaire | Vitesse moyenne |
|---|---|---|
| Nuit | 21h – 05h | 40 km/h |
| Matin | 06h – 09h | 20 km/h (heure de pointe) |
| Midi | 10h – 14h | 25 km/h |
| Soir | 15h – 20h | 18 km/h (pointe sévère) |

Le même trajet peut donc prendre **plus du double de temps** selon l'heure — une réalité que le modèle intègre pour décider *quand* et *avec quel véhicule* livrer.

**Les zones à accès restreint** sont encodées dans une matrice `acces_autorise[véhicule, client]` : si un client se trouve dans la médina, seuls les triporteurs peuvent le desservir. Le modèle refuse toute affectation interdite.

### Modélisation

Deux modèles MiniZinc ont été écrits (`maroc/models/`) :

- **`maroc_vrptw_cppur.mzn` — CP pur.** Une formulation exacte par contraintes : un circuit hamiltonien unique parcourt tous les clients (`circuit`), les fenêtres de temps et la cohérence temporelle sont propagées, la capacité par véhicule est bornée (`bin_packing`), et les accès interdits sont exclus. Sans mécanisme d'échappement, il sert à mesurer *jusqu'où* le CP seul peut aller.
- **`maroc_vrptw_cplns_v3.mzn` — CP + LNS.** Le même modèle, augmenté d'une stratégie *destroy-and-repair* : à chaque itération, 50 % des variables (dont les affectations véhicule) sont relâchées puis reconstruites par le solveur, avec des relances Luby pour éviter les cycles. C'est ce qui permet de **restructurer globalement** les tournées et d'échapper aux minima locaux.

---

## Résultats

### Sur Casablanca — le LNS fait la différence

| Méthode | 1ʳᵉ solution | Meilleure solution | Amélioration | Nb. solutions |
|---|---|---|---|---|
| **CP pur** | 706 km | **676 km** | −4,3 % | 14 |
| **CP + LNS** | 735 km | **479 km** | **−34,7 %** | 40 |

Le résultat central du projet est clair : **le CP pur plafonne à −4,3 %** dès les premières secondes (le solveur reste bloqué dans un minimum local, sans moyen d'en sortir), tandis que **le CP+LNS continue de descendre jusqu'à −34,7 %**, soit une tournée finale de **479 km contre 676 km** — près de **200 km économisés**.

La courbe de convergence du CP+LNS (voir `maroc/analysis/`) présente deux phases nettes :

- une **phase rapide** (0–30 s) où la distance chute de 735 à ≈ 610 km grâce à des réaffectations globales faciles ;
- une **phase lente** (30–375 s) de descente continue jusqu'à 479 km.

Un **saut brusque de −5,2 %** est observé autour de *t* ≈ 100–116 s : le LNS redéploie plusieurs clients des camions (5 000 kg) vers les fourgonnettes (1 200 kg) circulant dans des zones à trafic plus fluide, libérant plusieurs kilomètres de détour. C'est la signature typique d'un LNS qui restructure globalement les affectations véhicule-client — quelque chose que le CP pur ne sait pas faire.

### La nuance sur Clarke-Wright

L'heuristique de Clarke-Wright obtient **450 km en 0,022 s** sur l'instance marocaine — apparemment meilleure et instantanée. Mais ce chiffre est **trompeur** : Clarke-Wright calcule ses fusions sur des distances brutes, **sans intégrer rigoureusement** le trafic par créneau ni garantir le respect strict des fenêtres de temps. Sa solution n'est donc pas directement déployable.

Le CP+LNS, lui, **modélise toutes les contraintes de manière rigoureuse** (trafic variable, zones interdites, flotte hétérogène) et fournit une solution **opérationnelle, directement applicable** — c'est là sa vraie valeur.

### Sur les instances Solomon — validation confirmée

| Résultat | Constat |
|---|---|
| MiniZinc vs meilleures solutions publiées | Écart ≤ 3 % sur les 6 instances (plusieurs atteignent ou dépassent la référence) |
| CP + LNS vs Clarke-Wright | Le CP+LNS surpasse Clarke-Wright de **26,5 % en moyenne** |
| Frontière CP pur / LNS | située autour de **30–40 clients** |

La frontière est le second résultat clé : **pour n ≤ 25 clients, le CP pur suffit** (solution quasi-optimale en moins de 50 s). **Au-delà de n ≥ 50, le LNS devient indispensable** — le CP pur sature là où le LNS continue d'améliorer nettement.

---

## Conclusion

Le projet démontre que **CP + LNS est une approche efficace et adaptable** pour le VRPTW réaliste :

- il produit des solutions **quasi-optimales** sur les benchmarks Solomon (écart ≤ 3 %) ;
- il **surpasse Clarke-Wright de 26,5 %** en moyenne ;
- sur le cas réel de Casablanca, il **améliore la tournée de −34,7 %** (479 km) là où le CP pur plafonne à −4,3 % (676 km), tout en **respectant strictement** les horaires, les accès et les capacités — donc une solution réellement déployable ;
- la bascule du CP pur vers le LNS s'impose autour de **30–40 clients**.

Autrement dit : sur des problèmes de livraison urbaine à taille réelle, une heuristique rapide comme Clarke-Wright donne un ordre de grandeur, mais seule une approche CP+LNS produit une tournée **fiable et exploitable** dans les vraies conditions de la ville.

---

## Structure du dépôt

```
report/              Rapport complet (PDF)

maroc/                Cas réel — Casablanca (50 clients)
├── data/            Instances .dzn et base de données logistique (casa_logistics.xlsx)
├── models/          Modèles MiniZinc — CP pur et CP+LNS (trafic, zones, flotte hétérogène)
├── scripts/         Construction de la base de données et génération des instances
├── clarke_wright/   Notebook Clarke-Wright et résultats pour Casablanca
└── analysis/        Analyse de convergence CP pur vs CP+LNS, logs solveur, graphes

solomon/             Validation sur les instances de référence (C101, R101, RC101)
├── data/            Fichiers .dzn (25/50/100 clients), texte Solomon brut, script de conversion
├── models/          Modèles MiniZinc génériques — CP pur et CP+LNS
├── clarke_wright/   Notebook Clarke-Wright, courbes de convergence, cartes de routes
└── analysis/        Comparaison aux meilleures solutions connues, logs, graphes
```
