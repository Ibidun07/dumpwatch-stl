"""Step 13: Do City service failures come before dumping?

Event study on the 311 data. For each streetlight-outage or missed-collection report, count
dumping reports on the same ~195 m block in the 60 days BEFORE and the 60 days AFTER it
(the report day itself is left out, since one caller often reports both on the same day).
If the failure invites dumping, dumping should rise after it.

Busy blocks generate more calls of every kind, so each group is compared with a PLACEBO
group from the same callers and departments where no mechanism exists:
  - streetlights out   vs  'Lights ON Daytime'  (same lights, but nothing is dark)
  - missed collection  vs  container blocking / move requests (same carts, nothing left out)

For outages we also test DOSE: dumping per day while the light was out vs. the same number of
days after it was fixed, on the same block.

Usage: python 13_service_gaps.py data/raw outputs
Output: outputs/service_gaps.json
"""
import pandas as pd, numpy as np, glob, json, sys

raw, o = sys.argv[1], sys.argv[2]
S, WIN = 250, 60
GROUPS = {
    'Streetlight out': ['Single Light Out', 'Whole Blk Lights Out', 'Light(s) Out'],
    'Lights on in daytime (placebo)': ['Lights ON Daytime'],
    'Missed collection': ['Refuse not collected', 'Bulky items missed', 'Cntnr overflow/bulky', 'Yrd Wste Not Collect'],
    'Container blocking/move (placebo)': ['Cntnr blocking', 'Move container'],
}
code2g = {c: g for g, cs in GROUPS.items() for c in cs}

parts = []
for f in sorted(glob.glob(raw + '/20*.csv')):
    if int(f[-8:-4]) < 2014:
        continue
    d = pd.read_csv(f, dtype=str, usecols=['REQUESTID', 'PROBLEMCODE', 'DATETIMEINIT', 'DATETIMECLOSED', 'SRX', 'SRY', 'STATUS'],
                    encoding='cp1252', encoding_errors='replace')
    parts.append(d[d.PROBLEMCODE.isin(code2g)])
e = pd.concat(parts).drop_duplicates('REQUESTID')
e['group'] = e.PROBLEMCODE.map(code2g)
e['t'] = pd.to_datetime(e.DATETIMEINIT, errors='coerce')
e['tc'] = pd.to_datetime(e.DATETIMECLOSED, errors='coerce')
x, y = pd.to_numeric(e.SRX, errors='coerce'), pd.to_numeric(e.SRY, errors='coerce')
e = e[x.between(-10060000, -10035000) & y.between(4655000, 4690000) & e.t.notna()].copy()
e['gx'] = (pd.to_numeric(e.SRX) // S).astype(int)
e['gy'] = (pd.to_numeric(e.SRY) // S).astype(int)

dump = pd.read_parquet(o + '/dumping.parquet')
dump['gx'] = (pd.to_numeric(dump.SRX) // S).astype(int)
dump['gy'] = (pd.to_numeric(dump.SRY) // S).astype(int)
end = dump.DATETIMEINIT.max()
dday = {k: np.sort(g.DATETIMEINIT.values.astype('datetime64[D]')) for k, g in dump.groupby(['gx', 'gy'])}

# keep one event per block per group per 60 days, with full windows inside the data
e = e[(e.t >= pd.Timestamp('2014-03-01')) & (e.t <= end - pd.Timedelta(days=WIN + 1))].sort_values('t')
e['prev'] = e.groupby(['group', 'gx', 'gy']).t.shift()
e = e[e.prev.isna() | ((e.t - e.prev).dt.days > WIN)].copy()


def window_counts(row):
    t = dday.get((row.gx, row.gy))
    if t is None:
        return pd.Series({'before': 0, 'after': 0})
    d0 = np.datetime64(row.t.date())
    b = ((t >= d0 - np.timedelta64(WIN, 'D')) & (t < d0)).sum()
    a = ((t > d0) & (t <= d0 + np.timedelta64(WIN, 'D'))).sum()
    return pd.Series({'before': int(b), 'after': int(a)})


e[['before', 'after']] = e.apply(window_counts, axis=1)
res = []
for g in GROUPS:
    s = e[e.group == g]
    B, A = s.before.sum(), s.after.sum()
    # block-bootstrap style CI by resampling events
    rng = np.random.default_rng(0)
    idx = np.arange(len(s))
    ratios = []
    for _ in range(500):
        k = rng.choice(idx, len(idx))
        bb, aa = s.before.values[k].sum(), s.after.values[k].sum()
        ratios.append(aa / bb if bb else np.nan)
    lo, hi = np.nanpercentile(ratios, [2.5, 97.5])
    res.append({'group': g, 'events': int(len(s)), 'dump_before': int(B), 'dump_after': int(A),
                'change_pct': round((A / B - 1) * 100, 1) if B else None,
                'ci_low_pct': round((lo - 1) * 100, 1), 'ci_high_pct': round((hi - 1) * 100, 1),
                'blocks_with_any_dumping_after_pct': round((s.after > 0).mean() * 100, 1)})
    print(f"{g:36s} events {len(s):6d} | dumping before {B:5d} after {A:5d} | change {res[-1]['change_pct']:+.1f}% "
          f"(95% CI {res[-1]['ci_low_pct']:+.1f} to {res[-1]['ci_high_pct']:+.1f})")

# Dose: dumping per day during outage vs same length after repair (streetlights with known repair date)
L = e[(e.group == 'Streetlight out') & e.tc.notna()].copy()
L['dur'] = (L.tc - L.t).dt.days
L = L[(L.dur >= 3) & (L.dur <= 120) & (L.tc + pd.to_timedelta(L.dur, unit='D') <= end)]


def during_after(row):
    t = dday.get((row.gx, row.gy))
    if t is None:
        return pd.Series({'during': 0, 'post': 0})
    a0, a1 = np.datetime64(row.t.date()), np.datetime64(row.tc.date())
    du = ((t > a0) & (t <= a1)).sum()
    po = ((t > a1) & (t <= a1 + np.timedelta64(int(row.dur), 'D'))).sum()
    return pd.Series({'during': int(du), 'post': int(po)})


L[['during', 'post']] = L.apply(during_after, axis=1)
L['len'] = pd.cut(L.dur, [2, 14, 45, 121], labels=['3-14 days', '15-45 days', '46-120 days'])
dose = []
for k, g in L.groupby('len', observed=True):
    dose.append({'outage_length': str(k), 'outages': int(len(g)), 'dump_during': int(g.during.sum()),
                 'dump_after_fix': int(g.post.sum()),
                 'during_vs_after_pct': round((g.during.sum() / max(g.post.sum(), 1) - 1) * 100, 1)})
tot = {'outages': int(len(L)), 'dump_during': int(L.during.sum()), 'dump_after_fix': int(L.post.sum()),
       'during_vs_after_pct': round((L.during.sum() / max(L.post.sum(), 1) - 1) * 100, 1),
       'median_outage_days': float(L.dur.median())}
print('\nWhile the light was out vs the same number of days after repair:', tot)
for r in dose:
    print('  ', r)
json.dump({'window_days': WIN, 'event_study': res, 'outage_dose': {'total': tot, 'by_length': dose}},
          open(o + '/service_gaps.json', 'w'), indent=1)

# ---- Witnessed-dumping check: reports where someone SAW a person dump cannot be the uncollected pile itself.
wit = dump[dump.type == 'Witnessed dumping']
wday = {k: np.sort(g.DATETIMEINIT.values.astype('datetime64[D]')) for k, g in wit.groupby(['gx', 'gy'])}


def wcount(row, a, b):
    t = wday.get((row.gx, row.gy))
    if t is None:
        return 0
    d0 = np.datetime64(row.t.date())
    return int(((t >= d0 + np.timedelta64(a, 'D')) & (t <= d0 + np.timedelta64(b, 'D'))).sum())


wres = []
for c in ['Cntnr overflow/bulky', 'Refuse not collected', 'Bulky items missed', 'Cntnr blocking', 'Move container', 'Single Light Out', 'Whole Blk Lights Out', 'Lights ON Daytime']:
    s = e[e.PROBLEMCODE == c]
    if not len(s):
        continue
    B = int(s.apply(lambda r: wcount(r, -WIN, -1), axis=1).sum())
    A = int(s.apply(lambda r: wcount(r, 1, WIN), axis=1).sum())
    se = np.sqrt(1 / max(B, 1) + 1 / max(A, 1))
    r = A / B if B else np.nan
    wres.append({'code': c, 'events': int(len(s)), 'witnessed_before': B, 'witnessed_after': A,
                 'change_pct': round((r - 1) * 100, 1), 'ci_low_pct': round((r * np.exp(-1.96 * se) - 1) * 100, 1),
                 'ci_high_pct': round((r * np.exp(1.96 * se) - 1) * 100, 1)})
    print(f"witnessed dumping after {c:22s} {B:5d} -> {A:5d}  {wres[-1]['change_pct']:+.1f}% "
          f"(95% CI {wres[-1]['ci_low_pct']:+.1f} to {wres[-1]['ci_high_pct']:+.1f})")

# ---- Per-site service history for the app (last 12 months before the data end), same site order as step 8
R = pd.read_csv(o + '/risk_cells.csv').sort_values('risk', ascending=False).head(40)
recent = pd.concat(parts)
recent['group'] = recent.PROBLEMCODE.map(code2g)
recent['t'] = pd.to_datetime(recent.DATETIMEINIT, errors='coerce')
x, y = pd.to_numeric(recent.SRX, errors='coerce'), pd.to_numeric(recent.SRY, errors='coerce')
recent = recent[x.between(-10060000, -10035000) & y.between(4655000, 4690000) & (recent.t > end - pd.Timedelta(days=365))].copy()
recent['gx'] = (pd.to_numeric(recent.SRX) // S).astype(int)
recent['gy'] = (pd.to_numeric(recent.SRY) // S).astype(int)
recent = recent.drop_duplicates('REQUESTID')
sites = []
for gx, gy in zip(R.gx, R.gy):
    g = recent[(recent.gx == gx) & (recent.gy == gy)]
    sites.append({'missed': int((g.group == 'Missed collection').sum()),
                  'overflow': int((g.PROBLEMCODE == 'Cntnr overflow/bulky').sum()),
                  'lights': int((g.group == 'Streetlight out').sum())})
cityavg = recent.groupby(['gx', 'gy']).group.apply(lambda s: (s == 'Missed collection').sum()).mean()
out = json.load(open(o + '/service_gaps.json'))
out.update({'witnessed_check': wres, 'sites': sites, 'avg_missed_per_block_12mo': round(float(cityavg), 1)})
json.dump(out, open(o + '/service_gaps.json', 'w'), indent=1)
print('sites missed-collection last 12 mo:', [s['missed'] for s in sites])
print('lights:', [s['lights'] for s in sites], 'city avg missed per active block', round(cityavg, 1))
