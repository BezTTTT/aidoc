from flask import jsonify, request, Blueprint
from ... import db
from . import admin
from ... import auth
admin_bp = Blueprint('admin', __name__)

@auth.login_required
@auth.admin_only
@admin_bp.route('/admin_page_api/', methods=['GET'])
def get_admin_page():
    return admin.generate_admin_page()

@auth.login_required
@auth.admin_only
@admin_bp.route('/edit_user_info_api/', methods=['GET'])
def get_edit_user():
    id = request.args.get('id')
    output = admin.generate_user_edit_info(id)
    return output

@auth.login_required
@auth.admin_only
@admin_bp.route('/delete_user_api/', methods=['DELETE'])
def delete_user():
    data = request.get_json()
    
    if not data or 'id' not in data:
        return jsonify({'error': 'No user ID provided'}), 400  
    
    user_id = data['id']
    
    output = admin.delete_user(user_id)
    
    return output

@auth.login_required
@auth.admin_only
@admin_bp.route('/submit_info_api/', methods=['PUT'])
def put_submit_edited_info():
    data = request.get_json()

    required_fields = [
        "name", "surname", "job_position", "is_patient", "is_osm", 
        "is_specialist", "is_admin", "email", "province",
        "hospital", "phone", "id"
    ]
    
    # for field in required_fields:
    #     if field not in data:
    #         return jsonify({"error": f"Missing required field: {field}"}), 400

    output = admin.put_update_user_info(data)
    return output

@auth.login_required
@auth.admin_only
@admin_bp.route('/check_phone_api/', methods=['POST'])
def get_duplicate_phone_info():
    data = request.get_json()
    output = admin.get_duplicate_phone(data)
    return jsonify(output)

