import json
from ... import db
from ..common import common_mapper

def generate_total_account():
    connection, cursor = db.get_db()
    try:
        with cursor:
            account_list = fetch_total_accoun(cursor)
            output = [{**entry, "job_category": common_mapper.map_job_position_to_th_presist_job(entry["job_category"])}for entry in account_list]
    except Exception as e:
        print(f"Error occurred: {e}")
        return json.dumps({"error": f"An error occurred while generate province list: {e}"}), 500
        
    return output

def fetch_total_accoun(cursor):
    query = """
        SELECT 
            all_users.job_category, 
            all_users.user_count AS total_users, 
            COALESCE(submission_users.user_count, 0) AS submitted_users, 
            all_users.user_count - COALESCE(submission_users.user_count, 0) AS not_submitted_users
        FROM 
            (SELECT 
                CASE 
                    WHEN job_position IN (
                        'Computer Technical Officer', 
                        'Dental Nurse', 
                        'Dentist', 
                        'General Public', 
                        'OSM', 
                        'Other Government Officer', 
                        'Other Public Health Officer', 
                        'Physician', 
                        'Programmer', 
                        'Public Health Technical Officer'
                    ) THEN job_position  
                    ELSE 'ประชาชนทั่วไป'  
                END AS job_category, 
                COUNT(*) AS user_count
            FROM user
            GROUP BY job_category) AS all_users
        LEFT JOIN 
            (SELECT 
                CASE 
                    WHEN u.job_position IN (
                        'Computer Technical Officer', 
                        'Dental Nurse', 
                        'Dentist', 
                        'General Public', 
                        'OSM', 
                        'Other Government Officer', 
                        'Other Public Health Officer', 
                        'Physician', 
                        'Programmer', 
                        'Public Health Technical Officer'
                    ) THEN u.job_position  
                    ELSE 'ประชาชนทั่วไป'  
                END AS job_category, 
                COUNT(DISTINCT u.id) AS user_count
            FROM user u
            INNER JOIN submission_record sr ON sr.sender_id = u.id
            GROUP BY job_category) AS submission_users
        ON all_users.job_category = submission_users.job_category;
    """
    cursor.execute(query)
    return cursor.fetchall()