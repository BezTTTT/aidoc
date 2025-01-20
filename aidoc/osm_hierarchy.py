import json
from flask import Blueprint, jsonify, render_template, request, session
from aidoc.auth import login_required
from aidoc.db import get_db

bp = Blueprint('osm_hierarchy', __name__)


@bp.route('/', methods=['GET'])
@login_required
def render_osm_hierarchy():
    user_id = session.get('user_id')
    db, cursor = get_db()
    
    try:
        cursor.execute(
            """
            SELECT group_id, is_supervisor 
            FROM osm_hierarchy 
            WHERE user_id = %s
            """,
            (user_id,)
        )
        user_data = cursor.fetchone()

        if not user_data:
            return render_template('/newTemplate/osm_hierarchy.html', group_id=-1, is_user_supervisor=0)

        group_id = user_data['group_id']
        is_supervisor = user_data['is_supervisor']
        return render_template('/newTemplate/osm_hierarchy.html', group_id=group_id, is_user_supervisor=is_supervisor)
    finally:
        cursor.close()
        db.close()


@bp.route('/group/<int:group_id>', methods=['GET'])
@login_required
def get_group_users(group_id):
    if group_id == -1:
        return jsonify({'group_list': []})
    db, cursor = get_db()
    try:
        cursor.execute(
            """
            SELECT oh.group_id, oh.user_id AS osm_id, oh.is_supervisor, u.name, u.surname, u.hospital, u.province, u.phone,
            (SELECT COUNT(*) FROM submission_record sr WHERE sr.patient_id = oh.user_id OR sr.sender_id = oh.user_id) AS submission_count
            FROM osm_hierarchy oh
            LEFT JOIN user u ON oh.user_id = u.id
            WHERE oh.group_id = %s
            ORDER BY CASE WHEN oh.is_supervisor = 1 THEN 1 ELSE 2 END
            """,
            (group_id,)
        )
        hierarchy = cursor.fetchall()
            
        print(hierarchy)
        group_list = [
            {
                "osm_id": osm["osm_id"],
                "name": osm["name"],
                "surname": osm["surname"],
                "is_supervisor": osm["is_supervisor"],
                "hospital": osm["hospital"],
                "province": osm["province"],
                "submission_count": osm["submission_count"],
                "phone_number": osm["phone"]
            }
            for osm in hierarchy if osm["name"] and osm["surname"]
        ]
        return jsonify({'group_list': group_list})
    finally:
        cursor.close()
        db.close()


@bp.route('/add', methods=['POST'])
@login_required
def add_to_group():
    data = request.get_json()
    
    if not data or 'user_id' not in data or 'group_id' not in data:
        return json.dumps({'error': 'No osm_id/group_id provided'}), 400  

    user_id_to_add = data.get('user_id')
    group_id = data.get('group_id')

    if group_id == -1:
        return json.dumps({'error': 'Invalid group_id'}), 400
    
    db, cursor = get_db()
    try:
        cursor.execute(
            "INSERT INTO osm_hierarchy (user_id, group_id, is_supervisor) VALUES (%s, %s, 0)",
            (user_id_to_add, group_id)
        )
        db.commit()
        return json.dumps({'message': 'User added to group'}), 200
    except Exception as e:
        db.rollback()
        return json.dumps({'error': f'An error occurred while adding user to group: {e}'}), 500
    finally:
        cursor.close()
        db.close()


@bp.route('/remove', methods=['DELETE'])
@login_required
def remove_from_group():
    body = request.get_json()
    
    if not body or 'user_id' not in body or 'group_id' not in body:
        return json.dumps({'error': 'No osm_id/group_id provided'}), 400    
    
    user_id = body.get('user_id')
    group_id = body.get('group_id')

    if group_id == -1:
        return json.dumps({'error': 'Invalid group_id'}), 400
    
    db, cursor = get_db()
    try:
        cursor.execute(
            "DELETE FROM osm_hierarchy WHERE user_id = %s AND group_id = %s",
            (user_id, group_id)
        )
        db.commit()
        return json.dumps({"message": "User removed from group."}), 200
    except Exception as e:
        db.rollback()
        return json.dumps({"error": f"An error occurred while removing user from group: {e}"}), 500
    finally:
        cursor.close()
        db.close()


@bp.route('/get_osm_for_search', methods=['GET'])
@login_required
def search_users():
    db, cursor = get_db()
    try:
        cursor.execute("""
            SELECT id, name, surname, phone as phone_number, province, hospital
            FROM user 
            WHERE is_osm = 1 
            AND id NOT IN (SELECT user_id FROM osm_hierarchy)
        """)
        users = cursor.fetchall()
        return jsonify({'osm_list': users})
    finally:
        cursor.close()
        db.close()
