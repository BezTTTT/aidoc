from flask import request, jsonify, current_app
from ... import db
from .line_utils import send_message, get_line_api

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
            message = event["message"]["text"]

            if message == "7":
                send_message(line_id, "กรุณากรอกเบอร์โทรศัพท์ของคุณ")

            elif message.isdigit() and len(message) == 10:
                cursor = db.cursor(dictionary=True)
                cursor.execute("SELECT phone FROM aidoc_development.user WHERE lineId = %s", (line_id,))
                existing_user = cursor.fetchone()

                if existing_user:
                    send_message(line_id, "เบอร์โทรศัพท์ของคุณได้เชื่อมต่อเรียบร้อยแล้ว")
                else:
                    cursor.execute("UPDATE user SET lineId = %s WHERE phone = %s", (line_id, message))
                    db.commit()

                    if cursor.rowcount > 0:
                        send_message(line_id, "ลงทะเบียนสำเร็จ! เบอร์โทรศัพท์ของคุณได้รับการเชื่อมต่อแล้ว")
                    else:
                        send_message(line_id, "ไม่พบข้อมูลในระบบ กรุณาสมัครสมาชิกที่ https://icohold.anamai.moph.go.th:82/patient")

            else:
                send_message(line_id, "กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง (10 หลัก)")

    return "OK", 200