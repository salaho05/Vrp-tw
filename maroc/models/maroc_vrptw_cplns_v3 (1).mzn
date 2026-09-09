
% Modèle CP+LNS pour VRPTW Marocain (Casablanca) - v3


%   1) Trafic variable par créneau (4 matrices Waze NUIT/MATIN/MIDI/SOIR)
%   2) Zones à accès restreint (médina / proche médina)
%   3) Flotte hétérogène (Triporteur / Fourgonnette / Camion)



include "globals.mzn";
include "circuit.mzn";
include "inverse.mzn";
include "bin_packing_capa.mzn";

% =============== PARAMÈTRES (depuis le .dzn) =================
int: num_clients;
int: num_vehicules;

array[1..num_clients+1] of int: demande;
array[1..num_vehicules] of int: capacite_vehicule;
array[1..num_vehicules] of int: type_vehicule;

array[1..num_clients+1] of int: early;
array[1..num_clients+1] of int: late;
array[1..num_clients+1] of int: service;

array[1..num_clients+1, 1..num_clients+1] of int: distance;
array[1..num_clients+1, 1..num_clients+1] of int: temps_trajet;
array[1..num_clients+1, 1..num_clients+1] of int: temps_trajet_c0;  % NUIT
array[1..num_clients+1, 1..num_clients+1] of int: temps_trajet_c1;  % MATIN
array[1..num_clients+1, 1..num_clients+1] of int: temps_trajet_c2;  % MIDI
array[1..num_clients+1, 1..num_clients+1] of int: temps_trajet_c3;  % SOIR
array[1..num_vehicules, 1..num_clients] of int: acces_autorise;

% =============== CONSTANTES DÉRIVÉES =========================
int: Cl = num_clients;
int: V  = num_vehicules;
int: ND = Cl + 1;
int: NV = ND + V - 1;

set of int: NODES        = 1..NV;
set of int: CLIENTS      = 2..ND;
set of int: DEPOT_COPIES = (ND+1)..NV;
set of int: DEPOTS       = {1} union DEPOT_COPIES;

array[1..V] of int: depot_of = [1] ++ [ND + v - 1 | v in 2..V];

int: H_MAX = max(late);

% Découpage horaire (t=0 = 06h00) :
%   MATIN (06h-10h) → c1 : t in [0, 240)
%   MIDI  (10h-15h) → c2 : t in [240, 540)
%   SOIR  (15h-21h) → c3 : t in [540, 900)
%   NUIT  (21h+)    → c0 : t >= 900
array[0..H_MAX+100] of 0..3: creneau_de = array1d(0..H_MAX+100,
  [ if t < 240 then 1
    elseif t < 540 then 2
    elseif t < 900 then 3
    else 0 endif
  | t in 0..H_MAX+100 ]);

% =============== EXTENSION AUX NŒUDS-COPIES ==================
function int: ext(int: i) = if i in CLIENTS then i else 1 endif;

array[NODES] of int: dem = [if i in CLIENTS then demande[i] else 0       endif | i in NODES];
array[NODES] of int: ear = [if i in CLIENTS then early[i]   else early[1] endif | i in NODES];
array[NODES] of int: lat = [if i in CLIENTS then late[i]    else late[1]  endif | i in NODES];
array[NODES] of int: srv = [if i in CLIENTS then service[i] else 0       endif | i in NODES];

% Matrice distance étendue
array[NODES, NODES] of int: D =
  array2d(NODES, NODES, [distance[ext(i), ext(j)] | i in NODES, j in NODES]);

% Matrice 3D : TT[créneau, i, j] = temps trajet (minutes) selon créneau horaire
array[0..3, NODES, NODES] of int: TT = array3d(0..3, NODES, NODES,
  [temps_trajet_c0[ext(i), ext(j)] | i in NODES, j in NODES] ++
  [temps_trajet_c1[ext(i), ext(j)] | i in NODES, j in NODES] ++
  [temps_trajet_c2[ext(i), ext(j)] | i in NODES, j in NODES] ++
  [temps_trajet_c3[ext(i), ext(j)] | i in NODES, j in NODES]);

% =============== VARIABLES DE DÉCISION =======================
array[NODES] of var NODES:        successor;
array[NODES] of var NODES:        predecessor;
array[NODES] of var 1..V:         vehicle;
array[NODES] of var 0..H_MAX:     arrivee;

% =============== CONTRAINTES =================================

% (1) Tournée fermée + lien predecessor/successor
constraint circuit(successor);
constraint inverse(successor, predecessor);

% (2) Affectation véhicule fixe pour les dépôts
constraint forall(v in 1..V)(vehicle[depot_of[v]] = v);

% (3) Propagation du véhicule via prédécesseur
constraint forall(i in CLIENTS)(vehicle[i] = vehicle[predecessor[i]]);

% (4) Heure d'arrivée au dépôt = 0
constraint forall(i in DEPOTS)(arrivee[i] = 0);

% (5) Fenêtres de temps clients
constraint forall(i in CLIENTS)(
  arrivee[i] >= ear[i] /\ arrivee[i] <= lat[i]
);

% (6) Cohérence temporelle TIME-DEPENDENT (4 créneaux Waze)
%     Pour chaque client i : arrivée >= arrivée_prédécesseur
%                          + service_prédécesseur
%                          + trajet(créneau au départ, prédécesseur, i)
constraint forall(i in CLIENTS)(
  let {
    var NODES: p     = predecessor[i];
    var 0..H_MAX: tp = arrivee[p] + srv[p];   % heure de départ depuis p
    var 0..3: cp     = creneau_de[tp];        % créneau Waze à ce départ
  } in
  arrivee[i] >= tp + TT[cp, p, i]
);

% (7) Retour au dépôt avant fermeture (avec créneau dynamique)
constraint forall(i in CLIENTS)(
  let {
    var 0..H_MAX: ti = arrivee[i] + srv[i];
    var 0..3: ci     = creneau_de[ti];
  } in
  ti + TT[ci, i, 1] <= lat[1]
);

% (8) Capacité par véhicule (bin packing global) - flotte hétérogène
constraint bin_packing_capa(
  capacite_vehicule,
  [vehicle[i] | i in CLIENTS],
  [dem[i]     | i in CLIENTS]
);

% (9) Zones à accès restreint (médina, proche médina)
constraint forall(i in CLIENTS, v in 1..V where acces_autorise[v, i-1] = 0)(
  vehicle[i] != v
);

% =============== OBJECTIF ====================================
var int: distance_totale = sum(i in NODES)(D[i, successor[i]]);

% =============== RECHERCHE CP + LNS ==========================
solve
  :: seq_search([
       int_search(successor, first_fail, indomain_min),
       int_search(vehicle,   first_fail, indomain_min),
       int_search(arrivee,   smallest,   indomain_min)
     ])
  :: relax_and_reconstruct(successor, 85)
  :: restart_luby(100)
  minimize distance_totale;

% =============== SORTIE ======================================
output [
  "=== SOLUTION VRPTW Casablanca (v3 - time-dependent) ===\n",
  "Distance totale : ", show(distance_totale), " m\n",
  "\nsuccessor = ", show(successor), "\n",
  "vehicle   = ", show(vehicle),   "\n",
  "arrivee   = ", show(arrivee),   "\n",
  "\n--- Charge par véhicule ---\n"
] ++ [
  "V" ++ show(v) ++ " (type=" ++ show(type_vehicule[v])
        ++ ", cap=" ++ show(capacite_vehicule[v]) ++ ") : charge="
        ++ show(sum(i in CLIENTS)(bool2int(fix(vehicle[i]) = v) * dem[i]))
        ++ " kg\n"
| v in 1..V ];
