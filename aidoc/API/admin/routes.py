from flask import jsonify, request, Blueprint
from ... import db
from . import admin

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin_page_api/', methods=['GET'])
def get_admin_page():
    return admin.generate_admin_page()

@admin_bp.route('/edit_user_info_api/', methods=['GET'])
def get_edit_user():
    id = request.args.get('id')
    output = admin.generate_user_edit_info(id)
    return output

@admin_bp.route('/delete_user_api/', methods=['DELETE'])
def delete_user():
    data = request.get_json()
    
    if not data or 'id' not in data:
        return jsonify({'error': 'No user ID provided'}), 400  
    
    user_id = data['id']
    
    output = admin.delete_user(user_id)
    
    return output

@admin_bp.route('/submit_info_api/', methods=['PUT'])
def put_submit_edited_info():
    data = request.get_json()

    required_fields = [
        "name", "surname", "job_position", "is_patient", "is_osm", 
        "is_specialist", "is_admin", "email", "province", "national_id", 
        "hospital", "phone", "license", "id"
    ]

    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    output = admin.put_update_user_info(data)

    return output

@admin_bp.route('/image_manage_api/', methods=['GET'])
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


    output = admin.get_image_manage_list(data)
    
    return output


