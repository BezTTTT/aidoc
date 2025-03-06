from flask import flash, session
from aidoc.db import get_db
import re
from dateutil.parser import parse
from datetime import date

# These helper functions are mostly for register systems

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
    if "phone" in data and data['phone']:
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
    if "license" in data and data["license"]:
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
    cursor.execute('SELECT * FROM user WHERE name=%s AND surname=%s ORDER BY created_at DESC', (data["name"], data["surname"]))
    duplicate_users = cursor.fetchall() # Result in list of dicts
    if "create_new_account" not in form and "merge_account" not in form:
        if len(duplicate_users)>0:
            duplicate_users = duplicate_users[-1] # Only the last matched user will be selected, the previous duplicated accounts will become inactive and will be merged or deleted by admin
            session['user_id'] = duplicate_users['id'] # Accounts of the same name, surname and phone will be automatically merged
            if duplicate_users['phone']!=data["phone"]: # If same name but different phone (or the only one is null), will ask the user 
                if duplicate_users['is_patient']:
                    error_msg = "ตรวจพบข้อมูลผู้ใช้ที่ชื่อตรงกันกับท่านใน [ระบบประชาชน] ... ท่านต้องการรวมบัญชีหรือไม่? กดปุ่มสีเขียวเพื่อรวมบัญชี กดปุ่มสีเหลืองเพื่อสร้างบัญชีใหม่แยก (บัญชีเก่า เจ้าหน้าที่จะพิจารณาลบหรือรวมข้อมูลให้ทีหลัง)"
                    error_msg += f" [ ข้อมูลซ้ำ: คุณ {duplicate_users['name']} {duplicate_users['surname']} ]"
                elif duplicate_users['is_osm']:
                    error_msg = "ตรวจพบข้อมูลผู้ใช้ที่ชื่อตรงกันกับท่านใน [ระบบผู้นำส่งข้อมูล] ... ท่านต้องการรวมบัญชีหรือไม่? กดปุ่มสีเขียวเพื่อรวมบัญชี กดปุ่มสีเหลืองเพื่อสร้างบัญชีใหม่แยก (บัญชีเก่า เจ้าหน้าที่จะพิจารณาลบหรือรวมข้อมูลให้ทีหลัง)"
                    error_msg += f" [ ข้อมูลซ้ำ: คุณ {duplicate_users['name']} {duplicate_users['surname']} สังกัด {duplicate_users['hospital']}]"
                else:            
                    error_msg = "ตรวจพบข้อมูลผู้ใช้ที่ชื่อตรงกันกับท่านใน [ระบบทันตแพทย์] ... ท่านต้องการรวมบัญชีหรือไม่? กดปุ่มสีเขียวเพื่อรวมบัญชี กดปุ่มสีเหลืองเพื่อสร้างบัญชีใหม่แยก (บัญชีเก่า เจ้าหน้าที่จะพิจารณาลบหรือรวมข้อมูลให้ทีหลัง)"
                    error_msg += f" [ ข้อมูลซ้ำ: คุณ {duplicate_users['name']} {duplicate_users['surname']} สังกัด {duplicate_users['hospital']}]"
                flash(error_msg)
                data["duplicate_flag"] = True
                session['duplicate_flag'] = True
                return False, data, duplicate_users
        return True, data, duplicate_users
    return True, data, duplicate_users

def validate_duplicate_users_except_yourself(args):
    data = args['data']
    
    db, cursor = get_db()
    cursor.execute('SELECT * FROM user WHERE name=%s AND surname=%s AND id!=%s ORDER BY created_at DESC', (data["name"], data["surname"],data["id"]))
    duplicate_users = cursor.fetchall() # Result in list of dicts
    if len(duplicate_users)>0:
        error_msg = "ตรวจพบข้อมูลผู้ใช้ที่ชื่อตรงกันกับท่าน"
        data["valid_name_surname"] = False
        flash(error_msg)
        return False, data, duplicate_users
    return True, data, duplicate_users
# region validate_duplicate_phone
# Generally, duplicate phone number is not allowed.
# Except in the process of merging duplicated accounts, the validation will be bypassed.
# validate_duplicate_users must be called first to get duplicate_users before running this function
def validate_duplicate_phone(args): 
    data = args['data']
    form = args['form']
    duplicate_users = args['duplicate_users']
    if "phone" in data and data["phone"] and (len(duplicate_users)==0 or form.get('create_new_account')): 
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

def validate_duplicate_phone_except_yourself(args): 
    data = args['data']
    duplicate_users = args['duplicate_users']
    if "phone" in data and data["phone"]: 
        db, cursor = get_db()
        cursor.execute('SELECT id FROM user WHERE phone=%s AND id!=%s',
                        (data["phone"], data["id"]))
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
    if "national_id" in data and data["national_id"] and (len(duplicate_users)==0 or form.get('create_new_account')):
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

def validate_old_username(args):
    data = args['data']
    db, cursor = get_db()
    cursor.execute('SELECT id FROM user WHERE username=%s AND id !=%s', (data["username"],data["id"]))
    duplicate_usersname = cursor.fetchall() # Result in list of dicts
    if len(duplicate_usersname)>0:
        error_msg = "รหัสผู้ใช้ (Username) นี้ มีผู้อื่นใช้ไปแล้ว กรุณาเลือกรหัสผู้ใช้ใหม่"
        data["valid_username"] = False
        flash(error_msg)
        return False, data, []
    return True, data, []

def calculate_age(born):
    if isinstance(born,str):
        born = parse(born)
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def format_thai_datetime(x):
    month_list_th = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน','กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
    output_thai_datetime_str = '{} {} {} {}:{}'.format(
        x.strftime('%d'),
        month_list_th[int(x.strftime('%m'))-1],
        int(x.strftime('%Y'))+543,
        x.strftime('%H'),
        x.strftime('%M')
    )
    return output_thai_datetime_str

def save_app_metadata(var_name, var_value):
    data_type = type(var_value).__name__
    db, cursor = get_db()
    cursor.execute('''
        INSERT INTO app_metadata (variable_name, variable_value, data_type)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            variable_value = %s,
            data_type = %s
    ''', (var_name, var_value, data_type, var_value, data_type))
    return 0

def get_app_metadata(var_name):
    db, cursor = get_db()
    cursor.execute('''
        SELECT variable_value, data_type
        FROM app_metadata
        WHERE variable_name = %s
    ''', (var_name, ))
    var = cursor.fetchone()

    if var is None:
        return None
    
    var_value = var['variable_value']
    data_type = var['data_type']

    try:
        if data_type == 'int':
            return int(var_value)
        elif data_type == 'bool':
            return var_value == '1'
        else:
            return str(var_value)
    except:
        return var_value # return default type if not match any of the following