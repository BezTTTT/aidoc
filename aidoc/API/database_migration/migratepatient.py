import datetime
import json
import os

import requests
from .aicompute import upload_submission_module
from flask import jsonify, request, Blueprint, current_app
from ... import db
from PIL import Image
UPLOAD_FOLDER = '/test'

def get_patient_id_with_submission():
    db.close_db()
    connection, cursor = db.get_db_2()
    try:
        with cursor:
            sql = """
            SELECT DISTINCT u.id 
            FROM patients AS u
            INNER JOIN patients_history AS s
            ON u.id = s.userid """
            user_id = cursor.execute(sql)
            output = cursor.fetchall()
            output_array_form = [item['id'] for item in output]
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching image records: {e}"}), 500
    return output_array_form

def migrate_patient():
    try:
            patient_id_list = get_patient_id_with_submission()
        
            for patient_id in patient_id_list:
                # move patient data
                patient_data = get_patient_by_id(patient_id)
                patient_move_data = {
                    "name": split_name(patient_data['fullname'])[0],
                    "surname": split_name(patient_data['fullname'])[1],
                    "national_id": patient_data['license'],
                    "email": patient_data['email'],
                    "phone": patient_data['phone'],
                    "sex": map_sex_th_to_en(patient_data["sex"]),
                    "birthdate": patient_data["birth_date"],
                    "username": None,
                    "password": None,
                    "job_position": patient_data["work"],
                    "osm_job": None,
                    "hospital": None,
                    "province": patient_data["province"],
                    "address": patient_data["address"],
                    "license": None,
                    "is_patient": True,
                    "is_osm": False,
                    "is_specialist": False,
                    "is_admin": False,
                    "default_sender_phone": None,
                    "default_location": None,
                    "created_at": patient_data["created_at"],
                }
                new_uid = post_user_query(patient_move_data)
                # move user submission data
                ps = get_patient_submission_by_id(patient_id)
                for submission in ps:
                    filename = submission["fname"]
                    image_url = "https://icohold.anamai.moph.go.th:82/static/images/inputs/"+filename
                    response = requests.get(image_url, stream=True)
                    if response.status_code != 200:
                        return jsonify({'error': 'Failed to download image'}), 400
                    testDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'test')
                    imgPath = os.path.join(testDir, filename)
                    with open(imgPath, 'wb') as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    ai_prediction,ai_score = upload_submission_module(new_uid,filename,imgPath)
                    sender_id = submission["sender_id"] 
                    if submission["sender_id"] == None:
                        sender_id = new_uid
                    location_zipcode = submission["zip_code"]
                    if location_zipcode == '':
                        location_zipcode = None
                    dentist_fcode,dentist_fcomment = map_dentist_feedback( submission["dentist_comment"],submission["comment"])
                    patient_modified_submission = {
                        "channel": "PATIENT",
                        "fname": submission["fname"],
                        "sender_id": sender_id,
                        "sender_phone": None,
                        "special_request": submission["is_special"],
                        "patient_id": new_uid,
                        "patient_national_id": submission["identity_id"],
                        "dentist_id": submission["commenter_id"],
                        "dentist_feedback_code": dentist_fcode,
                        "dentist_feedback_comment": dentist_fcomment,
                        "dentist_feedback_lesion": submission["lesion"],
                        "dentist_feedback_location": submission["position"],
                        "dentist_feedback_date": submission["comment_date"],
                        "case_report": '',
                        "biopsy_fname": None,
                        "biopsy_comment": None,
                        "ai_prediction": ai_prediction,
                        "ai_scores":  str(ai_score),
                        "lesion_ai_version": current_app.config['AI_LESION_VER'],
                        "quality_ai_prediction": None,
                        "quality_ai_version": current_app.config['AI_QUALITY_VER'],
                        "ai_updated_at": None,
                        "location_district": submission["location_district"],
                        "location_amphoe": submission["location_amphoe"],
                        "location_province": patient_data["province"],
                        "location_zipcode": location_zipcode,
                        "Remark": None,
                        "created_at": submission["date"],
                    }
                    post_submission_query(patient_modified_submission)
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching image record: {e}"}), 500
    return {}

def post_user_query(data):
    db.close_db()
    connection, cursor = db.get_db_3()
    try:
        with cursor:
            sql = """
                INSERT INTO user (
                    name, surname, national_id, email, phone, sex, birthdate, username, password, job_position,
                    osm_job, hospital, province, address, license, is_patient, is_osm, is_specialist, is_admin,
                    default_sender_phone, default_location, created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
            """
            cursor.execute(sql, (
                data['name'], data['surname'], data['national_id'], data['email'], data['phone'],
                data['sex'], data['birthdate'], data['username'], data['password'], data['job_position'],
                data['osm_job'], data['hospital'], data['province'], data['address'], data['license'],
                data['is_patient'], data['is_osm'], data['is_specialist'], data['is_admin'],
                data['default_sender_phone'], data['default_location'], data['created_at']
            ))
            
            new_id = cursor.lastrowid

    except Exception as e:
        return print({"error": f"An error occurred while fetching image record: {e}"}), 500
    return new_id

def post_submission_query(data):
    try:
        # Close any previous database connections
        db.close_db()
        connection, cursor = db.get_db_3()

        with connection:
            # Define SQL query to match patient_modified_submission fields
            sql = """
                INSERT INTO submission_record (
                    channel, fname, sender_id, sender_phone, special_request, patient_id, patient_national_id,
                    dentist_id, dentist_feedback_code, dentist_feedback_comment, dentist_feedback_lesion, 
                    dentist_feedback_location, dentist_feedback_date, case_report, biopsy_fname, biopsy_comment, 
                    ai_prediction, ai_scores, lesion_ai_version, quality_ai_prediction, quality_ai_version, 
                    ai_updated_at, location_district, location_amphoe, location_province, location_zipcode, Remark, 
                    created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                    %s, %s, %s, %s, NOW()
                )
            """
            # Execute the query with corresponding data
            cursor.execute(sql, (
                data['channel'], data['fname'], data['sender_id'], data['sender_phone'], data['special_request'],
                data['patient_id'], data['patient_national_id'], data['dentist_id'], data['dentist_feedback_code'],
                data['dentist_feedback_comment'], data['dentist_feedback_lesion'], data['dentist_feedback_location'],
                data['dentist_feedback_date'], data['case_report'], data['biopsy_fname'], data['biopsy_comment'],
                data['ai_prediction'], data['ai_scores'], data['lesion_ai_version'], data['quality_ai_prediction'],
                data['quality_ai_version'], data['ai_updated_at'], data['location_district'], data['location_amphoe'],
                data['location_province'], data['location_zipcode'], data['Remark'], data['created_at']
            ))
            
            submission_id = cursor.lastrowid
            post_case(submission_id)
    except Exception as e:
        # Handle and log errors
        return {"error": f"An error occurred while inserting submission record: {e}"}, 500

def get_patient_by_id(id):
    db.close_db()
    connection, cursor = db.get_db_2()
    try:
        with cursor:
            sql = """
            SELECT * 
            FROM patients AS p
            WHERE p.id = %s"""
            user_id = cursor.execute(sql,(id,))
            output = cursor.fetchone()
    except Exception as e:
        return print({"error": f"An error occurred while fetching image record: {e}"}), 500
    return output

def post_case(submission_id):
    db.close_db()
    connection, cursor = db.get_db_3()
    try:
        with cursor:
            sql = """
            INSERT INTO patient_case_id (id) VALUES (%s)
            """
            cursor.execute(sql, (submission_id,))
    except Exception as e:
        return print({"error": f"An error occurred while fetching image record: {e}"}), 500
    return {}

def get_patient_submission_by_id(id):
    db.close_db()
    connection, cursor = db.get_db_2()
    try:
        with cursor:
            sql = """
            SELECT * 
            FROM patients_history AS ph
            WHERE ph.userid = %s"""
            result = cursor.execute(sql,(id,))
            output = cursor.fetchall()
    except Exception as e:
        return print({"error": f"An error occurred while fetching image record: {e}"}), 500
    return output

def split_name(fullname):
    # Check if the fullname is a valid string and contains spaces
    if isinstance(fullname, str) and ' ' in fullname:
        return fullname.split()
    else:
        # Return a list with two elements, filling with empty string if not splitable
        return [fullname, ""] if isinstance(fullname, str) else ["", ""]

def map_sex_th_to_en(sex):
    if sex == "ชาย":
        return  "M"
    else:
        return "F"
def map_dentist_feedback(dentist_comment,comment):
    d_comment_to_fcode_dict = {
    "OPMD": "OPMD",
    "NM": "NORMAL",
    "BAD_IMG": "BAD_IMG",
    "ไม่เห็นด้วย~มีจุดแดง": "OSCC",
    "ไม่เห็นด้วย~ภาพเบลอ โปรแกรมทำงานผิดพลาด สอน AI ใหม่": "BAD_IMG",
    "ไม่เห็นด้วย~โปรแกรมทำงานผิดพลาด สอน AI ใหม่": "OTHER",
    "ไม่เห็นด้วย~AI ทำนายผิด": "OTHER",
    "ไม่เห็นด้วย~ระบบทำนายผิด": "OTHER",
    "เห็นด้วย~ระบบทำนายผิด": "OTHER",
    "OTHER": "OTHER",
    "OSCC": "OSCC",
    "เห็นด้วย~ยืนยันว่าไม่พบรอยโรคจริง": "NORMAL",
    "เห็นด้วย~ยืนยันว่าไม่พบรอยโรคจริง กรุณาส่งภาพถ่ายช่องปากมุมมองอื่น ๆ มาให้ตรวจด้วย เช่น ข้างลิ้น กระพุ้งแก้มเป็นต้น": "NORMAL"
    }

    
    comment_to_fcomment_dict = {
        "ภาพเบลอ ไม่ชัด": "BLUR",
        "ภาพช่องปากมืดเกินไป ขอเปิดแฟลชด้วย": "DARK",
        "มุมมองไม่ได้มาตรฐาน": "NON_STANDARD",
        "ช่องปากเล็กเกินไป ขอนำกล้องเข้าใกล้ปากมากกว่านี้": "SMALL",
        "ภาพช่องปากมืดเกินไป ขอเปิดแฟลชด้วย กรุณาส่งใหม่": "DARK",
        "ภาพเบลอ ไม่ชัด กรุณาส่งใหม่": "BLUR"
    }
    dentist_fcode = d_comment_to_fcode_dict.get(dentist_comment, None)
    dentist_fcomment = ""
    if(dentist_fcode=="BAD_IMG"):
        if(dentist_comment=="BAD_IMG"):
            dentist_fcomment = comment_to_fcomment_dict.get(comment, comment)
        else:
            dentist_fcomment ="BLUR"
    if(dentist_fcode=="OTHER" and dentist_comment!="OTHER"):
        dentist_fcomment = dentist_comment

    return dentist_fcode,dentist_fcomment