import json
from flask import Blueprint, jsonify, render_template, request, session
from aidoc.auth import login_required, role_validation
from aidoc.db import get_db

bp = Blueprint('osm_hierarchy', __name__)

def format_thai_datetime(x):
    month_list_th = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน','กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
    output_thai_datetime_str = '{} {} {} {}:{}'.format(
        x.strftime('%d'),
        month_list_th[int(x.strftime('%m'))-1],
        int(x.strftime('%Y'))+543,
        x.strftime('%H'),
        x.strftime('%M')
    )
    return output_thai_datetime_str


# render osm hierarchy page
@bp.route('/', methods=['GET']) 
@login_required
@role_validation
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

#render osm hierarchy record page
@bp.route('/group_record/<int:osm_id>', methods=('GET', 'POST'))
@login_required
@role_validation
def render_osm_hierarchy_record(osm_id): # Submission records

    # Reload the record every time the page is reloaded
    db, cursor = get_db()
    sql = '''SELECT submission_record.id, channel, fname,
                patient_user.name, patient_user.surname, patient_user.birthdate, patient_user.province,
                case_id, sender_id, patient_id, dentist_id, special_request, sender_phone, 
                location_province, location_zipcode, 
                dentist_feedback_comment,dentist_feedback_code,
                ai_prediction, submission_record.created_at
            FROM submission_record
            INNER JOIN patient_case_id ON submission_record.id = patient_case_id.id
            LEFT JOIN user AS patient_user ON submission_record.patient_id = patient_user.id
            LEFT JOIN user AS sender_user ON submission_record.sender_phone = sender_user.phone
            WHERE sender_id = %s OR submission_record.sender_phone is not NULL
            ORDER BY case_id DESC'''
    val = (osm_id,)
    cursor.execute(sql, val)
    db_query = cursor.fetchall()
    
    # Filter data if search query is provided
    if 'record_filter' not in session:
        session['record_filter'] = {}
    if request.method == 'POST':
        search_query = request.form.get("search", session['record_filter'].get('search_query', ""))
        agree = request.form.get("agree", "")
        filterStatus = request.form.get("filterStatus", "") 
        filterPriority = request.form.get("filterPriority", "") 
        filterProvince = request.form.get("filterProvince", "") 
        filterSpecialist = request.form.get("filterSpecialist", "")
        filterFollowup = request.form.get("filterFollowup", "")
        filterRetrain = request.form.get("filterRetrain", "")
        session['record_filter']['search_query'] = search_query
        session['record_filter']['agree'] = agree
        session['record_filter']['filterStatus'] = filterStatus
        session['record_filter']['filterPriority'] = filterPriority
        session['record_filter']['filterProvince'] = filterProvince
        session['record_filter']['filterSpecialist'] = filterSpecialist
        session['record_filter']['filterFollowup'] = filterFollowup
        session['record_filter']['filterRetrain'] = filterRetrain
    else:
        search_query = session['record_filter'].get('search_query', "")
        agree = session['record_filter'].get('agree', "")
        filterStatus = session['record_filter'].get('filterStatus', "")
        filterPriority = session['record_filter'].get('filterPriority', "")
        filterProvince = session['record_filter'].get('filterProvince', "")
        filterSpecialist = session['record_filter'].get('filterSpecialist', "")
        filterFollowup = session['record_filter'].get("filterFollowup", "")
        filterRetrain = session['record_filter'].get("filterRetrain", "")
    # Initialize an empty list to store filtered results
    filtered_data = []

    # Loop through the data and apply both search and filter criteria
    # This section must be researched for the efficiency (and refactored), but for now just let it be
    for record in db_query:
        record_fname = record.get("fname").lower()
        record_case_id = record.get("case_id")
        record_feedback_code = record.get("dentist_feedback_code")
        record_ai_prediction = record.get("ai_prediction")
        record_patient_name = record.get("name")
        record_patient_surname = record.get("surname")
        record_special_request = record.get("special_request")
        record_province = record.get("location_province")
        record_district = record.get("location_district")
        record_amphoe = record.get("location_amphoe")
        record_zipcode = record.get("location_zipcode")

        if search_query!="" or filterStatus!="" or filterPriority!="" or filterProvince!="":
            cumulativeFilterFlag = True

            if search_query!="":
                cumulativeFilterFlag &= (search_query in record_fname) or (str(record_case_id) == search_query) or \
                    (record_patient_name is not None) and (record_patient_name in search_query or record_patient_surname in search_query) or \
                    (record_feedback_code is not None) and (record_feedback_code.lower() == search_query.lower()) or \
                    (search_query.lower() == 'opmd') and (record_ai_prediction==1) or \
                    (search_query.lower() == 'oscc') and (record_ai_prediction==2) or \
                    (record_district is not None) and (search_query in record_district) or \
                    (record_amphoe is not None) and (search_query in record_amphoe) or \
                    (record_province is not None) and (search_query in record_province) or \
                    (record_zipcode is not None) and (search_query == record_zipcode)
            if filterStatus!="":
                cumulativeFilterFlag &= (filterStatus == "1" and record_feedback_code!=None) or (filterStatus == "0" and record_feedback_code==None)
            if filterPriority!="":
                cumulativeFilterFlag &= (filterPriority=="1" and record_special_request==1) or (filterPriority=="0" and record_special_request==0)
            
            if cumulativeFilterFlag:
                filtered_data.append(record)
        else:
            filtered_data.append(record)
   
    # Pagination
    page = request.args.get("page", 1, type=int)
    if request.method == "POST":
        if 'current_record_page' in session:
            page = session['current_record_page']
        else:
            page = 1
        
    PER_PAGE = 12 #number images data show on record page per page
    total_pages = (len(filtered_data) - 1) // PER_PAGE + 1
    start_idx = (page - 1) * PER_PAGE
    end_idx = start_idx + PER_PAGE
    paginated_data = filtered_data[start_idx:end_idx]
    
    # Process each item in paginated_data
    for item in paginated_data:
        if item['channel']=='PATIENT':
            item['owner_id'] = item['patient_id']
        else:
            item['owner_id'] = item['sender_id']
        item["formatted_created_at"] = item["created_at"].strftime("%d/%m/%Y %H:%M")
        if ("birthdate" in item and item["birthdate"]):
            item["age"] = 55# calculate_age(item["birthdate"])

    data = {}
    data['search'] = search_query
    data['agree'] = agree
    
    session['current_record_page'] = page

    print("filtered_data", data)

    return render_template(
                "/newTemplate/osm_hierarchy_record.html",
                osm_id=osm_id,

                data=data,
                dataCount=len(filtered_data),
                pagination=paginated_data,
                current_page=page,
                total_pages=total_pages,
                search_query=search_query,
                filters=[filterStatus,filterPriority,filterProvince,filterSpecialist,filterFollowup,filterRetrain])


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
            (SELECT COUNT(*) FROM submission_record sr WHERE sr.patient_id = oh.user_id OR sr.sender_id = oh.user_id) AS submission_count,
            (SELECT created_at FROM submission_record WHERE sender_id = oh.user_id ORDER BY created_at DESC LIMIT 1) AS last_activity
            FROM osm_hierarchy oh
            LEFT JOIN user u ON oh.user_id = u.id
            WHERE oh.group_id = %s
            ORDER BY CASE WHEN oh.is_supervisor = 1 THEN 1 ELSE 2 END
            """,
            (group_id,)
        )
        hierarchy = cursor.fetchall()
            
        
        group_list = [
            {
                "osm_id": osm["osm_id"],
                "name": osm["name"],
                "surname": osm["surname"],
                "is_supervisor": osm["is_supervisor"],
                "hospital": osm["hospital"],
                "province": osm["province"],
                "submission_count": osm["submission_count"],
                "phone_number": osm["phone"],
                "last_activity": format_thai_datetime(osm["last_activity"]) if osm["last_activity"] else "-"

            }
            for osm in hierarchy if osm["name"] and osm["surname"]
        ]
        print(group_list)
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

