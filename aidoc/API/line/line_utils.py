from flask import current_app
from linebot import LineBotApi
from linebot.models import TextSendMessage, ImageSendMessage
from aidoc.db import get_db
from flask import jsonify

def get_line_api():
    LINE_CHANNEL_ACCESS_TOKEN = current_app.config.get("LINE_CHANNEL_ACCESS_TOKEN")
    return LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def send_message(line_id, message):
    try:
        line_bot_api = get_line_api()
        print(f"Sending message to {line_id}: {message}")
        line_bot_api.push_message(line_id, TextSendMessage(text=message))
    except Exception as e:
        print(f"Error sending message to {line_id}: {e}")

def send_image(line_id, image_url, preview_image_url):
    try:
        line_bot_api = get_line_api()
        print(f"Sending image to {line_id}")
        line_bot_api.push_message(line_id, ImageSendMessage(
            original_content_url=image_url,
            preview_image_url=preview_image_url
        ))
    except Exception as e:
        print(f"Error sending image to {line_id}: {e}")

def send_line_message_handler(case_id):
    db,cursor = get_db()
    query = "SELECT lineId FROM submission_record ph INNER JOIN user p ON ph.patient_id = p.id WHERE ph.id = %s LIMIT 1"
    cursor.execute(query, (case_id,))
    line_id = cursor.fetchone()
    query = "SELECT ai_prediction, dentist_feedback_code FROM submission_record WHERE id = %s"
    cursor.execute(query, (case_id,))
    ai_prediction,dentist_feedback_code = cursor.fetchone()
    line_id = line_id["lineId"]

    if ai_prediction == 0 and dentist_feedback_code == 'NORMAL':
        send_message(line_id, "ทันตแพทย์ยืนยันว่าช่องปากของคุณไม่พบรอยโรค")
    elif ai_prediction == 0 and (dentist_feedback_code == 'OPMD' or dentist_feedback_code == 'OSCC'):
        send_message(line_id, "ทันตแพทย์ยืนยันว่าช่องปากของคุณน่าจะมีรอยโรคจริง")
    elif ai_prediction != 0 and (dentist_feedback_code == 'OPMD' or dentist_feedback_code == 'OSCC'):
        send_message(line_id, "ทันตแพทย์ยืนยันว่าช่องปากของคุณอาจมีรอยโรคจริง")
    elif ai_prediction == 0 and (dentist_feedback_code == 'OPMD' or dentist_feedback_code == 'OSCC'):
        send_message(line_id, "ทันตแพทย์ยืนยันว่าช่องปากของคุณน่าจะมีรอยโรคจริง")
    elif ai_prediction != 0 and (dentist_feedback_code == 'OPMD' or dentist_feedback_code == 'OSCC'):
        send_message(line_id, "ทันตแพทย์ยืนยันว่าช่องปากของคุณอาจมีรอยโรคจริง")
    else:
        send_message(line_id, "ทันตแพทย์ยืนยันว่าช่องปากของคุณน่าจะมีรอยโรคจริง")
    
    return jsonify({"message": "Message sent successfully"}), 200
