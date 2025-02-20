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
    priority = request.args.get('priority')
    dentist_checked = request.args.get('dentist_checked')
    province = request.args.get('province')
    dentist_id = request.args.get('dentist_id')
    search_term = request.args.get('search_term')
    ai_prediction = request.args.get('ai_prediction')
    data = {
        "priority": priority,
        "dentist_checked": dentist_checked,
        "province": province,
        "dentist_id": dentist_id,
        "search_term": search_term,
        "ai_prediction": ai_prediction,
        "limit": limit,
        "page": page
    }


    output = image_record.get_image_manage_list(data)
    
    return output


