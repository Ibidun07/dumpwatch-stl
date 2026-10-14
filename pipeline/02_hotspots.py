import pandas as pd, numpy as np, sys, json
d=pd.read_parquet(sys.argv[1]+'/dumping.parquet')
r=d[d.year>=2022].copy()   # recent window: 2022 - Oct 2026
print('recent reports',len(r))
# 200m grid in meters (web mercator ~ scale factor 1.28 at this lat; use ~250 mercator units ≈ 195 m)
x=pd.to_numeric(r.SRX); y=pd.to_numeric(r.SRY); S=250
r['gx']=(x//S).astype(int); r['gy']=(y//S).astype(int)
g=r.groupby(['gx','gy']).agg(n=('REQUESTID','size'),lat=('lat','mean'),lon=('lon','mean'),
   yrs=('year','nunique'),witnessed=('type',lambda s:(s=='Witnessed dumping').sum())).reset_index()
yearly=r.groupby(['gx','gy','year']).size().unstack(fill_value=0)
g=g.merge(yearly,left_on=['gx','gy'],right_index=True)
# Getis-Ord Gi* on 3x3 neighborhood
cnt={(a,b):n for a,b,n in zip(g.gx,g.gy,g.n)}
# include empty cells inside bbox for mean/sd
allx=range(g.gx.min(),g.gx.max()+1); ally=range(g.gy.min(),g.gy.max()+1)
vals=np.array([cnt.get((a,b),0) for a in allx for b in ally]); N=len(vals); xb=vals.mean(); s=np.sqrt((vals**2).mean()-xb**2)
def gi(a,b):
    w=[cnt.get((a+i,b+j),0) for i in(-1,0,1) for j in(-1,0,1)]; W=9
    return (sum(w)-xb*W)/(s*np.sqrt((N*W-W*W)/(N-1)))
g['gi']=[gi(a,b) for a,b in zip(g.gx,g.gy)]
g['hot']=g.gi>2.58   # 99% confidence
# emerging: share of last 12 months vs prior
last=r[r.DATETIMEINIT>=r.DATETIMEINIT.max()-pd.Timedelta(days=365)]
lc=last.groupby(['gx','gy']).size().rename('last12')
g=g.merge(lc,left_on=['gx','gy'],right_index=True,how='left').fillna({'last12':0})
print('cells with reports',len(g),'hot cells',g.hot.sum(),'share of reports in hot cells',round(g[g.hot].n.sum()/g.n.sum()*100,1))
top=g.sort_values('n',ascending=False)
print('top 5% cells hold',round(top.head(int(len(g)*.05)).n.sum()/g.n.sum()*100,1),'% of reports')
# chronic addresses
a=r.groupby('addr').agg(n=('REQUESTID','size'),yrs=('year','nunique'),nb=('NEIGHBORHOOD','first'),ward=('WARD','first'),
   types=('type',lambda s:', '.join(sorted(set(s))))).sort_values('n',ascending=False)
print(a.head(20).to_string())
print('addresses with 5+ reports:',(a.n>=5).sum(),'holding',round(a[a.n>=5].n.sum()/a.n.sum()*100,1),'% of reports')
# timing of witnessed dumping (closest to actual dump time)
w=r[r.type=='Witnessed dumping']
print('witnessed by dow'); print(w.dow.value_counts().to_string())
print('witnessed by hour'); print(w.hour.value_counts().sort_index().to_string())
print('all by month'); print(r.month.value_counts().sort_index().to_string())
print('by neighborhood top 15'); print(r.NEIGHBORHOOD.value_counts().head(15).to_string())
print('median days to close by ward (top/bottom)'); m=r.groupby('WARD').days_to_close.median().sort_values(); print(m.head(5).to_string()); print(m.tail(5).to_string())
g.to_csv(sys.argv[1]+'/grid.csv',index=False); a.head(200).to_csv(sys.argv[1]+'/chronic_addresses.csv')
