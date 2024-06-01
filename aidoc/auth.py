from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash

import functools
import datetime

from aidoc.db import get_db

bp = Blueprint('auth', __name__)

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        db, cursor = get_db()
        cursor.execute('SELECT * FROM user WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        if user is None:
            session.pop('user_id', None)
        else:
            g.user = user

@bp.route('/')
def index():
    if g.get('user') is None:
        session.clear() # logged out from everything

    if g.user: # already logged in
        if 'sender_mode' in session and session['sender_mode']=='dentist':
            return redirect(url_for("image.history", role='dentist'))
        elif 'sender_mode' in session and session['sender_mode']=='osm':
            return redirect(url_for("image.history", role='osm'))
        else:
            return render_template("patient_upload.html")
    else:
        return render_template("patient_login.html") # OSM and Patient login are on the same page

@bp.route('/dentist')
def dentist_index():
    if g.get('user') is None:
        session.clear() # logged out from everything

    if g.user: # already logged in
        if 'sender_mode' in session and session['sender_mode']=='dentist':
            return redirect(url_for("image.history", role='dentist'))
    else:
        return render_template("dentist_login.html")

@bp.route('/login/<role>', methods=('Post',))
def login(role):
    
    session['sender_mode'] = role
    
    if role=='patient':
        national_id = request.form['national_id']
    
        db, cursor = get_db()
        cursor.execute(
            'SELECT * FROM user WHERE national_id = %s', (national_id,)
        )
        user = cursor.fetchone()
        if user is None:
            error_msg = "กรุณาลงทะเบียน เลขบัตรประจำตัวประชาชนของท่านยังไม่ถูกลงทะเบียนในระบบ"
            session['national_id'] = national_id
            flash(error_msg)
            return redirect(url_for('user.register', role='patient'))
        elif user['is_patient']: # Logged in sucessfully
            session['user_id'] = user['id']
            load_logged_in_user()
            return redirect(url_for('image.upload_image', role='patient'))
        else: # Duplicate account found, ask for merging
            error_msg = "พบข้อมูลเบื้องต้นของท่านในระบบ แต่ท่านยังไม่ได้ถูกลงทะเบียนในฐานะคนไข้ กรุณาลงทะเบียนก่อน"
            session['user_id'] = user['id']
            flash(error_msg)

            data = {} # a data container to store submitted values from the form
            data['current_year'] = datetime.date.today().year # set the current Thai Year to the global variable
            data["valid_national_id"] = True
            data["valid_phone"] = True
            data["name"] = user["name"]
            data["surname"] = user["surname"]
            data["national_id"] = user["national_id"]
            data["phone"] = user["phone"]
            data['sex'] = user['sex']
            data["job_position"] = user["job_position"]
            data["province"] = user["province"]
            if user["email"] is None:
                data["email"] = ''
            return render_template("patient_register.html", data=data)
    elif role=='osm':
        national_id = request.form['osm_national_id']
        phone = request.form['osm_phone']

        db, cursor = get_db()
        cursor.execute(
            'SELECT * FROM user WHERE national_id = %s OR phone = %s', (national_id, phone)
        )
        user = cursor.fetchone()
        if user is None:
            error_msg = "ไม่พบข้อมูลของท่านในระบบ กรุณาลงทะเบียนก่อน"
            session['national_id'] = national_id
            session['phone'] = phone
            flash(error_msg)
            return redirect(url_for('user.register', role='osm'))
        elif user['is_osm'] and national_id==user['national_id'] and phone==user['phone']: # osm logged in successfully
            # Logged in sucessfully
            session['user_id'] = user['id']
            load_logged_in_user()
            return redirect('/')
        else:
            error_msg = "พบข้อมูลเบื้องต้นของท่านในระบบ แต่ท่านยังไม่ได้ถูกลงทะเบียนในฐานะผู้ตรวจคัดกรอง กรุณาลงทะเบียนก่อน"
            flash(error_msg)
            session['user_id'] = user['id'] # Mark that this user as duplicated user
            data = {} # data to populate the osm register page (with the already registered user)
            data["name"] = user["name"]
            data["surname"] = user["surname"]
            data["national_id"] = user["national_id"]
            data["email"] = user["email"]
            data["phone"] = user["phone"]
            data["province"] = user["province"]
            return render_template("osm_register.html", data=data)
    elif role=='dentist':
        
        username = request.form['username']
        password = request.form['password']      
        error_msg = None
        db, cursor = get_db()
        cursor.execute(
            'SELECT * FROM user WHERE username = %s', (username,)
        )
        user = cursor.fetchone()
        if user is None:
            error_msg = "ไม่พบรหัสผู้ใช้ โปรดลองอีกครั้งหนึ่งหรือสมัครบัญชีใหม่ ... หากลืมกรุณาติดต่อศูนย์ทันตสาธารณสุขระหว่างประเทศ"
        elif not check_password_hash(user['password'], password):
            error_msg = "รหัสผ่านไม่ถูกต้อง โปรดลองอีกครั้งหนึ่ง ... หากลืมกรุณากดเลือก ลืมรหัสผ่าน"
        if error_msg is None: # Logged in sucessfully
            session['user_id'] = user['id']
            load_logged_in_user()
            return redirect(url_for('image.history', role='dentist'))
        flash(error_msg)
        return render_template("dentist_login.html")

@bp.route('/logout')
def logout():
    if 'sender_mode' in session and session['sender_mode']=='dentist':
        session.clear()
        g.user = None
        return redirect(url_for('auth.dentist_index'))
    else:
        session.clear()
        g.user = None
        return redirect('/')

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            if 'sender_mode' in session and session['sender_mode']=='dentist':
                return redirect(url_for('auth.login', role='dentist'))
            elif 'sender_mode' in session and session['sender_mode']=='osm':
                return redirect(url_for('auth.login', role='osm'))
            else:
                return redirect(url_for('auth.login', role='patient'))
        return view(**kwargs)
    return wrapped_view