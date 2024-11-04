import os
from flask import Flask, g
from config import load_config
from database import ComicDatabase
from logger import app_logger
from text_analysis import create_yogi_bear_voice
from modules.auth_module import auth_bp
from modules.loyalty_module import loyalty_bp
from modules.media_module import media_bp
from modules.routes_module import routes_bp
from modules.comic_module import comic_bp

def create_app():
    app = Flask(__name__, static_folder='static')
    config = load_config()

    # Store config on app for access in other parts of application
    app.config['APP_CONFIG'] = config

    # Set the secret key for Flask sessions
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app_logger.debug(f"Secret key set: {config.SECRET_KEY[:5]}...")

    # Configure image serving for generated images
    app.config['GENERATED_IMAGES_FOLDER'] = config.OUTPUT_DIR
    os.makedirs(app.config['GENERATED_IMAGES_FOLDER'], exist_ok=True)

    # Configure audio serving for albums (using relative path)
    app.config['ALBUMS_FOLDER'] = 'audio/albums'

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(loyalty_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(routes_bp)
    app.register_blueprint(comic_bp)

    @app.before_first_request
    def before_first_request():
        # Create Yogi Bear voice when the application starts
        if config.GENERATE_AUDIO:
            create_yogi_bear_voice()

    @app.after_request
    def add_csp_header(response):
        csp = ("default-src 'self'; "
               "script-src 'self' 'unsafe-inline' https://code.jquery.com https://unpkg.com https://stackpath.bootstrapcdn.com https://cdn.jsdelivr.net; "
               "style-src 'self' 'unsafe-inline' https://unpkg.com https://stackpath.bootstrapcdn.com; "
               "img-src 'self' https://*.tile.openstreetmap.org https://unpkg.com data:; "
               "font-src 'self' https://stackpath.bootstrapcdn.com; "
               "connect-src 'self' https://nominatim.openstreetmap.org;")
        response.headers['Content-Security-Policy'] = csp
        return response

    @app.teardown_appcontext
    def close_db(error):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    return app, config

if __name__ == '__main__':
    app, config = create_app()
    app_logger.info("Starting Grizz-AI web application")
    app.run(host='0.0.0.0', port=config.WEB_PORT, debug=config.WEB_DEBUG)
