from flask import jsonify, request, Blueprint
from ... import db
from . import image_record
from ... import auth
image_record_bp = Blueprint('image_record', __name__)

@auth.login_required
@image_record_bp.route('/image_record_api/', methods=['GET'])
def get_image_manage():
    limit = request.args.get('limit', default=10, type=int)
    page = request.args.get('page', default=1, type=int)
    user_id = request.args.get('user_id')
    
    channel_patient = request.args.get('channel_patient')
    channel_osm = request.args.get('channel_osm')
    channel_dentist = request.args.get('channel_dentist')
    
    priority = request.args.get('priority')
    dentist_checked = request.args.get('dentist_checked')
    province = request.args.get('province')
    dentist_id = request.args.get('dentist_id')
    search_term = request.args.get('search_term')
    ai_prediction = request.args.get('ai_prediction')
    
    dentist_feedback_code = request.args.get('dentist_feedback_code')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    job_position = request.args.get('job_position')
    
    is_followup = request.args.get('is_followup')
    is_retrain = request.args.get('is_retrain')
    data = {
        "user_id": user_id,
        "channel_patient": channel_patient,
        "channel_osm": channel_osm,
        "channel_dentist": channel_dentist,
        "priority": priority,
        "dentist_checked": dentist_checked,
        "province": province,
        "dentist_id": dentist_id,
        "search_term": search_term,
        "ai_prediction": ai_prediction,
        "dentist_feedback_code": dentist_feedback_code,
        "start_date": start_date,
        "end_date": end_date,
        "job_position": job_position,
        "is_followup": is_followup,
        "is_retrain": is_retrain,
        "limit": limit,
        "page": page
    }


    output = image_record.get_image_manage_list(data)
    
    return output


