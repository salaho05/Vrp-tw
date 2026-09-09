include "globals.mzn";

% ==========================================
% 1. PARAMÈTRES (lus dynamiquement depuis les fichiers .dzn)
% ==========================================
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

% ==========================================
% 2. CONSTANTES ET PRÉCALCULS
% ==========================================
int: N = n + K;

% Matrice étendue pour gérer les dépôts virtuels sans erreur
array[1..N, 1..N] of int: dist_ext = array2d(1..N, 1..N, [
    dist[if i > n then 0 else i endif, if j > n then 0 else j endif]
    | i in 1..N, j in 1..N
]);

% ==========================================
% 3. VARIABLES DE DÉCISION
% ==========================================
array[1..N] of var 1..N: suivant;
array[1..n] of var 0..depot_late: arrivee;
array[1..n] of var 1..K: vehicule;

% ==========================================
% 4. CONTRAINTES UNIVERSELLES
% ==========================================
constraint circuit(suivant);

constraint forall(i in 1..n)(
    arrivee[i] >= early[i] /\ arrivee[i] <= late[i]
);

constraint forall(i in 1..n, j in 1..n)(
    suivant[i] = j -> arrivee[j] >= arrivee[i] + service[i] + dist_ext[i, j]
);

constraint forall(i in n+1..N, j in 1..n)(
    suivant[i] = j -> arrivee[j] >= depot_early + dist_ext[i, j]
);

constraint forall(i in 1..n)(
    suivant[i] > n -> arrivee[i] + service[i] + dist_ext[i, suivant[i]] <= depot_late
);

constraint forall(i in n+1..N, j in 1..n)(
    suivant[i] = j -> vehicule[j] = i - n
);

constraint forall(i in 1..n, j in 1..n)(
    suivant[i] = j -> vehicule[j] = vehicule[i]
);

constraint forall(k in 1..K)(
    sum(i in 1..n where vehicule[i] = k)(demand[i]) <= cap
);

% Casser les symétries pour les véhicules vides
constraint forall(i in n+1..N-1)(
    suivant[i] > n -> suivant[i] = i + 1
);

% ==========================================
% 5. RÉSOLUTION (CP PUR)
% ==========================================
var int: total_distance = sum(i in 1..N)(dist_ext[i, suivant[i]]);

solve minimize total_distance;

% ==========================================
% 6. OUTPUT
% ==========================================
output [
    "Distance totale = ", show(total_distance), "\n",
    "Suivant = ", show(suivant), "\n",
    "Vehicules = ", show(vehicule), "\n"
];