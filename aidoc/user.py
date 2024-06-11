from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, jsonify
)
from werkzeug.security import generate_password_hash

import datetime
import re

from aidoc.db import get_db
from aidoc.auth import login_required
from aidoc.auth import load_logged_in_user

# 'user' blueprint manages user management system
bp = Blueprint('user', __name__)

@login_required
@bp.route("/find_sender", methods=["POST"])
def find_sender():
    #get phone num
    phone_number = request.form.get('phone_number')
    db, cursor = get_db()
    cursor.execute("SELECT id, name, surname FROM user WHERE phone = %s AND is_osm = 1", (phone_number,))
    senderInfo = cursor.fetchone()

    if(senderInfo is not None):
        return jsonify({
            'name': senderInfo['name'],
            'surname': senderInfo['surname'],
            'sender_id': senderInfo['id']
        }), 200
    else:
        return jsonify({}), 404

@bp.route('/register/<role>', methods=('GET', 'POST'))
def register(role):
    data = {}
    session['sender_mode'] = role
    if role=='patient':
        target_template = "patient_register.html"
        data['current_year'] = datetime.date.today().year # set the current Thai Year to the global variable
        if request.method == 'POST':
            # This section extract the submitted form to 
            data["name"] = remove_prefix(request.form["name"])
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
            data["valid_province_name"] = True
    
            # this section validate the input data, if fails, redirect back to the form
            # If the validation fails, automatically redirect to the target template
            duplicate_users = []
            valid_func_list = [validate_national_id,
                               validate_province_name,
                               validate_duplicate_users,
                               validate_duplicate_phone,
                               validate_duplicate_national_id]
            for valid_func in valid_func_list:
                args = {'data': data, 'form': request.form, 'duplicate_users': duplicate_users}
                valid_check, data, duplicate_users = valid_func(args)
                if not valid_check:
                    return render_template(target_template, data=data)

            #Change Thai Buddhist Era to Common Era
            data['dob_year'] = str(int(data['dob_year']) - 543)
            #Save Date of Birth
            dob = data['dob_year'] + "-" + data['dob_month'] + "-" + data['dob_day']
            dob_obj = datetime.datetime.strptime(dob, "%Y-%m-%d")

            if data["email"]=='':
                data["email"] = None
            if data["phone"]=='':
                data["phone"] = None

            # Create new account if there is no duplicate account, else merge the accounts
            db, cursor = get_db()
            if 'user_id' not in session or request.form.get('create_new_account'): # new account or user confirms that the duplicate account is not theirs
                sql = "INSERT INTO user (name, surname, national_id, email, phone, sex, birthdate, job_position, province, address, is_patient) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                val = (data["name"], data["surname"], data["national_id"], data["email"], data["phone"], data["sex"], dob_obj, data["job_position"], data["province"], data['address'], True)
                cursor.execute(sql, val)

                # Load the newly registered user to the session (using national_id and is_patient flag)
                cursor.execute('SELECT id FROM user where national_id = %s AND is_patient=TRUE', (data["national_id"],))
                new_user = cursor.fetchone()
                session['user_id'] = new_user['id']
                load_logged_in_user()

            else: # Merge account
                sql = "UPDATE user SET name=%s, surname=%s, national_id=%s, email=%s, phone=%s, sex=%s, birthdate=%s,  province=%s, address=%s, is_patient=%s WHERE id=%s"
                val = (data["name"], data["surname"], data["national_id"], data["email"], data["phone"], data["sex"], dob_obj, data["province"], data['address'], True, session['user_id'])
                cursor.execute(sql, val)

            # session['national_id'] is used to carry out id from login to register
            # After the registration is complete, this (sensitive) variable should be deleted
            if 'national_id' in session:  
                session.pop('national_id',None)  
                
            return redirect(url_for('image.upload_image', role='patient'))
        else:
            return render_template(target_template, data=data)
    elif role=='osm':
        target_template = "osm_register.html"
        if request.method == 'POST':
            # This section extract the submitted form to 
            data["name"] = remove_prefix(request.form["name"])
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
            data["valid_province_name"] = True

            # this section validate the input data, if fails, redirect back to the form
            duplicate_users = []
            valid_func_list = [validate_national_id,
                               validate_phone,
                               validate_province_name,
                               validate_duplicate_users,
                               validate_duplicate_phone,
                               validate_duplicate_national_id]
            for valid_func in valid_func_list:
                args = {'data': data, 'form': request.form, 'duplicate_users': duplicate_users}
                valid_check, data, duplicate_users = valid_func(args)
                if not valid_check:
                    return render_template(target_template, data=data)

            if data["osm_job"] == '':
                data["osm_job"] = None
            if data["license"] == '':
                data["license"] = None

            # Create new account if there is no duplicate account, else merge the accounts
            db, cursor = get_db()
            if 'user_id' not in session or request.form.get('create_new_account'): # new account or user confirms that the duplicate account is not theirs
                sql = "INSERT INTO user (name, surname, national_id, phone, job_position, osm_job, hospital, province, license, is_osm) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                val = (data["name"], data["surname"], data["national_id"], data["phone"], data["job_position"], data["osm_job"], data["hospital"], data["province"], data["license"], True)
                cursor.execute(sql, val)

                # Load the newly registered user to the session (using national_id and phone and is_osm flag)
                cursor.execute('SELECT id FROM user WHERE national_id=%s AND phone=%s AND is_osm=TRUE', (data["national_id"], data["phone"]))
                new_user = cursor.fetchone()
                session['user_id'] = new_user['id']
                load_logged_in_user()     
                
            else: # merge account
                sql = "UPDATE user SET name=%s, surname=%s, national_id=%s, phone=%s, osm_job=%s, hospital=%s, province=%s, license=%s, is_osm=%s WHERE id=%s"
                val = (data["name"], data["surname"], data["national_id"], data["phone"], data["osm_job"], data["hospital"], data["province"], data["license"], True, session['user_id'])
                cursor.execute(sql, val)                  
            
            # Flag to refresh db_query for record page
            if 'need_db_refresh' in session:
                session['need_db_refresh']=True
                
            return redirect('/')
        else:
            return render_template(target_template, data=data)
    elif role=='dentist':
        target_template = "dentist_register.html"
        if request.method == 'POST':
            # This section extract the submitted form to 
            data["name"] = remove_prefix(request.form["name"])
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
            data["valid_province_name"] = True

            # this section validate the input data, if fails, redirect back to the form
            duplicate_users = []
            valid_func_list = [validate_cf_password,
                               validate_username,
                               validate_province_name,
                               validate_duplicate_users,
                               validate_duplicate_phone]
            for valid_func in valid_func_list:
                args = {'data': data, 'form': request.form, 'duplicate_users': duplicate_users}
                valid_check, data, duplicate_users = valid_func(args)
                if not valid_check:
                    return render_template(target_template, data=data)

            if data["osm_job"] == '':
                data["osm_job"] = None
            if data["license"] == '':
                data["license"] = None
                
            # Create new account if there is no duplicate account, else merge the accounts
            db, cursor = get_db()
            if 'user_id' not in session or request.form.get('create_new_account'): # new account or user confirms that the duplicate account is not theirs
                sql = "INSERT INTO user (name, surname, email, phone, username, password, job_position, osm_job, hospital, province, license) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                val = (data["name"], data["surname"], data["email"], data["phone"], data["username"],generate_password_hash(data["password"]), data["job_position"], data["osm_job"], data["hospital"],data["province"], data["license"])
                cursor.execute(sql, val)

                # Load the newly registered user to the session (using username)
                cursor.execute('SELECT id FROM user WHERE username=%s', (data["username"],))
                new_user = cursor.fetchone()
                session['user_id'] = new_user['id']
                load_logged_in_user()    
                
            else:
                sql = "UPDATE user SET name=%s, surname=%s, email=%s, phone=%s, username=%s, password=%s, job_position=%s, osm_job=%s, hospital=%s, province=%s, license=%s WHERE id=%s"
                val = (data["name"], data["surname"], data["email"], data["phone"], data["username"],generate_password_hash(data["password"]), data["job_position"], data["osm_job"], data["hospital"],data["province"], data["license"], session['user_id'])
                cursor.execute(sql, val)

            # Flag to refresh db_query for record page
            if 'need_db_refresh' in session:
                session['need_db_refresh']=True
                
            return redirect(url_for('image.record', role='dentist'))
        else:
            return render_template(target_template, data=data)
    else:
        return redirect('/')

# Helper functions

def remove_prefix(input_str):
    prefixes = ["นาย", "นางสาว", "นาง", "น.ส.", "นส.", "น.",  "ทพญ.", "ทพ.", "ดร."]
    for prefix in prefixes:
        if input_str.startswith(prefix):
            return input_str[len(prefix):].strip()
    return input_str

# National ID validation: National ID must follow the CheckSum rule (disable if international)
# if given, cfnational_id must match national_id (inputs on the form)
def validate_national_id(args):
    data = args['data']
    form = args['form']
    # National ID Checksum
    # Define national id pattern
    digit13_pattern = r'^\d{13}$'
    # Convert the ID string to a list of integers
    digits = [int(digit) for digit in data["national_id"]]
    last_digit = digits[-1]
    # Calculate the weighted sum using list comprehension
    weighted_sum = sum(digit * (13 - i) for i, digit in enumerate(digits[:-1]))
    check_digit = (11- (weighted_sum%11))%10
    check_sum = (check_digit == last_digit)
    national_id_checksum_flag = (re.match(digit13_pattern, data["national_id"]) is not None) and check_sum
    
    if "cfnational_id" in form:
        if not (national_id_checksum_flag and data["national_id"]==form["cfnational_id"]):
            error_msg = "กรุณากรอกรหัสบัตรประชาชนให้ถูกต้อง"
            data["valid_national_id"] = False
            flash(error_msg)
            return False, data, []
    else:
        if not national_id_checksum_flag:
            error_msg = "กรุณากรอกรหัสบัตรประชาชนให้ถูกต้อง"
            data["valid_national_id"] = False
            flash(error_msg)
            return False, data, []
    return True, data, []

# Phone number validation: Number number must follow the 9-10 digits rule (should be disabled if international)
def validate_phone(args):
    data = args['data']
    if "phone" in data:
        phone_pattern = r'^\d{9,10}$'
        phone_validation_flag = re.match(phone_pattern, data["phone"]) is not None
        if not phone_validation_flag:
            error_msg = "กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง"
            data["valid_phone"] = False
            flash(error_msg)
            return False, data, []
    return True, data, []

# Thai province name must match the texts in thai_provinces database
# กรุงเทพมหานคร must be spelled exactly as this
def validate_province_name(args):
    data = args['data']
    db, cursor = get_db()
    # MySQL treats เชียงใหม่==เชียงใหม้, เชียงราย==เชียงร้าย
    cursor.execute('SELECT name_th FROM thai_provinces WHERE name_th=%s',(data["province"], ))
    row = cursor.fetchall()
    province_name_validation_flag = True
    if len(row)>0:
        province_name_validation_flag = row[0]['name_th'] == data["province"]
    else:
        province_name_validation_flag = False
    
    if not province_name_validation_flag:
        error_msg = "กรุณากรอกชื่อจังหวัดให้ถูกต้อง"
        data["valid_province_name"] = False
        flash(error_msg)
        return False, data, []
    return True, data, []
    
# Duplicate user validation: Check if there is a duplicate user with the same name and surname but different phone
# If found, ask user to merge the account
# If found with the same phone number, force merging the accounts
# If multiple duplications are found, the most recent one will be selected
def validate_duplicate_users(args):
    data = args['data']
    form = args['form']
    db, cursor = get_db()
    cursor.execute('SELECT * FROM user WHERE name=%s AND surname=%s', (data["name"], data["surname"]))
    duplicate_users = cursor.fetchall() # Result in list of dicts
    if "create_new_account" not in form and "merge_account" not in form:
        if len(duplicate_users)>0:
            duplicate_users = duplicate_users[-1] # Select only the last matched user
            session['user_id'] = duplicate_users['id'] # Same name and same phone must be merged automatically
            if duplicate_users['phone']!=data["phone"]: # Same name but different phone (or null), will ask the user 
                if duplicate_users['is_patient']:
                    error_msg = "ตรวจพบข้อมูลผู้ใช้ที่ชื่อตรงกันกับท่านใน [ระบบประชาชน] ... ท่านต้องการรวมบัญชีหรือไม่? กดปุ่มสีเขียวเพื่อรวมบัญชี กดปุ่มสีเหลืองเพื่อสร้างบัญชีใหม่แยก"
                    error_msg += f" [ ข้อมูลซ้ำ: คุณ {duplicate_users['name']} {duplicate_users['surname']} ]"
                elif duplicate_users['is_osm']:
                    error_msg = "ตรวจพบข้อมูลผู้ใช้ที่ชื่อตรงกันกับท่านใน [ระบบเจ้าหน้าที่ผู้นำส่งข้อมูล] ... ท่านต้องการรวมบัญชีหรือไม่? กดปุ่มสีเขียวเพื่อรวมบัญชี กดปุ่มสีเหลืองเพื่อสร้างบัญชีใหม่แยก"
                    error_msg += f" [ ข้อมูลซ้ำ: คุณ {duplicate_users['name']} {duplicate_users['surname']} สังกัด {duplicate_users['hospital']}]"
                else:            
                    error_msg = "ตรวจพบข้อมูลผู้ใช้ที่ชื่อตรงกันกับท่านใน [ระบบทันตแพทย์] ... ท่านต้องการรวมบัญชีหรือไม่? กดปุ่มสีเขียวเพื่อรวมบัญชี กดปุ่มสีเหลืองเพื่อสร้างบัญชีใหม่แยก"
                    error_msg += f" [ ข้อมูลซ้ำ: คุณ {duplicate_users['name']} {duplicate_users['surname']} สังกัด {duplicate_users['hospital']}]"
                flash(error_msg)
                data["duplicate_flag"] = True
                return False, data, duplicate_users
        return True, data, duplicate_users
    return True, data, duplicate_users
    
# Generally, duplicate phone number is not allowed.
# Except in the process of merging duplicated accounts, the validation will be bypassed.
# validate_duplicate_users must be called first to get duplicate_users before running this function
def validate_duplicate_phone(args): 
    data = args['data']
    form = args['form']
    duplicate_users = args['duplicate_users']
    if "phone" in data and (len(duplicate_users)==0 or form.get('create_new_account')): 
        db, cursor = get_db()
        cursor.execute('SELECT id FROM user WHERE phone=%s',
                        (data["phone"], ))
        row = cursor.fetchall() # Result in list of dicts
        if len(row) > 0:
            error_msg = "เบอร์โทรศัพท์นี้ถูกใช้ในการลงทะเบียนบัญชีอื่นแล้ว กรุณาใช้เบอร์โทรศัพท์อื่น"
            data["valid_phone"] = False
            flash(error_msg)
            return False, data, duplicate_users
    return True, data, duplicate_users

# Generally, duplicate national_id number is not allowed.
# Except in the process of merging duplicated accounts, the validation will be bypassed.
# validate_duplicate_users must be called first to get duplicate_users before running this function
def validate_duplicate_national_id(args):
    data = args['data']
    duplicate_users = args['duplicate_users']
    form = args['form']
    if "national_id" in data and (len(duplicate_users)==0 or form.get('create_new_account')):
        db, cursor = get_db()
        cursor.execute('SELECT id FROM user WHERE national_id=%s', (data["national_id"], ))
        row = cursor.fetchall() # Result in list of dicts
        if len(row) > 0:
            error_msg = "เลขบัตรประจำตัวประชาชนนี้ถูกลงทะเบียนแล้ว ... กรุณาติดต่อเจ้าหน้าที่เพื่อแก้ไขข้อมูล"
            data["valid_national_id"] = False
            flash(error_msg)
            return False, data, duplicate_users
    return True, data, duplicate_users

# Confirmation validation: the confirmation password must match
def validate_cf_password(args):
    data = args['data']
    form = args['form']
    if (data["password"] != form["cfpassword"]):
        error_msg = "กรุณากรอกรหัสผ่านให้ตรงกันทั้งสองครั้ง"
        data["password"] = ""
        data["valid_password"] = False
        flash(error_msg)
        return False, data, []
    return True, data, []

# Username validation: duplicate username is not allowed
def validate_username(args):
    data = args['data']
    db, cursor = get_db()
    cursor.execute('SELECT id FROM user WHERE username=%s', (data["username"], ))
    duplicate_usersname = cursor.fetchall() # Result in list of dicts
    if len(duplicate_usersname)>0:
        error_msg = "รหัสผู้ใช้ (Username) นี้ มีผู้อื่นใช้ไปแล้ว กรุณาเลือกรหัสผู้ใช้ใหม่"
        data["valid_username"] = False
        flash(error_msg)
        return False, data, []
    return True, data, []