import geopandas as gpd, pandas as pd, numpy as np, sys
from shapely.strtree import STRtree
o,g=sys.argv[1],sys.argv[2]; S=250
p=pd.read_parquet(o+'/parcels_pts.parquet')
p['gx']=(p.mx//S).astype(int); p['gy']=(p.my//S).astype(int)
f=p.groupby(['gx','gy']).agg(parcels=('ParcelId','size'),vac_lot=('vacant_lot','sum'),lra=('lra','sum'),vac_bldg=('vacbldg','sum'))
# arterial distance from cell center
s=gpd.read_file(g+'/streets/tgr_str_cl.shp',columns=['CLASS']).to_crs(3857)
art=s[s.CLASS.isin(['A31','A98','A97'])].geometry.union_all()
cx=(f.index.get_level_values(0)+.5)*S; cy=(f.index.get_level_values(1)+.5)*S
pts=gpd.GeoSeries(gpd.points_from_xy(cx,cy),crs=3857)
f['art_dist']=pts.distance(art).values*0.78   # mercator -> meters at 38.6N
f.reset_index().to_parquet(o+'/cell_land.parquet',index=False)
print(f.describe().round(1).to_string())
