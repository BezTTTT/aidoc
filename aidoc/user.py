from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, jsonify, g
)
from werkzeug.security import generate_password_hash

import datetime
import re

from aidoc.db import get_db
from aidoc.auth import login_required, load_logged_in_user, role_validation

# 'user' blueprint manages user management system
bp = Blueprint('user', __name__)

# region get_osm_info
@bp.route("/get_osm_info", methods=["POST"])
@login_required
def get_osm_info():
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

# region get_patient_info
@bp.route("/get_patient_info", methods=["POST"])
def get_patient_info():
    #get patient national id
    phone_number = request.form.get('patient_id')
    db, cursor = get_db()
    cursor.execute("SELECT id, name, surname FROM user WHERE national_id = %s AND is_patient = 1", (phone_number,))
    senderInfo = cursor.fetchone()

    if(senderInfo is not None):
        return jsonify({
            'name': senderInfo['name'],
            'surname': senderInfo['surname'],
            'patient_id': senderInfo['id']
        }), 200
    else:
        return jsonify({}), 404

# region register
@bp.route('/register/<role>', methods=('GET', 'POST'))
@role_validation
def register(role):
    data = {}

    # Check if a post calling from diagnosis pages
    if request.form.get('order', None):
        session['register_later'] = {}
        session['register_later']['order'] = request.form.get('order', None)
        session['register_later']['return_page'] = request.form.get('return_page', None)
        session['register_later']['sender_mode'] = request.form.get('role', None)
        session['register_later']['img_id'] = request.form.get('img_id', None)

        if session['register_later']['order']=='register-osm':

            # Check if any user uses the same phone, if yes, use the info as the initial info.
            data['phone'] = request.form.get('sender_phone', None)
            db, cursor = get_db()
            sql = '''SELECT name, surname, national_id, job_position, province, phone, hospital
                    FROM user
                    WHERE phone=%s'''
            val = (data['phone'], )
            cursor.execute(sql, val)
            data = cursor.fetchone()
            if data is None:
                data = {}
                data['phone'] = request.form.get('sender_phone', None)
            else:
                if data['hospital'] == None:
                    data['hospital'] = ''
            return render_template("osm_register.html", data=data)
        else: # patient register-later
            session['register_later']['user_id'] = request.form.get('patient_id', None)
            session['national_id'] = request.form.get('patient_national_id', None)

            if session['register_later']['order']=='register-patient':
                session['noNationalID'] = False
                if request.form.get('saved_patient_national_id', None) == None: # Check if the the submission has a patient_national_id
                    session['noNationalID'] = True
                else:
                    session['national_id'] = request.form.get('saved_patient_national_id', None)
            elif session['register_later']['order']=='edit-patient' or session['register_later']['order']=='link-patient':
                db, cursor = get_db()
                sql = '''SELECT name, surname, national_id, email, phone, sex, birthdate, job_position, province, address
                        FROM user
                        WHERE national_id=%s'''
                val = (session['national_id'], )
                cursor.execute(sql, val)
                data = cursor.fetchone()
                data['dob_day'] = data['birthdate'].day
                data["dob_month"] = data['birthdate'].month
                data["dob_year"] = data['birthdate'].year + 543
                if data['email'] == None:
                    data['email'] = ''
                if data['phone'] == None:
                    data['phone'] = ''
            data['current_year'] = datetime.date.today().year # set the current Thai Year to the global variable
            return render_template("patient_register.html", data=data)
    
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
            if 'register_later' in session and session['register_later']['order']=='edit-patient':
                valid_func_list = [validate_province_name,
                                validate_duplicate_phone]
            else:    
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
            # new account or user confirms that the duplicate account is not theirs, or register_later is defined
            if ('register_later' in session and session['register_later']['order']=='register-patient') or ('user_id' not in session) or (request.form.get('create_new_account')):
                sql = "INSERT INTO user (name, surname, national_id, email, phone, sex, birthdate, job_position, province, address, is_patient) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                val = (data["name"], data["surname"], data["national_id"], data["email"], data["phone"], data["sex"], dob_obj, data["job_position"], data["province"], data['address'], True)
                cursor.execute(sql, val)

                # Load the newly registered user to the session (using national_id and is_patient flag)
                cursor.execute('SELECT id FROM user where national_id = %s AND is_patient=TRUE', (data["national_id"],))
                new_user = cursor.fetchone()
                if 'register_later' not in session:
                    session['user_id'] = new_user['id']
                    load_logged_in_user()
                elif session['noNationalID']: # If the record has no national_id of the patient, add it here
                    sql = "UPDATE submission_record SET patient_id=%s, patient_national_id=%s WHERE id=%s"
                    val = (new_user['id'], data["national_id"], session['register_later']['img_id'])
                    cursor.execute(sql, val)
                else:
                    # Retrospectively update the all empty sender_id records with patient_national_id
                    sql = "UPDATE submission_record SET patient_id=%s WHERE patient_national_id=%s"
                    val = (new_user['id'], data["national_id"])
                    cursor.execute(sql, val)
            elif ('register_later' in session and session['register_later']['order']=='edit-patient'):
                sql = "UPDATE user SET name=%s, surname=%s, email=%s, phone=%s, sex=%s, birthdate=%s, job_position=%s, province=%s, address=%s, updated_at=%s WHERE national_id=%s"
                val = (data["name"], data["surname"], data["email"], data["phone"], data["sex"], dob_obj, data["job_position"], data["province"], data['address'], datetime.datetime.now(), data["national_id"])
                cursor.execute(sql, val)
            elif ('register_later' in session and session['register_later']['order']=='link-patient'): # Linking data does not update the patient info
                sql = "UPDATE submission_record SET patient_id=%s, patient_national_id=%s WHERE id=%s"
                val = (session['register_later']['user_id'], data["national_id"], session['register_later']['img_id'])
                cursor.execute(sql, val)
            else: # Merge account
                sql = "UPDATE user SET name=%s, surname=%s, national_id=%s, email=%s, phone=%s, sex=%s, birthdate=%s,  province=%s, address=%s, is_patient=%s WHERE id=%s"
                val = (data["name"], data["surname"], data["national_id"], data["email"], data["phone"], data["sex"], dob_obj, data["province"], data['address'], True, session['user_id'])
                cursor.execute(sql, val)

            # session['national_id'] is used to carry out id from login to register
            # After the registration is complete, this (sensitive) variable should be deleted
            if 'national_id' in session:  
                session.pop('national_id',None)  
            
            if 'register_later' not in session:
                return redirect(url_for('image.upload_image', role='patient'))
            elif session['register_later']['return_page'] == 'diagnosis':
                role = session['register_later']['sender_mode']
                session['sender_mode'] = role
                img_id = session['register_later']['img_id']
                session.pop('register_later', None)
                session.pop('noNationalID', None)
                return redirect(url_for('image.diagnosis', role=role, img_id=img_id))
        else:
            return render_template(target_template, data=data)
    elif role=='osm':
        target_template = "osm_register.html"
        if request.method == 'POST':
            
            session.pop('user_id', None) # User id will later be used to check duplicate users

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
                               validate_license,
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
                if 'register_later' not in session:
                    session['user_id'] = new_user['id']
                    load_logged_in_user()
                else: # If the record has no national_id of the patient, add it here
                    sql = "UPDATE submission_record SET sender_id=%s WHERE id=%s"
                    val = (new_user['id'], session['register_later']['img_id'])
                    cursor.execute(sql, val)
                
            else: # merge account
                sql = "UPDATE user SET name=%s, surname=%s, national_id=%s, phone=%s, osm_job=%s, hospital=%s, province=%s, license=%s, is_osm=%s WHERE id=%s"
                val = (data["name"], data["surname"], data["national_id"], data["phone"], data["osm_job"], data["hospital"], data["province"], data["license"], True, session['user_id'])
                cursor.execute(sql, val)

                if 'register_later' in session:
                    sql = "UPDATE submission_record SET sender_id=%s WHERE id=%s"
                    val = (session['user_id'], session['register_later']['img_id'])
                    cursor.execute(sql, val)

            if 'register_later' not in session:
                return redirect('/')
            elif session['register_later']['return_page'] == 'diagnosis':
                role = session['register_later']['sender_mode']
                session['sender_mode'] = role
                img_id = session['register_later']['img_id']
                session.pop('register_later', None)
                session['user_id'] = g.user['id'] 
                return redirect(url_for('image.diagnosis', role=role, img_id=img_id))
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

            data["national_id"] = None # Dummy variable for validate_duplicate_phone
            # this section validate the input data, if fails, redirect back to the form
            duplicate_users = []
            valid_func_list = [validate_cf_password,
                               validate_username,
                               validate_license,
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
                
            return redirect(url_for('image.record', role='dentist'))
        else:
            return render_template(target_template, data=data)
    else:
        return redirect('/')

#region forgot_password system
@bp.route('/forgot', methods=('GET', 'POST'))
def forgot():
    data={}
    if request.method == 'POST':
        if request.args.get('validationCheck', type=str)=='false':
            user_profile = {}
            user_profile['name'] = request.form.get('name')
            user_profile['surname'] = request.form.get('surname')
            user_profile['national_id'] = request.form.get('national_id')
            user_profile['job_position'] = request.form.get('job_position')
            user_profile['osm_job'] = request.form.get('osm_job')
            user_profile['license'] = request.form.get('license')
            user_profile['hospital'] = request.form.get('hospital')
            user_profile['province'] = request.form.get('province')
            user_profile['phone'] = request.form.get('phone')
            user_profile['email'] = request.form.get('email')
            user_profile['username'] = request.form.get('username')

            if all([x == '' for x in list(user_profile.values())]):
                flash("กรุณากรอกข้อมูลให้ถูกต้องอย่างน้อย 5 ใน 9 รายการดังต่อไปนี้")
                return render_template('forgot_password.html', data=data)

            db, cursor = get_db()
            sql = 'SELECT * FROM user WHERE (name=%s AND surname=%s) OR (national_id=%s) OR (license=%s) OR (phone=%s) OR (email=%s) OR (username=%s)'
            cursor.execute(sql, (user_profile['name'], user_profile['surname'], user_profile['national_id'], user_profile['license'], user_profile['phone'], user_profile['email'], user_profile['username']))
            users = cursor.fetchall() # Result in list of dicts
            data['username'] = None
            for user in users:
                validation_count = 0
                for identity in user_profile.keys():
                    validation_count += int(user_profile[identity] == user[identity])
                if validation_count>=6:
                    data['username'] = user['username']
                    break
            if data['username']==None:
                flash("ไม่พบข้อมูลของท่านในระบบ กรุณาลองใหม่ หรือ ติดต่อเจ้าหน้าที่ ศูนย์ทันตสาธารณสุขระหว่างประเทศ กรมอนามัยเพื่อแก้ไขข้อมูล")
        if request.args.get('validationCheck', type=str)=='true':

            # Validate the confirmation password
            data["username"] = request.form["username_on_db"]
            data["password"] = request.form["password"]
            data["valid_password"] = True
            args = {'data': data, 'form': request.form, 'duplicate_users': []}
            valid_check, data, duplicate_users = validate_cf_password(args)
            if not valid_check:
                return render_template('forgot_password.html', data=data)

            db, cursor = get_db()
            sql = "UPDATE user SET password=%s WHERE username=%s"
            val = (generate_password_hash(data["password"]), data["username"])
            cursor.execute(sql, val)

            return redirect('/dentist')

    return render_template('forgot_password.html', data=data)

#region cancel_register
@bp.route('/cancel_register', methods=('GET', ))
def cancel_register():
    if 'national_id' in session:  
        session.pop('national_id', None)
    if 'register_later' not in session:
        return redirect('/logout')
    elif session['register_later']['return_page'] == 'diagnosis':
        session['user_id'] = g.user['id'] 
        role = session['register_later']['sender_mode']
        session['sender_mode'] = role
        img_id = session['register_later']['img_id']
        session.pop('register_later', None)
        return redirect(url_for('image.diagnosis', role=role, img_id=img_id))

# Helper functions

# region remove_prefix
def remove_prefix(input_str):
    prefixes = ["นาย", "นางสาว", "นาง", "น.ส.", "นส.", "น.",  "ทพญ.", "ทพ.", "ดร."]
    for prefix in prefixes:
        if input_str.startswith(prefix):
            return input_str[len(prefix):].strip()
    return input_str

# region validate_national_id
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

# region validate_phone
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

# region validate_license
# License validation: License must be only numbers
def validate_license(args):
    data = args['data']
    if "license" in data:
        license_pattern = r'^[0-9]*$'
        license_validation_flag = re.match(license_pattern, data["license"]) is not None
        if not license_validation_flag:
            error_msg = "กรุณาเลขที่ใบอนุญาตให้ถูกต้อง กรอกเฉพาะตัวเลข ไม่ต้องใส่ ท. หรือ พ."
            data["valid_license"] = False
            flash(error_msg)
            return False, data, []
    return True, data, []

# region validate_province_name
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
    
# region validate_duplicate_users
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
            session['user_id'] = duplicate_users['id'] # Same name and same surname must be merged automatically
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
    
# region validate_duplicate_phone
# Generally, duplicate phone number is not allowed.
# Except in the process of merging duplicated accounts, the validation will be bypassed.
# validate_duplicate_users must be called first to get duplicate_users before running this function
def validate_duplicate_phone(args): 
    data = args['data']
    form = args['form']
    duplicate_users = args['duplicate_users']
    if "phone" in data and (len(duplicate_users)==0 or form.get('create_new_account')): 
        db, cursor = get_db()
        cursor.execute('SELECT id FROM user WHERE phone=%s AND national_id!=%s',
                        (data["phone"], data["national_id"]))
        row = cursor.fetchall() # Result in list of dicts
        if len(row) > 0:
            error_msg = "เบอร์โทรศัพท์นี้ถูกใช้ในการลงทะเบียนบัญชีอื่นแล้ว กรุณาใช้เบอร์โทรศัพท์อื่น"
            data["valid_phone"] = False
            flash(error_msg)
            return False, data, duplicate_users
    return True, data, duplicate_users

# region validate_duplicate_national_id
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
            error_msg = "เลขประจำตัวประชาชนนี้ถูกลงทะเบียนแล้ว ... กรุณาติดต่อเจ้าหน้าที่เพื่อแก้ไขข้อมูล"
            data["valid_national_id"] = False
            flash(error_msg)
            return False, data, duplicate_users
    return True, data, duplicate_users

# region validate_cf_password
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

# region validate_username
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