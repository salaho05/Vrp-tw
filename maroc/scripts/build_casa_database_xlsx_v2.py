"""
================================================================================
 build_casa_database_xlsx_v2.py
 Construit casa_logistics.xlsx avec des feuilles VRAIMENT EXPLOITABLES.

 Ameliorations vs v1 :
   - waze_times eclate en 7 feuilles WIDE (1 par jour, format identique a la source)
     * Format : ligne = (from, to), colonnes = h0, h1, ..., h23
   - access_rules en format WIDE (1 ligne par client, 3 colonnes Triporteur/Fourg/Camion)
   - restricted_zones SIMPLIFIE : on remplace WKT par bbox lisible + centroid
     (plus une colonne wkt pour usage programmatique)
================================================================================
"""

from pathlib import Path
import zipfile, hashlib, sys
import warnings; warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np

try:
    import geopandas as gpd
    from shapely.ops import unary_union
    from shapely import wkt
except ImportError:
    sys.exit("pip install geopandas fiona shapely pyproj openpyxl")


# =============================================================================
# CONFIG
# =============================================================================
DS_XLS    = Path("Dataset for traffic analysis in Casablanca, Morocco.xlsx")
GPKG_ZIP  = Path("morocco-260503-free.gpkg.zip")
NARSA_XLS = Path("trans.narsa2023.xlsx")
OUT_XLSX  = Path("casa_logistics.xlsx")

CASA_BBOX = (-7.78, 33.49, -7.42, 33.68)
PED_BUFFER_M, PED_CLUSTER_MIN_M2 = 40, 5000


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""): h.update(chunk)
    return h.hexdigest()[:16]


# =============================================================================
# 1. SOURCES
# =============================================================================
def build_sources():
    print("[1] Sources...")
    return pd.DataFrame([
        dict(source_id="dataset_casa",
             source_name="Dataset for traffic analysis in Casablanca, Morocco",
             file_name=DS_XLS.name, file_hash=file_sha256(DS_XLS),
             url="https://data.mendeley.com/datasets/...",
             notes="110 GPS points + Waze 7 jours x 24 heures"),
        dict(source_id="osm_morocco",
             source_name="OpenStreetMap Morocco (Geofabrik)",
             file_name=GPKG_ZIP.name, file_hash=file_sha256(GPKG_ZIP),
             url="https://download.geofabrik.de/africa/morocco.html",
             notes="Schema gis_osm_*_free"),
        dict(source_id="narsa_2023",
             source_name="NARSA - Parc auto Maroc 2023",
             file_name=NARSA_XLS.name, file_hash=file_sha256(NARSA_XLS),
             url="https://www.narsa.ma/",
             notes="Vehicules en circulation au 31/12/2023"),
    ])


# =============================================================================
# 2. CLIENTS + COMMUNES
# =============================================================================
def build_clients_communes():
    print("[2] Clients + Communes...")
    pts = pd.read_excel(DS_XLS, sheet_name="Table 0. Coordinates", skiprows=11)
    pts = pts[["Commune", "ZIP code", "Index", "Latitude", "Longitude"]].copy()
    pts["Commune"] = pts["Commune"].ffill()
    pts = pts.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)
    pts["Index"] = pts["Index"].astype(int)

    communes = (pts.groupby("Commune")
                  .agg(zip_code=("ZIP code", "first"),
                       n_clients=("Index", "count"))
                  .reset_index())
    communes["commune_id"] = range(1, len(communes) + 1)
    communes = communes.rename(columns={"Commune": "name"})
    communes = communes[["commune_id", "name", "zip_code", "n_clients"]]

    cm = dict(zip(communes["name"], communes["commune_id"]))
    pts["commune_id"] = pts["Commune"].map(cm)
    print(f"    {len(communes)} communes, {len(pts)} points GPS")
    return communes, pts


# =============================================================================
# 3. ZONES RESTREINTES (FORMAT LISIBLE)
# =============================================================================
def build_restricted_zones():
    print("[3] Zones pietonnes...")
    work = Path("./_tmp_gpkg"); work.mkdir(exist_ok=True)
    if not list(work.rglob("*.gpkg")):
        with zipfile.ZipFile(GPKG_ZIP) as z: z.extractall(work)
    gpkg_path = next(work.rglob("*.gpkg"))

    roads = gpd.read_file(gpkg_path, layer="gis_osm_roads_free", bbox=CASA_BBOX)
    ped = roads[roads["fclass"].isin(
        ["pedestrian", "living_street", "path", "steps"])]
    ped_proj = ped.to_crs(epsg=32629)
    buffered = unary_union(ped_proj.geometry.buffer(PED_BUFFER_M).values)
    polys = list(buffered.geoms) if hasattr(buffered, "geoms") else [buffered]
    big_proj = [p for p in polys if p.area > PED_CLUSTER_MIN_M2]
    gs_wgs = gpd.GeoSeries(big_proj, crs="EPSG:32629").to_crs("EPSG:4326")

    # FORMAT LISIBLE : centroide, bbox, surface en m2 + WKT en derniere colonne
    rows = []
    for i, (p_proj, g_wgs) in enumerate(zip(big_proj, gs_wgs)):
        c = g_wgs.centroid
        b = g_wgs.bounds  # (min_lon, min_lat, max_lon, max_lat)
        rows.append(dict(
            zone_id      = i + 1,
            zone_type    = "pedestrian_cluster",
            area_m2      = round(p_proj.area, 0),
            centroid_lat = round(c.y, 6),
            centroid_lon = round(c.x, 6),
            bbox_min_lat = round(b[1], 6),
            bbox_min_lon = round(b[0], 6),
            bbox_max_lat = round(b[3], 6),
            bbox_max_lon = round(b[2], 6),
            geometry_wkt = wkt.dumps(g_wgs),
        ))
    print(f"    {len(rows)} clusters pietons")
    return pd.DataFrame(rows), gs_wgs


# =============================================================================
# 4. CLIENTS AVEC TIER
# =============================================================================
def tag_clients(pts, ped_zones):
    print("[4] Tagging tier d'acces...")
    gdf = gpd.GeoDataFrame(pts,
        geometry=gpd.points_from_xy(pts["Longitude"], pts["Latitude"]),
        crs="EPSG:4326")
    ped_union = unary_union(list(ped_zones))
    gdf["in_ped"] = gdf.geometry.within(ped_union)
    gdf_proj = gdf.to_crs(epsg=32629)
    ped_proj = (gpd.GeoSeries([ped_union], crs="EPSG:4326")
                  .to_crs(epsg=32629).iloc[0])
    gdf["dist_ped_m"] = gdf_proj.geometry.distance(ped_proj).round(0)

    def tier(r):
        if r["in_ped"]:           return 1
        if r["dist_ped_m"] < 100: return 2
        return 3
    gdf["tier"] = gdf.apply(tier, axis=1)

    df = gdf[["Index", "commune_id", "Latitude", "Longitude",
              "in_ped", "dist_ped_m", "tier"]].copy()
    df.columns = ["client_id", "commune_id", "latitude", "longitude",
                  "in_pedestrian", "dist_ped_m", "tier"]
    df["in_pedestrian"] = df["in_pedestrian"].astype(int)
    counts = df["tier"].value_counts().to_dict()
    print(f"    tier1={counts.get(1,0)}, tier2={counts.get(2,0)}, "
          f"tier3={counts.get(3,0)}")
    return df


# =============================================================================
# 5. WAZE EN 7 FEUILLES WIDE (FORMAT IDENTIQUE A LA SOURCE)
# =============================================================================
def build_waze_wide():
    """Renvoie un dict {day_label: DataFrame WIDE avec from/to + 24 colonnes h0-h23}"""
    print("[5] Matrice Waze (7 feuilles WIDE)...")
    days = [("Table 5. Monday",      "monday"),
            ("Table 6. Tuesday",     "tuesday"),
            ("Table 7. Wednesday",   "wednesday"),
            ("Table. 8 Thursday",    "thursday"),
            ("Table. 9 Friday",      "friday"),
            ("Table. 10 Saturday",   "saturday"),
            ("Table. 11 Sunday",     "sunday")]
    out = {}
    for sheet_name, day_label in days:
        try:
            raw = pd.read_excel(DS_XLS, sheet_name=sheet_name, header=None)
            header_row = None
            for i in range(min(20, len(raw))):
                ints = [v for v in raw.iloc[i].tolist()
                        if isinstance(v, (int, float)) and not pd.isna(v)
                        and 0 <= v <= 23 and v == int(v)]
                if len(ints) >= 24: header_row = i; break
            if header_row is None: header_row = 9

            df = pd.read_excel(DS_XLS, sheet_name=sheet_name, header=header_row)
            int_cols_id, int_cols_hour = [], {}
            for c in df.columns:
                try:
                    h = int(c)
                    if 0 <= h <= 23: int_cols_hour[h] = c; continue
                except (ValueError, TypeError): pass
                if "index" in str(c).lower(): int_cols_id.append(c)
            if len(int_cols_hour) < 24 or len(int_cols_id) < 2:
                print(f"    {day_label}: SKIP"); continue

            from_col, to_col = int_cols_id[0], int_cols_id[1]
            df = df.dropna(subset=[from_col, to_col])
            df[from_col] = df[from_col].astype(int)
            df[to_col]   = df[to_col].astype(int)

            # Format WIDE : from_client | to_client | h0 | h1 | ... | h23
            wide = pd.DataFrame()
            wide["from_client"] = df[from_col].values
            wide["to_client"]   = df[to_col].values
            for h in range(24):
                wide[f"h{h:02d}"] = df[int_cols_hour[h]].values.round(2)
            out[day_label] = wide
            print(f"    {day_label:10}: {len(wide)} OD pairs x 24 heures")
        except Exception as e:
            print(f"    {day_label:10}: SKIP ({e})")
    return out


# =============================================================================
# 6. FLOTTE
# =============================================================================
def build_fleet():
    print("[6] Flotte (NARSA 2023)...")
    narsa = pd.read_excel(NARSA_XLS, sheet_name="3-4", header=None)
    n_moto = int(narsa.iloc[5, 1])
    n_util = int(narsa.iloc[7, 1])
    total = n_moto + n_util
    r_moto = n_moto / total
    r_util = n_util / total

    print(f"    NARSA : {n_moto:,} motos ({r_moto*100:.1f}%) | "
          f"{n_util:,} utilitaires ({r_util*100:.1f}%)")
    return pd.DataFrame([
        dict(vtype=1, name="Triporteur",   capacity_kg=300,  speed_kmh=25,
             fixed_cost_MAD=50,  var_cost_MAD_per_km=0.8,
             narsa_ratio=round(r_moto, 4),       access_pedestrian=1),
        dict(vtype=2, name="Fourgonnette", capacity_kg=1200, speed_kmh=35,
             fixed_cost_MAD=200, var_cost_MAD_per_km=2.5,
             narsa_ratio=round(r_util*0.80, 4), access_pedestrian=1),
        dict(vtype=3, name="Camion",       capacity_kg=5000, speed_kmh=30,
             fixed_cost_MAD=500, var_cost_MAD_per_km=4.5,
             narsa_ratio=round(r_util*0.20, 4), access_pedestrian=0),
    ])


# =============================================================================
# 7. ACCESS WIDE (1 LIGNE = 1 CLIENT, COLONNES = TYPES)
# =============================================================================
def build_access_wide(clients_df):
    print("[7] Access rules (format WIDE)...")
    rows = []
    for _, c in clients_df.iterrows():
        tier = int(c["tier"])
        a_tripo  = 1
        a_fourg  = 1 if tier in (2, 3) else 0
        a_camion = 1 if tier == 3 else 0
        rows.append(dict(
            client_id     = int(c["client_id"]),
            tier          = tier,
            access_Triporteur   = a_tripo,
            access_Fourgonnette = a_fourg,
            access_Camion       = a_camion,
        ))
    print(f"    {len(rows)} clients (110 lignes vs 330 en LONG)")
    return pd.DataFrame(rows)


# =============================================================================
# 8. README ENRICHI
# =============================================================================
def build_readme():
    return pd.DataFrame([
        dict(sheet="README",            rows="-",
             format="documentation",
             role="Cette feuille : guide d'utilisation"),
        dict(sheet="sources",           rows="3",
             format="WIDE",
             role="Tracabilite des 3 datasets primaires (hash SHA256)"),
        dict(sheet="communes",          rows="22",
             format="WIDE",
             role="Communes administratives Casa (referentiel)"),
        dict(sheet="clients",           rows="110",
             format="WIDE",
             role="Clients GPS + commune + tier d'acces"),
        dict(sheet="restricted_zones",  rows="453",
             format="WIDE",
             role="Zones pietonnes : centroide + bbox lisibles + WKT pour code"),
        dict(sheet="fleet_specs",       rows="3",
             format="WIDE",
             role="Specifications types vehicules + ratios NARSA"),
        dict(sheet="access_rules",      rows="110",
             format="WIDE (1 client/ligne)",
             role="Matrice acces : 3 colonnes Triporteur/Fourg/Camion"),
        dict(sheet="waze_monday",       rows="440",
             format="WIDE (h00..h23)",
             role="Matrice Waze Lundi : OD pairs x 24 colonnes heures"),
        dict(sheet="waze_tuesday",      rows="440",
             format="WIDE (h00..h23)", role="Idem Mardi"),
        dict(sheet="waze_wednesday",    rows="440",
             format="WIDE (h00..h23)", role="Idem Mercredi"),
        dict(sheet="waze_thursday",     rows="440",
             format="WIDE (h00..h23)", role="Idem Jeudi"),
        dict(sheet="waze_friday",       rows="440",
             format="WIDE (h00..h23)", role="Idem Vendredi"),
        dict(sheet="waze_saturday",     rows="440",
             format="WIDE (h00..h23)", role="Idem Samedi"),
        dict(sheet="waze_sunday",       rows="440",
             format="WIDE (h00..h23)", role="Idem Dimanche"),
    ])


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("CONSTRUCTION casa_logistics.xlsx (version exploitable)")
    print("=" * 70)

    sources_df       = build_sources()
    communes_df, pts = build_clients_communes()
    zones_df, ped_zones = build_restricted_zones()
    clients_df       = tag_clients(pts, ped_zones)
    waze_per_day     = build_waze_wide()
    fleet_df         = build_fleet()
    access_df        = build_access_wide(clients_df)
    readme_df        = build_readme()

    print(f"\n[8] Ecriture {OUT_XLSX}...")
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        readme_df.to_excel(writer,    sheet_name="README",         index=False)
        sources_df.to_excel(writer,    sheet_name="sources",        index=False)
        communes_df.to_excel(writer,   sheet_name="communes",       index=False)
        clients_df.to_excel(writer,    sheet_name="clients",        index=False)
        zones_df.to_excel(writer,      sheet_name="restricted_zones", index=False)
        fleet_df.to_excel(writer,      sheet_name="fleet_specs",    index=False)
        access_df.to_excel(writer,     sheet_name="access_rules",   index=False)
        # 7 feuilles Waze (1 par jour)
        for day, df in waze_per_day.items():
            df.to_excel(writer, sheet_name=f"waze_{day}", index=False)

    size_mb = OUT_XLSX.stat().st_size / (1024*1024)
    print(f"    [OK] {size_mb:.1f} MB")

    print("\n" + "=" * 70)
    print("BASE EXPLOITABLE PRETE")
    print("=" * 70)
    print(f"\n  Feuille            | Lignes | Format")
    print(f"  {'-'*48}")
    sheets_summary = [
        ("README",          len(readme_df),     "doc"),
        ("sources",         len(sources_df),    "WIDE"),
        ("communes",        len(communes_df),   "WIDE"),
        ("clients",         len(clients_df),    "WIDE"),
        ("restricted_zones",len(zones_df),      "WIDE+WKT"),
        ("fleet_specs",     len(fleet_df),      "WIDE"),
        ("access_rules",    len(access_df),     "WIDE matrice"),
    ]
    for s, n, f in sheets_summary:
        print(f"  {s:18} | {n:>6} | {f}")
    for day, df in waze_per_day.items():
        print(f"  waze_{day:13} | {len(df):>6} | WIDE (h00..h23)")
    print(f"\nFichier : {OUT_XLSX.resolve()}")
