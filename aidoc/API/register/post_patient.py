from ... import db
from flask import json

def post_patient(data):
    connection, cursor = db.get_db()
    try:
        with cursor:
            post_table_user(cursor,data)
            
            output = {
                "message":"post successfully",
                "patient_data":data
            }
    except Exception as e:
        return json.dumps({"error": "An unexpected error occurred","details":str(e)},500)

    return output



def post_table_user(cursor,data):
    sql = """
        INSERT INTO user (
            name,surname,national_id,birthdate,sex,province
            ,default_location,address,phone,job_position,is_patient
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    cursor.execute(sql, (
        data["name"],
        data["surname"],
        data["national_id"],
        data["birthdate"],
        data["sex"],
        data["province"],
        data["default_location"],
        data["address"],
        data["phone"],
        data["job_position"],
        True 
    ))
    