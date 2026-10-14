import pandas as pd, glob, sys
rows=[]
for f in sorted(glob.glob(sys.argv[1]+'/20*.csv')):
    d=pd.read_csv(f,usecols=['PROBLEMCODE','PLAIN_ENGLISH_NAME_FOR_PROBLEMCODE','GROUP','SRX','SRY'],dtype=str,low_memory=False,encoding='cp1252',encoding_errors='replace')
    d['yr']=f[-8:-4]; rows.append(d)
d=pd.concat(rows)
m=d.PROBLEMCODE.str.contains('dump|debris|trash|tire|litter|bulk|mattress',case=False,na=False)|d.PLAIN_ENGLISH_NAME_FOR_PROBLEMCODE.str.contains('dump',case=False,na=False)
t=d[m].groupby(['PROBLEMCODE','PLAIN_ENGLISH_NAME_FOR_PROBLEMCODE']).size().sort_values(ascending=False)
print(t.head(40).to_string())
print(d[m & d.PROBLEMCODE.str.contains('dump',case=False,na=False)].groupby('yr').size().to_string())
# coordinate ranges by year
d['x']=pd.to_numeric(d.SRX,errors='coerce')
print(d.groupby('yr').x.describe()[['min','50%','max']].to_string())
