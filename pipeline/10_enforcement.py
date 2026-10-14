"""Step 10: Enforcement outcomes and gaps.

The City's Environmental Investigations unit records how each WITNESSED dumping report ended
(PUBLICRESOLUTION): summons, arrest, warning, or closed for lack of evidence. This step groups
those outcomes, measures them by year and place, and finds high-risk blocks with no enforcement.

Usage: python 10_enforcement.py outputs
Inputs:  outputs/dumping.parquet, outputs/risk_cells.csv, outputs/app_data.json
Outputs: outputs/enforcement.json (summary + per-site outcomes, merged into app_data.json)
"""
import pandas as pd, json, sys

o = sys.argv[1]
S = 250
d = pd.read_parquet(o + '/dumping.parquet')
d['gx'] = (pd.to_numeric(d.SRX) // S).astype(int)
d['gy'] = (pd.to_numeric(d.SRY) // S).astype(int)
w = d[(d.type == 'Witnessed dumping') & (d.year >= 2022)].copy()
res = w.PUBLICRESOLUTION.fillna('').str.lower().str.strip()


def outcome(r):
    if r.startswith('summons'):
        return 'Summons issued'
    if r.startswith('cleared by arrest'):
        return 'Arrest'
    if 'warning' in r or 'instructional' in r:
        return 'Warning'
    if r in ('not enough evidence to lead to arrest', 'no evidence to lead to an arrest', 'no witness(es)',
             'incorrect information provided', 'witness(es) refuses to assist in prosecution',
             'caller is not the witness'):
        return 'Closed: not enough evidence'
    if r == 'no violation found':
        return 'No violation found'
    if r == 'camera request':
        return 'Camera requested'
    return 'No outcome recorded'


w['outcome'] = res.map(outcome)
w['detail'] = w.PUBLICRESOLUTION.fillna('(blank)').str.strip()
w['enforced'] = w.outcome.isin(['Summons issued', 'Arrest'])
w['nofail'] = w.outcome == 'Closed: not enough evidence'
decided = w[w.outcome.isin(['Summons issued', 'Arrest', 'Warning', 'Closed: not enough evidence', 'No violation found'])]

summary = {
    'witnessed': int(len(w)),
    'outcomes': {k: int(v) for k, v in w.outcome.value_counts().items()},
    'detail': {k: int(v) for k, v in w.detail.value_counts().items()},
    'decided': int(len(decided)),
    'enforced_share_of_decided': round(decided.enforced.mean() * 100, 1),
    'evidence_fail_share_of_decided': round(decided.nofail.mean() * 100, 1),
    'evidence_fail_breakdown': {k: int(v) for k, v in w[w.nofail].detail.value_counts().items()},
    'by_year': [{'year': int(y), 'enforced': int(g.enforced.sum()), 'evidence_fail': int(g.nofail.sum()),
                 'decided': int(g.outcome.isin(['Summons issued', 'Arrest', 'Warning', 'Closed: not enough evidence', 'No violation found']).sum())}
                for y, g in w.groupby('year')],
}

# All dumping (any type) vs enforcement, per cell, since 2022
r = d[d.year >= 2022]
cell = r.groupby(['gx', 'gy']).agg(reports=('REQUESTID', 'size'), lat=('lat', 'mean'), lon=('lon', 'mean'),
                                     nb=('NEIGHBORHOOD', lambda s: s.mode().iloc[0] if len(s.mode()) else None))
cw = w.groupby(['gx', 'gy']).agg(witnessed=('REQUESTID', 'size'), enforced=('enforced', 'sum'), nofail=('nofail', 'sum'))
cell = cell.join(cw).fillna({'witnessed': 0, 'enforced': 0, 'nofail': 0})
risk = pd.read_csv(o + '/risk_cells.csv').set_index(['gx', 'gy'])[['tier', 'risk']]
cell = cell.join(risk)

hi = cell[cell.tier.isin(['Critical', 'High'])]
summary['high_risk_cells'] = int(len(hi))
summary['high_risk_no_enforcement'] = int((hi.enforced == 0).sum())
summary['high_risk_reports'] = int(hi.reports.sum())
summary['high_risk_reports_in_no_enforcement_cells'] = int(hi[hi.enforced == 0].reports.sum())
summary['all_cells_enforcement_share_in_high_risk'] = round(hi.enforced.sum() / max(cell.enforced.sum(), 1) * 100, 1)
summary['all_reports_share_in_high_risk'] = round(hi.reports.sum() / cell.reports.sum() * 100, 1)

# Per-site outcomes for the 40 sites in the app (same cell keys as step 8)
app = json.load(open(o + '/app_data.json'))
R = pd.read_csv(o + '/risk_cells.csv').sort_values('risk', ascending=False).head(len(app['sites']))
site_enf = []
for (gx, gy) in zip(R.gx, R.gy):
    g = w[(w.gx == gx) & (w.gy == gy)]
    site_enf.append({'witnessed': int(len(g)), 'summons': int((g.outcome == 'Summons issued').sum()),
                     'arrest': int((g.outcome == 'Arrest').sum()), 'warning': int((g.outcome == 'Warning').sum()),
                     'nofail': int(g.nofail.sum())})
summary['sites_with_no_enforcement'] = sum(1 for s in site_enf if s['summons'] + s['arrest'] == 0)

# Gap list: high-risk cells, most reports, zero summons/arrests
gap = hi[hi.enforced == 0].sort_values('reports', ascending=False).head(15)
summary['gap_cells'] = [{'lat': round(x.lat, 5), 'lon': round(x.lon, 5), 'reports': int(x.reports),
                         'witnessed': int(x.witnessed), 'nofail': int(x.nofail), 'tier': x.tier, 'nb': x.nb}
                        for x in gap.itertuples()]
summary['gap_witnessed_but_no_case'] = int(((hi.enforced == 0) & (hi.witnessed > 0)).sum())
summary['gap_never_witnessed'] = int(((hi.enforced == 0) & (hi.witnessed == 0)).sum())
gap_all = [[round(x.lat, 5), round(x.lon, 5), int(x.reports), int(x.witnessed), int(x.nofail)]
           for x in hi[hi.enforced == 0].itertuples()]
out = {'summary': summary, 'sites': site_enf, 'gap_all': gap_all}
json.dump(out, open(o + '/enforcement.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k not in ('gap_cells', 'detail')}, indent=1))
