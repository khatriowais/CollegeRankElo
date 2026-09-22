# Data provenance — Mumbai cohort

This file documents exactly what in `mumbai_university_colleges.json` is **verified real
data** versus what is deliberately **left blank (`null`)**. It exists so the dataset is
defensible in a viva: nothing here is invented.

## What is real and cited

For each of the 22 colleges the following fields were cross-checked against the college's
official website and/or its Wikipedia article (see each row's `source_url`):

| Field | Meaning | Confidence |
|---|---|---|
| `college_name` | Official institution name | Verified |
| `city` | `"Mumbai"` for all (all lie within Greater Mumbai) | Verified |
| `locality` | Area of Mumbai (Fort, Matunga, Vile Parle, …) | Verified |
| `type` | Funding/management model — `Aided`, `Unaided`, or `Government` | Verified |
| `university` | Affiliating university — `University of Mumbai`, or `HSNC University` / `Dr. Homi Bhabha State University` for colleges that moved to the new cluster universities (2019–2020) | Verified |
| `naac_grade` | Most recent publicly reported NAAC accreditation grade | Best-known — **verify the current cycle** on the NAAC portal (naac.gov.in) before relying on it |
| `website` | Official site | Verified |
| `source_url` | Citation (Wikipedia article or official site) | — |

NAAC grades change each accreditation cycle. They are shown here as the most recently
reported grade to the best of available knowledge and carry only **5%** weight in the
comparison score. Confirm the live grade/CGPA on https://www.naac.gov.in before the viva.

## What is intentionally blank (`null`) — and why

`annual_fee`, `average_package`, `highest_package`, `placement_percentage`,
`nirf_rank`, and `student_rating` are **`null`** for every Mumbai college.

Reason: credible, per-college placement/fee/earnings figures for Mumbai undergraduate
arts/science/commerce colleges are **not published as free, structured, citable data**.
Rather than invent plausible-looking numbers (which is exactly the problem the old demo
data had — e.g. "St. Xavier's College" listed in *Bhiwandi* with an `example.edu` website),
these fields are left empty until real figures are loaded.

Consequences, all intended:
- The app runs and renders these fields as `—` (not fabricated numbers).
- A head-to-head **comparison** is decided by the one strong signal that *is* real here —
  the NAAC grade — until economic figures are supplied. This is stated plainly in the UI.
- The **Elo leaderboard** starts every college at 1500 and diverges only through real
  comparisons, exactly as the methodology page describes.

## How to load real figures (recommended before the viva)

Pick the handful of colleges you will actually demo and enter their real, sourced numbers:

1. **Admin panel** → log in → edit a college (fees, packages, placement %). Cite the source
   in your report (college prospectus, the college's NIRF Data / self-study report, or the
   official placement brochure).
2. **CSV import** (`/admin`, "Import CSV") — bulk-load a spreadsheet with the same columns.

Government-published, citable sources worth using:
- **NIRF Data Reports** (nirfindia.org) — colleges that participate publish fees, placement
  and higher-studies numbers in a standard format.
- The college's own **self-study report / annual placement report** (usually a PDF on the site).

## India directory cohort (shipped)

Alongside the 22 ranked Mumbai colleges, the app now includes an **all-India directory** of
476 institutions sourced from the open **Hipolabs university-domains list**
(https://github.com/Hipo/university-domains-list). A committed offline snapshot lives at
`data/snapshots/hipolabs_india.json` so ingestion — and the viva — works with no network.

What this dataset does and does not contain, and how the app treats it:

| Field | From Hipolabs | Notes |
|---|---|---|
| `college_name` | Yes | Official institution name |
| `country` | Yes | Always `India` for this cohort |
| `region` | Yes (`state-province`) | State/UT, where present |
| `website` | Yes (`web_pages[0]`) | Official domain |
| fees / packages / placement / NAAC / Elo | **No** | The dataset carries **no metrics**, so these stay `null` |

Because Hipolabs publishes no economic metrics, every India-directory row is stored with
`is_ranked = False` and `cohort = "india"`. The `is_ranked` flag gates the leaderboard,
`/api/compare`, and Elo entirely: directory colleges are **discovery-only** — searchable and
linkable, shown clearly as "not Elo-ranked", and never given a fabricated rating or metric.
Attempting to compare a directory college (or to compare across cohorts) returns HTTP 400.

Merge priority is `mumbai_curated > us_scorecard > hipolabs`, so a directory row can never
overwrite a curated Mumbai college's real, cited data on re-ingest (ingestion is idempotent).

## US College Scorecard Cohort (Shipped & Live)

Alongside the curated Mumbai colleges and India directory, the app includes **US Universities** sourced from the official **US Department of Education College Scorecard API** (https://collegescorecard.ed.gov/). A committed offline snapshot lives at `data/snapshots/us_scorecard.json` and can be refreshed online using `python ingest.py --online`.

| Field | Source | Meaning |
|---|---|---|
| `annual_fee` | `latest.cost.tuition.out_of_state` | Annual tuition and fees ($ USD) |
| `average_package` | `latest.earnings.10_yrs_after_entry.median` | Median earnings 10 years post-entry ($ USD) |
| `placement_percentage` | `latest.completion.rate_suppressed.overall` | Degree completion / graduation rate |
| `courses` | `latest.programs.cip_4_digit` | Program offerings, degree levels & duration |

## Courses & Fee Structure

Colleges carry a structured `courses` attribute containing their programs of study:
- **`course_name`**: e.g., B.Sc. Computer Science, B.Tech Information Technology, MBA, MS Computer Science
- **`degree_level`**: Undergraduate / Postgraduate
- **`duration`**: Program length (e.g. 3 Years, 4 Years, 2 Years)
- **`annual_fee`**: Course-specific tuition fee
- **`specialization`**: Concentration / track (e.g. Artificial Intelligence, Data Science, Finance)

Ranked cohorts (`mumbai`, `us`) are ranked independently with currency-aware comparisons (`INR` and `USD`). Merge priority is `mumbai_curated > us_scorecard > hipolabs`.
