#!/usr/bin/env bash
# Rebuild everything from the raw downloads. Takes about 10-15 minutes.
# See README.md for which files go in data/raw and data/geo.
set -euo pipefail
cd "$(dirname "$0")"
RAW=data/raw GEO=data/geo OUT=outputs
mkdir -p "$OUT"

echo "1/9 Clean 311 dumping reports";        python pipeline/01_clean_311.py   $RAW $OUT
echo "2/9 Hotspots and chronic addresses";   python pipeline/02_hotspots.py    $OUT
echo "3/9 Package first-look data";          python pipeline/03_pack_first_look.py $OUT
echo "4/9 Parcels + LRA + vacant buildings"; python pipeline/04_land_parcels.py $GEO $OUT
echo "5/9 Land features per block";          python pipeline/05_cell_features.py $OUT $GEO
echo "6a/9 Risk model, history only";        python pipeline/06_risk_model.py  $OUT hist
echo "6b/9 Risk model, with land";           python pipeline/06_risk_model.py  $OUT
echo "7/9 Watch-list test";                  python pipeline/07_watchlist_test.py $OUT
echo "8/9 Site profiles + map layers";       python pipeline/08_site_profiles.py $OUT $GEO
echo "10 Enforcement outcomes and gaps";       python pipeline/10_enforcement.py $OUT
echo "11 Cleanup speed test";                  python pipeline/11_cleanup_speed.py $OUT
echo "12 Address lookup index";                python pipeline/12_address_index.py $OUT
echo "13 City service gaps vs dumping";       python pipeline/13_service_gaps.py $RAW $OUT
echo "9/9 Build HTML pages";                 python pipeline/09_build_pages.py web $OUT
echo "Done. Open outputs/dumpwatch.html in a browser."
