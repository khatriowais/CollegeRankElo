# CollegeRankELO

A dynamic ranking system for Mumbai University colleges powered by the **Elo rating algorithm**.
Instead of static NIRF-style tables, colleges gain or lose rating points as they are compared head-to-head on real academic and placement metrics.

Final-year project · Flask · SQLAlchemy · SQLite (Postgres-ready) · vanilla JS · Chart.js.

---

## 1. Installation

```bash
# 1. Create a virtualenv (recommended)
python -m venv .venv && source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 2. Install requirements
pip install -r requirements.txt

# 3. Configure environment (no more hard-coded secrets!)
Copy-Item .env.example .env        # Windows PowerShell
# cp .env.example .env             # macOS / Linux
# Then edit .env: set SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, etc.

# 4. Seed the database (first time only — auto-seed also runs from app.py)
python seed_database.py

# 5. Run
python app.py
```

Open <http://localhost:5000>.

All configuration lives in `.env` (see `.env.example` for every key):

| Key | Purpose | Default |
|-----|---------|---------|
| `SECRET_KEY` | Flask session secret | dev-only placeholder |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Admin panel login | `admin` / `changeme` |
| `DATABASE_URL` | SQLAlchemy URL (SQLite or Postgres) | `sqlite:///database/colleges.db` |
| `PORT`, `FLASK_ENV` | Run port / mode | `5000` / `development` |
| `ELO_K_FACTOR`, `ELO_START_RATING`, `DRAW_THRESHOLD` | Rating tunables | `32`, `1500`, `2.0` |
| `WEIGHT_ROI`, `WEIGHT_PLACEMENT`, `WEIGHT_PACKAGE`, `WEIGHT_FEES`, `WEIGHT_NAAC` | Comparison weights (sum = 1) | `0.40/0.25/0.20/0.10/0.05` |
| `DATA_FILE` | Seed JSON path | `data/mumbai_university_colleges.json` |

For Postgres set `DATABASE_URL`, e.g.
`DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/collegerankelo`.

Admin login comes from your `.env` (`ADMIN_USERNAME` / `ADMIN_PASSWORD`).

---

## 2. Project report summary

**Problem.** Static rankings (NIRF, India Today) refresh once a year and only publish the top few dozen. Students comparing two mid-tier colleges get no useful signal.

**Solution.** Model each comparison as a chess-style match. A weighted score computed from real metrics (ROI, placement %, package, fees, NAAC) decides the winner; Elo then updates both ratings. Over many comparisons the leaderboard converges to a data-driven ranking that also reacts to new data instantly.

**Outcome.** A production-quality Flask app with 70+ real Mumbai colleges seeded, live leaderboard, side-by-side comparison, per-college analytics, admin CRUD, CSV import/export, and REST API.

---

## 3. Database schema

| Table          | Key columns |
|----------------|-------------|
| `colleges`     | id, college_name, city, type, university, naac_grade, nirf_rank, annual_fee, average_package, highest_package, placement_percentage, student_rating, website, logo, **elo_rating**, last_updated |
| `comparisons`  | id, college_a_id, college_b_id, winner, score_a, score_b, breakdown_a, breakdown_b, old_elo_a, old_elo_b, new_elo_a, new_elo_b, created_at |
| `elo_history`  | id, college_id, rating, created_at |

### 3.1 ER diagram (Mermaid)

```mermaid
erDiagram
    COLLEGES ||--o{ ELO_HISTORY : has
    COLLEGES ||--o{ COMPARISONS : "appears as A"
    COLLEGES ||--o{ COMPARISONS : "appears as B"
    COLLEGES {
      int id PK
      string college_name
      string city
      string type
      string naac_grade
      int annual_fee
      int average_package
      float placement_percentage
      float elo_rating
    }
    COMPARISONS {
      int id PK
      int college_a_id FK
      int college_b_id FK
      string winner
      float score_a
      float score_b
      float old_elo_a
      float new_elo_a
    }
    ELO_HISTORY {
      int id PK
      int college_id FK
      float rating
      datetime created_at
    }
```

### 3.2 Comparison flowchart (Mermaid)

```mermaid
flowchart TD
    A[User picks College A and College B] --> B[Fetch metrics from DB]
    B --> C[Normalise fees / package / placement / ROI]
    C --> D[Compute weighted score for A and B]
    D --> E{|score_A - score_B| < 2 ?}
    E -- yes --> F[Result = DRAW · S=0.5]
    E -- no  --> G{score_A > score_B ?}
    G -- yes --> H[Winner = A · S_A=1]
    G -- no  --> I[Winner = B · S_A=0]
    F --> J[Elo update: R_new = R_old + K*(S - Expected)]
    H --> J
    I --> J
    J --> K[Persist Comparison + EloHistory rows]
    K --> L[Return JSON to frontend and update UI]
```

---

## 4. Algorithm explanation

**Elo core.** Two formulas, both in `elo.py`:

```
Expected(A) = 1 / (1 + 10 ** ((R_B - R_A) / 400))
R_A_new    = R_A + K * (S_A - Expected(A))
```

- `K = 32` — standard chess K-factor; higher K = faster reactions but noisier.
- Starting rating = `1500`.
- Score `S_A`: 1 = win, 0.5 = draw, 0 = loss. Elo is zero-sum, so B mirrors A.

**Winner decision (`compare.py`).** Elo would be self-reinforcing if we let the higher rating simply win, so we decide winners from *external* attributes:

| Attribute        | Weight |
|------------------|--------|
| ROI              | 40%    |
| Placement %      | 25%    |
| Avg Package      | 20%    |
| Fees (inverted)  | 10%    |
| NAAC grade       | 5%     |

Metrics are normalised against the max of the two compared colleges. If |Δ| < 2 points, the match is a draw. Only then does Elo update.

---

## 5. Viva questions and answers

**Q1. Why Elo rather than just averaging metrics?**
Elo captures *pairwise* information. A college can rise even if it never enters the top 10 by consistently beating peers just above it. Averages are static; Elo is a Markov process that converges to a true ordering.

**Q2. Why K=32?**
It's the FIDE standard for developing players — a fair balance between reactivity to new data and stability. K can be lowered for established ratings.

**Q3. What is the expected-score formula?**
`E = 1 / (1 + 10^((R_opp - R)/400))`. The 400 is Elo's scaling constant: a 400-point gap ≈ 91% expected win rate.

**Q4. Why don't you decide winners from Elo?**
Circular reinforcement — the top-rated college would always win, so it would stay top. We pick winners from real attributes and use Elo purely as an integrator.

**Q5. What if two colleges are near-identical?**
The weighted-score difference falls below the draw threshold (2 points) and we award both S=0.5. Their Elos move only slightly toward each other's expected score.

**Q6. Can this scale to Postgres?**
Yes — SQLAlchemy is the ORM; only `DATABASE_URL` changes. No SQLite-specific SQL is used.

**Q7. How is the admin panel secured?**
Session-based login with credentials from `.env` (`ADMIN_USERNAME` / `ADMIN_PASSWORD`) plus a `login_required` decorator on every admin route. No secrets are hard-coded; `.env` is git-ignored and `.env.example` documents every key.

**Q8. What happens on “Recalculate all ratings”?**
Every college is reset to 1500, `elo_history` is cleared, then all stored comparisons are replayed in chronological order. This lets you tune K or the weights and re-derive ratings deterministically.

**Q9. How do you handle CSV import?**
`csv.DictReader` streams the upload, skips rows whose `college_name` already exists, and initialises new rows at Elo 1500.

**Q10. How is the frontend built?**
Pure HTML + CSS + vanilla JS — no framework — with Chart.js for graphs. Jinja2 renders server-side; JS only handles interactivity (search, filters, compare fetch, theme toggle).

---

## 6. REST API

| Method | Path                              | Purpose |
|--------|-----------------------------------|---------|
| GET    | `/api/colleges`                   | list all colleges |
| GET    | `/api/college/<id>`               | single college |
| GET    | `/api/leaderboard`                | ranked list |
| POST   | `/api/compare`                    | run a comparison; body `{a,b}` |
| POST   | `/api/addCollege` *(admin)*       | create |
| PUT    | `/api/updateCollege/<id>` *(admin)* | update |
| DELETE | `/api/deleteCollege/<id>` *(admin)* | delete |

Admin routes require an active browser session (login with your `.env` credentials).

---

## 7. Folder structure

```
CollegeRankELO/
├── app.py
├── config.py              # env-based settings (SECRET_KEY, admin, Elo tunables…)
├── .env.example           # documented template — copy to .env
├── elo.py
├── compare.py
├── database.py
├── models.py
├── seed_database.py
├── requirements.txt
├── README.md
├── templates/{index,leaderboard,compare,college,admin,about,_base,_macros}.html
├── static/css/style.css   # clean light/dark theme
├── static/js/{main,charts,compare}.js
├── database/colleges.db     (auto-created)
└── data/mumbai_university_colleges.json
```
