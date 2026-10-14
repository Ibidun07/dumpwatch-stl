import pandas as pd, numpy as np, geopandas as gpd, json, sys
from sklearn.linear_model import LogisticRegression
o,g=sys.argv[1],sys.argv[2]; S=250
d=pd.read_parquet(o+'/dumping.parquet'); d['gx']=(pd.to_numeric(d.SRX)//S).astype(int); d['gy']=(pd.to_numeric(d.SRY)//S).astype(int)
now=d.DATETIMEINIT.max()
R=pd.read_csv(o+'/risk_cells.csv')
nb=gpd.read_file(g+'/nbhd/Neighborhoods/Neighborhoods.shp')
NBN=dict(zip(nb.NHD_NUM.astype(int),nb.NHD_NAME))
p=pd.read_parquet(o+'/parcels_pts.parquet'); p['gx']=(p.mx//S).astype(int); p['gy']=(p.my//S).astype(int)
st=gpd.read_file(g+'/streets/tgr_str_cl.shp',columns=['STREETNAME','STREETTYPE','CLASS']).to_crs(3857)
art=st[st.CLASS.isin(['A31','A98','A97'])].copy(); art['nm']=(art.STREETNAME.fillna('')+' '+art.STREETTYPE.fillna('')).str.strip().str.title()
def nbname(v):
    try: return NBN.get(int(float(v)),str(v))
    except: return str(v)
DOW=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
def ring(a,b,k=1): return [(a+i,b+j) for i in range(-k,k+1) for j in range(-k,k+1)]
top=R.sort_values('risk',ascending=False).head(40)
sites=[]
for i,r in enumerate(top.itertuples(),1):
    keys=ring(r.gx,r.gy,0); kn=ring(r.gx,r.gy,1)
    h=d[d.set_index(['gx','gy']).index.isin(keys)]
    hr=h[h.year>=2022]
    w=hr[hr.type=='Witnessed dumping']
    land=p[p.set_index(['gx','gy']).index.isin(kn)]
    vbl=land[land.vacbldg].sort_values('vb_mo',ascending=False)
    pt=gpd.GeoSeries(gpd.points_from_xy([r.gx*S+S/2],[r.gy*S+S/2]),crs=3857)[0]
    dist=art.distance(pt); j=dist.idxmin()
    addr=hr.addr.str.replace(r',\s*\d{5}$','',regex=True).str.strip().value_counts().head(4)
    l12=(h.DATETIMEINIT>=now-pd.Timedelta(days=365)).sum(); p12=((h.DATETIMEINIT<now-pd.Timedelta(days=365))&(h.DATETIMEINIT>=now-pd.Timedelta(days=730))).sum()
    mix=hr.type.value_counts(normalize=True)
    wshare=mix.get('Witnessed dumping',0); vshare=mix.get('Vacant lot debris',0)+mix.get('Vacant building debris',0)
    acts=[]
    if wshare>=.25: acts.append(['Camera','Witnesses report dumping here regularly. A visible camera aimed at '+(addr.index[0].title() if len(addr) else 'the main approach')+' can capture plates.'])
    if land.lra.sum()>=40 or land.vacant_lot.sum()>=60: acts.append(['Secure lots',f'{int(land.lra.sum())} city-owned parcels and {int(land.vacant_lot.sum())} vacant lots nearby. Bollards or fencing on open frontage remove easy drop spots.'])
    if len(vbl)>=40: acts.append(['Board-up',f'{len(vbl)} registered vacant buildings nearby. Prioritize board-up and code enforcement.'])
    if mix.get('Alley/street debris',0)>=.5: acts.append(['Alley lighting + signs','Most reports are alley or street debris. Lighting and fine signage ($1,000) at alley mouths.'])
    if not acts: acts.append(['Rapid cleanup','Clear quickly. Piles left in place attract more dumping.'])
    nbv=hr.NEIGHBORHOOD.mode(); nbv=nbv.iloc[0] if len(nbv) else None
    sites.append({'rank':i,'lat':round(r.lat,5),'lon':round(r.lon,5),'tier':r.tier,'risk':round(float(r.risk),2),
      'nb':nbname(nbv),'ward':str(hr.WARD.mode().iloc[0]).lstrip('0') if len(hr) else '',
      'n_all':int(len(h)),'n_recent':int(len(hr)),'last12':int(l12),'prev12':int(p12),
      'years':{int(y):int(c) for y,c in h.groupby('year').size().items()},
      'mix':{k:int(v) for k,v in hr.type.value_counts().items()},
      'w_dow':[int((w.dow==x).sum()) for x in DOW],'w_n':int(len(w)),
      'addrs':[[a.title(),int(c)] for a,c in addr.items()],
      'med_close':round(float(hr.days_to_close.median()),1) if hr.days_to_close.notna().any() else None,
      'last':str(h.DATETIMEINIT.max().date()),
      'lra':int(land.lra.sum()),'vac_lot':int(land.vacant_lot.sum()),'vac_bldg':int(len(vbl)),
      'vb_list':[[str(a).title(),int(m),int(v)] for a,m,v in zip(vbl.SITEADDR.head(5),vbl.vb_mo.head(5),vbl.vb_vmaj.head(5))],
      'road':art.loc[j,'nm'],'road_m':int(dist[j]*0.78),'actions':acts})
# watch list: quiet cells with high land risk
L=pd.read_parquet(o+'/cell_land.parquet').set_index(['gx','gy']); L['vac_bldg']=L.vac_bldg.clip(upper=50); L=L[L.parcels>=5]
for c in ['vac_lot','lra','vac_bldg']:
    m=L[c].to_dict(); L[c+'_nb']=[sum(m.get((a+i,b+j),0) for i in(-1,0,1) for j in(-1,0,1)) for a,b in L.index]
F=['vac_lot','lra','vac_bldg','vac_lot_nb','lra_nb','vac_bldg_nb','art_dist','parcels']
def setup(cut,end):
    prior=d[(d.DATETIMEINIT<cut)&(d.DATETIMEINIT>=cut-pd.Timedelta(days=1095))].groupby(['gx','gy']).size()
    nxt=d[(d.DATETIMEINIT>=cut)&(d.DATETIMEINIT<end)].groupby(['gx','gy']).size()
    z=L[~L.index.isin(prior.index)].copy(); z['y']=z.index.isin(nxt.index).astype(int); return z
tr=pd.concat([setup(pd.Timestamp(f'{y}-01-01'),pd.Timestamp(f'{y+1}-01-01')) for y in [2022,2023,2024,2025,2026]])
m=LogisticRegression(max_iter=2000).fit(np.log1p(tr[F]),tr.y)
prior=d[d.DATETIMEINIT>=now-pd.Timedelta(days=1095)].groupby(['gx','gy']).size()
q=L[~L.index.isin(prior.index)].copy(); q['p']=m.predict_proba(np.log1p(q[F]))[:,1]
pp=p.groupby(['gx','gy']).agg(lat=('lat','mean'),lon=('lon','mean'),nbh=('NBRHD',lambda s:s.mode().iloc[0] if len(s.mode()) else None))
q=q.join(pp).sort_values('p',ascending=False).head(25)
watch=[{'lat':round(r.lat,5),'lon':round(r.lon,5),'p':round(float(r.p)*100),'nb':nbname(r.nbh),'lra':int(r.lra_nb),'vac_bldg':int(r.vac_bldg_nb),'vac_lot':int(r.vac_lot_nb)} for r in q.itertuples()]
# map layers
nbs=nb.to_crs(4326); nbs['geometry']=nbs.simplify(0.0003)
def rings(geom):
    polys=[geom] if geom.geom_type=='Polygon' else list(geom.geoms)
    return [[[round(x,4),round(y,4)] for x,y in pg.exterior.coords] for pg in polys]
nbl=[{'name':n,'num':int(k),'rings':rings(gm)} for n,k,gm in zip(nbs.NHD_NAME,nbs.NHD_NUM,nbs.geometry)]
a4=art.to_crs(4326); a4['geometry']=a4.simplify(0.0002)
lines=[[[round(x,4),round(y,4)] for x,y in (gm.coords if gm.geom_type=='LineString' else [c for l in gm.geoms for c in l.coords])] for gm in a4.geometry]
cells=[[round(r.lat,5),round(r.lon,5),round(float(r.risk),2),r.tier[0],int(r.n1)] for r in R.itertuples() if r.risk>=0.05 or r.n1>0]
val=json.load(open(o+'/risk_validation.json'))
out={'asof':str(now.date()),'sites':sites,'watch':watch,'nb':nbl,'roads':lines,'cells':cells,'val':val,
 'tiers':R.tier.value_counts().to_dict()}
json.dump(out,open(o+'/app_data.json','w'),separators=(',',':'))
print(len(json.dumps(out,separators=(',',':')))//1024,'KB','sites',len(sites),'watch',len(watch),'cells',len(cells))
for s in sites[:12]: print(s['rank'],s['nb'],s['ward'],s['n_recent'],s['last12'],s['prev12'],s['addrs'][:1],s['lra'],s['vac_bldg'],[a[0] for a in s['actions']])
for w in watch[:5]: print(w)
