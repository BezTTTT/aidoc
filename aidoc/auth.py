from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

import functools
import datetime
import re

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
        session.clear()

    if 'sender_mode' in session and session['sender_mode']=='dentist':
        if g.user:
            return redirect(url_for("image.dentist_history"))
        else:
            return render_template("dentist_login.html")
    else:
        if g.user:
            return render_template("patient_upload.html")
        else:
            return render_template("patient_login.html")

@bp.route('/login/patient', methods=('Post', ))
def patient_login():
    session['sender_mode'] = 'patient'
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
        return redirect(url_for('auth.patient_register'))
    elif user['is_patient']:
        # Logged in sucessfully
        session['user_id'] = user['id']
        load_logged_in_user()
        return redirect(url_for('image.upload_image', role='patient'))
    else:
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

@bp.route('/register/patient', methods=('GET', 'POST'))
def patient_register():
    data = {} # a data container to store submitted values from the form
    data['current_year'] = datetime.date.today().year # set the current Thai Year to the global variable
    session['sender_mode'] = 'patient'
    if request.method == 'POST':
        # This section extract the submitted form to 
        prefixList = ["นาย ", "นาง ", "นางสาว ", "น.ส.", "น.", "นส."]
        #data["name"] = remove_prefix(request.form["name"], prefixList)
        data["name"] = request.form["name"]
        data["surname"] = request.form["surname"]
        data["national_id"] = request.form["national_id"]
        data["email"] = request.form["email"]
        data["phone"] = request.form["phone"]
        data['sex'] = request.form['sex']
        data['dob_day'] = request.form["dob_day"]
        data["dob_month"] = request.form["dob_month"]
        data["dob_year"] = request.form["dob_year"]
        data["job_position"] = request.form["job_position"]
        data["province"] = request.form["province"]
        data['address'] = request.form['address']

        data["valid_national_id"] = True
        data["valid_phone"] = True
        
        # this section validate the input data, if fails, redirect back to the form

        # Validation 1: National ID must follow the CheckSum rule (disable if international) [DISABLE in TEST]
        # Validation 2: National ID and Retyped National ID must match
        #if (data["national_id"] and not validate_national_id(data["national_id"]) or
        if (data["national_id"] != request.form["cfnational_id"]
        ):
            error_msg = "กรุณากรอกรหัสบัตรประชาชนให้ถูกต้อง"
            data["national_id"] = None
            data["valid_national_id"] = False
            flash(error_msg)
            return (render_template("patient_register.html", data=data))
        
        # Validation 3: Number number must follow the 9-10 digits rule (disable if international)
        if ( data["phone"] and not validate_phone(data["phone"])
        ):
            error_msg = "กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง"
            data["phone"] =  None
            data["valid_phone"] = False
            flash(error_msg)
            return (render_template("patient_register.html", data=data))

        '''
        #Check license duplicate in patient and user
        check_patient_license = check_if_duplicate(data,"license","patients")
        check_user_license = check_if_duplicate(data,"license","users")
        if check_patient_license == True or check_user_license== True:
            data["status"] ,data["userId"],data['error'],data["licenseInvalid"] =  "รหัสบัตรประชาชนนี้ถูกใช้ไปแล้วกรุณาใช้รหัสบัตรประชาชนอื่น",None,True,True
            return ( render_template("patients/register.html",data=data,),200,)
        '''
        
        #Change Thai era year to Common Era
        data['dob_year'] = str(int(data['dob_year']) - 543)
        #Save Date of Birth
        dob = data['dob_year'] + "-" + data['dob_month'] + "-" + data['dob_day']
        dob_obj = datetime.datetime.strptime(dob, "%Y-%m-%d")

        # Pack data for SQL query
        val = (
            data["name"],
            data["surname"],
            data["national_id"],
            data["email"],
            data["phone"],
            data["sex"],
            dob_obj,
            data["job_position"],
            data["province"],
            data['address'],
            True
        )

        db, cursor = get_db()
        if session.get('user_id'): # Check if the user is already registered (checked by auth.osm_login)
            sql = "UPDATE user SET name=%s, surname=%s, national_id=%s, email=%s, phone=%s, sex=%s, birthdate=%s, job_position=%s, province=%s, address=%s, is_patient=%s WHERE id=%s"
            val = val + (session['user_id'], )
            cursor.execute(sql, val)
        else:
            sql = "INSERT INTO user (name, surname, national_id, email, phone, sex, birthdate, job_position, province, address, is_patient) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            cursor.execute(sql, val)
            
            # Load the newly registered user to the session
            db, cursor = get_db()
            cursor.execute('SELECT id FROM user where national_id = %s', (data["national_id"],))
            new_user = cursor.fetchone()
            session['user_id'] = new_user['id']
            load_logged_in_user()
        
        # session['national_id'] is used to carry out id from login to register
        # After the registration is complete, this (sensitive) variable should be deleted
        if 'national_id' in session:  
            session.pop('national_id',None)  
            
        return redirect(url_for("index"))

    return render_template("patient_register.html", data=data)

@bp.route('/login/osm', methods=('Post', ))
def osm_login():
        
    session['sender_mode'] = 'osm'
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
        return redirect(url_for('auth.osm_register'))
    elif user['is_osm'] and national_id==user['national_id'] and phone==user['phone']: # osm logged in successfully
        # Logged in sucessfully
        session['user_id'] = user['id']
        load_logged_in_user()
        return redirect(url_for('index'))
    else:
        error_msg = "พบข้อมูลเบื้องต้นของท่านในระบบ แต่ท่านยังไม่ได้ถูกลงทะเบียนในฐานะผู้ตรวจคัดกรอง กรุณาลงทะเบียนก่อน"
        flash(error_msg)
        session['user_id'] = user['id'] # Mark that this user is already in the database

        data = {} # data to populate the osm register page (with the already registered user)
        data["name"] = user["name"]
        data["surname"] = user["surname"]
        data["national_id"] = user["national_id"]
        data["email"] = user["email"]
        data["phone"] = user["phone"]
        data["province"] = user["province"]
        return render_template("osm_register.html", data=data)

@bp.route('/register/osm', methods=('GET', 'POST'))
def osm_register():
    data = {} # a data container to store submitted values from the form
    session['sender_mode'] = 'osm'
    if request.method == 'POST':
        # This section extract the submitted form to 
        prefixList = ["นาย ", "นาง ", "นางสาว ", "น.ส.", "น.", "นส."]
        #data["name"] = remove_prefix(request.form["name"], prefixList)
        data["name"] = request.form["name"]
        data["surname"] = request.form["surname"]
        data["job_position"] = request.form["job_position"]
        data["osm_job"] = request.form["osm_job"]
        data["license"] = request.form["license"]
        data["hospital"] = request.form["hospital"]
        data["province"] = request.form["province"]
        data["national_id"] = request.form["national_id"]
        data["phone"] = request.form["phone"]

        data["valid_national_id"] = True
        data["valid_phone"] = True
        
        # this section validate the input data, if fails, redirect back to the form

        # Validation 1: National ID must follow the CheckSum rule (disable if international) [DISABLE in TEST]
        '''
        if (data["national_id"] and not validate_national_id(data["national_id"])
        ):
            error_msg = "กรุณากรอกรหัสบัตรประชาชนให้ถูกต้อง"
            data["national_id"] = None
            data["valid_national_id"] = False
            flash(error_msg)
            return (render_template("osm_register.html", data=data))
        '''

        # Validation 2: Number number must follow the 9-10 digits rule (disable if international)
        if ( data["phone"] and not validate_phone(data["phone"])
        ):
            error_msg = "กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง"
            data["phone"] =  None
            data["valid_phone"] = False
            flash(error_msg)
            return (render_template("osm_register.html", data=data))

        '''
        #Check license duplicate in patient and user
        check_patient_license = check_if_duplicate(data,"license","patients")
        check_user_license = check_if_duplicate(data,"license","users")
        if check_patient_license == True or check_user_license== True:
            data["status"] ,data["userId"],data['error'],data["licenseInvalid"] =  "รหัสบัตรประชาชนนี้ถูกใช้ไปแล้วกรุณาใช้รหัสบัตรประชาชนอื่น",None,True,True
            return ( render_template("patients/register.html",data=data,),200,)
        '''

        # Pack data for SQL query
        val = (
                data["name"],
                data["surname"],
                data["national_id"],
                data["phone"],
                data["job_position"],
                data["osm_job"],
                data["province"],
                data["license"],
                True
            )

        db, cursor = get_db()
        if session.get('user_id'): # Check if the user is already registered (checked by auth.osm_login)
            sql = "UPDATE user SET name=%s, surname=%s, national_id=%s, phone=%s, job_position=%s, osm_job=%s, province=%s, license=%s, is_osm=%s WHERE id=%s"
            val = val + (session['user_id'],)
            cursor.execute(sql, val)
        else:
            sql = "INSERT INTO user (name, surname, national_id, phone, job_position, osm_job, province, license, is_osm) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            cursor.execute(sql, val)

             # Load the newly registered user to the session
            # db, cursor = get_db()
            cursor.execute('SELECT id FROM user WHERE national_id=%s AND is_osm=TRUE', (data["national_id"],))
            new_user = cursor.fetchone()
            session['user_id'] = new_user['id']
            load_logged_in_user()       
        
        # Flag to refresh db_query for history page
        if 'need_db_refresh' in session:
            session['need_db_refresh']=True

        # session['national_id'] is used to carry out id from login to register
        # After the registration is complete, this (sensitive) variable should be deleted
        if 'national_id' in session:  
            session.pop('national_id',None) 
            session.pop('phone',None)  
            
        return redirect(url_for("index"))

    return render_template("osm_register.html", data=data)

@bp.route('/dentist', methods=('GET', 'POST'))
@bp.route('/login/dentist', methods=('GET', 'POST'))
def dentist_login():

    session['sender_mode'] = 'dentist'
    if request.method == 'POST':
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
        if error_msg is None:
            # Logged in sucessfully
            session['user_id'] = user['id']
            load_logged_in_user()
            return redirect(url_for('image.dentist_history'))
        flash(error_msg)
    if g.user:
        return redirect(url_for('image.dentist_history'))
    else:
        return render_template("dentist_login.html")

@bp.route('/register/dentist', methods=('GET', 'POST'))
def dentist_register():
    data = {} # a data container to store submitted values from the form
    session['sender_mode'] = 'dentist'
    if request.method == 'POST':
        # This section extract the submitted form to 
        prefixList = ["นาย ", "นาง ", "นางสาว ", "น.ส.", "น.", "นส."]
        #data["name"] = remove_prefix(request.form["name"], prefixList)
        data["name"] = request.form["name"]
        data["surname"] = request.form["surname"]
        data["job_position"] = request.form["job_position"]
        data["osm_job"] = request.form["osm_job"]
        data["license"] = request.form["license"]
        data["hospital"] = request.form["hospital"]
        data["province"] = request.form["province"]
        data["email"] = request.form["email"]
        data["username"] = request.form["username"]
        data["password"] = request.form["password"]
        data["phone"] = request.form["phone"]

        data["valid_password"] = True
        data["valid_username"] = True
        
        # this section validate the input data, if fails, redirect back to the form

        # Validation 1: Password must matched confirmed password
        if (data["password"] != request.form["cfpassword"]):
            error_msg = "กรุณากรอกรหัสผ่านให้ตรงกันทั้งสองครั้ง"
            data["password"] = ""
            data["valid_password"] = False
            flash(error_msg)
            return (render_template("dentist_register.html", data=data))

        # Validation 2: Check if there is the username is already taken
        '''
        db, cursor = get_db()
        cursor.execute('SELECT id FROM user WHERE username=%s', (data["username"], ))
        duplicate_username = cursor.fetchall() # Result in list of dicts
        if len(duplicate_username)>0:
            error_msg = "รหัสผู้ใช้ (Username) นี้ มีผู้อื่นใช้ไปแล้ว กรุณาเลือกรหัสผู้ใช้ใหม่"
            data["username"] = ""
            data["valid_username"] = False
            flash(error_msg)
            return (render_template("dentist_register.html", data=data))
        '''

        # Validation 3: Check if there is a user with the same (name, surname) or email or phone
        if "create_new_account" not in request.form and "merge_account" not in request.form:
            db, cursor = get_db()
            cursor.execute('SELECT id, name, surname, email, phone, is_patient FROM user WHERE username IS NULL AND name=%s AND surname=%s AND phone=%s',
                        (data["name"], data["surname"], data["phone"]))
            duplicate_user = cursor.fetchall() # Result in list of dicts
            if len(duplicate_user)>0:
                duplicate_user = duplicate_user[0] # Select only the first matched user
                if duplicate_user['is_patient']:
                    error_msg = "ตรวจพบข้อมูลของท่านใน [ระบบประชาชน] ... ท่านต้องการรวมบัญชีหรือไม่? กดปุ่มสีเขียวเพื่อรวมบัญชี กดปุ่มสีเหลืองเพื่อสร้างบัญชีใหม่แยก"
                else:
                    error_msg = "ตรวจพบข้อมูลของท่านใน [ระบบเจ้าหน้าที่ผู้ตรวจคัดกรอง] ... ท่านต้องการรวมบัญชีหรือไม่? กดปุ่มสีเขียวเพื่อรวมบัญชี กดปุ่มสีเหลืองเพื่อสร้างบัญชีใหม่แยก"
                error_msg += f" [ ข้อมูลซ้ำ: คุณ {duplicate_user['name']} {duplicate_user['surname']} ]"
                flash(error_msg)
                data["dublicate_flag"] = True
                session['user_id'] = duplicate_user['id']
                return (render_template("dentist_register.html", data=data))

        '''
        #Check license duplicate in patient and user
        check_patient_license = check_if_duplicate(data,"license","patients")
        check_user_license = check_if_duplicate(data,"license","users")
        if check_patient_license == True or check_user_license== True:
            data["status"] ,data["userId"],data['error'],data["licenseInvalid"] =  "รหัสบัตรประชาชนนี้ถูกใช้ไปแล้วกรุณาใช้รหัสบัตรประชาชนอื่น",None,True,True
            return ( render_template("patients/register.html",data=data,),200,)
        '''
        data["name"] = request.form["name"]
        data["surname"] = request.form["surname"]
        data["job_position"] = request.form["job_position"]
        data["osm_job"] = request.form["osm_job"]
        data["license"] = request.form["license"]
        data["hospital"] = request.form["hospital"]
        data["province"] = request.form["province"]
        data["email"] = request.form["email"]
        data["username"] = request.form["username"]
        data["password"] = request.form["password"]
        data["phone"] = request.form["phone"]

        # Pack data for SQL query
        val = (
                data["name"],
                data["surname"],
                data["email"],
                data["phone"],
                data["username"],
                generate_password_hash(data["password"]),
                data["job_position"],
                data["osm_job"],
                data["hospital"],
                data["province"],
                data["license"]
            )
        db, cursor = get_db()
        if request.form.get("merge_account"): # Check if the user is already registered (checked by auth.osm_login)
            sql = "UPDATE user SET name=%s, surname=%s, email=%s, phone=%s, username=%s, password=%s, job_position=%s, osm_job=%s, hospital=%s, province=%s, license=%s WHERE id=%s"
            val = val + (session['user_id'],)
            cursor.execute(sql, val)
        else:
            sql = "INSERT INTO user (name, surname, email, phone, username, password, job_position, osm_job, hospital, province, license) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            cursor.execute(sql, val)

             # Load the newly registered user to the session
            # db, cursor = get_db()
            cursor.execute('SELECT id FROM user WHERE username=%s', (data["username"],))
            new_user = cursor.fetchone()
            session['user_id'] = new_user['id']
            load_logged_in_user()
        
        # Flag to refresh db_query for history page
        if 'need_db_refresh' in session:
            session['need_db_refresh']=True
            
        # session['national_id'] is used to carry out id from login to register
        # After the registration is complete, this (sensitive) variable should be deleted
        if 'national_id' in session:  
            session.pop('national_id',None) 
            session.pop('phone',None)  
            
        return redirect(url_for('image.dentist_history'))

    return render_template("dentist_register.html", data=data)

@bp.route('/logout')
def logout():
    if 'sender_mode' in session and session['sender_mode']=='dentist':
        session.clear()
        g.user = None
        return redirect(url_for('dentist'))
    else:
        session.clear()
        g.user = None
        return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            if 'sender_mode' in session and session['sender_mode']=='dentist':
                return redirect(url_for('auth.dentist_login'))
            else:
                return redirect(url_for('auth.patient_login'))
        return view(**kwargs)
    return wrapped_view

# Helper functions

def remove_prefix(input_str, prefixes):
    for prefix in prefixes:
        if input_str.startswith(prefix):
            return input_str[len(prefix):].strip()
    return input_str

def validate_national_id(national_id):
    # Define national id pattern
    digit13_pattern = r'^\d{13}$'

    # Convert the ID string to a list of integers
    digits = [int(digit) for digit in national_id]
    last_digit = digits[-1]
    # Calculate the weighted sum using list comprehension
    weighted_sum = sum(digit * (13 - i) for i, digit in enumerate(digits[:-1]))
    check_digit = (11- (weighted_sum%11))%10
    check_sum = (check_digit == last_digit)
    return (re.match(digit13_pattern, national_id) is not None) and check_sum

def validate_phone(phone_number):
    phone_pattern = r'^\d{9,10}$'
    return re.match(phone_pattern, phone_number) is not None
