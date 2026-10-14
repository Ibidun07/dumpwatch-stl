"""Step 9: Inject the JSON data into the HTML templates to make self-contained pages.

Usage: python 09_build_pages.py web outputs
Outputs: outputs/dumpwatch.html (the app), outputs/dumping-atlas.html (first-look page)
"""
import sys

w, o = sys.argv[1], sys.argv[2]
for tpl, data, out in [('dumpwatch_template.html', 'app_data.json', 'dumpwatch.html'),
                       ('first_look_template.html', 'first_look.json', 'dumping-atlas.html')]:
    html = open(f'{w}/{tpl}').read().replace('__DATA__', open(f'{o}/{data}').read())
    open(f'{o}/{out}', 'w').write(html)
    print('built', out, len(html) // 1024, 'KB')
