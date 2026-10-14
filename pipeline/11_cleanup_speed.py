"""Step 11: Does fast cleanup reduce repeat dumping?

For every debris report (alley/street, vacant lot, vacant building) closed between 2022 and
Aug 13, 2026, check whether the same ~195 m block got a NEW dumping report within 60 days
after the closure. Compare fast (<= 3 days), medium (4-14) and slow (> 14) closures.

Busy blocks get more repeats no matter what, so the comparison is made within groups of blocks
with similar activity in the previous 365 days, and within the same report type; the overall
gap is the average of the within-group gaps, weighted by group size.

Usage: python 11_cleanup_speed.py outputs
Output: outputs/cleanup_speed.json
"""
import pandas as pd, numpy as np, json, sys

o = sys.argv[1]
S, WIN = 250, 60
d = pd.read_parquet(o + '/dumping.parquet')
d['gx'] = (pd.to_numeric(d.SRX) // S).astype(int)
d['gy'] = (pd.to_numeric(d.SRY) // S).astype(int)
d = d.sort_values('DATETIMEINIT').reset_index(drop=True)
end = d.DATETIMEINIT.max()

times = {k: g.DATETIMEINIT.values for k, g in d.groupby(['gx', 'gy'])}

c = d[d.type.isin(['Alley/street debris', 'Vacant lot debris', 'Vacant building debris'])
      & (d.year >= 2022) & d.DATETIMECLOSED.notna()
      & (d.STATUS.str.upper() == 'CLOSED') & (d.days_to_close >= 0)].copy()
c = c[c.DATETIMECLOSED <= end - pd.Timedelta(days=WIN)]


def stats(row):
    t = times[(row.gx, row.gy)]
    close, init = np.datetime64(row.DATETIMECLOSED), np.datetime64(row.DATETIMEINIT)
    after = ((t > close) & (t <= close + np.timedelta64(WIN, 'D'))).sum()
    prior = ((t < init) & (t >= init - np.timedelta64(365, 'D'))).sum()
    return pd.Series({'repeat': int(after > 0), 'prior': int(prior)})


c[['repeat', 'prior']] = c.apply(stats, axis=1)
c['speed'] = pd.cut(c.days_to_close, [-0.01, 3, 14, 1e9], labels=['Fast (0-3 days)', 'Medium (4-14 days)', 'Slow (over 14 days)'])
c['activity'] = pd.cut(c.prior, [-1, 0, 2, 9, 1e9], labels=['0', '1-2', '3-9', '10+'])

raw = c.groupby('speed', observed=True).repeat.agg(['size', 'mean'])
print('Raw repeat rate within 60 days of closure:')
print(raw.assign(mean=lambda x: (x['mean'] * 100).round(1)).to_string())

# Stratified comparison: fast vs slow inside each (type, activity) group
rows = []
for (t, a), g in c.groupby(['type', 'activity'], observed=True):
    f, s = g[g.speed == 'Fast (0-3 days)'], g[g.speed == 'Slow (over 14 days)']
    if len(f) >= 30 and len(s) >= 30:
        rows.append({'type': t, 'activity': str(a), 'n_fast': len(f), 'n_slow': len(s),
                     'fast': round(f.repeat.mean() * 100, 1), 'slow': round(s.repeat.mean() * 100, 1)})
st = pd.DataFrame(rows)
st['gap'] = st.slow - st.fast
w = st.n_fast + st.n_slow
adj = {'fast': round((st.fast * w).sum() / w.sum(), 1), 'slow': round((st.slow * w).sum() / w.sum(), 1)}
print('\nWithin matched groups (type x prior-year activity):')
print(st.to_string(index=False))
print('\nWeighted: fast', adj['fast'], '% vs slow', adj['slow'], '%; groups where slow is worse:', int((st.gap > 0).sum()), 'of', len(st))

by_type = c.groupby('type').days_to_close.median().round(1).to_dict()
out = {'window_days': WIN, 'n': int(len(c)),
       'raw': [{'speed': str(k), 'n': int(v['size']), 'repeat_pct': round(v['mean'] * 100, 1)} for k, v in raw.iterrows()],
       'adjusted': adj, 'groups': st.to_dict('records'), 'groups_slow_worse': int((st.gap > 0).sum()),
       'groups_total': int(len(st)), 'median_days_to_close_by_type': by_type}
json.dump(out, open(o + '/cleanup_speed.json', 'w'), indent=1)
