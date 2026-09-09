include "globals.mzn";

% --- PARAMÈTRES (lus depuis le fichier .dzn) ---
int: n;
int: K;
int: cap;

array[1..n] of int: demand;
array[1..n] of int: early;
array[1..n] of int: late;
array[1..n] of int: service;

int: depot_early;
int: depot_late;

% Matrice des distances (0 = Dépôt, 1..n = Clients)
array[0..n, 0..n] of int: dist;

% --- CONSTANTES ---
int: N = n + K;

% --- PRÉCALCUL DE LA MATRICE ÉTENDUE ---
array[1..N, 1..N] of int: dist_ext = array2d(1..N, 1..N, [
    dist[if i > n then 0 else i endif, if j > n then 0 else j endif]
    | i in 1..N, j in 1..N
]);

% --- VARIABLES DE DÉCISION ---
array[1..N] of var 1..N: suivant;
array[1..n] of var 0..depot_late: arrivee;
array[1..n] of var 1..K: vehicule;

% --- CONTRAINTES ---
constraint circuit(suivant);

% Fenêtres temporelles clients
constraint forall(i in 1..n)(
    arrivee[i] >= early[i] /\ arrivee[i] <= late[i]
);

% Cohérence temporelle entre clients successifs
constraint forall(i in 1..n, j in 1..n)(
    suivant[i] = j -> arrivee[j] >= arrivee[i] + service[i] + dist_ext[i, j]
);

% Départ depuis le dépôt vers un client
constraint forall(i in n+1..N, j in 1..n)(
    suivant[i] = j -> arrivee[j] >= depot_early + dist_ext[i, j]
);

% Retour au dépôt avant depot_late
constraint forall(i in 1..n)(
    suivant[i] > n -> arrivee[i] + service[i] + dist_ext[i, suivant[i]] <= depot_late
);

% Affectation véhicule depuis le dépôt
constraint forall(i in n+1..N, j in 1..n)(
    suivant[i] = j -> vehicule[j] = i - n
);

% Propagation du véhicule sur la route
constraint forall(i in 1..n, j in 1..n)(
    suivant[i] = j -> vehicule[j] = vehicule[i]
);

% Capacité par véhicule
constraint forall(k in 1..K)(
    sum(i in 1..n where vehicule[i] = k)(demand[i]) <= cap
);

% Chaînage des dépôts fictifs inactifs (brise la symétrie)
constraint forall(i in n+1..N-1)(
    suivant[i] > n -> suivant[i] = i + 1
);

% --- OBJECTIF ---
var int: total_distance = sum(i in 1..N)(dist_ext[i, suivant[i]]);

% --- LNS CORRIGÉ POUR SOLOMON R, C ET RC ---
%
%  Changements par rapport à la version initiale :
%  1. int_search étendu à suivant ++ arrivee ++ vehicule
%     → meilleure solution initiale sur les 3 types
%  2. restart_luby(250) → restart_luby(1000)
%     → moins d'interruptions, meilleure exploration locale
%  3. relax_and_reconstruct(suivant, 80) → 50
%     → voisinage 2.5x plus grand (50% relâché au lieu de 20%)
%  4. Ajout de relax_and_reconstruct sur arrivee (crucial pour C)
%     → débloque le LNS quand les fenêtres temporelles sont étroites
%  5. Ajout de relax_and_reconstruct sur vehicule (crucial pour RC)
%     → permet les réaffectations inter-véhicules / inter-clusters

solve
    :: int_search(suivant ++ arrivee ++ vehicule, first_fail, indomain_min)
    :: restart_luby(1000)
    :: relax_and_reconstruct(suivant,  50)
    :: relax_and_reconstruct(arrivee,  50)
    :: relax_and_reconstruct(vehicule, 50)
    minimize total_distance;

% --- OUTPUT ---
output [
    "Distance totale = ", show(total_distance), "\n",
    "Suivant = ", show(suivant), "\n",
    "Vehicules = ", show(vehicule), "\n"
];