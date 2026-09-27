"""HTTP-Routen."""

from __future__ import annotations

from flask import (Blueprint, abort, current_app, flash, make_response, redirect, render_template,
                   request, url_for)

from .matches import POSITION_LABELS, POSITIONS
from .riot import NotFound, RiotAPIError
from .services import PrimeStats
from .store import Team
from .team_stats import (LABELS, build_report, filter_records, history_rows, opponents, patches)
from .timeline import analysis_payload

bp = Blueprint("main", __name__)

MAX_ANALYSIS_GAMES = 30


def ps() -> PrimeStats:
    service = current_app.extensions["primestats"]
    if service is None:
        abort(503, "Kein Riot-API-Key konfiguriert. Setze LOL_API_KEY oder starte mit PRIMESTATS_DEMO=1.")
    return service


def _team_or_404(team_id: int) -> Team:
    team = ps().store.get_team(team_id)
    if team is None:
        abort(404)
    return team


@bp.errorhandler(RiotAPIError)
def riot_error(exc: RiotAPIError):
    return render_template("error.html", message=exc.message), 502


@bp.app_errorhandler(404)
@bp.app_errorhandler(503)
def http_error(exc):
    return render_template("error.html", message=exc.description, code=exc.code), exc.code


# ---------------------------------------------------------------- start
@bp.get("/")
def index():
    service = current_app.extensions["primestats"]
    teams = service.store.list_teams() if service else []
    return render_template("index.html", teams=teams)


# --------------------------------------------------------------- player
@bp.get("/player")
def player():
    riot_id = (request.args.get("riot_id") or "").strip()
    if not riot_id:
        return redirect(url_for("main.index"))
    count = min(max(request.args.get("count", 20, type=int), 5), 60)
    try:
        account, games = ps().player_games(riot_id, count)
    except (ValueError, NotFound) as exc:
        flash(getattr(exc, "message", None) or str(exc), "error")
        return redirect(url_for("main.index"))
    return render_template("player.html", account=account, games=games, count=count)


# ------------------------------------------------------------- analysis
@bp.get("/analysis")
def analysis():
    ids = list(dict.fromkeys(request.args.getlist("m")))[:MAX_ANALYSIS_GAMES]
    if not ids:
        flash("Bitte mindestens ein Spiel auswählen.", "error")
        return redirect(request.referrer or url_for("main.index"))
    service = ps()
    items, matches = [], []
    for mid in ids:
        match = service.match(mid)
        summary = service.timeline_summary(match)
        if summary:
            items.append((match, summary))
            matches.append(match)
    focus = set(request.args.getlist("focus"))
    team_id = request.args.get("team", type=int)
    if team_id:
        team = service.store.get_team(team_id)
        if team:
            focus |= team.puuids
    payload = analysis_payload(items, focus)
    for p in payload["players"]:
        p["position_label"] = POSITION_LABELS.get(p["position"], p["position"])
    matches.sort(key=lambda m: m.created, reverse=True)
    return render_template("analysis.html", payload=payload, matches=matches)


# ---------------------------------------------------------------- match
@bp.get("/match/<match_id>")
def match_detail(match_id: str):
    match = ps().match(match_id)
    focus = request.args.get("team", type=int)
    team = ps().store.get_team(focus) if focus else None
    return render_template("match.html", match=match, team=team)


# ---------------------------------------------------------------- teams
@bp.get("/teams")
def teams():
    return render_template("teams.html", teams=ps().store.list_teams())


def _member_entries() -> list[tuple[str, str]]:
    ids = request.form.getlist("riot_id")
    roles = request.form.getlist("role")
    roles += [""] * (len(ids) - len(roles))
    return [(rid.strip(), role if role in POSITIONS else "") for rid, role in zip(ids, roles) if rid.strip()]


def _team_form_values():
    name = (request.form.get("name") or "").strip()[:60]
    tag = (request.form.get("tag") or "").strip()[:8]
    min_members = min(max(request.form.get("min_members", 4, type=int), 1), 5)
    return name, tag, min_members


@bp.get("/teams/new")
def team_new():
    return render_template("team_form.html", team=None, entries=[("", p) for p in POSITIONS] + [("", "")])


@bp.post("/teams")
def team_create():
    name, tag, min_members = _team_form_values()
    entries = _member_entries()
    if not name or not entries:
        flash("Name und mindestens ein Spieler sind Pflicht.", "error")
        return render_template("team_form.html", team=None, entries=entries or [("", "")], form=request.form), 400
    members, errors = ps().resolve_members(entries)
    if errors:
        for err in errors:
            flash(err, "error")
        return render_template("team_form.html", team=None, entries=entries, form=request.form), 400
    team_id = ps().store.create_team(name, tag, min_members, members)
    flash(f"Team {name} angelegt – starte die Synchronisation, um Custom Games zu finden.", "ok")
    return redirect(url_for("main.team_detail", team_id=team_id))


@bp.get("/teams/<int:team_id>/edit")
def team_edit(team_id: int):
    team = _team_or_404(team_id)
    entries = [(m.riot_id, m.role) for m in team.members] + [("", "")]
    return render_template("team_form.html", team=team, entries=entries)


@bp.post("/teams/<int:team_id>/edit")
def team_update(team_id: int):
    team = _team_or_404(team_id)
    name, tag, min_members = _team_form_values()
    entries = _member_entries()
    members, errors = ps().resolve_members(entries)
    if errors or not name or not members:
        for err in errors or ["Name und mindestens ein Spieler sind Pflicht."]:
            flash(err, "error")
        return render_template("team_form.html", team=team, entries=entries or [("", "")], form=request.form), 400
    ps().store.update_team(team_id, name, tag, min_members, members)
    flash("Team gespeichert. Neue Spieler werden bei der nächsten Synchronisation berücksichtigt.", "ok")
    return redirect(url_for("main.team_detail", team_id=team_id))


@bp.post("/teams/<int:team_id>/delete")
def team_delete(team_id: int):
    team = _team_or_404(team_id)
    ps().store.delete_team(team_id)
    flash(f"Team {team.name} gelöscht.", "ok")
    return redirect(url_for("main.teams"))


@bp.get("/teams/<int:team_id>")
def team_detail(team_id: int):
    service = ps()
    team = _team_or_404(team_id)
    records = service.team_records(team)
    filters = {
        "label": request.args.get("label", "all"),
        "side": request.args.get("side", "all"),
        "patch": request.args.get("patch", ""),
        "opponent": request.args.get("opponent", ""),
        "last": request.args.get("last", 0, type=int),
    }
    if filters["label"] not in {"all", *LABELS}:
        filters["label"] = "all"
    selected = filter_records(records, **filters)
    report = build_report(team, selected)
    dt = current_app.jinja_env.filters["dt"]
    chart_data = {
        "gold_curves": report["gold_curves"],
        "trend": [{**t, "date": dt(t["date"], "%d.%m.")} for t in report["trend"]],
    }
    return render_template(
        "team.html", team=team, report=report, filters=filters, chart_data=chart_data,
        history=history_rows(records), selected_ids={r.match.match_id for r in selected},
        patches=patches(records), opponents=opponents(records), job=service.jobs.get(team_id),
    )


@bp.post("/teams/<int:team_id>/sync")
def team_sync(team_id: int):
    team = _team_or_404(team_id)
    job = ps().jobs.start(team)
    return render_template("_sync_status.html", team=team, job=job)


@bp.get("/teams/<int:team_id>/sync")
def team_sync_status(team_id: int):
    team = _team_or_404(team_id)
    job = ps().jobs.get(team_id)
    resp = make_response(render_template("_sync_status.html", team=team, job=job))
    if job and job.status == "done" and request.headers.get("HX-Request"):
        resp.headers["HX-Refresh"] = "true"
    return resp


@bp.post("/teams/<int:team_id>/games/<match_id>")
def team_game_update(team_id: int, match_id: str):
    _team_or_404(team_id)
    label = request.form.get("label")
    included = request.form.get("included")
    ps().store.update_team_game(
        team_id, match_id,
        label=label if label in LABELS else None,
        included=None if included is None else included in {"1", "true", "on"},
    )
    if request.headers.get("HX-Request"):
        resp = make_response("")
        resp.headers["HX-Refresh"] = "true"
        return resp
    return redirect(request.referrer or url_for("main.team_detail", team_id=team_id))
