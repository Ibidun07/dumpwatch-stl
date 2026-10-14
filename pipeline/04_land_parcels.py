"""Step 4: Attach City-owned (LRA) land and registered vacant buildings to parcel points.

Usage: python 04_land_parcels.py data/geo outputs
Inputs (in data/geo):
  parcels/Parcels.shp            Assessor parcels (State Plane MO East, feet)
  lra.csv                        LRA inventory (ParcelId)
  vb.json                        Vacant building overview, keyed by parcel HANDLE
Output: outputs/parcels_pts.parquet  one point per parcel with flags
"""
import geopandas as gpd, pandas as pd, json, sys

g, o = sys.argv[1], sys.argv[2]
p = gpd.read_file(g + '/parcels/Parcels.shp',
                  columns=['ParcelId', 'HANDLE', 'VacantLot', 'AsrLandUse', 'LANDAREA',
                           'NBRHD', 'SITEADDR', 'OwnerCode', 'NbrOfBld_1'])
p['ParcelId'] = p.ParcelId.astype(str).str.strip()

# One representative point per parcel, in three coordinate systems
c = p.geometry.representative_point()
ll = gpd.GeoSeries(c, crs=p.crs).to_crs(4326)
merc = gpd.GeoSeries(c, crs=p.crs).to_crs(3857)   # same system as 311 SRX/SRY
p['lat'], p['lon'] = ll.y, ll.x
p['mx'], p['my'] = merc.x, merc.y

# City-owned land (LRA) joins on ParcelId
lra = pd.read_csv(g + '/lra.csv', dtype=str)
p['lra'] = p.ParcelId.isin(set(lra.ParcelId.str.strip()))

# Vacant building registry is keyed by HANDLE, not ParcelId.
# Several parcels can share a HANDLE, so count each building once.
vb = json.load(open(g + '/vb.json'))
h = p.HANDLE.astype(str).str.split('.').str[0]
p['vacbldg'] = h.isin(set(vb)) & ~p.HANDLE.duplicated()
for k in ['mo', 'vmaj', 'csb']:   # months vacant, major violations, 311 count
    p['vb_' + k] = h.map(lambda i: vb.get(i, {}).get(k, 0))

p['vacant_lot'] = p.VacantLot.astype(str).isin(['-1', '1', 'True'])

print(f'parcels {len(p)} | LRA {p.lra.sum()} of {lra.ParcelId.nunique()} | '
      f'vacant buildings {p.vacbldg.sum()} of {len(vb)} | vacant lots {p.vacant_lot.sum()}')
p.drop(columns='geometry').to_parquet(o + '/parcels_pts.parquet', index=False)
