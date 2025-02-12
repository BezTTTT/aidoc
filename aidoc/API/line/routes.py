import logging
from flask import Blueprint, request, jsonify, render_template
from .webhook import webhook_handler
from .line_utils import send_line_message_handler, get_default_message
from .line_utils import send_message
from aidoc.db import get_db
from linebot import LineBotApi, WebhookHandler
from instance.config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET  

line_blueprint = Blueprint("line", __name__)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@line_blueprint.route("/webhook", methods=["POST"])
def handle_webhook():
    return webhook_handler()

@line_blueprint.route("/get-default-message", methods=["GET"])
def get_default_message_route():
    return get_default_message()

@line_blueprint.route("/send-adjusted-message", methods=["POST"])
def send_adjusted_message():
    data = request.get_json()
    case_id = data.get("case_id")
    message = data.get("message")

    db, cursor = get_db()
    cursor.execute(
        "SELECT p.lineId FROM submission_record ph INNER JOIN user p ON ph.patient_id = p.id WHERE ph.id = %s LIMIT 1",
        (case_id,),
    )
    row = cursor.fetchone()
    logging.info(f"Case ID {case_id}: LINE ID found: {row}")

    if not row or not row.get("lineId"):
        return jsonify({"error": "No LINE ID found"}), 400

    line_id = row["lineId"]
    send_message(line_id, message)
    return jsonify({"message": "Message sent successfully"}), 200

@line_blueprint.route("/noti_confirmation", methods=["GET"])
def noti_confirmation():
    return render_template('newTemplate/noti_confirmation.html')