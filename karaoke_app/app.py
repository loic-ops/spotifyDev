# backend flask - admin + api pour electron
import os, time, logging
from datetime import timedelta

from flask import Flask, request, session, redirect, url_for, jsonify
from config import Config
from services.auth import generate_csrf_token
from blueprints.admin import admin_bp
from blueprints.api_public import api_public_bp
from blueprints.api_admin import api_admin_bp

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('karaoking')

app = Flask(__name__)
app.config.from_object(Config)

# session securisee
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

REMEMBER_ME_LIFETIME = 30 * 24 * 3600   # 30 jours
DEFAULT_SESSION_LIFETIME = 4 * 3600     # 4h

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

app.jinja_env.globals['csrf_token'] = generate_csrf_token


@app.context_processor
def inject_admin_role():
    # expose le role admin courant a tous les templates (None si non connecte)
    return {'current_admin_role': session.get('admin_role')}


# db init
def wait_for_database(max_retries=30, delay=2):
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError

    for i in range(max_retries):
        try:
            eng = create_engine(Config.DATABASE_URI)
            with eng.connect():
                print("Database connected successfully!")
                return True
        except OperationalError:
            print(f"Waiting for database... ({i+1}/{max_retries})")
            time.sleep(delay)
    return False


@app.before_request
def initialize_database():
    if not hasattr(app, 'db_initialized'):
        try:
            from database.db_utils import init_db
            init_db()
            app.db_initialized = True
            print("Database initialized successfully!")
        except Exception as e:
            print(f"Database initialization error: {e}")


@app.before_request
def apply_session_lifetime():
    if session.get('remember_me'):
        app.permanent_session_lifetime = timedelta(seconds=REMEMBER_ME_LIFETIME)
    else:
        app.permanent_session_lifetime = timedelta(seconds=DEFAULT_SESSION_LIFETIME)


# CORS /api/* pour l'Electron (cookies de session autorises)
def _apply_cors_headers(resp):
    origin = request.headers.get('Origin')
    if origin:
        # Avec credentials, le browser interdit Allow-Origin: *
        resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        resp.headers['Vary'] = 'Origin'
    else:
        resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRF-Token'
    resp.headers['Access-Control-Max-Age'] = '3600'


@app.after_request
def handle_cors(resp):
    if request.path.startswith('/api/'):
        _apply_cors_headers(resp)
    return resp


@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS' and request.path.startswith('/api/'):
        from flask import make_response
        resp = make_response()
        _apply_cors_headers(resp)
        return resp


# headers securite
@app.after_request
def set_security_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    if not request.path.startswith('/api/'):
        resp.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; "
            "img-src 'self' data: https://i.ytimg.com; "
            "media-src 'self'; "
            "connect-src 'self'"
        )
    return resp


@app.route('/')
def root():
    if session.get('admin_id'):
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('admin.login'))


# blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(api_public_bp)
app.register_blueprint(api_admin_bp)


# error handlers
@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': str(e.description) if hasattr(e, 'description') else 'Bad request'}), 400

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({'error': 'Authentication required'}), 401

@app.errorhandler(403)
def forbidden(e):
    return jsonify({'error': str(e.description) if hasattr(e, 'description') else 'Forbidden'}), 403

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large (max 100MB)'}), 413

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    print("Waiting for database...")
    if wait_for_database():
        try:
            from database.db_utils import init_db
            init_db()
            print("Database tables created successfully!")
        except Exception as e:
            print(f"Could not initialize database: {e}")
    else:
        print("Warning: Could not connect to database. Starting anyway...")

    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=5000)
