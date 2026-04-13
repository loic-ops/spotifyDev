# auth helpers: admin_required, csrf
import secrets
from functools import wraps
from flask import session, request, jsonify, redirect, url_for, abort


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def verify_csrf():
    tok = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
    if not tok or tok != session.get('_csrf_token'):
        abort(403, description="CSRF token missing or invalid")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_id'):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


def csrf_protected(f):
    # verifie csrf sur les endpoints mutants
    @wraps(f)
    def decorated(*args, **kwargs):
        verify_csrf()
        return f(*args, **kwargs)
    return decorated
