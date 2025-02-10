from flask import current_app, jsonify
from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage
from aidoc.db import get_db
import logging

logging.basicConfig(level=logging.INFO)

def get_line_api():
    LINE_CHANNEL_ACCESS_TOKEN = current_app.config.get("LINE_CHANNEL_ACCESS_TOKEN")
    return LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def send_message(line_id, message):
    try:
        line_bot_api = get_line_api()
        logging.info(f"Sending message to {line_id}: {message}")
        line_bot_api.push_message(line_id, TextSendMessage(text=message))
    except Exception as e:
        logging.error(f"Error sending message to {line_id}: {e}")

def get_default_message():
    db, cursor = get_db()

    # Fetch all records that have lineId and submission record data
    cursor.execute(
        """SELECT sr.id, sr.ai_prediction, sr.dentist_feedback_code, sr.dentist_feedback_comment, u.lineId
           FROM submission_record sr
           JOIN user u ON sr.patient_id = u.id
           WHERE u.lineId IS NOT NULL"""
    )
    
    rows = cursor.fetchall()

    if not rows:
        return jsonify({"error": "No records found with valid Line IDs"}), 400

    messages = []
    for row in rows:
        print(f"Processing row: {row}")  # Debugging step

        # Extract values from dictionary
        case_id = row.get("id")
        ai_prediction = row.get("ai_prediction", 0)
        dentist_feedback_code = (row.get("dentist_feedback_code") or "").strip()
        dentist_feedback_comment = (row.get("dentist_feedback_comment") or "").strip()
        line_id = row.get("lineId")

        # Convert ai_prediction to int
        try:
            ai_prediction = int(ai_prediction)
        except (TypeError, ValueError):
            ai_prediction = 0

        print(f"Case ID: {case_id}, AI Prediction: {ai_prediction}, Dentist Feedback: {dentist_feedback_code}")  # Debugging step

        # Define the messages based on ai_prediction and dentist_feedback_code
        if dentist_feedback_code == 'NORMAL' and ai_prediction == 0:
            message = f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณไม่พบรอยโรค"
        
        elif dentist_feedback_code == 'OPMD' and ai_prediction == 0:
            message = f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณน่าจะมีรอยโรคจริง แต่ AI อาจทำงานผิดพลาด"
        
        elif dentist_feedback_code == 'OSCC' and ai_prediction == 0:
            message = f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณน่าจะมีรอยโรคจริง แต่ AI อาจทำงานผิดพลาด"
        
        elif dentist_feedback_code in ['OPMD', 'OSCC'] and ai_prediction == 1:
            message = f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณอาจมีรอยโรคจริง"
        
        elif dentist_feedback_code == 'NORMAL' and ai_prediction == 1:
            message = f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณไม่พบรอยโรค"
        
        elif dentist_feedback_code == 'BAD_IMG':
            feedback_messages = {
                'NON_STANDARD': "มุมมองไม่ได้มาตรฐาน",
                'BLUR': "ภาพเบลอ ไม่ชัด",
                'DARK': "ภาพช่องปากมืดเกินไป ขอเปิดแฟลชด้วย",
                'SMALL': "ช่องปากเล็กเกินไป ขอนำกล้องเข้าใกล้ปากมากกว่านี้"
            }
            specific_message = feedback_messages.get(dentist_feedback_comment, "มีปัญหาเกี่ยวกับรูปภาพ")
            message = f"case ID: {case_id} {specific_message}"
        
        else:
            message = f"case ID: {case_id} กรุณาติดต่อทันตแพทย์เพื่อข้อมูลเพิ่มเติม"

        messages.append({
            "case_id": case_id,
            "line_id": line_id,
            "message": message
        })

    return jsonify({"messages": messages}), 200
       
def send_line_message_handler(case_id):
    db, cursor = get_db()
    
    # Fetch line_id
    cursor.execute(
        """SELECT p.lineId 
        FROM submission_record ph 
        INNER JOIN user p ON ph.patient_id = p.id 
        WHERE ph.id = %s LIMIT 1""",
        (case_id,)
    )
    row = cursor.fetchone()
    if not row or "lineId" not in row:
        logging.warning(f"Case ID {case_id}: No LINE ID found")
        return jsonify({"error": "No LINE ID found"}), 400
    line_id = row["lineId"]
    
    # Fetch AI prediction & dentist feedback
    cursor.execute(
        """SELECT ai_prediction, dentist_feedback_code, dentist_feedback_comment 
        FROM submission_record WHERE id = %s""",
        (case_id,)
    )
    row = cursor.fetchone()
    if not row:
        logging.warning(f"Case ID {case_id}: No submission record found")
        return jsonify({"error": "No submission record found"}), 400
    
    ai_prediction, dentist_feedback_code, dentist_feedback_comment = row

    messages = {
        ('NORMAL', 0): f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณไม่พบรอยโรค",
        ('OPMD', 0): f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณน่าจะมีรอยโรคจริง แต่ AI อาจทำงานผิดพลาด",
        ('OSCC', 0): f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณน่าจะมีรอยโรคจริง แต่ AI อาจทำงานผิดพลาด",
        ('OPMD', 1): f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณอาจมีรอยโรคจริง",
        ('OSCC', 1): f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณอาจมีรอยโรคจริง",
        ('NORMAL', 1): f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณไม่พบรอยโรค",
    }
    
    message = messages.get((dentist_feedback_code, ai_prediction), None)
    if message:
        print(message)
        send_message(line_id, message)
        logging.info(message)
    elif dentist_feedback_code == 'BAD_IMG':
        feedback_messages = {
            'NON_STANDARD': "มุมมองไม่ได้มาตรฐาน",
            'BLUR': "ภาพเบลอ ไม่ชัด",
            'DARK': "ภาพช่องปากมืดเกินไป ขอเปิดแฟลชด้วย",
            'SMALL': "ช่องปากเล็กเกินไป ขอนำกล้องเข้าใกล้ปากมากกว่านี้"
        }
        message = f"case ID: {case_id} {feedback_messages.get(dentist_feedback_comment, 'มีปัญหาเกี่ยวกับรูปภาพ')}"
        send_message(line_id, message)
        logging.info(message)
    else:
        message = f"case ID: {case_id} ทันตแพทย์ยืนยันว่าช่องปากของคุณน่าจะมีรอยโรคจริง"
        send_message(line_id, message)
        logging.info(message)

    return jsonify({"message": "Message sent successfully"}), 200