"""
app.py
------
Flask entry point for CollegeRankELO.

Run:
    pip install -r requirements.txt
    python seed_database.py    # first time only
    python app.py
Then open http://localhost:5000
"""

import csv
import io
import json
from functools import wraps

from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, session, Response, flash, abort)

from database import SessionLocal, init_db
from models import College, Comparison, EloHistory
from elo import EloService, EloConfig
from compare import CompareService, NAAC_MAP, WEIGHTS, DRAW_THRESHOLD
from match import run_match, eligibility_error
from config import settings

app = Flask(__name__)
app.secret_key = settings.secret_key

if settings.is_production and settings.secret_key.startswith("dev-"):
    import warnings
    warnings.warn(
        "SECRET_KEY is still the dev default while FLASK_ENV=production. "
        "Set a strong SECRET_KEY in .env."
    )

elo_service = EloService(k=settings.elo_k_factor)
compare_service = CompareService()

ADMIN_USER = settings.admin_username
ADMIN_PASS = settings.admin_password


# ---------- helpers ----------------------------------------------------------

def db():
    return SessionLocal()


@app.teardown_appcontext
def _remove_session(exception=None):
    # Return the scoped session's connection to the pool after every request.
    # Without this, each request leaks a connection and the pool is exhausted
    # after ~15 requests (QueuePool TimeoutError).
    SessionLocal.remove()


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return fn(*a, **kw)
    return wrapper


def college_or_404(s, cid: int) -> College:
    c = s.get(College, cid)
    if not c:
        abort(404)
    return c


# ---------- page routes ------------------------------------------------------

@app.route("/")
def index():
    s = db()
    # Only ranked colleges (Mumbai cohort) carry an Elo / metrics.
    ranked = s.query(College).filter(College.is_ranked == True).all()  # noqa: E712
    directory_count = (s.query(College)
                       .filter(College.is_ranked == False).count())  # noqa: E712
    top10 = sorted(ranked, key=lambda c: c.elo_rating or 0, reverse=True)[:10]
    pkgs = [c.average_package for c in ranked if c.average_package is not None]
    fees = [c.annual_fee for c in ranked if c.annual_fee is not None]
    states = (s.query(College.region)
              .filter(College.is_ranked == False,  # noqa: E712
                      College.region.isnot(None))
              .distinct().count())
    stats = {
        "ranked": len(ranked),
        "directory": directory_count,
        "count": len(ranked) + directory_count,
        "top_elo": round(max((c.elo_rating for c in ranked), default=0), 2),
        "states": states,
        "avg_package": int(sum(pkgs) / len(pkgs)) if pkgs else None,
        "avg_fee": int(sum(fees) / len(fees)) if fees else None,
    }
    recent = (s.query(Comparison).order_by(Comparison.created_at.desc())
              .limit(5).all())
    return render_template("index.html", stats=stats,
                           top10=[c.to_dict() for c in top10],
                           recent=[_comparison_dict(s, r) for r in recent])


@app.route("/leaderboard")
def leaderboard():
    s = db()
    colleges = [c.to_dict() for c in
                s.query(College).filter(College.is_ranked == True).all()]  # noqa: E712
    colleges.sort(key=lambda c: c["elo_rating"] or 0, reverse=True)
    return render_template("leaderboard.html", colleges=colleges)


@app.route("/directory")
def directory():
    """Searchable, filterable directory across all institutions (Mumbai, India, US)."""
    s = db()
    q = (request.args.get("q") or "").strip()
    region = (request.args.get("region") or "").strip()
    country = (request.args.get("country") or "").strip()
    status = (request.args.get("status") or "").strip()
    type_val = (request.args.get("type") or "").strip()
    view_mode = (request.args.get("view") or "grid").strip()
    page = request.args.get("page", 1, type=int) or 1
    page = max(1, page)
    per_page = 24 if view_mode == "grid" else 30

    base = s.query(College)
    if q:
        search_pattern = f"%{q}%"
        base = base.filter(
            (College.college_name.ilike(search_pattern)) |
            (College.city.ilike(search_pattern)) |
            (College.region.ilike(search_pattern)) |
            (College.courses.ilike(search_pattern))
        )
    if country:
        base = base.filter(College.country == country)
    if region:
        base = base.filter(College.region == region)
    if type_val:
        base = base.filter(College.type == type_val)
    if status == "ranked":
        base = base.filter(College.is_ranked == True)  # noqa: E712
    elif status == "directory":
        base = base.filter(College.is_ranked == False)  # noqa: E712

    total = base.count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    
    # Order ranked first if all, then alphabetical
    rows = (base.order_by(College.is_ranked.desc(), College.college_name.asc())
            .limit(per_page).offset((page - 1) * per_page).all())

    # Get distinct filter options
    regions = [r[0] for r in
               s.query(College.region)
               .filter(College.region.isnot(None))
               .distinct().order_by(College.region).all() if r[0]]
    countries = [c[0] for c in
                 s.query(College.country)
                 .filter(College.country.isnot(None))
                 .distinct().order_by(College.country).all() if c[0]]
    types = [t[0] for t in
             s.query(College.type)
             .filter(College.type.isnot(None))
             .distinct().order_by(College.type).all() if t[0]]

    # Stats for directory header
    stats = {
        "total_colleges": s.query(College).count(),
        "total_ranked": s.query(College).filter(College.is_ranked == True).count(),  # noqa: E712
        "total_directory": s.query(College).filter(College.is_ranked == False).count(),  # noqa: E712
        "total_regions": len(regions),
    }

    return render_template("directory.html",
                           rows=[c.to_dict() for c in rows],
                           total=total, page=page, pages=pages,
                           per_page=per_page, q=q, region=region,
                           country=country, status=status, type_val=type_val,
                           view_mode=view_mode, regions=regions,
                           countries=countries, types=types, stats=stats)


@app.route("/compare")
def compare_page():
    s = db()
    colleges = [c.to_dict() for c in s.query(College)
                .filter(College.is_ranked == True)  # noqa: E712
                .order_by(College.college_name).all()]
    return render_template("compare.html", colleges=colleges,
                           weights=WEIGHTS, draw_threshold=DRAW_THRESHOLD)


@app.route("/college/<int:cid>")
def college_detail(cid):
    s = db()
    c = college_or_404(s, cid)
    history = (s.query(EloHistory).filter_by(college_id=cid)
               .order_by(EloHistory.created_at.asc()).all())
    comps = (s.query(Comparison)
             .filter((Comparison.college_a_id == cid) |
                     (Comparison.college_b_id == cid))
             .order_by(Comparison.created_at.desc()).limit(20).all())
    return render_template("college.html",
                           college=c.to_dict(),
                           history=[{"t": h.created_at.isoformat(),
                                     "r": h.rating} for h in history],
                           comparisons=[_comparison_dict(s, cc) for cc in comps])


@app.route("/about")
def about():
    return render_template("about.html", weights=WEIGHTS,
                           draw_threshold=DRAW_THRESHOLD,
                           k=EloConfig.K_FACTOR,
                           start=EloConfig.START_RATING,
                           naac=NAAC_MAP)


# ---------- admin ------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if (request.form.get("username") == ADMIN_USER and
                request.form.get("password") == ADMIN_PASS):
            session["is_admin"] = True
            return redirect(url_for("admin_panel"))
        flash("Invalid credentials", "error")
    return render_template("admin.html", logged_in=False, colleges=[])


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_panel():
    s = db()
    colleges = [c.to_dict() for c in s.query(College)
                .order_by(College.college_name).all()]
    return render_template("admin.html", logged_in=True, colleges=colleges)


@app.route("/admin/reset-elo", methods=["POST"])
@login_required
def admin_reset_elo():
    s = db()
    for c in s.query(College).filter(College.is_ranked == True).all():  # noqa: E712
        c.elo_rating = EloConfig.START_RATING
        s.add(EloHistory(college_id=c.id, rating=EloConfig.START_RATING))
    s.commit()
    flash("All Elo ratings reset to 1500.", "ok")
    return redirect(url_for("admin_panel"))


@app.route("/admin/recalculate", methods=["POST"])
@login_required
def admin_recalculate():
    """Replay all stored comparisons from scratch."""
    s = db()
    ranked = s.query(College).filter(College.is_ranked == True).all()  # noqa: E712
    for c in ranked:
        c.elo_rating = EloConfig.START_RATING
    s.query(EloHistory).delete()
    for c in ranked:
        s.add(EloHistory(college_id=c.id, rating=EloConfig.START_RATING))
    s.flush()

    comps = s.query(Comparison).order_by(Comparison.created_at.asc()).all()
    for cmp in comps:
        a = s.get(College, cmp.college_a_id)
        b = s.get(College, cmp.college_b_id)
        if not a or not b:
            continue
        score_a = 0.5 if cmp.winner == "DRAW" else (1.0 if cmp.winner == "A" else 0.0)
        res = elo_service.update(a.elo_rating, b.elo_rating, score_a)
        cmp.old_elo_a, cmp.old_elo_b = a.elo_rating, b.elo_rating
        cmp.new_elo_a, cmp.new_elo_b = res.new_a, res.new_b
        a.elo_rating, b.elo_rating = res.new_a, res.new_b
        s.add(EloHistory(college_id=a.id, rating=res.new_a))
        s.add(EloHistory(college_id=b.id, rating=res.new_b))
    s.commit()
    flash(f"Recalculated Elo from {len(comps)} comparisons.", "ok")
    return redirect(url_for("admin_panel"))


@app.route("/admin/import", methods=["POST"])
@login_required
def admin_import_csv():
    f = request.files.get("file")
    if not f:
        flash("No file uploaded", "error")
        return redirect(url_for("admin_panel"))
    s = db()
    reader = csv.DictReader(io.StringIO(f.read().decode("utf-8")))
    added = 0
    for row in reader:
        if s.query(College).filter_by(college_name=row["college_name"]).first():
            continue
        c = College(
            college_name=row["college_name"],
            city=row.get("city", "Mumbai"),
            type=row.get("type", "Private"),
            university=row.get("university", "University of Mumbai"),
            naac_grade=row.get("naac_grade", "B"),
            nirf_rank=int(row.get("nirf_rank") or 0) or None,
            annual_fee=int(row.get("annual_fee") or 0),
            average_package=int(row.get("average_package") or 0),
            highest_package=int(row.get("highest_package") or 0),
            placement_percentage=float(row.get("placement_percentage") or 0),
            student_rating=float(row.get("student_rating") or 0),
            website=row.get("website", ""),
            logo=row.get("logo", ""),
            elo_rating=EloConfig.START_RATING,
        )
        s.add(c)
        added += 1
    s.commit()
    flash(f"Imported {added} colleges.", "ok")
    return redirect(url_for("admin_panel"))


@app.route("/admin/export/<fmt>")
@login_required
def admin_export(fmt):
    s = db()
    rows = [c.to_dict() for c in s.query(College).all()]
    if fmt == "json":
        return Response(json.dumps(rows, indent=2),
                        mimetype="application/json",
                        headers={"Content-Disposition":
                                 "attachment;filename=colleges.json"})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":
                             "attachment;filename=colleges.csv"})


# ---------- REST API ---------------------------------------------------------

@app.route("/api/colleges")
def api_colleges():
    s = db()
    return jsonify([c.to_dict() for c in s.query(College).all()])


@app.route("/api/college/<int:cid>")
def api_college(cid):
    s = db()
    return jsonify(college_or_404(s, cid).to_dict())


@app.route("/api/leaderboard")
def api_leaderboard():
    s = db()
    cohort = request.args.get("cohort")
    q = s.query(College).filter(College.is_ranked == True)  # noqa: E712
    if cohort:
        q = q.filter(College.cohort == cohort)
    rows = sorted([c.to_dict() for c in q.all()],
                  key=lambda c: c["elo_rating"] or 0, reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return jsonify(rows)


@app.route("/api/compare", methods=["POST"])
def api_compare():
    payload = request.get_json(force=True)
    s = db()
    a = college_or_404(s, int(payload["a"]))
    b = college_or_404(s, int(payload["b"]))
    # Only ranked colleges have metrics/Elo; never mix cohorts (currencies).
    err = eligibility_error(a, b)
    if err:
        return jsonify({"error": err}), 400

    result = run_match(s, a, b, compare_service, elo_service)
    s.commit()

    return jsonify({
        "a": a.to_dict(), "b": b.to_dict(),
        "winner": result["winner"],
        "score_a": result["score_a"].as_dict(),
        "score_b": result["score_b"].as_dict(),
        "old_elo": result["old_elo"],
        "new_elo": result["new_elo"],
        "expected": result["expected"],
        "weights": WEIGHTS,
        # Which parameters actually decided this match. When two colleges only
        # share a NAAC grade this is ["naac"] alone -- the UI says so rather
        # than implying fees and placement were weighed.
        "metrics_used": result["metrics_used"],
    })


@app.route("/api/addCollege", methods=["POST"])
@login_required
def api_add_college():
    p = request.get_json(force=True)
    s = db()
    c = College(elo_rating=EloConfig.START_RATING, **p)
    s.add(c); s.commit()
    return jsonify(c.to_dict()), 201


@app.route("/api/updateCollege/<int:cid>", methods=["PUT"])
@login_required
def api_update_college(cid):
    p = request.get_json(force=True)
    s = db()
    c = college_or_404(s, cid)
    for k, v in p.items():
        if hasattr(c, k):
            setattr(c, k, v)
    s.commit()
    return jsonify(c.to_dict())


@app.route("/api/deleteCollege/<int:cid>", methods=["DELETE"])
@login_required
def api_delete_college(cid):
    s = db()
    c = college_or_404(s, cid)
    s.delete(c); s.commit()
    return jsonify({"deleted": cid})


# ---------- helpers ----------------------------------------------------------

def _comparison_dict(s, cmp: Comparison) -> dict:
    ca = s.get(College, cmp.college_a_id)
    cb = s.get(College, cmp.college_b_id)
    return {
        "id": cmp.id,
        "a": ca.college_name if ca else "?",
        "b": cb.college_name if cb else "?",
        "winner": cmp.winner,
        "score_a": cmp.score_a,
        "score_b": cmp.score_b,
        "old_elo_a": cmp.old_elo_a,
        "old_elo_b": cmp.old_elo_b,
        "new_elo_a": cmp.new_elo_a,
        "new_elo_b": cmp.new_elo_b,
        "created_at": cmp.created_at.isoformat() if cmp.created_at else None,
    }


# ---------- bootstrap --------------------------------------------------------

@app.errorhandler(404)
def _404(_e):
    return render_template("index.html",
                           stats={"count": 0, "ranked": 0, "directory": 0,
                                  "states": 0, "top_elo": 0,
                                  "avg_package": None, "avg_fee": None},
                           top10=[], recent=[]), 404


if __name__ == "__main__":
    init_db()
    # Auto-seed on first run if DB is empty.
    s = SessionLocal()
    if s.query(College).count() == 0:
        s.close()
        from seed_database import run as seed_run
        seed_run()
    else:
        s.close()
    app.run(debug=not settings.is_production, host="0.0.0.0",
            port=settings.port)
