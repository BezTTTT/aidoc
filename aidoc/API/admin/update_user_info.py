
from flask import json, jsonify
from ... import db

def update_user_info(data):
    connection, cursor = db.get_db()
    try:
        with cursor:
            update_table_user(cursor,data)

            # update_table_submission_record_national_id(cursor,data)
            
            output = {
                "message": "User information updated successfully.",
                "updated_info": data  
            }
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching user data: {e}"}), 500
    return output

def update_table_user(cursor, data):
    query_set = []
    param_set = []

    if isinstance(data, dict):  # Ensure data is a dictionary
        for key, value in data.items():
            if key != "id":
                select_line = f"{key} = %s"
                query_set.append(select_line)
                param_set.append(value)
    print(query_set)
    print(param_set)
    if "id" not in data:
        raise ValueError("Missing 'id' field in data")

    param_set.append(data["id"])

    set_sql = "UPDATE user SET "
    where_sql = " WHERE id = %s;"
    
    sql = set_sql + ", ".join(query_set) + where_sql  # Convert list to SQL string
    
    cursor.execute(sql, tuple(param_set))  # Ensure params are passed as a tuple


def update_table_submission_record_national_id(cursor,data):
            sql = """
            UPDATE submission_record
            SET 
                patient_national_id = %s
                WHERE patient_id = %s;
            """
            cursor.execute(sql, (data['national_id'],data['id'],))