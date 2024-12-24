
from flask import json, jsonify
from ... import db
from ..common import common_mapper as cm

def user_info(id):
    connection, cursor = db.get_db()
    try:
        with cursor:
            user_info_query = fetch_user_info(cursor,id)

            if not user_info_query:
                return json.dumps({"error": "User not found."}), 400
            
            user_data = {
                **user_info_query,
                "job_position_th": cm.map_job_position_to_th(user_info_query['job_position'])
            }


            output = user_data

    except Exception as e:
        return  json.dumps({"error": f"An error occurred while fetching user data: {e}"}), 500
    
    finally:
        db.close_db()

    return output

def fetch_user_info(cursor,id):
    print(id)
    query ="""
        SELECT
            id,
            name,
            surname,
            job_position,
            is_patient,
            is_osm,
            is_specialist,
            is_admin,
            email,
            province,
            national_id,
            hospital,
            phone,
            license,
            username
            FROM user 
        WHERE id = %s
            """
    cursor.execute(query,(id,))
    user_info_query = cursor.fetchone()

    return user_info_query