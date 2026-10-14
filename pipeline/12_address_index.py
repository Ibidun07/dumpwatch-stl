"""Step 12: Address lookup index for the report form.

Turns the Assessor's parcel addresses into a compact index of street "hundred blocks"
(e.g. the 5900 block of Lillian Ave) with the average location of the parcels on each,
so the app can place a typed address without any outside geocoding service.

Usage: python 12_address_index.py outputs
Input:  outputs/parcels_pts.parquet (step 4)
Output: outputs/address_index.json  {"DIR|NAME": [[block, lat, lon], ...], ...}
"""
import pandas as pd, re, json, sys

o = sys.argv[1]
p = pd.read_parquet(o + '/parcels_pts.parquet', columns=['SITEADDR', 'lat', 'lon'])
TYPES = {'ST', 'AVE', 'AV', 'BLVD', 'DR', 'PL', 'RD', 'LN', 'CT', 'WAY', 'SQ', 'PKY', 'PKWY', 'TER', 'PLZ',
         'MALL', 'WALK', 'CIR', 'HWY', 'ROW', 'TRL', 'XING', 'LOOP', 'PATH'}
pat = re.compile(r'^(\d+)\s+(.*)$')
rows = []
for a, la, lo in zip(p.SITEADDR.fillna(''), p.lat, p.lon):
    a = re.sub(r'\s+', ' ', str(a).upper()).strip()
    m = pat.match(a)
    if not m:
        continue
    num, rest = int(m.group(1)), m.group(2).split(' ')
    d = rest[0] if rest and rest[0] in ('N', 'S', 'E', 'W') and len(rest) > 1 else ''
    if d:
        rest = rest[1:]
    if len(rest) > 1 and rest[-1] in TYPES:
        rest = rest[:-1]
    name = ' '.join(rest).strip()
    if name:
        rows.append((f'{d}|{name}', num // 100 * 100, la, lo))
df = pd.DataFrame(rows, columns=['key', 'block', 'lat', 'lon'])
g = df.groupby(['key', 'block']).agg(lat=('lat', 'mean'), lon=('lon', 'mean')).reset_index()
idx = {}
for k, b, la, lo in zip(g.key, g.block, g.lat, g.lon):
    idx.setdefault(k, []).append([int(b), round(la, 5), round(lo, 5)])
json.dump(idx, open(o + '/address_index.json', 'w'), separators=(',', ':'))
print(f'{len(df)} addresses -> {len(g)} hundred-blocks on {len(idx)} streets; '
      f'{len(json.dumps(idx, separators=(",", ":"))) // 1024} KB')
