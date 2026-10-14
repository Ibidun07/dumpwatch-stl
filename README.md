# DumpWatch STL

**Illegal dumping risk map and enforcement queue for the City of St. Louis.**
Built for Problem Set #3 (Illegal Dumping), St. Louis Innovation Week Hackathon, October 2026.

DumpWatch turns the City's open data into a ranked to-do list:

- **Act here next:** the 40 blocks most likely to be dumped on in the coming year. Each one has an evidence file with its report history, repeat addresses, the weekdays dumping gets reported, nearby vacant and city-owned property, and a recommended action (camera, secure lots, board-up, alley lighting and signs).
- **Watch list:** 25 blocks with no dumping reports for three years that are surrounded by the conditions that came before dumping elsewhere. Secure them before the first pile appears.
- **Cases:** a witness-report form (vehicle, color, make, partial plate, marks, what was dumped, photo) that links sightings from different sites into one case file for investigators, with the reasons for each link and suggested next steps. Runs on clearly labeled sample reports; reports you add stay in your browser.
- **Enforcement record:** each site file shows how witnessed reports there ended (summons, arrest, warning, or closed for lack of evidence), and a map layer shows high-risk blocks with no enforcement since 2022.
- **Does it work?:** the model was trained on data through 2025 and tested on January–October 2026 reports it never saw.

Open `outputs/dumpwatch.html` in any browser. It is a single self-contained file with no server.

---

## Results (tested on Jan–Oct 2026, 3,008 reports)

| Blocks flagged | DumpWatch model | "Where it happened last year" | Random |
|---|---|---|---|
| Top 1% | 7% | 6% | 1% |
| **Top 5%** | **22%** | 19% | 5% |
| Top 10% | 36% | 31% | 10% |

**Watch list:** among 592 blocks with no reports in 2023–2025, the top fifth by land score got a first dumping report in 2026 at **29%**, versus 15% for all quiet blocks (AUC 0.71).

**Why catching dumpers is hard:** since 2022, 3,488 witnessed-dumping reports went to the City's Environmental Investigations unit. Of the 2,951 with a recorded outcome, 52% ended in a summons (775) or arrest (749), and **36% (1,067) were closed for lack of evidence**, including 159 where the caller's information was wrong.

**Enforcement gap:** 110 of 199 Critical and High blocks have had no summons or arrest since 2022. In 80 of them someone witnessed dumping but no case resulted; in 30, no one ever reported seeing it.

**Fast cleanup (tested, not supported):** matching blocks by report type and prior activity, a new report followed within 60 days after 49.7% of fast cleanups (0–3 days) and 43.0% of slow ones (over 14 days). Cleaner blocks probably make new dumping easier to see and report, so 311 data cannot answer this; it needs a controlled pilot.

**Note:** a history-only version of the model (step 6a) scores about the same on the top 5% (24%). Adding land data mainly helps with blocks that have no dumping history, which is what the watch list is for.

---

## Data sources

All data is from the [City of St. Louis Open Data portal](https://www.stlouis-mo.gov/data/). The raw files are not in this repository because they are large. Download them and place them as shown.

| File | Put it at | Source |
|---|---|---|
| CSB Service Requests (311), one CSV per year | `data/raw/2013.csv` … `data/raw/2026.csv` | [csb.zip](https://www.stlouis-mo.gov/data/upload/data-files/csb.zip) — unzip |
| Current parcels (shapefile) | `data/geo/parcels/Parcels.shp` (+ .dbf .shx .prj) | [PARCELS.zip](https://static.stlouis-mo.gov/open-data/ASSESSOR/PARCELS.zip) |
| LRA (city-owned) inventory | `data/geo/lra.csv` | [LRA_INVENTORY.csv](https://static.stlouis-mo.gov/open-data/SLDC/REAL-ESTATE/LRA_INVENTORY.csv) |
| Vacant building overview | `data/geo/vb.json` | [GetVacantBuildingOverview](https://www.stlcitypermits.com/API/VacantBuilding/GetVacantBuildingOverview) — save page as JSON |
| City streets (shapefile) | `data/geo/streets/tgr_str_cl.shp` | [streets.zip](https://www.stlouis-mo.gov/data/upload/data-files/streets.zip) |
| Neighborhood boundaries | `data/geo/nbhd/Neighborhoods/Neighborhoods.shp` | [neighborhoods.zip](https://static.stlouis-mo.gov/open-data/planning/neighborhoods/neighborhoods.zip) |

---

## How to run

```bash
pip install -r requirements.txt
./run_all.sh        # about 1-2 minutes
```

Then open `outputs/dumpwatch.html`.

---

## Pipeline

| Step | Script | What it does |
|---|---|---|
| 1 | `01_clean_311.py` | Reads 2013–2026 311 files (Windows-1252 encoding). Keeps four problem codes: `Illegal dumpg report`, `Debris-alley/street`, `Debris-Vacant Lot`, `Debris-Vacant Bldg`. Converts SRX/SRY from Web Mercator to lat/lon, drops points outside the city, and removes repeat reports at the same address and type within 7 days. Result: 101,532 reports. |
| 2 | `02_hotspots.py` | Bins reports since 2022 into ~200 m grid cells (250 Web Mercator units). Runs Getis-Ord Gi* hotspot statistics on each cell's 3×3 neighborhood. Ranks chronic addresses. Summarizes timing by month, weekday and hour. |
| 3 | `03_pack_first_look.py` | Packages step 2 results for the first-look page (`dumping-atlas.html`). |
| 4 | `04_land_parcels.py` | One point per parcel. Flags city-owned (LRA) parcels (matched on `ParcelId`), registered vacant buildings (matched on `HANDLE`, deduplicated) and assessor vacant lots. |
| 5 | `05_cell_features.py` | Counts parcels, vacant lots, LRA parcels and vacant buildings per grid cell, plus distance to the nearest arterial street. |
| 6 | `06_risk_model.py` | Poisson gradient-boosted model predicting next-year report count per cell. Features: report counts over 1/2/3/5 years, report-type mix, years active, days since last report, neighbors' counts (3×3 and 5×5), and land features. Trained on 2021–2024 outcomes, tested on 2025, then refit through 2025 and tested on 2026. Run with `hist` for the history-only baseline. Writes `risk_cells.csv` with tiers: Critical (top 1%), High (95–99th percentile), Elevated (80–95th), Low. |
| 7 | `07_watchlist_test.py` | Tests whether land features predict a first report in blocks that had none for three years (logistic regression, trained 2022–2025, tested 2026). |
| 8 | `08_site_profiles.py` | Builds evidence files for the top 40 cells, the 25-block watch list, and simplified map layers. Writes `app_data.json`. |
| 10 | `10_enforcement.py` | Groups the outcomes of witnessed reports (`PUBLICRESOLUTION`: summons, arrest, warning, not enough evidence), counts them per site and per year, and finds high-risk blocks with no summons or arrest. Writes `enforcement.json`. |
| 11 | `11_cleanup_speed.py` | Tests whether fast closure of debris reports is followed by fewer repeat reports within 60 days, matching blocks by report type and prior-year activity. Writes `cleanup_speed.json`. |
| 9 | `09_build_pages.py` | Merges steps 10–11 into the app data and injects it into the HTML templates in `web/` to produce the two self-contained pages. Runs last. |

`explore_problem_codes.py` is the exploration script used to find which 311 problem codes relate to dumping.

### Recommended-action rules (step 8)

| Condition at the site | Action |
|---|---|
| Witnessed dumping is 25%+ of reports | **Camera**, aimed at the most-reported address |
| 40+ LRA parcels or 60+ vacant lots within ~300 m | **Secure lots** (bollards, fencing) |
| 40+ registered vacant buildings within ~300 m | **Board-up** and code enforcement |
| Alley/street debris is 50%+ of reports | **Alley lighting and fine signage** |
| None of the above | **Rapid cleanup** |

---

## Limits

- **311 reports measure where dumping is reported, not every dump.** About 28% of reports are logged by City staff, so patrolled areas are over-represented.
- **Timestamps record when dumping was reported, not when it happened.** Weekday patterns largely reflect reporting habits.
- **Coding changed over time.** Vacant-lot and vacant-building debris reports drop sharply after 2022, likely a change in how the City logs them.
- **Police dumping reports and citations are not in this data.**
- **The 311 description field is a category name, not free text,** so debris type (tires, construction, mattresses) cannot be extracted.
- **Building permits are published only as dashboards,** so permit-to-dump matching was not possible.
- **The app does not identify individuals.** It narrows down where and when to watch.

## Next steps with City data access

- Add SLMPD dumping citations and camera locations to measure deterrence.
- Get a building permit export to flag contractors working near construction-debris sites.
- Connect the Cases form (prototyped in the app) to the Citizens' Service Bureau so real witness reports are linked across sites.
- Have crews photograph each pile and check it for addressed mail or receipts before hauling; log debris type.
- Require landfill or transfer-station receipts before construction and demolition permits close.
- Run a controlled pilot of 48-hour cleanup at half of the top sites to measure its effect on repeat dumping.
- Re-run weekly, since the 311 data updates weekly.

## Project layout

```
pipeline/   Python steps 01–09
web/        HTML templates (app and first-look page)
outputs/    Built pages and result files
data/       Raw downloads go here (not committed)
run_all.sh  Runs the whole pipeline
```
