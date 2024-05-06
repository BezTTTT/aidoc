from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

import functools
import mysql.connector
import datetime
import re

from aidoc.db import get_db

bp = Blueprint('patient_auth', __name__)

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
        g.user = cursor.fetchone()

# Patient login page is the same as index page
@bp.route('/', methods=('GET', 'POST'))
def index():
    if request.method == 'POST':
        session.clear()
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
            return redirect(url_for('patient_auth.register'))
        else:
            session['user_id'] = user['id']
            return redirect(url_for('index'))

    return render_template("patient/index.html")

@bp.route('/register', methods=('GET', 'POST'))
def register():
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
        data["job"] = request.form["job"]
        data["province"] = request.form["province"]
        data['address'] = request.form['address']


        data["valid_national_id"] = True
        data["valid_phone"] = True
        
        # this section validate the input data, if fails, redirect back to the form

        # Validation 1: National ID must follow the CheckSum rule (disable if international)
        # Validation 2: National ID and Retyped National ID must match
        if (data["national_id"] and not validate_national_id(data["national_id"]) or
            (data["national_id"] != request.form["cnational_id"])
        ):
            error_msg = "กรุณากรอกรหัสบัตรประชาชนให้ถูกต้อง"
            data["national_id"] = None
            data["valid_national_id"] = False
            flash(error_msg)
            return (render_template("patient/register.html", data=data))
        
        # Validation 3: Number number must follow the 9-10 digits rule (disable if international)
        if ( data["phone"] and not validate_phone(data["phone"])
        ):
            error_msg = "กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง"
            data["phone"] =  None
            data["valid_phone"] = False
            flash(error_msg)
            return (render_template("patient/register.html", data=data))

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

        # Insert to Database
        db, cursor = get_db()
        sql = "INSERT INTO user (name, surname, national_id, email, phone, sex, birthdate, job, province, address, is_patient) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        val = (
            data["name"],
            data["surname"],
            data["national_id"],
            data["email"],
            data["phone"],
            data["sex"],
            dob_obj,
            data["job"],
            data["province"],
            data['address'],
            True
        )
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

    return render_template("patient/register.html", data=data)

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
