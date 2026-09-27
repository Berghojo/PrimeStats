"""Startpunkt: ``python main_page.py`` (oder ``flask --app main_page run``)."""

import os

from dotenv import load_dotenv

load_dotenv()

from primestats import create_app  # noqa: E402  (nach load_dotenv, damit .env greift)

app = create_app()

if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG", "0") == "1")
