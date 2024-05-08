from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

import functools
import mysql.connector
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
        cursor.execute(
            'SELECT * FROM user WHERE id = %s', (user_id,)
        )
        user = cursor.fetchone()
        if user is None:
            session.clear()
        else:
            g.user = user

@bp.route('/')
def index():
    return render_template("patient_login.html")

@bp.route('/login/patient', methods=('Post', ))
def patient_login():
    session.clear()
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
        session['user_id'] = user['id']
        return redirect(url_for('index'))
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
        
    session.clear()
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
        session['user_id'] = user['id']
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
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('dentist'))
        
        flash(error_msg)

    return render_template("dentist_login.html")

@bp.route('/register/dentist', methods=('GET', 'POST'))
def dentist_register():
    data = {} # a data container to store submitted values from the form
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
        if request.form.get("create_new_account") is None and request.form.get("merge_account") is None:
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
        # session['national_id'] is used to carry out id from login to register
        # After the registration is complete, this (sensitive) variable should be deleted
        if 'national_id' in session:  
            session.pop('national_id',None) 
            session.pop('phone',None)  
            
        return redirect(url_for("dentist"))

    return render_template("dentist_register.html", data=data)

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
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

'''
def check_if_duplicate(data,attribute,table):
    # Check if exists Email
    sql = "SELECT "+attribute+" FROM "+table+";"
    mycursor.execute(sql)
    all_data = mycursor.fetchall()
    mydb.commit()
    lst_all = []
    for i in range(len(all_data)):
        lst_all.append(list(all_data[i].values())[0])
    
    if data[attribute] in lst_all:
        return True
'''

'''
@bp.route("/patient", methods=["GET"])
def patients_login_page():
    try:
        
        # data = get_cookies()
        data = get_cookies()
        mydb.reconnect(attempts=1, delay=0)  # reconnect to database if timeout
        data['page'] = "patient"
        print("trigger login page patient")
        if(data['role']!='patient' and request.cookies.get('role')!=None):
            #clear cookie
            
            respond = make_response(redirect(url_for("patients_auth_blueprint.patients_login_page")))
            respond.set_cookie("userID", "", expires=0)
            respond.set_cookie("username", "", expires=0)
            respond.set_cookie("usersurname", "", expires=0)
            respond.set_cookie("role", "", expires=0)
            respond.set_cookie("work", "", expires=0)
            
            return respond
        return render_template("patients/login.html", data=data), 200
    except Exception as e:
        traceback.print_exc()
        print(e)
        push_log(str(e)) # push error on logs file
        return render_template("patients/login.html", data={"userId": None}), 200


@patients_auth_blueprint.route("/patient", methods=["POST"])
def patient_login_post():
    mydb.reconnect(attempts=1, delay=0)  # reconnect to database if timeout
    if request.method == "POST":
        licenseId = request.form["license"]
        current_year = int(datetime.datetime.now().year) +543 #Thai Year

        if licenseId == "" :
            return (
                render_template(
                    "/patients/login.html",
                    data={
                        "status": "กรุณาใส่รหัสประจำตัวประชาชน",
                        "userId": None,
                        "error": True,
                        "page": 'patient',
                    },
                ),
                200,
            )
        elif len(licenseId) != 13 :
            return (
                render_template(
                    "/patients/login.html",
                    data={
                        "status": "กรุณาใส่รหัสประจำตัวประชาชนให้ครบ13หลัก",
                        "userId": None,
                        "error": True,
                        "page": 'patient',
                    },
                ),
                200,
            )



        sql = "SELECT * FROM patients WHERE license = %s" #Login by Patients license
        val = (licenseId,)
        mycursor.execute(sql, val)
        patient_license_res = mycursor.fetchall()


        #Check username or email to login and check if does not have username in out database
        if len(patient_license_res) != 0:
            res = patient_license_res
        else:
            return (
                render_template(
                    "/patients/register.html",
                    data={
                        "status": "กรุณาลงทะเบียน เลขบัตรประจำตัวประชาชนของท่านยังไม่ถูกลงทะเบียนในระบบ",
                        "userId": None,
                        "error": True,
                        "page": 'patient',
                        "current_year":current_year,
                        "license":licenseId,
                    },
                ),
                200,
            )

        try:
            res = res[0]  # get json
            print(res)

            #Check return role user or patient
            print("Role",res['role'])
            if res['role'] == "user" or res['role'] == "admin":
                respond = make_response(redirect("/history"))
            elif res['role'] == "patient":
                respond = make_response(redirect("/main"))
                
            expire_date = datetime.datetime.now()
            expire_date = expire_date + datetime.timedelta(days=0.2)

            respond.set_cookie("userID", str(res["id"]), expires=expire_date)
            respond.set_cookie("username", res["fullname"], expires=expire_date)
            respond.set_cookie("role", res["role"], expires=expire_date)
            respond.set_cookie("work",res["work"], expires=expire_date) 
            # add log
            try:
                add_login_log(
                    res["id"], res["name"] + " " + res["surname"], res["role"], "login"
                )
            except:
                add_login_log(
                    res["id"], res['fullname'], res["role"], "login"
                )
            
            client_ip = request.remote_addr
            user_agent = request.headers.get('User-Agent', 'N/A')
            print("user_agent : ", user_agent)
            print("client_ip : ", client_ip)
            # Counting user login
            print("User : ", res['fullname'], " Login Succes!!!")  # print(username who login)
            push_log("User : "+str(res['fullname'])+" Login Succes!!!")
            # global user_login_count
            # user_login_count += 1
            # print("Now Login Users = ", user_login_count)
            return respond

        except Exception as e:
            traceback.print_exc()
            print(e)
            push_log(str(e)) # push error on logs file
            return (
                render_template(
                    "patients/login.html",
                    data={
                        "status": "Can not connect to database. Please try again after.",
                        "userId": None,
                        "error": True,
                    },
                ),
                200,
            )
    return render_template("patients/login.html", data={"userId": None}), 200




'''
