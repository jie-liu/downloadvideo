from flask import Flask
from flask_cors import CORS
from routes import bp
from config import PORT


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(bp)
    return app


if __name__ == "__main__":
    app = create_app()
    print(f"Video Downloader Server running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    app.run(host="0.0.0.0", port=PORT, debug=False)
