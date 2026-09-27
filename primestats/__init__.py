"""PrimeStats – Statistiken für Prime-League- und Custom-Games."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask

from .config import Settings
from .ddragon import DataDragon
from .matches import POSITION_LABELS
from .riot import MatchSource, RiotClient
from .services import PrimeStats
from .store import Store
from .team_stats import LABELS

TZ = ZoneInfo("Europe/Berlin")


def create_app(settings: Settings | None = None, source: MatchSource | None = None,
               store: Store | None = None) -> Flask:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app = Flask(__name__)
    app.secret_key = settings.secret_key
    app.config["SETTINGS"] = settings

    store = store or Store(settings.data_dir / "primestats.sqlite")
    if source is None:
        if settings.demo:
            from .demo import DemoSource
            source = DemoSource()
        elif settings.api_key:
            source = RiotClient(settings.api_key, store, region=settings.region)
    ddragon = DataDragon(settings.data_dir / "ddragon", fetch=settings.ddragon_fetch,
                         language=settings.ddragon_language)
    app.extensions["primestats"] = PrimeStats(store, source, settings.sync_match_count) if source else None
    app.extensions["ddragon"] = ddragon

    _register_template_helpers(app, ddragon)

    from .views import bp
    app.register_blueprint(bp)
    return app


def _register_template_helpers(app: Flask, ddragon: DataDragon) -> None:
    def pct(value, digits=0):
        return "–" if value is None else f"{value * 100:.{digits}f}%"

    def num(value, digits=1):
        if value is None:
            return "–"
        return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def signed(value, digits=0):
        if value is None:
            return "–"
        return ("+" if value > 0 else "") + num(value, digits)

    def duration(seconds):
        if seconds is None:
            return "–"
        seconds = int(seconds)
        return f"{seconds // 60}:{seconds % 60:02d}"

    def dt(value: datetime, fmt="%d.%m.%Y %H:%M"):
        return value.astimezone(TZ).strftime(fmt)

    def tone(value, neutral=0.0):
        if value is None or value == neutral:
            return ""
        return "pos" if value > neutral else "neg"

    app.jinja_env.filters.update(pct=pct, num=num, signed=signed, duration=duration, dt=dt, tone=tone)
    app.jinja_env.globals.update(
        champ=ddragon.champion,
        champ_url=ddragon.icon_url,
        position_label=lambda p: POSITION_LABELS.get(p, p or "–"),
        label_name=lambda key: LABELS.get(key, key),
        LABELS=LABELS,
        POSITION_LABELS=POSITION_LABELS,
    )

    @app.context_processor
    def inject_mode():
        settings: Settings = app.config["SETTINGS"]
        return {"demo_mode": settings.demo, "configured": app.extensions["primestats"] is not None}
