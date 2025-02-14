import json
from ... import db

def check_duplicate_phone(data):
    connection, cursor = db.get_db()
    try:
        with cursor:
            # Check if the phone is a duplicate
            result = is_duplicate_phone(cursor,data)
            return result
            
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching user data: {e}"}), 500

def is_duplicate_phone(cursor,data):
    sql= """
    SELECT 
        phone,
        id
    FROM 
        user 
        WHERE phone = %s
        AND id != %s
"""
    cursor.execute(sql, (data['phone'],data['id']))
    result = cursor.fetchone()
    return result