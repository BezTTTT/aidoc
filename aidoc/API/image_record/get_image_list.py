from ... import db
import json
import math
from decimal import Decimal
from .image_record_mapper import map_dentist_send_list_data, map_image_manage_list_data
from flask import (
    session, g
)

def image_manage_list(data):
    connection, cursor = db.get_db()
    try:
        with cursor:
            if data['limit'] <= 0 or data['page'] <= 0:
                return json.dumps({"error": "Invalid 'limit' or 'page' values."}), 400

            offset = (data['page'] - 1) * data['limit']

            image_manage_list_query = fetch_image_manage_list(cursor, data['limit'], offset, data)
            image_manage_list = map_image_manage_list_data(image_manage_list_query)

            total_count = fetch_total_count(cursor, data)

            total_pages = math.ceil(total_count / data['limit'])

            province_send_dropdown_list = fetch_province_send_dropdown_list(cursor)

            dentist_send = fetch_dentist_send_dropdown_list(cursor)

            output = {
                "data": image_manage_list,
                "pagination": {
                    "limit": data['limit'],
                    "page": data['page'],
                    "total_count": total_count,
                    "total_pages": total_pages
                },
                "province_dropdown_list": province_send_dropdown_list,
                "dentist_dropdown_list": dentist_send
            }
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching image records: {e}"}), 500

    return output


def fetch_image_manage_list(cursor, limit, offset, data):
    query = """
        SELECT 
            sr.channel,sr.id as submission_id,pci.case_id, sr.fname, sr.created_at, sr.ai_prediction, 
            u1.name AS user_name, u1.surname AS user_surname,
            sr.special_request, sr.location_province, 
            sr.dentist_id, sr.dentist_feedback_comment,
            sr.dentist_feedback_code,
            u1.national_id, u2.name AS dentist_name, u1.hospital,
            u2.surname AS dentist_surname, u1.job_position, sr.sender_id,rr.retrain_request_status as retrain_request_status,
            u3.birthdate, u3.name AS patient_name ,u3.surname AS patient_surname ,fr.id as followup_id,rr.id as retrain_id ,
            fr.followup_request_status as followup_request_status
        FROM submission_record sr
        LEFT JOIN user u1 ON sr.sender_id = u1.id
        LEFT JOIN user u2 ON sr.dentist_id = u2.id
        LEFT JOIN user u3 ON sr.patient_id = u3.id
        LEFT JOIN patient_case_id pci ON sr.id = pci.id
        LEFT JOIN followup_request fr ON sr.id = fr.submission_id
        LEFT JOIN retrain_request rr ON sr.id = rr.submission_id
    """

    conditions, params = build_conditions(data)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY sr.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    print(query)
    cursor.execute(query, tuple(params))
    return cursor.fetchall()


def fetch_total_count(cursor, data):
    query = """
        SELECT COUNT(*) as N
        FROM submission_record sr
        LEFT JOIN user u1 ON sr.sender_id = u1.id
        LEFT JOIN user u2 ON sr.dentist_id = u2.id
        LEFT JOIN user u3 ON sr.patient_id = u3.id
        LEFT JOIN patient_case_id pci ON sr.id = pci.id
        LEFT JOIN followup_request fr ON sr.id = fr.submission_id
        LEFT JOIN retrain_request rr ON sr.id = rr.submission_id
    """

    conditions, params = build_conditions(data)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    cursor.execute(query, tuple(params))
    print(query)
    total_count = cursor.fetchone()
    return total_count['N']


def build_conditions(data):
    conditions = []
    params = []

    # Search term
    if data.get('search_term'):
        search_pattern = set_input(data['search_term'])
        conditions.append(f""" 
            sr.fname LIKE %s OR
            sr.sender_phone LIKE %s OR
            sr.patient_national_id LIKE %s OR
            sr.dentist_feedback_comment LIKE %s OR
            sr.dentist_feedback_code LIKE %s OR
            sr.dentist_feedback_date LIKE %s OR
            sr.location_district LIKE %s OR
            sr.location_amphoe LIKE %s OR
            sr.location_province LIKE %s OR
            sr.location_zipcode LIKE %s OR
            sr.channel LIKE %s OR
            pci.case_id LIKE %s OR
            u1.name LIKE %s OR
            u1.surname LIKE %s OR
            u1.national_id LIKE %s OR
            u1.email LIKE %s OR
            u1.phone LIKE %s OR
            u1.province LIKE %s OR
            u1.job_position LIKE %s OR
            u2.name LIKE %s OR
            u2.surname LIKE %s OR
            u2.national_id LIKE %s OR
            u2.email LIKE %s OR
            u2.phone LIKE %s OR
            u2.province LIKE %s OR
            u2.job_position LIKE %s OR
            u3.name LIKE %s OR
            u3.surname LIKE %s OR
            u3.national_id LIKE %s OR
            u3.email LIKE %s OR
            u3.phone LIKE %s OR
            u3.province LIKE %s OR
            u3.job_position LIKE %s
        """)
        params.extend([search_pattern] * 33)

    # Ai prediction filter
    if data.get('ai_prediction'):
        ai_prediction = set_input(data['ai_prediction'])
        conditions.append("sr.ai_prediction LIKE %s")
        params.append(ai_prediction)

    # Priority filter
    if data.get('priority'):
        priority = set_input(data['priority'])
        conditions.append("sr.special_request LIKE %s")
        params.append(priority)

    # Dentist check filter
    if data.get('dentist_checked') is not None:
        if data['dentist_checked'].lower() == '1':
            conditions.append("sr.dentist_feedback_code IS NOT NULL")
        else:
            conditions.append("sr.dentist_feedback_code IS NULL")

    # Province filter
    if data.get('province'):
        province = set_input(data['province'])
        conditions.append("sr.location_province LIKE %s")
        params.append(province)

    # Dentist feedbacID filter
    if data.get('dentist_id'):
        dentist_id = set_input(data['dentist_id'])
        conditions.append("sr.dentist_id LIKE %s")
        params.append(dentist_id)
        
    # Dentist Feedback code filter
    if data.get('dentist_feedback_code'):
        dentist_feedback_code = set_input(data['dentist_feedback_code'])
        conditions.append("sr.dentist_feedback_code LIKE %s")
        params.append(dentist_feedback_code)
        
    #Channel filter
    if data.get('channel_patient') or data.get('channel_osm') or data.get('channel_dentist'):
        channel_list = []
        
        if data.get('channel_patient'):
            channel_list.append(data.get('channel_patient'))

        if data.get('channel_osm'):
            channel_list.append(data.get('channel_osm'))

        if data.get('channel_dentist'):
            channel_list.append(data.get('channel_dentist'))

        if channel_list:
            placeholders = ', '.join(['%s'] * len(channel_list))
            conditions.append(f"sr.channel IN ({placeholders})")
            params.extend(channel_list)
        
    #job_position sender filter
    if data.get('job_position'):
        job_position = set_input(data['job_position'])
        conditions.append("u1.job_position LIKE %s")
        params.append(job_position)
        
    #job_position dentist filter
    if data.get('job_position'):
        job_position = set_input(data['job_position'])
        conditions.append("u2.job_position LIKE %s")
        params.append(job_position) 

    #job_position patient filter
    if data.get('job_position'):
        job_position = set_input(data['job_position'])
        conditions.append("u3.job_position LIKE %s")
        params.append(job_position) 
        
    #is_followup filter
    if data.get('is_followup'):
        is_followup = set_input(data['is_followup'])
        conditions.append("fr.followup_request_status LIKE %s")
        params.append(is_followup) 
        
    #is_retrain filter
    if data.get('is_retrain'):
        if data['is_retrain']:
            is_retrain = set_input(data['is_retrain'])
            conditions.append("rr.retrain_request_status LIKE %s")
            params.append(is_retrain)
    
    # start_date filter
    if data['start_date']:
        start_date = data['start_date']
        conditions.append("DATE(sr.created_at) >= %s")
        params.append(start_date)

    # end_date filter
    if data['end_date']:
        end_date = data['end_date']
        conditions.append("DATE(sr.created_at) <= %s")
        params.append(end_date)

    # Role filter
    if g.user['is_admin']==1 and session['login_mode']=='dentist':
        # user_id filter for admin
        if data['user_id']:
            user_id = data['user_id']
            conditions.append("sr.sender_id = %s")
            params.append(user_id)
    return conditions, params


def set_input(input):
    return f"%{input}%" if input else "%%"

def fetch_province_send_dropdown_list(cursor):
    query = """
        SELECT DISTINCT location_province FROM submission_record
    """
    cursor.execute(query)
    province_send_dropdown_list = cursor.fetchall()

    province_list = [row['location_province'] for row in province_send_dropdown_list]

    return province_list


def fetch_dentist_send_dropdown_list(cursor):
    query = """
        SELECT DISTINCT 
            u.name, 
            u.surname, 
            u.license, 
            u.id 
        FROM submission_record sr 
        LEFT JOIN user u 
        ON sr.dentist_id = u.id
        WHERE sr.dentist_id IS NOT NULL
        AND u.id IS NOT NULL
    """
    cursor.execute(query)
    dentist_send_dropdown_list = map_dentist_send_list_data(cursor.fetchall())
    
    return dentist_send_dropdown_list
