import math
import os

def parse_solomon(filename):
    """Lit un fichier Solomon .txt et retourne les données"""
    with open(filename, 'r') as f:
        lines = f.readlines()

    # Chercher la section VEHICLE
    for i, line in enumerate(lines):
        if 'VEHICLE' in line.upper():
            vehicle_line = lines[i+2].split()
            nb_vehicles = int(vehicle_line[0])
            capacity    = int(vehicle_line[1])
            break

    # Chercher la section CUSTOMER
    customers = []
    reading = False
    for line in lines:
        if 'CUST' in line.upper() and 'NO' in line.upper():
            reading = True
            continue
        if reading:
            parts = line.split()
            if len(parts) == 7:
                customers.append({
                    'id'      : int(parts[0]),
                    'x'       : float(parts[1]),
                    'y'       : float(parts[2]),
                    'demand'  : int(parts[3]),
                    'early'   : int(parts[4]),
                    'late'    : int(parts[5]),
                    'service' : int(parts[6])
                })

    return nb_vehicles, capacity, customers


def compute_distances(customers):
    """Calcule la matrice de distances euclidiennes"""
    n = len(customers)
    dist = []
    for i in range(n):
        row = []
        for j in range(n):
            dx = customers[i]['x'] - customers[j]['x']
            dy = customers[i]['y'] - customers[j]['y']
            # Arrondi à l'entier le plus proche (convention Solomon)
            row.append(round(math.sqrt(dx*dx + dy*dy)))
        dist.append(row)
    return dist


def write_dzn(output_file, nb_vehicles, capacity, customers):
    """Écrit le fichier .dzn pour MiniZinc"""
    
    # Client 0 = dépôt, clients 1..n = vrais clients
    depot    = customers[0]
    clients  = customers[1:]  # sans le dépôt
    n        = len(clients)
    all_cust = customers      # dépôt + clients

    dist = compute_distances(all_cust)

    with open(output_file, 'w') as f:
        f.write(f"% Instance générée automatiquement depuis Solomon\n")
        f.write(f"% Fichier : {output_file}\n\n")

        # Nombre de clients (sans dépôt)
        f.write(f"n = {n};\n")

        # Nombre de véhicules
        f.write(f"K = {nb_vehicles};\n")

        # Capacité par véhicule
        f.write(f"cap = {capacity};\n\n")

        # Demandes (clients 1..n, sans le dépôt)
        demands = [c['demand'] for c in clients]
        f.write(f"demand = {demands};\n\n")

        # Fenêtres de temps — early (clients 1..n)
        early = [c['early'] for c in clients]
        f.write(f"early = {early};\n\n")

        # Fenêtres de temps — late (clients 1..n)
        late = [c['late'] for c in clients]
        f.write(f"late = {late};\n\n")

        # Temps de service (clients 1..n)
        service = [c['service'] for c in clients]
        f.write(f"service = {service};\n\n")

        # Fenêtre du dépôt
        f.write(f"depot_early = {depot['early']};\n")
        f.write(f"depot_late  = {depot['late']};\n\n")

        # Matrice de distances (n+1 x n+1, incluant dépôt en index 0)
        f.write(f"% dist[i,j] : distance entre i et j (0 = dépôt, 1..n = clients)\n")
        f.write(f"dist = [|")
        for i in range(n + 1):
            row_str = ", ".join(str(dist[i][j]) for j in range(n + 1))
            if i < n:
                f.write(f"\n  {row_str},")
            else:
                f.write(f"\n  {row_str}")
        f.write(f"\n|];\n")

    print(f"  OK Genere : {output_file}  ({n} clients, {nb_vehicles} vehicules, cap={capacity})")


def convert_instance(solomon_file, sizes=[25, 50, 100]):
    """Convertit un fichier Solomon en plusieurs tailles"""
    
    if not os.path.exists(solomon_file):
        print(f"  ERREUR : Fichier introuvable : {solomon_file}")
        return

    nb_vehicles, capacity, customers = parse_solomon(solomon_file)
    
    # customers[0] = dépôt, customers[1:] = vrais clients
    base_name = os.path.splitext(os.path.basename(solomon_file))[0]  # ex: R101

    for size in sizes:
        # Prendre dépôt + 'size' premiers clients
        subset = customers[:size + 1]  # +1 pour le dépôt
        
        if len(subset) < size + 1:
            print(f"  ATTENTION : {solomon_file} n'a que {len(customers)-1} clients, ignore pour taille {size}")
            continue

        output_file = f"{base_name}_{size}.dzn"
        write_dzn(output_file, nb_vehicles, capacity, subset)


# ============================================================
# MAIN — Lance la conversion ici
# ============================================================
if __name__ == "__main__":
    
    print("=" * 50)
    print("  Conversion Solomon -> MiniZinc .dzn")
    print("=" * 50)

    # Liste des fichiers Solomon à convertir
    # ⚠️  Mets ici le chemin exact vers tes fichiers téléchargés
    fichiers = [
        "R101.txt",
        "C101.txt",
        "RC101.txt"
    ]

    tailles = [25, 50, 100]

    for f in fichiers:
        print(f"\n>> Traitement de {f} ...")
        convert_instance(f, tailles)

    print("\n" + "=" * 50)
    print("  Conversion terminée !")
    print("  Fichiers .dzn générés dans le dossier courant")
    print("=" * 50)