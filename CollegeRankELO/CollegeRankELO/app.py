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
import os
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, session, Response, flash, abort, send_file)

from database import SessionLocal, init_db
from models import College, Comparison, EloHistory
from elo import EloService, EloConfig
from compare import CompareService, NAAC_MAP, WEIGHTS, DRAW_THRESHOLD

app = Flask(__name__)
app.secret_key = "collegerankelo-dev-secret"

elo_service = EloService()
compare_service = CompareService()

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


# ---------- helpers ----------------------------------------------------------

def db():
    return SessionLocal()


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return fn(*a, **kw)
    return wrapper


def college_or_404(s, cid: int) -> College:
    c = s.query(College).get(cid)
    if not c:
        abort(404)
    return c


# ---------- page routes ------------------------------------------------------

@app.route("/")
def index():
    s = db()
    colleges = s.query(College).all()
    top10 = sorted(colleges, key=lambda c: c.elo_rating or 0, reverse=True)[:10]
    stats = {
        "count": len(colleges),
        "top_elo": round(max((c.elo_rating for c in colleges), default=0), 2),
        "avg_package": int(sum(c.average_package or 0 for c in colleges) /
                           max(1, len(colleges))),
        "avg_fee": int(sum(c.annual_fee or 0 for c in colleges) /
                       max(1, len(colleges))),
    }
    recent = (s.query(Comparison).order_by(Comparison.created_at.desc())
              .limit(5).all())
    return render_template("index.html", stats=stats,
                           top10=[c.to_dict() for c in top10],
                           recent=[_comparison_dict(s, r) for r in recent])


@app.route("/leaderboard")
def leaderboard():
    s = db()
    colleges = [c.to_dict() for c in s.query(College).all()]
    colleges.sort(key=lambda c: c["elo_rating"], reverse=True)
    return render_template("leaderboard.html", colleges=colleges)


@app.route("/compare")
def compare_page():
    s = db()
    colleges = [c.to_dict() for c in s.query(College)
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
    for c in s.query(College).all():
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
    for c in s.query(College).all():
        c.elo_rating = EloConfig.START_RATING
    s.query(EloHistory).delete()
    for c in s.query(College).all():
        s.add(EloHistory(college_id=c.id, rating=EloConfig.START_RATING))
    s.flush()

    comps = s.query(Comparison).order_by(Comparison.created_at.asc()).all()
    for cmp in comps:
        a = s.query(College).get(cmp.college_a_id)
        b = s.query(College).get(cmp.college_b_id)
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
    rows = sorted([c.to_dict() for c in s.query(College).all()],
                  key=lambda c: c["elo_rating"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return jsonify(rows)


@app.route("/api/compare", methods=["POST"])
def api_compare():
    payload = request.get_json(force=True)
    s = db()
    a = college_or_404(s, int(payload["a"]))
    b = college_or_404(s, int(payload["b"]))
    if a.id == b.id:
        return jsonify({"error": "select two different colleges"}), 400

    a_dict, b_dict = a.to_dict(), b.to_dict()
    peers = compare_service.peers_max(a_dict, b_dict)
    score_a = compare_service.score(a_dict, peers)
    score_b = compare_service.score(b_dict, peers)
    winner = compare_service.decide(score_a, score_b)

    outcome_a = {"A": 1.0, "B": 0.0, "DRAW": 0.5}[winner]
    old_a, old_b = a.elo_rating, b.elo_rating
    res = elo_service.update(old_a, old_b, outcome_a)
    a.elo_rating, b.elo_rating = res.new_a, res.new_b

    s.add(EloHistory(college_id=a.id, rating=res.new_a))
    s.add(EloHistory(college_id=b.id, rating=res.new_b))
    comp = Comparison(
        college_a_id=a.id, college_b_id=b.id, winner=winner,
        score_a=score_a.total, score_b=score_b.total,
        breakdown_a=json.dumps(score_a.as_dict()),
        breakdown_b=json.dumps(score_b.as_dict()),
        old_elo_a=old_a, old_elo_b=old_b,
        new_elo_a=res.new_a, new_elo_b=res.new_b,
    )
    s.add(comp)
    s.commit()

    return jsonify({
        "a": a.to_dict(), "b": b.to_dict(),
        "winner": winner,
        "score_a": score_a.as_dict(),
        "score_b": score_b.as_dict(),
        "old_elo": {"a": old_a, "b": old_b},
        "new_elo": {"a": res.new_a, "b": res.new_b},
        "expected": {"a": res.expected_a, "b": res.expected_b},
        "weights": WEIGHTS,
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
    return {
        "id": cmp.id,
        "a": s.query(College).get(cmp.college_a_id).college_name,
        "b": s.query(College).get(cmp.college_b_id).college_name,
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
    return render_template("index.html", stats={"count": 0, "top_elo": 0,
                                                "avg_package": 0, "avg_fee": 0},
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
    app.run(debug=True, host="0.0.0.0", port=5000)
