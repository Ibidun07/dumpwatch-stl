import pandas as pd, json, sys
o=sys.argv[1]
NB={1:'Carondelet',2:'Patch',5:'Bevo Mill',15:'Tower Grove South',16:'Dutchtown',19:'Gravois Park',50:'Wells Goodfellow',51:'Academy',56:'The Greater Ville',68:"O'Fallon",69:'Penrose',70:'Mark Twain I-70 Industrial',71:'Mark Twain',72:'Walnut Park East',73:'North Pointe',74:'Baden',76:'Walnut Park West',78:'Hamilton Heights',82:'Forest Park'}
d=pd.read_parquet(o+'/dumping.parquet'); r=d[d.year>=2022]
g=pd.read_csv(o+'/grid.csv')
a=pd.read_csv(o+'/chronic_addresses.csv').head(12)
nbc=pd.to_numeric(r.NEIGHBORHOOD,errors='coerce').dropna().value_counts().head(10)
out={
 'cells':[[round(la,5),round(lo,5),int(n),int(l),round(gi,1)] for la,lo,n,l,gi in zip(g.lat,g.lon,g.n,g.last12,g.gi)],
 'yearly':d.groupby(['year','type']).size().unstack(fill_value=0).reset_index().to_dict('records'),
 'month':r.month.value_counts().sort_index().tolist(),
 'dow':[int((r[r.type=='Witnessed dumping'].dow==x).sum()) for x in ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']],
 'nb':[[NB.get(int(k),str(int(k))),int(v)] for k,v in nbc.items()],
 'addr':[[r_.addr.title(),int(r_.n),int(r_.yrs),NB.get(int(float(r_.nb)) if str(r_.nb).replace('.','').isdigit() else -1,str(r_.nb)),r_.types] for r_ in a.itertuples()],
 'stats':{'total':len(d),'recent':len(r),'hotshare':round(g[g.gi>2.58].n.sum()/g.n.sum()*100),'chronic':int((pd.read_csv(o+'/chronic_addresses.csv').n>=5).sum()),
   'top5':21,'medclose':{k:round(v,1) for k,v in r.groupby('type').days_to_close.median().items()},'staff':round((r.CALLERTYPE=='NSO').mean()*100)}
}
json.dump(out,open(o+'/first_look.json','w'),separators=(',',':'),default=int)
print(len(json.dumps(out,default=int))//1024,'KB', out['stats'])
