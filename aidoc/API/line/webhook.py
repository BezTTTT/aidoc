from flask import request, jsonify, current_app
from ... import db
from .line_utils import send_message, get_line_api

def validate_phone_number(phone_number):
    return phone_number.isdigit() and len(phone_number) == 10

def save_line_id_to_database(phone_number, line_id):
    try:
        cursor = db.cursor(dictionary=True)
        query = "UPDATE user SET lineId = %s WHERE phone = %s"
        params = (line_id, phone_number)
        cursor.execute(query, params)
        db.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error saving line ID to database: {e}")
        return False

def webhook_handler():
    if request.method != "POST":
        return jsonify({"error": "Method not allowed"}), 405

    body = request.get_data(as_text=True)
    print(f"Received body: {body}")  # Debugging

    events = request.json.get("events", [])
    print(f"Received events: {events}")  # Debugging

    line_bot_api = get_line_api()

    for event in events:
        line_id = event["source"]["userId"]

        if event["type"] == "follow":
            send_message(line_id, "กรุณาพิมพ์เลข 7 เพื่อลงทะเบียน")

        elif event["type"] == "message" and event.get("message", {}).get("type") == "text":
            user_message = event["message"]["text"]

            if user_message == "7":
                send_message(line_id, "กรุณากรอกเบอร์โทรศัพท์ของคุณ")

            else:
                cursor = db.cursor(dictionary=True)
                cursor.execute("SELECT phone FROM user WHERE lineId = %s", (line_id,))
                existing_user = cursor.fetchone()

                if existing_user:
                    send_message(line_id, "เบอร์โทรศัพท์ของคุณได้เชื่อมต่อเรียบร้อยแล้ว")
                else:
                    if validate_phone_number(user_message):
                        if save_line_id_to_database(user_message, line_id):
                            send_message(line_id, "เชื่อมต่อเบอร์โทรศัพท์เรียบร้อยแล้ว")
                        else:
                            send_message(line_id, "ผิดพลาดในการเชื่อมต่อเบอร์โทรศัพท์")
                    else:
                        send_message(line_id, "กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง (10 หลัก) ถ้าหากยังไม่ได้ลงทะเบียน https://icohold.anamai.moph.go.th:85/")

    return "OK", 200