import pandas as pd, numpy as np, sys, json
from sklearn.ensemble import HistGradientBoostingRegressor
o=sys.argv[1]; d=pd.read_parquet(o+'/dumping.parquet'); S=250
d['gx']=(pd.to_numeric(d.SRX)//S).astype(int); d['gy']=(pd.to_numeric(d.SRY)//S).astype(int)
cells=d.groupby(['gx','gy']).agg(lat=('lat','mean'),lon=('lon','mean')).reset_index()
land=pd.read_parquet(o+'/cell_land.parquet'); land['vac_bldg']=land.vac_bldg.clip(upper=50)
pp=pd.read_parquet(o+'/parcels_pts.parquet'); pp['gx']=(pp.mx//S).astype(int); pp['gy']=(pp.my//S).astype(int)
lc=pp.groupby(['gx','gy']).agg(lat=('lat','mean'),lon=('lon','mean')).reset_index()
cells=pd.concat([cells,lc[~lc.set_index(['gx','gy']).index.isin(cells.set_index(['gx','gy']).index)]],ignore_index=True)
LAND=land.set_index(['gx','gy'])
USE_LAND=len(sys.argv)<3
def feats(cut):
    h=d[d.DATETIMEINIT<cut]; f=cells[['gx','gy']].copy().set_index(['gx','gy'])
    for k,days in [('n1',365),('n2',730),('n3',1095),('n5',1826)]:
        f[k]=h[h.DATETIMEINIT>=cut-pd.Timedelta(days=days)].groupby(['gx','gy']).size()
    f['w3']=h[(h.DATETIMEINIT>=cut-pd.Timedelta(days=1095))&(h.type=='Witnessed dumping')].groupby(['gx','gy']).size()
    f['alley3']=h[(h.DATETIMEINIT>=cut-pd.Timedelta(days=1095))&(h.type=='Alley/street debris')].groupby(['gx','gy']).size()
    f['vac3']=h[(h.DATETIMEINIT>=cut-pd.Timedelta(days=1095))&h.type.str.startswith('Vacant')].groupby(['gx','gy']).size()
    f['yrs']=h[h.DATETIMEINIT>=cut-pd.Timedelta(days=1826)].groupby(['gx','gy']).year.nunique()
    last=h.groupby(['gx','gy']).DATETIMEINIT.max(); f['recency']=(cut-last).dt.days
    f=f.fillna({c:0 for c in f.columns if c!='recency'}).fillna({'recency':5000})
    # spatial lag: neighbors' 3-yr count (3x3 and 5x5 rings)
    m=f.n3.to_dict()
    def lag(r):
        return [sum(m.get((a+i,b+j),0) for i in range(-r,r+1) for j in range(-r,r+1) if (i,j)!=(0,0)) for a,b in f.index]
    f['lag1']=lag(1); f['lag2']=lag(2)
    if USE_LAND:
        L=LAND.reindex(f.index).fillna({'parcels':0,'vac_lot':0,'lra':0,'vac_bldg':0,'art_dist':1000})
        for c in ['parcels','vac_lot','lra','vac_bldg','art_dist']: f[c]=L[c].values
        for c in ['vac_lot','lra','vac_bldg']:
            m2=L[c].to_dict(); f[c+'_nb']=[sum(m2.get((a+i,b+j),0) for i in(-1,0,1) for j in(-1,0,1)) for a,b in f.index]
    return f
def target(a,b):
    t=d[(d.DATETIMEINIT>=a)&(d.DATETIMEINIT<b)].groupby(['gx','gy']).size()
    return t
X=['n1','n2','n3','n5','w3','alley3','vac3','yrs','recency','lag1','lag2']+(['parcels','vac_lot','lra','vac_bldg','art_dist','vac_lot_nb','lra_nb','vac_bldg_nb'] if USE_LAND else [])
# train: features as of 2024-01-01 -> target 2024; 2023->2023 etc.
tr=[]
for y in [2021,2022,2023,2024]:
    c=pd.Timestamp(f'{y}-01-01'); f=feats(c); f['y']=target(c,pd.Timestamp(f'{y+1}-01-01')).reindex(f.index).fillna(0); tr.append(f)
tr=pd.concat(tr)
mdl=HistGradientBoostingRegressor(loss='poisson',max_iter=300,learning_rate=.05,max_leaf_nodes=15,random_state=0).fit(tr[X],tr.y)
# validation: train cut 2025 targets? -> test on 2025 with features as of 2025-01-01 (model trained 2021-2024)
def evaluate(c,end,label):
    f=feats(c); y=target(c,end).reindex(f.index).fillna(0); tot=y.sum()
    f['pred']=mdl.predict(f[X]); out={}
    for name,score in [('model',f.pred),('last year only',f.n1),('3-year count',f.n3)]:
        r=[]
        for p in [.01,.05,.10]:
            k=int(len(f)*p); top=score.sort_values(ascending=False).index[:k]; r.append(round(y.loc[top].sum()/tot*100,1))
        out[name]=r
    print(label,'total',int(tot),'| % of reports captured in top 1/5/10% of cells'); [print(' ',k,v) for k,v in out.items()]
    return f,y,out
evaluate(pd.Timestamp('2025-01-01'),pd.Timestamp('2026-01-01'),'TEST 2025')
# refit including 2025 then test on 2026 YTD (Jan - Oct 12)
c=pd.Timestamp('2025-01-01'); f=feats(c); f['y']=target(c,pd.Timestamp('2026-01-01')).reindex(f.index).fillna(0)
tr2=pd.concat([tr,f]); mdl.fit(tr2[X],tr2.y)
ft,yt,res=evaluate(pd.Timestamp('2026-01-01'),pd.Timestamp('2026-12-31'),'TEST 2026 YTD')
# final forecast: features as of now
now=d.DATETIMEINIT.max().normalize()+pd.Timedelta(days=1); ff=feats(now); ff['risk']=mdl.predict(ff[X])
ff=ff.join(cells.set_index(['gx','gy']))
ff['pct']=ff.risk.rank(pct=True)*100
ff['tier']=pd.cut(ff.pct,[0,80,95,99,100.1],labels=['Low','Elevated','High','Critical'])
print(ff.tier.value_counts().to_string())
ff.reset_index().to_csv(o+('/risk_cells.csv' if USE_LAND else '/risk_cells_hist.csv'),index=False)
json.dump({'validation_2026':res,'validation_note':'trained on 2021-2025 outcomes; tested on Jan-Oct 2026 reports'},open(o+('/risk_validation.json' if USE_LAND else '/risk_validation_hist.json'),'w'))
imp=pd.Series(np.abs(np.corrcoef(tr2[X].T,tr2.y)[-1,:-1]),index=X).sort_values(ascending=False); print('corr with outcome'); print(imp.round(2).to_string())
