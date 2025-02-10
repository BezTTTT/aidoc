#check with pathis.sender_id

import datetime
import json
import os

import requests
from .aicompute import upload_submission_module
from flask import jsonify, request, Blueprint, current_app
from ... import db
from PIL import Image
UPLOAD_FOLDER = '/test'
# # move record from h to record_submission
# def get_osm_id_that_have_rec_in_h():
#     db.close_db()
#     connection, cursor = db.get_db_2()
#     try:
#         with cursor:
#             sql = """
#             SELECT DISTINCT u.id 
#             FROM users AS u
#             INNER JOIN history AS s
#             ON u.id = s.userid
#             WHERE work = "อสม." """
#             user_id = cursor.execute(sql)
#             output = cursor.fetchall()
#             array_form = [item['id'] for item in output]
#     except Exception as e:
#         return print({"error": f"An error occurred while fetching image records: {e}"}), 500
#     return array_form

# # move record from ph to record_submission
# def get_osm_id_that_have_rec_in_ph_pat_null():
#     db.close_db()
#     connection, cursor = db.get_db_2()
#     try:
#         with cursor:
#             sql = """
#             SELECT DISTINCT u.id 
#             FROM users AS u
#             INNER JOIN patients_history AS s
#             ON u.id = s.sender_id
#             WHERE work = "อสม."
#             AND s.userid IS NULL
#             AND s.sender_id IS NOT NULL"""
#             user_id = cursor.execute(sql)
#             output = cursor.fetchall()
#             array_form = [item['id'] for item in output]
#     except Exception as e:
#         return print({"error": f"An error occurred while fetching image records: {e}"}), 500
#     return array_form

# # update record in record_submission only
# def get_osm_id_that_have_rec_in_ph_pat_not_null():
#     db.close_db()
#     connection, cursor = db.get_db_2()
#     try:
#         with cursor:
#             sql = """
#             SELECT DISTINCT u.id 
#             FROM users AS u
#             INNER JOIN patients_history AS s
#             ON u.id = s.sender_id
#             WHERE work = "อสม."
#             AND s.userid IS NOT NULL
#             AND s.sender_id IS NOT NULL"""
#             user_id = cursor.execute(sql)
#             output = cursor.fetchall()
#             array_form = [item['id'] for item in output]
#     except Exception as e:
#         return print({"error": f"An error occurred while fetching image records: {e}"}), 500
#     return array_form

def get_distinct_osm_ids():
    db.close_db()
    connection, cursor = db.get_db_2()
    try:
        with cursor:
            sql = """
            SELECT DISTINCT u.id 
            FROM users AS u
            INNER JOIN history AS s ON u.id = s.userid
            WHERE work = "อสม."
            UNION
            SELECT DISTINCT u.id 
            FROM users AS u
            INNER JOIN patients_history AS s ON u.id = s.sender_id
            WHERE work = "อสม."
            """
            cursor.execute(sql)
            output = cursor.fetchall()
            distinct_ids = list({item['id'] for item in output})  # Using a set to ensure uniqueness
    except Exception as e:
        return {"error": f"An error occurred while fetching image records: {e}"}, 500
    return distinct_ids

def migrate_osm():
    try:
            osm_id_list = get_distinct_osm_ids()
            # osm_id_list = [563]
            for osm_id in osm_id_list:
                # move osm data
                osm_data = get_osm_by_id(osm_id)
                osm_move_data = {
                    "name": osm_data['name'],
                    "surname": osm_data['surname'],
                    "national_id": osm_data['username'],
                    "email": osm_data['email'],
                    "phone": osm_data['phone'],
                    "sex": None,
                    "birthdate": None,
                    "username": None,
                    "password": None,
                    "job_position": "OSM",
                    "osm_job": None,
                    "hospital": osm_data['hospital'],
                    "province": osm_data["province"],
                    "address": None,
                    "license": osm_data['license'],
                    "is_patient": False,
                    "is_osm": True,
                    "is_specialist": False,
                    "is_admin": False,
                    "default_sender_phone": None,
                    "default_location": None,
                    "created_at": osm_data['created_at'],
                }
                new_uid = post_user_query(osm_move_data)    
                # move from history where userid = id
                ps1 = get_osm_submission_from_history_by_id(osm_id)
                for submission in ps1:
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
                    dentist_fcode1,dentist_fcomment1 = map_dentist_feedback_for_dent( submission["comment"])
                    osm_modified_submission = {
                        "channel": "OSM",
                        "fname": submission["fname"],
                        "sender_id": new_uid,
                        "sender_phone": None,
                        "special_request": 0,
                        "patient_id": None,
                        "patient_national_id": None,
                        "dentist_id": None,
                        "dentist_feedback_code":dentist_fcode1,
                        "dentist_feedback_comment": dentist_fcomment1,
                        "dentist_feedback_lesion": submission["lesions"],
                        "dentist_feedback_location": submission["position"],
                        "dentist_feedback_date":None,
                        "case_report": '',
                        "biopsy_fname": None,
                        "biopsy_comment": None,
                        "ai_prediction": ai_prediction,
                        "ai_scores":  str(ai_score),
                        "lesion_ai_version": current_app.config['AI_LESION_VER'],
                        "quality_ai_prediction": None,
                        "quality_ai_version": current_app.config['AI_QUALITY_VER'],
                        "ai_updated_at": None,
                        "location_district": None,
                        "location_amphoe": None,
                        "location_province": osm_data["province"],
                        "location_zipcode": None,
                        "Remark": None,
                        "created_at": submission["date"],
                    }
                    post_submission_query(osm_modified_submission)
                # move from patients_history where userid is null and sender_id = id
                ps2 = get_osm_submission_from_p_history_by_sender_id(osm_id)
                for submission in ps2:
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
                    location_zipcode = submission["zip_code"]
                    if location_zipcode == '':
                        location_zipcode = None
                    dentist_fcode2,dentist_fcomment2 = map_dentist_feedback( submission["dentist_comment"],submission["comment"])
                    osm_modified_submission2 = {
                        "channel": "OSM",
                        "fname": submission["fname"],
                        "sender_id": new_uid,
                        "sender_phone": None,
                        "special_request": submission["is_special"],
                        "patient_id": None,
                        "patient_national_id": submission["identity_id"],
                        "dentist_id": submission["commenter_id"],
                        "dentist_feedback_code":dentist_fcode2,
                        "dentist_feedback_comment": dentist_fcomment2,
                        "dentist_feedback_lesion": submission["lesion"],
                        "dentist_feedback_location": submission["position"],
                        "dentist_feedback_date":submission["comment_date"],
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
                        "location_province": osm_data["province"],
                        "location_zipcode": location_zipcode,
                        "Remark": None,
                        "created_at": submission["date"],
                    }
                    post_submission_query(osm_modified_submission2)
                # update submission_record where where userid is not null and sender_id =id
                update_sr_with_sender_id(new_uid,osm_id)
    except Exception as e:
        return json.dumps({"error": f"An error occurred while migrating process: {e}"}), 500
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
                data['default_sender_phone'], data['default_location'],data['created_at']
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
                data['location_province'], data['location_zipcode'], data['Remark'],data['created_at']
            ))
            
            submission_id = cursor.lastrowid
            post_case(submission_id)
    except Exception as e:
        # Handle and log errors
        return {"error": f"An error occurred while inserting submission record: {e}"}, 500

def get_osm_by_id(id):
    db.close_db()
    connection, cursor = db.get_db_2()
    try:
        with cursor:
            sql = """
            SELECT * 
            FROM users AS p
            WHERE p.id = %s"""
            user_id = cursor.execute(sql,(id,))
            output = cursor.fetchone()
    except Exception as e:
        return print({"error": f"An error occurred while fetching image records: {e}"}), 500
    return output

def get_osm_submission_from_history_by_id(id):
    db.close_db()
    connection, cursor = db.get_db_2()
    try:
        with cursor:
            sql = """
            SELECT * 
            FROM history AS ph
            WHERE ph.userid = %s"""
            result = cursor.execute(sql,(id,))
            output = cursor.fetchall()
    except Exception as e:
        return print({"error": f"An error occurred while fetching image record: {e}"}), 500
    return output

def get_osm_submission_from_p_history_by_sender_id(id):
    db.close_db()
    connection, cursor = db.get_db_2()
    try:
        with cursor:
            sql = """
            SELECT * 
            FROM patients_history AS ph
            WHERE ph.sender_id = %s
            AND ph.userid IS NULL"""
            result = cursor.execute(sql,(id,))
            output = cursor.fetchall()
    except Exception as e:
        return print({"error": f"An error occurred while fetching image: {e}"}), 500
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
        return print({"error": f"An error occurred while post case: {e}"}), 500
    return {}

def update_sr_with_sender_id(new_osm_id,old_osm_id):
    db.close_db()
    connection, cursor = db.get_db_3()
    try:
        with cursor:
            sql = """
            UPDATE submission_record
            SET sender_id = %s
            WHERE sender_id = %s
            AND patient_id IS NOT NULL;
            """
            result = cursor.execute(sql,(new_osm_id,old_osm_id))
            # output = cursor.fetchall()
    except Exception as e:
        return print({"error": f"An error occurred while fetching image recordz: {e}"}), 500
    return {}

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
    return dentist_fcode,dentist_fcomment

def map_dentist_feedback_for_dent(comment):
    cm = split_tilde(comment)
    d_comment_to_fcode_dict = {
    "เห็นด้วย": "AGREE",
    "ไม่เห็นด้วย": "DISAGREE",
    }

    dentist_fcode = d_comment_to_fcode_dict.get(cm[0], None)
    dentist_fcomment = cm[1]
    return dentist_fcode,dentist_fcomment

def split_tilde(text):
    if "~" in text:
        return text.split("~")
    return [text,""]