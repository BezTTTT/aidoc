from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, g
)
from werkzeug.security import check_password_hash

import bcrypt
import functools
import datetime

from aidoc.db import get_db

bp = Blueprint('auth', __name__)

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    elif 'g_user' not in session or session['g_user']['id'] != user_id:
        reload_user_profile(user_id)
    else:
        g.user = session['g_user']

def reload_user_profile(user_id):
    db, cursor = get_db()
    if 'login_mode' in session and session['login_mode']=='general':
        cursor.execute('SELECT * FROM general_user WHERE id = %s', (user_id,))
    else:
        cursor.execute('SELECT * FROM user WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    if user is None:
        session.pop('user_id', None)
    else:
        if 'login_mode' in session and session['login_mode']=='general':
            session['general_user'] = True
        else:

            job_position_dict = {"OSM":"อสม.", "Dental Nurse":"ทันตาภิบาล/เจ้าพนักงานทันตสาธารณสุข", "Dentist":"ทันตแพทย์",
                                    "Oral Pathologist": "ทันตแพทย์เฉพาะทาง วิทยาการวินิจฉัยโรคช่องปาก", "Oral and Maxillofacial Surgeon":"ทันตแพทย์เฉพาะทาง ศัลยศาสตร์ช่องปากและแม็กซิลโลเฟเชียล",
                                    "Physician":"แพทย์", "Public Health Technical Officer":"นักวิชาการสาธารณสุข", "Computer Technical Officer":"นักวิชาการคอมพิวเตอร์/นักวิจัย/ผู้พัฒนาระบบ",
                                    "Other Public Health Officer":"ข้าราชการ/เจ้าพนักงานกระทรวงสาธารณสุข", "Other Government Officer":"เจ้าหน้าที่รัฐอื่น", "General Public":"บุคคลทั่วไป"}
            if user['job_position'] in job_position_dict:
                user['job_position_th'] = job_position_dict[user['job_position']]
            else:
                user['job_position_th'] = user['job_position']

            if user['is_osm']: # check if the osm user is a osm_group member/supervisor
                
                # check and get osm group info for showing the osm group option on navbar
                group_info = load_osm_group_info_query(user['id'])
                user['group_info'] = group_info
                
    session['g_user'] = user
    g.user = session['g_user']

def load_osm_group_info_query(user_id):
    db, cursor = get_db()
    query = """
        SELECT 
            COALESCE(supervisor.is_supervisor, FALSE) AS is_supervisor,
            COALESCE(member.is_member, FALSE) AS is_member,
            ogm.group_id,
            og.group_name,
            CONCAT(su.name, ' ', su.surname) AS group_supervisor
        FROM osm_group_member ogm
        JOIN osm_group og ON og.group_id = ogm.group_id
        LEFT JOIN user su ON su.id = og.osm_supervisor_id
        LEFT JOIN (
            SELECT TRUE AS is_supervisor
            FROM osm_group 
            WHERE osm_supervisor_id = %s
            LIMIT 1
        ) supervisor ON TRUE
        LEFT JOIN (
            SELECT TRUE AS is_member
            FROM osm_group_member 
            WHERE osm_id = %s
            LIMIT 1
        ) member ON TRUE
        WHERE ogm.osm_id = %s;
    """
    cursor.execute(query, (user_id, user_id, user_id))
    group = cursor.fetchone()
    
    group_info = {
        "is_supervisor": group["is_supervisor"] if group else False,
        "is_member": group["is_member"] if group else False,
        "group_name": group["group_name"] if group else "",
        "group_id": group["group_id"] if group else -1,
        "group_supervisor": group["group_supervisor"] if group else ""
    }
    return group_info

@bp.route('/')
def index():
    if g.user is None:
        session.clear() # logged out from everything
        return render_template("patient_login.html") # default index page (patient and osm login)
    else: # if user is already logged in
        if 'login_mode' in session and session['login_mode']=='dentist':
            return redirect(url_for("webapp.record", role='dentist'))
        elif 'login_mode' in session and session['login_mode']=='osm':
            return redirect(url_for("webapp.record", role='osm'))
        else:
            return redirect(url_for("image.upload_image", role='patient'))

@bp.route('/dentist')
def dentist_index():
    if g.user is None:
        session.clear() # logged out from everything

    if g.user and ('login_mode' in session) and (session['login_mode']=='dentist'): # already logged in
        return redirect(url_for("webapp.record", role='dentist'))
    else:
        return render_template("dentist_login.html")

def role_validation(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        allowed_roles = ['patient', 'osm', 'dentist', 'specialist', 'admin']
        userNotInSession = (g.user is None) or ('is_patient' not in g.user) or ('login_mode' not in session)
        byPassValidation = ('register_later' in session)
        if ('role' not in kwargs) or \
            (kwargs['role'] not in allowed_roles) or \
            (userNotInSession) or \
            (kwargs['role']=='osm' and (g.user['is_osm']==0 or session['login_mode']!='osm') and not byPassValidation) or \
            (kwargs['role']=='patient' and (g.user['is_patient']==0 or session['login_mode']!='patient') and not byPassValidation) or \
            (kwargs['role']=='specialist' and (g.user['is_specialist']==0 or session['login_mode']!='dentist') and not byPassValidation) or \
            (kwargs['role']=='admin' and (g.user['is_admin']==0 or session['login_mode']!='dentist') and not byPassValidation) or \
            (kwargs['role']=='dentist' and (g.user['username'] is None or session['login_mode']!='dentist')) \
        :
            return render_template('unauthorized_access.html', error_msg='คุณไม่มีสิทธิ์เข้าถึงข้อมูล Unauthorized Access [role_validation]')
        return view(**kwargs)
    return wrapped_view

def admin_only(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None or g.user['is_admin']==0 or session['login_mode']!='dentist':
            return render_template('unauthorized_access.html', error_msg='คุณไม่มีสิทธิ์เข้าถึงข้อมูล Unauthorized Access [admin_only]')
        return view(**kwargs)
    return wrapped_view

def specialist_only(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None or g.user['is_specialist']==0 or session['login_mode']!='dentist':
            return render_template('unauthorized_access.html', error_msg='คุณไม่มีสิทธิ์เข้าถึงข้อมูล Unauthorized Access [specialist_only]')
        return view(**kwargs)
    return wrapped_view

@bp.route('/login/<role>', methods=('Post',))
def login(role):
    
    if role=='patient':
        national_id = request.form['national_id']
    
        db, cursor = get_db()
        cursor.execute(
            'SELECT * FROM user WHERE national_id = %s ORDER BY created_at DESC', (national_id,)
        )
        user = cursor.fetchall()
        # If match several accounts, the last created account will be selected.
        # The previous duplicated accounts are inactive and will later be merged and deleted by admin
        if len(user)>0:
            user = user[-1]
        else:
            user = None

        if user is None:
            error_msg = "กรุณาลงทะเบียน เลขประจำตัวประชาชนนี้ยังไม่ถูกลงทะเบียนในระบบ"
            session['national_id'] = national_id
            flash(error_msg)
            return redirect(url_for('user.register', role='patient'))
        elif user['is_patient']: # Logged in sucessfully
            session['user_id'] = user['id']
            log_last_user_login(user['id'])
            session['login_mode'] = 'patient'
            return redirect(url_for('image.upload_image', role='patient'))
        else: # Duplicate account found, ask for merging
            error_msg = "พบข้อมูลเบื้องต้นในระบบ แต่ท่านยังไม่ได้ถูกลงทะเบียนในฐานะคนไข้ กรุณาลงทะเบียนก่อน"
            #session['user_id'] = user['id']
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
            data["province"] = user["province"]
            if user["email"] is None:
                data["email"] = ''
            return render_template("patient_register.html", data=data)
    elif role=='osm':
        national_id = request.form['osm_national_id']
        phone = request.form['osm_phone']

        db, cursor = get_db()
        cursor.execute(
            'SELECT * FROM user WHERE national_id = %s OR phone = %s ORDER BY created_at DESC', (national_id, phone)
        )
        user = cursor.fetchall()
        # If match several accounts, the last created account will be selected.
        # The previous duplicated accounts are inactive and will later be merged and deleted by admin
        if len(user)>0:
            user = user[-1]
        else:
            user = None

        if user is None:
            error_msg = "ไม่พบข้อมูลของผู้ตรวจคัดกรองในระบบ หากยังไม่ได้ลงทะเบียน กรุณาลงทะเบียนก่อนการใช้งาน"
            session['national_id'] = national_id
            session['phone'] = phone
            session['sender'] = 'osm'
            flash(error_msg)
            return render_template("patient_login.html")
        elif user['is_osm'] and national_id==user['national_id'] and phone!=user['phone']: # incorrect login
            error_msg = "ท่านกรอกข้อมูลผิด กรุณากรอกข้อมูลให้ถูกต้อง หากปัญหานี้ยังคงอยู่ ขอให้ติดต่อผู้ดูแลระบบ"
            session['national_id'] = national_id
            session['phone'] = phone
            session['sender'] = 'osm'
            flash(error_msg)
            return render_template("patient_login.html")
        elif user['is_osm'] and national_id==user['national_id'] and phone==user['phone']: # osm logged in successfully
            # Logged in sucessfully
            session['user_id'] = user['id']
            log_last_user_login(user['id'])
            session['login_mode'] = 'osm'
            return redirect('/')
        else:
            error_msg = "พบข้อมูลเบื้องต้นของท่านในระบบ แต่ท่านยังไม่ได้ถูกลงทะเบียนในฐานะผู้ตรวจคัดกรอง กรุณาลงทะเบียนก่อน"
            flash(error_msg)
            #session['user_id'] = user['id'] # Mark that this user as duplicated user
            data = {} # data to populate the osm register page (with the already registered user)
            data["name"] = user["name"]
            data["surname"] = user["surname"]
            if user["national_id"]:
                data["national_id"] = user["national_id"]
            else:
                data["national_id"] = ""
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
            'SELECT * FROM user WHERE username = %s ORDER BY created_at DESC', (username,)
        )
        user = cursor.fetchall()
        # If match several accounts, the last created account will be selected.
        # The previous duplicated accounts are inactive and will later be merged and deleted by admin
        if len(user)>0:
            user = user[-1]
        else:
            user = None


        if user is None:
            error_msg = "ไม่พบรหัสผู้ใช้ โปรดลองอีกครั้งหนึ่งหรือสมัครบัญชีใหม่ ... หากลืมกรุณาติดต่อศูนย์ทันตสาธารณสุขระหว่างประเทศ"
        elif check_old_password(password, user['password']):
            data = {}
            data["name"] = user["name"] if user["name"] is not None else ""
            data["surname"] = user["surname"] if user["surname"] is not None else ""
            data["job_position"] = user["job_position"] if user["job_position"] is not None else ""
            data["osm_job"] = user["osm_job"] if user["osm_job"] is not None else ""
            data["license"] = user["license"] if user["license"] is not None else ""
            data["hospital"] = user["hospital"] if user["hospital"] is not None else ""
            data["province"] = user["province"] if user["province"] is not None else ""
            data["email"] = user["email"] if user["email"] is not None else ""
            data["username"] = user["username"] if user["username"] is not None else ""
            data["password"] = user["password"] if user["password"] is not None else ""
            data["phone"] = user["phone"] if user["phone"] is not None else ""
            data["old_username"] = user["username"] if user["username"] is not None else ""

            data["valid_password"] = True
            data["valid_username"] = True
            data["valid_phone"] = True
            data["valid_name_surname"] = True
            data["valid_province_name"] = True

            data["national_id"] = None
            return render_template('/newTemplate/old_user_update.html', data=data)
        elif not check_current_password(password, user['password']):
            error_msg = "รหัสผ่านไม่ถูกต้อง โปรดลองอีกครั้งหนึ่ง ... หากลืมรหัสผ่าน กรุณากดเลือก ลืมรหัสผ่าน"
        if error_msg is None: # Logged in sucessfully
            session['user_id'] = user['id']
            log_last_user_login(user['id'])
            session['login_mode'] = 'dentist'
            return redirect(url_for('webapp.record', role='dentist'))
        flash(error_msg)
        return render_template("dentist_login.html")

def check_old_password(password, user_password):
    try:
        password_bytes = bytes(password, "ascii")
        stored_password_bytes = bytes(user_password, "ascii")
        return bcrypt.checkpw(password_bytes, stored_password_bytes)
    except Exception as e:
        return False
def check_current_password(password, user_password):
    try:
        return check_password_hash(user_password, password)
    except Exception as e:
        return False
def log_last_user_login(user_id):
    # Log last_login to the user
    db, cursor = get_db()
    sql = "UPDATE user SET last_login = NOW() WHERE id = %s"
    cursor.execute(sql, (user_id,))

@bp.route('/logout')
def logout():
    if 'login_mode' in session and session['login_mode']=='general':
        session.clear()
        g.pop('user', None)
        return redirect('/general')
    elif 'login_mode' in session and session['login_mode']=='dentist':
        session.clear()
        g.pop('user', None)
        return redirect(url_for('auth.dentist_index'))
    else:
        session.clear()
        g.pop('user', None)
        return redirect('/')

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            if 'login_mode' in session:
                if session['login_mode'] in ['dentist', 'osm', 'specialist', 'admin']:
                    return redirect(url_for('auth.dentist_index'))
                elif session['login_mode']=='general':
                    return redirect('/general')
            return redirect('/')
        return view(**kwargs)
    return wrapped_view