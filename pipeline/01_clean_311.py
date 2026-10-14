import pandas as pd, numpy as np, glob, sys
src,dst=sys.argv[1],sys.argv[2]
CODES={'Illegal dumpg report':'Witnessed dumping','Debris-alley/street':'Alley/street debris',
       'Debris-Vacant Lot':'Vacant lot debris','Debris-Vacant Bldg':'Vacant building debris'}
keep=['REQUESTID','PROBLEMCODE','DATETIMEINIT','DATETIMECLOSED','DATECANCELLED','STATUS','DESCRIPTION','PUBLICRESOLUTION',
      'PROBADDRESS','PROBZIP','NEIGHBORHOOD','WARD','SRX','SRY','CALLERTYPE','SUBMITTO']
parts=[]
for f in sorted(glob.glob(src+'/20*.csv')):
    if int(f[-8:-4])<2013: continue
    d=pd.read_csv(f,dtype=str,low_memory=False,encoding='cp1252',encoding_errors='replace',usecols=lambda c:c in keep)
    parts.append(d[d.PROBLEMCODE.isin(CODES)])
d=pd.concat(parts,ignore_index=True)
n0=len(d)
d['type']=d.PROBLEMCODE.map(CODES)
for c in ['DATETIMEINIT','DATETIMECLOSED','DATECANCELLED']: d[c]=pd.to_datetime(d[c],errors='coerce')
x=pd.to_numeric(d.SRX,errors='coerce'); y=pd.to_numeric(d.SRY,errors='coerce')
R=6378137.0
d['lon']=np.degrees(x/R); d['lat']=np.degrees(2*np.arctan(np.exp(y/R))-np.pi/2)
ok=d.lat.between(38.53,38.78)&d.lon.between(-90.33,-90.16)
d=d[ok].copy(); n1=len(d)
d=d.drop_duplicates('REQUESTID')
# duplicate reports: same address+type within 7 days -> keep first
d=d.sort_values('DATETIMEINIT')
d['addr']=d.PROBADDRESS.str.upper().str.strip()
d['prev']=d.groupby(['addr','type']).DATETIMEINIT.shift()
d['dup']=(d.DATETIMEINIT-d.prev).dt.days.lt(7)
n2=len(d); d=d[~d.dup].drop(columns=['prev','dup'])
d['year']=d.DATETIMEINIT.dt.year; d['month']=d.DATETIMEINIT.dt.month
d['dow']=d.DATETIMEINIT.dt.day_name(); d['hour']=d.DATETIMEINIT.dt.hour
d['days_to_close']=(d.DATETIMECLOSED-d.DATETIMEINIT).dt.total_seconds()/86400
d.to_parquet(dst+'/dumping.parquet',index=False)
print(f'raw {n0}, valid coords {n1}, after dedupe {len(d)} (removed {n2-len(d)} repeat reports)')
print(d.groupby(['year','type']).size().unstack(fill_value=0).to_string())
print(d.STATUS.value_counts().head(6).to_string())
print('median days to close by type'); print(d.groupby('type').days_to_close.median().round(1).to_string())
print(d.DESCRIPTION.dropna().sample(15,random_state=1).str[:120].to_string())
