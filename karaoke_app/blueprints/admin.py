# routes admin (html pages + auth)
from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, jsonify

from services.auth import admin_required, csrf_protected
from services.rate_limit import check_rate_limit, reset_rate_limit
from database.db_utils import (
    create_admin, authenticate_admin, admin_exists, change_admin_password,
    reset_admin_password,
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    # premier admin -> setup
    if not admin_exists():
        return redirect(url_for('admin.setup'))

    error = None
    if request.method == 'POST':
        ip = request.remote_addr
        if check_rate_limit(ip):
            error = 'Trop de tentatives. Attendez 5 minutes.'
            return render_template('admin_login.html', error=error)

        username = request.form.get('username', '').strip()
        pwd = request.form.get('password', '')
        remember = request.form.get('remember_me') == 'on'

        admin_id = authenticate_admin(username, pwd)
        if admin_id:
            reset_rate_limit(ip)
            session.permanent = True
            session['admin_id'] = admin_id
            session['admin_username'] = username
            session['remember_me'] = remember
            session.modified = True
            return redirect(url_for('admin.dashboard'))
        error = 'Identifiants incorrects'

    return render_template('admin_login.html', error=error)



@admin_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if admin_exists():
        return redirect(url_for('admin.login'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        pwd = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if len(username) < 3:
            error = "Le nom d'utilisateur doit contenir au moins 3 caracteres"
        elif len(pwd) < 8:
            error = "Le mot de passe doit contenir au moins 8 caracteres"
        elif pwd != confirm:
            error = "Les mots de passe ne correspondent pas"
        else:
            admin_id = create_admin(username, pwd)
            if admin_id:
                session.permanent = True
                session['admin_id'] = admin_id
                session['admin_username'] = username
                return redirect(url_for('admin.dashboard'))
            error = "Erreur lors de la creation du compte"

    return render_template('admin_setup.html', error=error)


@admin_bp.route('/change-password', methods=['POST'])
@admin_required
@csrf_protected
def change_password():
    current_pwd = request.form.get('current_password', '')
    new_pwd = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')

    if len(new_pwd) < 8:
        return jsonify(ok=False, error="Le nouveau mot de passe doit contenir au moins 8 caracteres"), 400
    if new_pwd != confirm:
        return jsonify(ok=False, error="Les mots de passe ne correspondent pas"), 400

    admin_id = session.get('admin_id')
    if change_admin_password(admin_id, current_pwd, new_pwd):
        return jsonify(ok=True, message="Mot de passe modifie avec succes")
    return jsonify(ok=False, error="Mot de passe actuel incorrect"), 400


@admin_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    error = None
    success = None
    if request.method == 'POST':
        ip = request.remote_addr
        if check_rate_limit(ip):
            error = 'Trop de tentatives. Attendez 5 minutes.'
            return render_template('admin_forgot_password.html', error=error)

        username = request.form.get('username', '').strip()
        current_pwd = request.form.get('current_password', '')
        new_pwd = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if len(new_pwd) < 8:
            error = 'Le nouveau mot de passe doit contenir au moins 8 caracteres'
        elif new_pwd != confirm:
            error = 'Les mots de passe ne correspondent pas'
        elif current_pwd == new_pwd:
            error = 'Le nouveau mot de passe doit etre different de l\'ancien'
        elif not authenticate_admin(username, current_pwd):
            error = 'Identifiants incorrects'
        elif reset_admin_password(username, new_pwd):
            reset_rate_limit(ip)
            success = 'Mot de passe reinitialise avec succes'
        else:
            error = 'Erreur lors de la reinitialisation'

    return render_template('admin_forgot_password.html', error=error, success=success)


@admin_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('admin.login'))


# pages dashboard

@admin_bp.route('/')
@admin_required
def dashboard():
    return render_template('admin.html')


@admin_bp.route('/upload')
@admin_required
def upload_page():
    return render_template('admin_upload.html')


@admin_bp.route('/alerts')
@admin_required
def alerts_page():
    return render_template('admin_alerts.html')


@admin_bp.route('/ads')
@admin_required
def ads_page():
    return render_template('admin_ads.html')


@admin_bp.route('/catalogue')
@admin_required
def catalogue_page():
    return render_template('admin_catalogue.html')


@admin_bp.route('/analytics')
@admin_required
def analytics_page():
    return render_template('admin_analytics.html')


@admin_bp.route('/stream')
@admin_required
def stream():
    # sse endpoint pour le dashboard
    from flask import Response
    from services.sse import event_stream
    return Response(event_stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache',
                             'X-Accel-Buffering': 'no',
                             'Connection': 'keep-alive'})
