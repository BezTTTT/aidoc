from .admin_mapper import map_user_list_data
from ... import db
import json
from decimal import Decimal

def users_list():
    connection, cursor = db.get_db()
    try:
        with cursor:
            user_list_query = fetch_user_list(cursor)
            user_list = map_user_list_data(user_list_query)

            output = user_list
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching user accounts: {e}"}),500
    
    finally:
        db.close_db()
    
    return output

def fetch_user_list(cursor):
    query ="""
SELECT 
    u.id,
    u.name,
    u.surname,
    u.job_position,
    u.is_patient,
    u.is_osm,
    u.is_specialist,
    u.is_admin,
    u.email,
    u.province,
    COALESCE(sr.N, 0) AS N
FROM 
    user u
LEFT JOIN 
    (
        SELECT 
            sender_id,
            COUNT(*) AS N 
        FROM 
            submission_record 
        GROUP BY 
            sender_id
    ) sr
ON 
    u.id = sr.sender_id;

    """
    cursor.execute(query)
    user_list_query = cursor.fetchall()

    return user_list_query