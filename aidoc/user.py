from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, jsonify, g, current_app, send_from_directory, make_response
)
from werkzeug.security import generate_password_hash

from PyPDF2 import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4
import datetime
import io
import os
from aidoc.utils import *

from aidoc.db import get_db
from aidoc.auth import login_required, load_logged_in_user, role_validation, log_last_user_login

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
def register(role):
    data = {}

    # Check if a post calling from diagnosis pages
    if request.form.get('order', None):
        session['register_later'] = {}
        session['register_later']['order'] = request.form.get('order', None)
        session['register_later']['return_page'] = request.form.get('return_page', None)
        session['register_later']['login_mode'] = request.form.get('role', None)
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

            log_last_user_login(session['user_id'])
            session['login_mode'] = 'patient'

            # session['national_id'] is used to carry out id from login to register
            # After the registration is complete, this (sensitive) variable should be deleted
            if 'national_id' in session:  
                session.pop('national_id',None)  
            
            if 'register_later' not in session:
                return redirect(url_for('image.upload_image', role='patient'))
            elif session['register_later']['return_page'] == 'diagnosis':
                role = session['register_later']['login_mode']
                session['login_mode'] = role
                img_id = session['register_later']['img_id']
                session.pop('register_later', None)
                session.pop('noNationalID', None)
                return redirect(url_for('webapp.diagnosis', role=role, img_id=img_id))
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

            log_last_user_login(session['user_id'])
            session['login_mode'] = 'osm'

            if 'register_later' not in session:
                return redirect('/')
            elif session['register_later']['return_page'] == 'diagnosis':
                role = session['register_later']['login_mode']
                session['login_mode'] = role
                img_id = session['register_later']['img_id']
                session.pop('register_later', None)
                session['user_id'] = g.user['id'] 
                return redirect(url_for('webapp.diagnosis', role=role, img_id=img_id))
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
                
            log_last_user_login(session['user_id'])
            session['login_mode'] = 'dentist'

            return redirect(url_for('webapp.record', role='dentist'))
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
        role = session['register_later']['login_mode']
        session['login_mode'] = role
        img_id = session['register_later']['img_id']
        session.pop('register_later', None)
        return redirect(url_for('webapp.diagnosis', role=role, img_id=img_id))

# region load_legal_docs
@bp.route('/load_legal_docs/<int:user_id>/<document>')
@login_required
def load_legal_docs(user_id, document):
    if (g.user['is_admin'] == 0) and (session['user_id'] != user_id):
        return render_template('unauthorized_access.html', error_msg='คุณไม่มีสิทธิ์เข้าถึงข้อมูล Unauthorized Access')
    
    legalDir = current_app.config['LEGAL_DIR']
    agreementVer = current_app.config['CURRENT_AGREEMENT_VER']
    consentVer = current_app.config['CURRENT_CONSENT_VER']
    doc_Dir = os.path.join(legalDir, str(user_id))

    if document=='draft_agreement' or document=='agreement':
        doc_filename = document + "_v" + agreementVer + ".pdf"
    elif document=='draft_consent' or document=='consent':
        doc_filename = document + "_v" + consentVer + ".pdf"
    else:
        doc_filename = ''

    pdf = send_from_directory(doc_Dir, doc_filename)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=%s' % doc_filename
    return response

# region show_legal_docs
@bp.route('/show_legal_docs/<int:user_id>/<document>')
@login_required
def show_legal_docs(user_id, document):

    if (g.user['is_admin'] == 0) and (session['user_id'] != user_id):
        return render_template('unauthorized_access.html', error_msg='คุณไม่มีสิทธิ์เข้าถึงข้อมูล Unauthorized Access')

    data = {'user_id': user_id ,'document':document}
    return render_template('document_display.html', data=data)

# region submit_compliance
@bp.route('/submit_compliance/<int:user_id>', methods=('POST', ))
@login_required
def submit_compliance(user_id):

    if (g.user['is_admin'] == 0) and (session['user_id'] != user_id):
        return render_template('unauthorized_access.html', error_msg='คุณไม่มีสิทธิ์เข้าถึงข้อมูล Unauthorized Access')

    answer = request.form.get('answer')
    if answer=='accept':
        set_user_compliance(user_id)
        returning_page = session['returning_page']
        session.pop('returning_page', None)
        if returning_page=='upload_image':
            return redirect(url_for('image.upload_image', role=session['login_mode']))
    elif answer=='reject':
        legalDir = current_app.config['LEGAL_DIR']
        agreementVer = current_app.config['CURRENT_AGREEMENT_VER']
        consentVer = current_app.config['CURRENT_CONSENT_VER']
        draft1 = os.path.join(legalDir, str(user_id), "draft_agreement_v" + agreementVer + ".pdf")
        draft2 = os.path.join(legalDir, str(user_id), "draft_consent_v" + consentVer + ".pdf")
        os.remove(draft1)
        os.remove(draft2)
        return redirect('/logout')

# region get_user_compliance
# Comply with the current versions of user_agreement and informed_consent
def get_user_compliance(user_id):
    sql = 'SELECT * FROM user_compliance WHERE user_id=%s'
    val = (user_id, )
    db, cursor = get_db()
    cursor.execute(sql, val)
    results = cursor.fetchall()
    if results:
        result = results[-1] # Get the latest agreement
        return  (result['user_agreement_version'] == current_app.config['CURRENT_AGREEMENT_VER']) and \
                (result['informed_consent_version'] == current_app.config['CURRENT_CONSENT_VER'])
    else:
        return False

# region set_user_compliance
# Comply with the current versions of user_agreement and informed_consent
def set_user_compliance(user_id):

    legalDir = current_app.config['LEGAL_DIR']
    agreementVer = current_app.config['CURRENT_AGREEMENT_VER']
    consentVer = current_app.config['CURRENT_CONSENT_VER']

    sql = '''INSERT INTO user_compliance
        (user_id, user_agreement_version, user_agreement_datetime, informed_consent_version, informed_consent_datetime)
        VALUES (%s, %s, %s, %s, %s)'''
    val = (user_id, agreementVer, datetime.datetime.now(), consentVer, datetime.datetime.now())
    db, cursor = get_db()
    cursor.execute(sql, val)

    # Make the drafts to be the final ones
    draft1 = os.path.join(legalDir, str(user_id), "draft_agreement_v" + agreementVer + ".pdf")
    final1 = os.path.join(legalDir, str(user_id), "agreement_v" + agreementVer + ".pdf")
    draft2 = os.path.join(legalDir, str(user_id), "draft_consent_v" + consentVer + ".pdf")
    final2 = os.path.join(legalDir, str(user_id), "consent_v" + consentVer + ".pdf")
    os.rename(draft1, final1)
    os.rename(draft2, final2)

# region generate_legal_drafts
# Generate user_agreement and informed_consent pdfs
def generate_legal_drafts(user_id):
    sql = 'SELECT name, surname, national_id FROM user WHERE id=%s'
    val = (user_id, )
    db, cursor = get_db()
    cursor.execute(sql, val)
    result = cursor.fetchone()
    full_name = f"{result['name']} {result['surname']}"
    if result['national_id']:
        full_name_with_id = f"{result['name']} {result['surname']} (ID: {result['national_id']})"
    else:
        full_name_with_id = full_name
    
    legalDir = current_app.config['LEGAL_DIR']
    agreementVer = current_app.config['CURRENT_AGREEMENT_VER']
    consentVer = current_app.config['CURRENT_CONSENT_VER']
    os.makedirs(os.path.join(legalDir, str(user_id)) , exist_ok=True)

    # Generate PDFs
    pdfmetrics.registerFont(TTFont('THSarabunNew-Bold', os.path.join(legalDir, 'templates', 'THSarabunNew Bold.ttf')))
    current_time = format_thai_datetime(datetime.datetime.now())

    for i in range(2):
        packet = io.BytesIO()
        text_canvas = canvas.Canvas(packet, pagesize=A4)
        text_canvas.setFont('THSarabunNew-Bold', 16)
        if i==0: # User Agreement
            text_canvas.drawString(160, 530, full_name) 
            text_canvas.drawString(385, 530, current_time + ' น.')
        else: # Broad Informed Consent
            text_canvas.drawString(160, 735, full_name_with_id) 
            text_canvas.drawString(170, 335, full_name)
            text_canvas.drawString(400, 335, current_time + ' น.')
            text_canvas.drawString(170, 300, "รศ.ดร.ปฏิเวธ วุฒิสารวัฒนา") # PI
            text_canvas.drawString(400, 300, current_time + ' น.')
            text_canvas.drawString(180, 265, "ทพ.ดร.แมนสรวง วงศ์อภัย") # Project Head
            text_canvas.drawString(400, 265, current_time + ' น.')
        text_canvas.save()
        packet.seek(0)
        canvas_pdf = PdfReader(packet)
        output = PdfWriter()
        if i==0: # User Agreement
            input = PdfReader(open(os.path.join(legalDir, 'templates', 'agreement_v'+ agreementVer + ".pdf"), "rb"))
            output.add_page(input.pages[0])
            page = input.pages[1]
            page.merge_page(canvas_pdf.pages[0])
            output.add_page(page)
            output_stream = open(os.path.join(legalDir, str(user_id), "draft_agreement_v" + agreementVer + ".pdf"), "wb")
        else: # Broad Informed Consent
            input = PdfReader(open(os.path.join(legalDir, 'templates', 'consent_v'+ consentVer + ".pdf"), "rb"))
            output.add_page(input.pages[0])
            output.add_page(input.pages[1])
            output.add_page(input.pages[2])
            page = input.pages[3]
            page.merge_page(canvas_pdf.pages[0])
            output.add_page(page)
            output_stream = open(os.path.join(legalDir, str(user_id), "draft_consent_v" + consentVer + ".pdf"), "wb")
        output.write(output_stream)
        output_stream.close()