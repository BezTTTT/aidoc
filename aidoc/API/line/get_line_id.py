from flask import jsonify, request
from ... import db

def get_line_id_handler():
    try:
        data = request.get_json()
        print("Request data:", data)
        
        userid = data.get("userid")
        if not userid:
            return jsonify({"error": "userid is required"}), 400

        print(f"Looking up LINE ID for userid: {userid}")

        cursor = db.cursor(dictionary=True)
        
        while db.unread_result:
            db.get_rows()

        query = """
            SELECT p.lineId
            FROM submission_record ph
            INNER JOIN user p ON ph.patient_id = p.id
            WHERE ph.patient_id = %s
            LIMIT 1
        """
        cursor.execute(query, (userid,))
        result = cursor.fetchone()
        print("Query result:", result)

        while cursor.nextset():
            pass

        if result and result['lineId']:
            return jsonify({"line_id": result['lineId']}), 200
        else:
            return jsonify({"error": "No LINE ID found for this user"}), 404
            
    except Exception as e:
        print(f"Error in get_line_id: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.commit()