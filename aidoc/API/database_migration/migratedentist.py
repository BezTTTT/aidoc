import datetime
import json
import os

import requests
from .aicompute import upload_submission_module
from flask import jsonify, request, Blueprint, current_app
from ... import db
from PIL import Image
UPLOAD_FOLDER = '/test'

def get_user_id_with_submission_that_not_osm():
    db.close_db()
    connection, cursor = db.get_db_2()
    try:
        with cursor:
            sql = """
            SELECT DISTINCT u.id 
            FROM users AS u
            INNER JOIN history AS s
            ON u.id = s.userid
            WHERE work != "อสม." """
            user_id = cursor.execute(sql)
            output = cursor.fetchall()
            array_form = [item['id'] for item in output]
    except Exception as e:
        return print({"error": f"An error occurred while fetching image records: {e}"}), 500
    return array_form


def migrate_dentist():
    try:
            dentist_id_list = get_user_id_with_submission_that_not_osm()
            # dentist_id_list = [283]
            for dentist_id in dentist_id_list:
                # move dentist data
                #need to map job back to eng
                dentist_data = get_dentist_by_id(dentist_id)
                dentist_move_data = {
                    "name": dentist_data['name'],
                    "surname": dentist_data['surname'],
                    "national_id": None,
                    "email": dentist_data['email'],
                    "phone": dentist_data['phone'],
                    "sex": None,
                    "birthdate": None,
                    "username": dentist_data['username'],
                    "password": dentist_data['password'],
                    "job_position": map_job_position_to_en(dentist_data["work"]),
                    "osm_job": None,
                    "hospital": dentist_data['hospital'],
                    "province": dentist_data["province"],
                    "address": None,
                    "license": dentist_data['license'],
                    "is_patient": False,
                    "is_osm": False,
                    "is_specialist": False,
                    "is_admin": False,
                    "default_sender_phone": None,
                    "default_location": None,
                    "created_at": dentist_data['created_at'],
                }
                new_uid = post_user_query(dentist_move_data)
                # move user submission data
                ps = get_dentist_submission_by_id(dentist_id)
                for submission in ps:
                    #download_image from port 82
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
                    #recompute image
                    ai_prediction,ai_score = upload_submission_module(new_uid,filename,imgPath)
                    dentist_fcode,dentist_fcomment = map_dentist_feedback_for_dent( submission["comment"])
                    dentist_modified_submission = {
                        "channel": "DENTIST",
                        "fname": submission["fname"],
                        "sender_id": new_uid,
                        "sender_phone": None,
                        "special_request": 0,
                        "patient_id": None,
                        "patient_national_id": None,
                        "dentist_id": None,
                        "dentist_feedback_code":dentist_fcode,
                        "dentist_feedback_comment": dentist_fcomment,
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
                        "location_province": dentist_data["province"],
                        "location_zipcode": None,
                        "Remark": None,
                        "created_at": submission["date"],
                    }
                    post_submission_query(dentist_modified_submission)
                #update sr on dentist_id
                update_sr_with_commenter_id(new_uid,dentist_id)
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
    except Exception as e:
        # Handle and log errors
        return {"error": f"An error occurred while inserting submission record: {e}"}, 500

def get_dentist_by_id(id):
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
        return print({"error": f"An error occurred while fetching image record: {e}"}), 500
    return output

def get_dentist_submission_by_id(id):
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


def map_job_position_to_en(job_position):
    job_position_dict = {
        "อสม.": "OSM",
        "ทันตาภิบาล/เจ้าพนักงานทันตสาธารณสุข":"Dental Nurse",
        "ทันตแพทย์": "Dentist",
        "ทันตแพทย์เฉพาะทาง วิทยาการวินิจฉัยโรคช่องปาก": "Oral Pathologist",
        "ทันตแพทย์เฉพาะทาง ศัลยศาสตร์ช่องปากและแม็กซิลโลเฟเชียล" : "Oral and Maxillofacial Surgeon",
        "แพทย์" : "Physician",
        "นักวิชาการสาธารณสุข" : "Public Health Technical Officer",
        "นักวิชาการคอมพิวเตอร์/วิศวกร" : "Computer Technical Officer",
        "ข้าราชการ/เจ้าพนักงานกระทรวงสาธารณสุข":"Other Public Health Officer",
        "เจ้าหน้าที่รัฐอื่น" : "Other Government Officer",
        "บุคคลทั่วไป" : "General Public",
        "ทันตสาธารณสุข":"Dental Nurse",
        "จพ.ทันตสาธารณสุข":"Dental Nurse",
        "จพ.ทันตสาธารณสุขปฏิบัติงาน":"Dental Nurse",
        "นักวิชาการทันตสาธารณสุข":"Dental Nurse",
        "นักวิชาการสาธารณสุขปฏิบัติการ":"Other Public Health Officer",
        "เจ้าพนักงานทันตสาธารณสุขชำนาญงาน":"Dental Nurse",
        "เจ้าพนักงานทันตสาธารณสุข":"Dental Nurse",
        "นักวิชาการสาธารณสุข(ทันตสาธารณสุข)":"Dental Nurse",
        "ทันตบุคลากร":"Dental Nurse",
        "เจ้าพนักงานสาธารณสุขชำนาญงาน":"Other Public Health Officer",
        "เจ้าพนักงานทันตสาธารณสุข ชำนาญงาน":"Dental Nurse",
        "เจ้าพนักงานสาธารณสุขอื่น":"Other Public Health Officer",
        "ทันตาภิบาล":"Dental Nurse",
    }

    return job_position_dict.get(job_position, job_position)

def update_sr_with_commenter_id(new_dentist_id,old_dentist_id):
    db.close_db()
    connection, cursor = db.get_db_3()
    try:
        with cursor:
            sql = """
            UPDATE submission_record
            SET dentist_id = %s
            WHERE dentist_id = %s;
            """
            result = cursor.execute(sql,(new_dentist_id,old_dentist_id))
            # output = cursor.fetchall()
    except Exception as e:
        return print({"error": f"An error occurred while fetching image record: {e}"}), 500
    return {}

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