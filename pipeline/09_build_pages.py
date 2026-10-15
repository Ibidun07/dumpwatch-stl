"""Step 9: Inject the JSON data into the HTML templates to make self-contained pages.

Usage: python 09_build_pages.py web outputs
Merges enforcement.json (step 10), cleanup_speed.json (step 11) address_index.json (step 12) and service_gaps.json (step 13) into the app data when present.
Outputs: outputs/dumpwatch.html (the app), outputs/dumping-atlas.html (first-look page)
"""
import json, os, sys

w, o = sys.argv[1], sys.argv[2]
app = json.load(open(f'{o}/app_data.json'))
for key, fname in [('enf', 'enforcement.json'), ('speed', 'cleanup_speed.json'), ('addr', 'address_index.json'), ('svc', 'service_gaps.json')]:
    if os.path.exists(f'{o}/{fname}'):
        app[key] = json.load(open(f'{o}/{fname}'))
pages = [('dumpwatch_template.html', json.dumps(app, separators=(',', ':')), 'dumpwatch.html'),
         ('first_look_template.html', open(f'{o}/first_look.json').read(), 'dumping-atlas.html')]
for tpl, data, out in pages:
    html = open(f'{w}/{tpl}').read().replace('__DATA__', data)
    open(f'{o}/{out}', 'w').write(html)
    print('built', out, len(html) // 1024, 'KB')
