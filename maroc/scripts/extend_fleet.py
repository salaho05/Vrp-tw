# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
Génère une version modifiée de instance_maroc_vrptw.dzn avec plus de véhicules.
Usage :
    python extend_fleet.py <input.dzn> <output.dzn> <n_triporteurs> <n_fourgonnettes> <n_camions>

Exemple :
    python extend_fleet.py instance_maroc_vrptw.dzn instance_maroc_vrptw_25.dzn 15 5 5
    -> 15 triporteurs + 5 fourgonnettes + 5 camions = 25 véhicules
"""
import re
import sys
from pathlib import Path

# Capacités par type (kg)
CAPS = {1: 300, 2: 1200, 3: 5000}
NAMES = {1: "Triporteur", 2: "Fourgonnette", 3: "Camion"}


def parse_acces_autorise(text):
    """Extrait la matrice acces_autorise sous forme de liste de lignes (chaînes brutes)."""
    m = re.search(r"acces_autorise\s*=\s*\[\|(.*?)\|\];", text, re.DOTALL)
    if not m:
        raise ValueError("Section acces_autorise introuvable")
    body = m.group(1)
    # Chaque ligne est séparée par '|', on garde les lignes non vides
    rows = [r.strip() for r in body.split("|") if r.strip()]
    return rows, m.span()


def build_new_dzn(input_path, output_path, n_trip, n_four, n_cam):
    text = Path(input_path).read_text(encoding="utf-8")

    # Extraire les lignes d'accès originales (18 lignes : 8 trip + 5 four + 5 cam)
    rows, span = parse_acces_autorise(text)
    if len(rows) != 18:
        print(f"⚠️  Attention : {len(rows)} lignes d'accès trouvées (18 attendues).")

    # Modèles : ligne typique pour chaque type (on prend la 1ère existante)
    row_trip = rows[0]   # triporteur (tout = 1)
    row_four = rows[8]   # fourgonnette (proche médina interdite)
    row_cam  = rows[13]  # camion (médina + proche médina interdites)

    # Construire les nouvelles lignes en respectant la structure par type
    new_rows = (
        [row_trip] * n_trip +
        [row_four] * n_four +
        [row_cam]  * n_cam
    )
    n_total = n_trip + n_four + n_cam

    # Construire les nouveaux tableaux capacite_vehicule et type_vehicule
    types  = [1]*n_trip + [2]*n_four + [3]*n_cam
    caps   = [CAPS[t] for t in types]

    # Reconstruire le contenu
    new_text = text

    # 1) num_vehicules
    new_text = re.sub(
        r"num_vehicules\s*=\s*\d+\s*;",
        f"num_vehicules = {n_total};",
        new_text
    )

    # 2) capacite_vehicule
    new_text = re.sub(
        r"capacite_vehicule\s*=\s*\[[^\]]*\];",
        f"capacite_vehicule = {caps};",
        new_text
    )

    # 3) type_vehicule
    new_text = re.sub(
        r"type_vehicule\s*=\s*\[[^\]]*\];",
        f"type_vehicule     = {types};",
        new_text
    )

    # 4) Comment "Types:" pour rester cohérent
    new_text = re.sub(
        r"% Types:[^\n]*",
        f"% Types: 1=Triporteur(300kg)x{n_trip}, 2=Fourgonnette(1200kg)x{n_four}, 3=Camion(5000kg)x{n_cam}",
        new_text
    )

    # 5) acces_autorise (reconstruction complète)
    new_acces_body = "\n  " + " |\n  ".join(new_rows) + " |"
    new_acces = f"acces_autorise = \n[|{new_acces_body}];"
    new_text = re.sub(
        r"acces_autorise\s*=\s*\[\|.*?\|\];",
        new_acces,
        new_text,
        flags=re.DOTALL
    )

    Path(output_path).write_text(new_text, encoding="utf-8")
    print(f"✅ Généré : {output_path}")
    print(f"   Total : {n_total} véhicules ({n_trip} triporteurs + {n_four} fourgonnettes + {n_cam} camions)")
    cap_total = sum(caps)
    print(f"   Capacité totale : {cap_total} kg")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(__doc__)
        sys.exit(1)
    build_new_dzn(
        sys.argv[1], sys.argv[2],
        int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    )