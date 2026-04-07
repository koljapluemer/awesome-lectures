from flask import Flask, g, request
from flask_cors import CORS

from config import Config
from db import close_db, init_db, get_db
from routes.interactions import bp as interactions_bp
from routes.ratings import bp as ratings_bp
from routes.suggestions import bp as suggestions_bp

FP_HEADER = "X-AL-Fingerprint"


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    CORS(app, origins=app.config["ALLOWED_ORIGINS"], allow_headers=[FP_HEADER, "Content-Type"])
    app.teardown_appcontext(close_db)

    app.register_blueprint(interactions_bp)
    app.register_blueprint(ratings_bp)
    app.register_blueprint(suggestions_bp)

    init_db(app)

    @app.before_request
    def load_fingerprint():
        fp = request.headers.get(FP_HEADER, "").strip()
        g.fingerprint = fp if fp else None
        if g.fingerprint:
            db = get_db()
            db.execute("INSERT OR IGNORE INTO fingerprints (id) VALUES (?)", (fp,))
            db.commit()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
