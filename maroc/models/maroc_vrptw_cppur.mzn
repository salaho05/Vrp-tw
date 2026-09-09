
% Modele CP PUR pour VRPTW Marocain (Casablanca)

% SANS LNS - pour analyser la frontiere CP pur / LNS
% Question : a quelle taille CP pur devient-il insuffisant ?



include "globals.mzn";
include "circuit.mzn";
include "inverse.mzn";
include "bin_packing_capa.mzn";

% =============== PARAMETRES =================================
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
array[1..num_clients+1, 1..num_clients+1] of int: temps_trajet_c0;
array[1..num_clients+1, 1..num_clients+1] of int: temps_trajet_c1;
array[1..num_clients+1, 1..num_clients+1] of int: temps_trajet_c2;
array[1..num_clients+1, 1..num_clients+1] of int: temps_trajet_c3;
array[1..num_vehicules, 1..num_clients] of int: acces_autorise;

% =============== CONSTANTES =================================
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

array[0..H_MAX+100] of int: creneau_de = array1d(0..H_MAX+100,
  [ if t < 240 then 1
    elseif t < 540 then 2
    elseif t < 900 then 3
    else 0 endif
  | t in 0..H_MAX+100 ]);

function int: ext(int: i) = if i in CLIENTS then i else 1 endif;

array[NODES] of int: dem = [if i in CLIENTS then demande[i] else 0        endif | i in NODES];
array[NODES] of int: ear = [if i in CLIENTS then early[i]   else early[1]  endif | i in NODES];
array[NODES] of int: lat = [if i in CLIENTS then late[i]    else late[1]   endif | i in NODES];
array[NODES] of int: srv = [if i in CLIENTS then service[i] else 0        endif | i in NODES];

array[NODES, NODES] of int: D =
  array2d(NODES, NODES, [distance[ext(i), ext(j)] | i in NODES, j in NODES]);

array[0..3, NODES, NODES] of int: TT = array3d(0..3, NODES, NODES,
  [temps_trajet_c0[ext(i), ext(j)] | i in NODES, j in NODES] ++
  [temps_trajet_c1[ext(i), ext(j)] | i in NODES, j in NODES] ++
  [temps_trajet_c2[ext(i), ext(j)] | i in NODES, j in NODES] ++
  [temps_trajet_c3[ext(i), ext(j)] | i in NODES, j in NODES]);

% =============== VARIABLES ==================================
array[NODES] of var NODES:    successor;
array[NODES] of var NODES:    predecessor;
array[NODES] of var 1..V:     vehicle;
array[NODES] of var 0..H_MAX: arrivee;

var int: distance_totale = sum(i in NODES)(D[i, successor[i]]);

% =============== CONTRAINTES ================================

constraint circuit(successor);
constraint inverse(successor, predecessor);

constraint forall(v in 1..V)(vehicle[depot_of[v]] = v);

constraint forall(i in CLIENTS)(vehicle[i] = vehicle[predecessor[i]]);

constraint forall(i in DEPOTS)(arrivee[i] = 0);

constraint forall(i in CLIENTS)(
  arrivee[i] >= ear[i] /\ arrivee[i] <= lat[i]
);

constraint forall(i in CLIENTS)(
  let {
    var NODES: p     = predecessor[i];
    var 0..H_MAX: tp = arrivee[p] + srv[p];
    var 0..3: cp     = creneau_de[min(tp, H_MAX+100)];
  } in
  arrivee[i] >= tp + TT[cp, p, i]
);

constraint forall(i in CLIENTS)(
  let {
    var 0..H_MAX: ti = arrivee[i] + srv[i];
    var 0..3: ci     = creneau_de[min(ti, H_MAX+100)];
  } in
  ti + TT[ci, i, 1] <= lat[1]
);

constraint bin_packing_capa(
  capacite_vehicule,
  [vehicle[i] | i in CLIENTS],
  [dem[i]     | i in CLIENTS]
);

constraint forall(i in CLIENTS, v in 1..V where acces_autorise[v, i-1] = 0)(
  vehicle[i] != v
);

% =============== OBJECTIF CP PUR ============================
% Pas de LNS, pas de restart, pas de relax_and_reconstruct
% Chuffed explore l'espace de recherche avec clause learning
solve
  :: seq_search([
       int_search(successor, first_fail, indomain_min),
       int_search(vehicle,   first_fail, indomain_min),
       int_search(arrivee,   smallest,   indomain_min)
     ])
  minimize distance_totale;

% =============== OUTPUT =====================================
output [
  "\n========================================================\n",
  "   SOLUTION VRPTW - CP PUR (sans LNS)\n",
  "   Solveur : Chuffed\n",
  "========================================================\n",
  "Distance totale    : ", show(distance_totale div 1000), " km\n",
  "Distance totale    : ", show(distance_totale), " m\n",
  "--------------------------------------------------------\n",
  "TOURNEES PAR VEHICULE :\n",
  "--------------------------------------------------------\n"
] ++ [
  "V" ++ show(v) ++
  " [" ++ (if   type_vehicule[v] = 1 then "Triporteur   300kg"
           elseif type_vehicule[v] = 2 then "Fourgon     1200kg"
           else                             "Camion      5000kg" endif) ++
  "] charge=" ++ show(sum(i in CLIENTS)(bool2int(fix(vehicle[i]) = v) * dem[i])) ++
  "kg : Depot" ++
  concat([
    " -> C" ++ show(i-1) ++
    "(arr=" ++ show(fix(arrivee[i])) ++
    ",zone=" ++ (if acces_autorise[1, i-1] = 0 then "MED1"
                 elseif acces_autorise[3, i-1] = 0 then "MED2"
                 else "OK" endif) ++ ")"
    | i in CLIENTS where fix(vehicle[i]) = v
  ]) ++
  " -> Depot\n"
  | v in 1..V
  where exists(i in CLIENTS)(fix(vehicle[i]) = v)
] ++ [
  "--------------------------------------------------------\n",
  "Vehicules utilises : ",
  show(sum(v in 1..V)(bool2int(exists(i in CLIENTS)(fix(vehicle[i]) = v)))),
  " / ", show(V), "\n"
];
