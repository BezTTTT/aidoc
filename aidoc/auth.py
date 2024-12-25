from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, g
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
        if 'sender_mode' in session and session['sender_mode']=='general':
            cursor.execute('SELECT * FROM general_user WHERE id = %s', (user_id,))
        else:
            cursor.execute('SELECT * FROM user WHERE id = %s', (user_id,))
        g.user = cursor.fetchone()
        if g.user is None:
            session.pop('user_id', None)
        else:
            if 'sender_mode' in session and session['sender_mode']=='general':
                session['general_user'] = True
            elif g.user['is_patient']:
                g.user['job_position_th'] = g.user['job_position']
            else:
                job_position_dict = {"OSM":"อสม.", "Dental Nurse":"ทันตาภิบาล/เจ้าพนักงานทันตสาธารณสุข", "Dentist":"ทันตแพทย์",
                                    "Oral Pathologist": "ทันตแพทย์เฉพาะทาง วิทยาการวินิจฉัยโรคช่องปาก", "Oral and Maxillofacial Surgeon":"ทันตแพทย์เฉพาะทาง ศัลยศาสตร์ช่องปากและแม็กซิลโลเฟเชียล",
                                    "Physician":"แพทย์", "Public Health Technical Officer":"นักวิชาการสาธารณสุข", "Computer Technical Officer":"นักวิชาการคอมพิวเตอร์/นักวิจัย/ผู้พัฒนาระบบ",
                                    "Other Public Health Officer":"ข้าราชการ/เจ้าพนักงานกระทรวงสาธารณสุข", "Other Government Officer":"เจ้าหน้าที่รัฐอื่น", "General Public":"บุคคลทั่วไป"}
                g.user['job_position_th'] = job_position_dict[g.user['job_position']]

@bp.route('/')
def index():
    if g.user is None:
        session.clear() # logged out from everything
        return render_template("patient_login.html") # default index page (patient and osm login)
    else: # if user is already logged in
        if 'sender_mode' in session and session['sender_mode']=='dentist':
            return redirect(url_for("image.record", role='dentist'))
        elif 'sender_mode' in session and session['sender_mode']=='osm':
            return redirect(url_for("image.record", role='osm'))
        else:
            return render_template("patient_upload.html")

@bp.route('/dentist')
def dentist_index():
    if g.user is None:
        session.clear() # logged out from everything

    if g.user: # already logged in
        if 'sender_mode' in session and session['sender_mode']=='dentist':
            return redirect(url_for("image.record", role='dentist'))
    else:
        return render_template("dentist_login.html")

def role_validation(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        allowed_roles = ['patient', 'osm', 'dentist', 'specialist', 'admin']
        isUserDefinedInSession = g.user is not None
        byPassValidation = 'register_later' in session
        if ('role' not in kwargs) or (kwargs['role'] not in allowed_roles) or \
            (not byPassValidation and kwargs['role']=='osm' and isUserDefinedInSession and g.user['is_osm']==0) or \
            (not byPassValidation and kwargs['role']=='patient' and isUserDefinedInSession and g.user['is_patient']==0) or \
            (kwargs['role']=='specialist' and isUserDefinedInSession and g.user['is_specialist']==0) or \
            (kwargs['role']=='admin' and isUserDefinedInSession and g.user['is_admin']==0) or \
            (kwargs['role']=='dentist' and isUserDefinedInSession and g.user['username'] is None) \
        :
            session.pop('sender_mode', None)
            return render_template('unauthorized_access.html', error_msg='คุณไม่มีสิทธิ์เข้าถึงข้อมูล Unauthorized Access [role_validation]')
        return view(**kwargs)
    return wrapped_view

@bp.route('/login/<role>', methods=('Post',))
@role_validation
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
            error_msg = "กรุณาลงทะเบียน เลขประจำตัวประชาชนนี้ยังไม่ถูกลงทะเบียนในระบบ"
            session['national_id'] = national_id
            flash(error_msg)
            return redirect(url_for('user.register', role='patient'))
        elif user['is_patient']: # Logged in sucessfully
            session['user_id'] = user['id']
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
            'SELECT * FROM user WHERE national_id = %s OR phone = %s', (national_id, phone)
        )
        user = cursor.fetchone()
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
            'SELECT * FROM user WHERE username = %s', (username,)
        )
        user = cursor.fetchone()
        if user is None:
            error_msg = "ไม่พบรหัสผู้ใช้ โปรดลองอีกครั้งหนึ่งหรือสมัครบัญชีใหม่ ... หากลืมกรุณาติดต่อศูนย์ทันตสาธารณสุขระหว่างประเทศ"
        elif not check_password_hash(user['password'], password):
            error_msg = "รหัสผ่านไม่ถูกต้อง โปรดลองอีกครั้งหนึ่ง ... หากลืมรหัสผ่าน กรุณากดเลือก ลืมรหัสผ่าน"
        if error_msg is None: # Logged in sucessfully
            session['user_id'] = user['id']
            return redirect(url_for('image.record', role='dentist'))
        flash(error_msg)
        return render_template("dentist_login.html")

@bp.route('/logout')
def logout():
    if 'sender_mode' in session and session['sender_mode']=='general':
        session.clear()
        return redirect('/general')
    elif 'sender_mode' in session and session['sender_mode']=='dentist':
        session.clear()
        return redirect(url_for('auth.dentist_index'))
    else:
        session.clear()
        return redirect('/')

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            if 'sender_mode' in session:
                if session['sender_mode']=='dentist':
                    return redirect(url_for('auth.login', role='dentist'))
                elif session['sender_mode']=='osm':
                    return redirect(url_for('auth.login', role='osm'))
                elif session['sender_mode']=='general':
                    return redirect('/general')
            return redirect('/')
        return view(**kwargs)
    return wrapped_view

@bp.route('/about')
def about():
    return render_template("about.html")

@bp.route('/example')
def example():
    img_names =['oscc1.png', 'oscc2.png', 'oscc3.png', 'oscc4.png', 'oscc5.png', 'oscc6.png',
                'opmd1.png', 'opmd2.png', 'opmd3.png', 'opmd4.png', 'opmd5.png', 'opmd6.png',
                'opmd7.png', 'opmd8.png', 'opmd10.png', 'opmd11.png', 'opmd12.png', 'opmd13.png',
                'opmd14.png','opmd15.png','opmd16.png', 'opmd17.png', 'opmd18.png', 'opmd19.png', 'opmd20.png',
                'normal1.png', 'normal2.png', 'normal3.png','normal4.png', 'normal5.png',
                'normal6.png', 'normal7.png', 'normal8.png', 'normal9.png', 'normal10.png']

    texts = [
        '''ตัวอย่างที่ 1 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นมะเร็งชนิด Oral Squamous Cell Carcinoma (OSCC) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นสูงถึง 94.01%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''ตัวอย่างที่ 2 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นมะเร็งชนิด Oral Squamous Cell Carcinoma (OSCC) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นสูงถึง 96.93%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''ตัวอย่างที่ 3 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นมะเร็งชนิด Oral Squamous Cell Carcinoma (OSCC) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นสูงถึง 93.83%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
    '''ตัวอย่างที่ 4 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นมะเร็งชนิด Oral Squamous Cell Carcinoma (OSCC) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นสูงถึง 94.31%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
    '''ตัวอย่างที่ 5 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ ที่ถูกระบุว่าเป็น Oral Squamous Cell Carcinoma (OSCC) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะที่ 93.21% 
    ภาพนี้ผู้พัฒนานำมาจาก Google Search Engine'''
        ,
        '''ตัวอย่างที่ 6 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ ที่ถูกระบุว่าเป็น Oral Squamous Cell Carcinoma (OSCC) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะที่ 96.34%
    ภาพนี้ผู้พัฒนานำมาจาก Google Search Engine'''
        ,
        '''ตัวอย่างที่ 7 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 68.28% 
        โปรดสังเกตุว่า หากช่องปากปรากฎรอยโรคหลายรอยหรือรอยโรคกินเนื้อเยื่อในบริเวณกว้าง ระบบจะระบุรอยที่ชัดเจนที่สุดเท่านั้น 
        ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''
        ตัวอย่างที่ 8 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 96.05%
    โปรดสังเกตุว่า หากช่องปากปรากฎรอยโรคหลายรอยหรือรอยโรคกินเนื้อเยื่อในบริเวณกว้าง ระบบจะระบุรอยที่ชัดเจนที่สุดเท่านั้น
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''ตัวอย่างที่ 9 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 85.95%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์
    '''
        ,
        '''ตัวอย่างที่ 10 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 89.62%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''ตัวอย่างที่ 11 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 90.41%
    โปรดสังเกตุว่า หากช่องปากปรากฎรอยโรคหลายรอยหรือรอยโรคกินเนื้อเยื่อในบริเวณกว้าง ระบบจะระบุรอยที่ชัดเจนที่สุดเท่านั้น 
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''ตัวอย่างที่ 12 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 92.98%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.ดร. จิตจิโรจน์ อิทธิชัยเจริญ คณะทันตแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่'''
        ,
        '''ตัวอย่างที่ 13 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 94.57%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.ดร. จิตจิโรจน์ อิทธิชัยเจริญ คณะทันตแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่'''
        ,
        '''ตัวอย่างที่ 14 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 90.19%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.ดร. จิตจิโรจน์ อิทธิชัยเจริญ คณะทันตแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่'''
        ,
        '''ตัวอย่างที่ 15 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 84.11%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.ดร. จิตจิโรจน์ อิทธิชัยเจริญ คณะทันตแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่'''
        ,
        '''ตัวอย่างที่ 16 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 85.26%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.ดร. จิตจิโรจน์ อิทธิชัยเจริญ คณะทันตแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่'''
        ,
        '''ตัวอย่างที่ 17 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 92.87%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.ดร. จิตจิโรจน์ อิทธิชัยเจริญ คณะทันตแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่'''
        ,
        '''ตัวอย่างที่ 18 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 94.53%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.ดร. จิตจิโรจน์ อิทธิชัยเจริญ คณะทันตแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่'''
        ,
        '''ตัวอย่างที่ 19 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 88.06%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.ดร. จิตจิโรจน์ อิทธิชัยเจริญ คณะทันตแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่'''
        ,
        '''ตัวอย่างที่ 20 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 89.73%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.ดร. จิตจิโรจน์ อิทธิชัยเจริญ คณะทันตแพทยศาสตร์ มหาวิทยาลัยเชียงใหม่'''
        ,
        '''ตัวอย่างที่ 21 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ที่ได้รับการวินิจฉัยทางพยาธิวิทยาว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 89.05%
    ภาพนี้ได้รับจากการลงพื้นที่ตรวจคัดกรองของ ศทป. โดยใช้กล้องมือถือในการถ่าย'''
        ,
        '''ตัวอย่างที่ 22 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ ที่ถูกระบุว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 90.61%
        ภาพนี้ผู้พัฒนานำมาจาก Google Search Engine'''
        ,
        '''ตัวอย่างที่ 23 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ ที่ถูกระบุว่าเป็นโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMF) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 78.82%
    ภาพนี้ผู้พัฒนานำมาจาก Google Search Engine'''
        ,
        '''ตัวอย่างที่ 24 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ ที่ถูกระบุว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 82.57%
    ภาพนี้ผู้พัฒนานำมาจาก Google Search Engine'''
        ,
        '''ตัวอย่างที่ 25 รูปภาพผลลัพธ์การระบุรอยโรคของภาพถ่ายช่องปากของคนไข้ ที่ถูกระบุว่าเป็นรอยโรคก่อนมะเร็ง หรือ Oral Potentially Malignant Disorder (OPMD) โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 88.30%
    ภาพนี้ผู้พัฒนานำมาจาก Google Search Engine'''
        ,
        '''ตัวอย่างที่ 26 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 100%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''ตัวอย่างที่ 27 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 100%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''ตัวอย่างที่ 28 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 100%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''ตัวอย่างที่ 29 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 99.98%
    ภาพนี้ได้รับความอนุเคราะห์จาก ผศ.ทพ.กฤษสิทธิ์ วารินทร์ คณะทันตแพทยศาสตร์ มหาวิทยาลัยธรรมศาสตร์'''
        ,
        '''ตัวอย่างที่ 30 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 100%
    ภาพนี้ได้รับจากการลงพื้นที่ตรวจคัดกรองของ ศทป. โดยใช้กล้องมือถือในการถ่าย
    ภาพนี้มีการแก้ไขทางคอมพิวเตอร์โดยทำให้เกิดการสะท้อนกระจกซ้ายขวาเพื่อประโยชน์ต่อการแสดงผล'''
        ,
        '''ตัวอย่างที่ 31 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 99.99%
    ภาพนี้ได้รับจากการลงพื้นที่ตรวจคัดกรองของ ศทป. โดยใช้กล้องมือถือในการถ่าย
    ภาพนี้มีการแก้ไขทางคอมพิวเตอร์โดยทำให้เกิดการสะท้อนกระจกซ้ายขวาเพื่อประโยชน์ต่อการแสดงผล'''
        ,
        '''ตัวอย่างที่ 32 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 99.88% 
    ภาพนี้ได้รับจากการลงพื้นที่ตรวจคัดกรองของ ศทป. โดยใช้กล้องมือถือในการถ่าย
    ภาพนี้มีการแก้ไขทางคอมพิวเตอร์โดยทำให้เกิดการสะท้อนกระจกซ้ายขวาเพื่อประโยชน์ต่อการแสดงผล'''
        ,
        '''ตัวอย่างที่ 33 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 99.86%
    ภาพนี้ได้รับจากการลงพื้นที่ตรวจคัดกรองของ ศทป. โดยใช้กล้องมือถือในการถ่าย'''
        ,
        '''ตัวอย่างที่ 34 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 99.97%
    ภาพนี้ได้รับจากการลงพื้นที่ตรวจคัดกรองของ ศทป. โดยใช้กล้องมือถือในการถ่าย'''
        ,
        '''ตัวอย่างที่ 35 ตัวอย่างรูปภาพที่ไม่พบรอยโรค หรือ Normal โดยระบบปัญญาประดิษฐ์แจ้งค่าความน่าจะเป็นที่ 99.89%
    ภาพนี้ได้รับจากการลงพื้นที่ตรวจคัดกรองของ ศทป. โดยใช้กล้องมือถือในการถ่าย
    ภาพนี้มีการแก้ไขทางคอมพิวเตอร์โดยทำให้เกิดการสะท้อนกระจกซ้ายขวาเพื่อประโยชน์ต่อการแสดงผล'''
    ]
    data = {}
    data["imgs_name"] = img_names
    data["texts"] = texts
    return render_template("example.html", data=data)