import json
from ... import db


def delete_user(id):
    connection, cursor = db.get_db()
    try:
        with cursor:
            delete_submission_record(cursor, id)
            
            update_submission_record(cursor, id)

            delete_user_query(cursor, id)

            if cursor.rowcount == 0:
                return json.dumps({"error": "User not found."}), 404

    except Exception as e:
        return json.dumps({"error": f"An error occurred while deleting user: {e}"}), 500
    
    finally:
        db.close_db()

    return json.dumps({"message": f"User with ID {id} deleted successfully."}), 200

def delete_submission_record(cursor, id):
    query = "DELETE FROM submission_record WHERE sender_id = %s"
    cursor.execute(query, (id,))

def update_submission_record(cursor, id):
    query = "UPDATE submission_record SET patient_id = NULL WHERE patient_id = %s"
    cursor.execute(query, (id,))

def delete_user_query(cursor, id):
    query = "DELETE FROM user WHERE id = %s"
    cursor.execute(query, (id,))
