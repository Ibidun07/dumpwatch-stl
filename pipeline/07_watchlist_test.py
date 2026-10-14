import pandas as pd, numpy as np, sys
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
o=sys.argv[1]; S=250
d=pd.read_parquet(o+'/dumping.parquet'); d['gx']=(pd.to_numeric(d.SRX)//S).astype(int); d['gy']=(pd.to_numeric(d.SRY)//S).astype(int)
L=pd.read_parquet(o+'/cell_land.parquet').set_index(['gx','gy']); L['vac_bldg']=L.vac_bldg.clip(upper=50); L=L[L.parcels>=5]
for c in ['vac_lot','lra','vac_bldg']:
    m=L[c].to_dict(); L[c+'_nb']=[sum(m.get((a+i,b+j),0) for i in(-1,0,1) for j in(-1,0,1)) for a,b in L.index]
def setup(cut,end):
    prior=d[(d.DATETIMEINIT<cut)&(d.DATETIMEINIT>=cut-pd.Timedelta(days=1095))].groupby(['gx','gy']).size()
    nxt=d[(d.DATETIMEINIT>=cut)&(d.DATETIMEINIT<end)].groupby(['gx','gy']).size()
    z=L[~L.index.isin(prior.index)].copy(); z['y']=z.index.isin(nxt.index).astype(int); return z
F=['vac_lot','lra','vac_bldg','vac_lot_nb','lra_nb','vac_bldg_nb','art_dist','parcels']
tr=pd.concat([setup(pd.Timestamp(f'{y}-01-01'),pd.Timestamp(f'{y+1}-01-01')) for y in [2022,2023,2024,2025]])
te=setup(pd.Timestamp('2026-01-01'),pd.Timestamp('2027-01-01'))
m=LogisticRegression(max_iter=2000).fit(np.log1p(tr[F]),tr.y); p=m.predict_proba(np.log1p(te[F]))[:,1]
print('quiet cells (no reports 2023-25):',len(te),'| got first report in 2026:',te.y.sum(),f'({te.y.mean()*100:.1f}%)')
print('AUC',round(roc_auc_score(te.y,p),3))
te['p']=p; q=te.sort_values('p',ascending=False)
for k in [.1,.2]:
    top=q.head(int(len(q)*k)); print(f'top {int(k*100)}% by land score: {top.y.sum()} of {te.y.sum()} new sites ({top.y.sum()/te.y.sum()*100:.0f}%), hit rate {top.y.mean()*100:.1f}% vs base {te.y.mean()*100:.1f}%')
print(dict(zip(F,m.coef_[0].round(2))))
