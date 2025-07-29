from flask import Flask, render_template, request, session
from collections import namedtuple
import requests
from utils import *
from collect_games import *
from dotenv import load_dotenv
import os
import secrets
from flask_session import Session


app = Flask(__name__)

@app.route("/")
def start():
    return render_template("index.html")


@app.route("/search")
def search():
    q = request.args.get("q")
    assert type(q) is str and len(q) > 0 and len(q) < 20
    if "#" in q:
        games, game_stats = get_by_name(q)


    games = list(games.values())
    return render_template("games.html", games=games)


@app.route("/data")
def data_aggregator():
    gameIds = json.loads(request.args.get("gameIds"))
    stats = get_game_stats(gameIds)

    stats = dataframe_to_google_chart(stats)
    return render_template("stats.html", stats=stats)

if __name__ == "__main__":
    load_dotenv()
    print(os.getenv("LOL_API_KEY"))
    app.secret_key = os.getenv("SECRET_KEY")
    app.jinja_env.filters['zip'] = zip
    app.run(debug=True)
