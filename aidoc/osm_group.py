from functools import singledispatch
import json
from flask import Blueprint, jsonify, render_template, request, session, g
from aidoc.auth import login_required, load_osm_group_info_query
from aidoc.db import get_db
from aidoc.utils import format_thai_datetime, calculate_age


bp = Blueprint('osm_group', __name__)

# render osm hierarchy record page
# region Group Record Render
@bp.route('/', methods=('GET', 'POST'))
@login_required
def render_osm_group_record():
    load_osm_group_info() # Load group info to g.user['group_info']
    # Prevent not supervisor accesses
    if(g.user['group_info']['is_supervisor'] == 0 or g.user['group_info']['group_id'] == -1 ):
        return render_template('newTemplate/osm_group_record.html', dataCount=0, paginated_data=[], current_page=1, total_pages=1, data={}, osm_filter_data={})
    
    # Filter Preparation
    if 'record_filter' not in session:
        session['record_filter'] = {}
    if request.method == 'POST':
        search_query = request.form.get("search", session['record_filter'].get('search_query', ""))
        agree = request.form.get("agree", "")   # This is exclusively for dentist system
        filterStatus = request.form.get("filterStatus", "") 
        filterPriority = request.form.get("filterPriority", "") 
        filterProvince = request.form.get("filterProvince", "") 
        filterSpecialist = request.form.get("filterSpecialist", "")
        filterFollowup = request.form.get("filterFollowup", "")
        filterRetrain = request.form.get("filterRetrain", "")
        filterSender = request.form.get("filterSender", "")

        # Save filter parameters to the session 
        session['record_filter']['search_query'] = search_query
        session['record_filter']['agree'] = agree
        session['record_filter']['filterStatus'] = filterStatus
        session['record_filter']['filterPriority'] = filterPriority
        session['record_filter']['filterProvince'] = filterProvince
        session['record_filter']['filterSpecialist'] = filterSpecialist
        session['record_filter']['filterFollowup'] = filterFollowup
        session['record_filter']['filterRetrain'] = filterRetrain
        session['record_filter']['filterSender'] = filterSender
    else:
        # Load values from session or use an empty string
        search_query = session['record_filter'].get('search_query', "")
        agree = session['record_filter'].get("agree", "")   # This is exclusively for dentist system
        filterStatus = session['record_filter'].get("filterStatus", "") 
        filterPriority = session['record_filter'].get("filterPriority", "") 
        filterProvince = session['record_filter'].get("filterProvince", "") 
        filterSpecialist = session['record_filter'].get("filterSpecialist", "")
        filterFollowup = session['record_filter'].get("filterFollowup", "")
        filterRetrain = session['record_filter'].get("filterRetrain", "")
        filterSender = session['record_filter'].get("filterSender", "")

    page = request.args.get("page", session.get('current_record_page', 1), type=int)
    session['current_record_page'] = page
    session['records_per_page'] = 12

    paginated_data, supplemental_data, dataCount, osm_filter_data = record_osm_group(None)

    # Further process each item in paginated_data
    for item in paginated_data:
        item["formatted_created_at"] = item["created_at"].strftime("%d/%m/%Y %H:%M")

    if dataCount is not None:
        dataCount = dataCount['full_count']
    else:
        dataCount = 0
    total_pages = (dataCount - 1) // session['records_per_page'] + 1
    return render_template(
                "newTemplate/osm_group_record.html",
                dataCount=dataCount,
                paginated_data=paginated_data,
                current_page=page,
                total_pages=total_pages,
                data=supplemental_data,
                osm_filter_data=osm_filter_data)

# region get record_osm_group
# overloading
@singledispatch
def record_osm_group(_):
    page = session['current_record_page']
    records_per_page = session['records_per_page']

    return record_osm_group(page, records_per_page)

@record_osm_group.register
def _(page: int, records_per_page: int):
    # Construct filter query and supplemental data
    from aidoc.webapp import construct_osm_filter_sql
    filter_query, supplemental_data = construct_osm_filter_sql()

    # Add sender filter if present
    filter_sender = session['record_filter'].get('filterSender', "")
    if filter_sender:
        filter_query += f" AND (sender_id = {filter_sender})" if filter_query else f"(sender_id = {filter_sender})"
        supplemental_data['filterSender'] = filter_sender

    # Pagination
    offset = (page-1)*records_per_page

    db, cursor = get_db()

    # Retrieve OSM group members
    cursor.execute('''
        SELECT osm_id as sender_id, user.phone as sender_phone, user.name as osm_name, user.surname as osm_surname 
        FROM osm_group_member 
        LEFT JOIN user ON user.id = osm_group_member.osm_id 
        WHERE group_id = (SELECT group_id FROM osm_group WHERE osm_supervisor_id = %s)
    ''', (session['user_id'],))
    member_list = cursor.fetchall()

    osm_filter_data = [{
        'sender_id': member['sender_id'],
        'osm_name': f"{member['osm_name']} {member['osm_surname']}"
    } for member in member_list]


    # Construct group member conditions
    group_member_conditions = []
    group_member_values = []
    if filter_sender:
        #filter by sender_id
        filter_member = next((item for item in member_list if str(item["sender_id"]) == filter_sender), None)
        group_member_conditions.append("(submission_record.sender_id = %s OR (submission_record.sender_phone IS NOT NULL AND submission_record.sender_phone = %s))")
        group_member_values.extend([filter_member['sender_id'], filter_member['sender_phone']])
    else:
        for member in member_list:
            group_member_conditions.append("(submission_record.sender_id = %s OR (submission_record.sender_phone IS NOT NULL AND submission_record.sender_phone = %s))")
            group_member_values.extend([member['sender_id'], member['sender_phone']])

    group_member_sql = '(' + ' OR '.join(group_member_conditions) + ')'

    if filter_query:
        base_sql = '''
            SELECT 
                sr.id,
                sr.channel,
                sr.fname,
                sr.patient_name,
                sr.patient_surname,
                sr.birthdate,
                sr.province,
                sr.case_id,
                sr.sender_id,
                sr.patient_id,
                sr.dentist_id,
                sr.special_request,
                sr.sender_phone,
                sr.location_province,
                sr.location_zipcode,
                sr.dentist_feedback_comment,
                sr.dentist_feedback_code,
                sr.ai_prediction,
                sr.created_at,
                sr.sender_name,
                sr.sender_surname,
                sr.osm_phone,
                c.full_count
            FROM (
                SELECT 
                    submission_record.id,
                    submission_record.channel,
                    submission_record.fname,
                    patient_user.name AS patient_name,
                    patient_user.surname AS patient_surname,
                    patient_user.birthdate,
                    patient_user.province,
                    patient_case_id.case_id,
                    submission_record.sender_id,
                    submission_record.patient_id,
                    submission_record.dentist_id,
                    submission_record.special_request,
                    submission_record.sender_phone,
                    submission_record.location_province,
                    submission_record.location_zipcode,
                    submission_record.dentist_feedback_comment,
                    submission_record.dentist_feedback_code,
                    submission_record.ai_prediction,
                    submission_record.created_at,
                    osm_user.name as sender_name,
                    osm_user.surname as sender_surname,
                    osm_user.phone as osm_phone
                FROM (
                    SELECT id
                    FROM submission_record
                    WHERE ''' + group_member_sql + ''' AND channel = 'OSM'
                ) AS submission_record_limited
                INNER JOIN submission_record
                    ON submission_record.id = submission_record_limited.id
                LEFT JOIN patient_case_id
                    ON submission_record.id = patient_case_id.id
                LEFT JOIN user AS patient_user
                    ON submission_record.patient_id = patient_user.id
                LEFT JOIN user AS osm_user
                    ON submission_record.sender_id = osm_user.id
                WHERE ''' + filter_query + '''
                ORDER BY submission_record.created_at DESC
                LIMIT %s OFFSET %s
            ) AS sr
            CROSS JOIN (
                SELECT 
                    COUNT(submission_record.id) AS full_count
                FROM (
                    SELECT id
                    FROM submission_record
                    WHERE ''' + group_member_sql + ''' AND channel = 'OSM'
                ) AS submission_record_limited
                INNER JOIN submission_record
                    ON submission_record.id = submission_record_limited.id
                LEFT JOIN patient_case_id
                    ON submission_record.id = patient_case_id.id
                LEFT JOIN user AS patient_user
                    ON submission_record.patient_id = patient_user.id
                LEFT JOIN user AS osm_user
                    ON submission_record.sender_id = osm_user.id
                WHERE ''' + filter_query + '''
            ) AS c
            ORDER BY sr.created_at DESC;
            '''
        val = tuple(group_member_values + [records_per_page, offset] + group_member_values)
    else:
        base_sql = '''
            SELECT 
                sr.id,
                sr.channel,
                sr.fname,
                sr.patient_name,
                sr.patient_surname,
                sr.birthdate,
                sr.province,
                sr.case_id,
                sr.sender_id,
                sr.patient_id,
                sr.dentist_id,
                sr.special_request,
                sr.sender_phone,
                sr.location_province,
                sr.location_zipcode,
                sr.dentist_feedback_comment,
                sr.dentist_feedback_code,
                sr.ai_prediction,
                sr.created_at,
                sr.sender_name,
                sr.sender_surname,
                sr.osm_phone,
                c.full_count
            FROM (
                SELECT 
                    submission_record.id,
                    submission_record.channel,
                    submission_record.fname,
                    patient_user.name AS patient_name,
                    patient_user.surname AS patient_surname,
                    patient_user.birthdate,
                    patient_user.province,
                    patient_case_id.case_id,
                    submission_record.sender_id,
                    submission_record.patient_id,
                    submission_record.dentist_id,
                    submission_record.special_request,
                    submission_record.sender_phone,
                    submission_record.location_province,
                    submission_record.location_zipcode,
                    submission_record.dentist_feedback_comment,
                    submission_record.dentist_feedback_code,
                    submission_record.ai_prediction,
                    submission_record.created_at,
                    osm_user.name as sender_name,
                    osm_user.surname as sender_surname,
                    osm_user.phone as osm_phone
                FROM (
                    SELECT id
                    FROM submission_record
                    WHERE ''' + group_member_sql + ''' AND channel = 'OSM'
                    ORDER BY submission_record.created_at DESC
                    LIMIT %s OFFSET %s
                ) AS submission_record_limited
                INNER JOIN submission_record
                    ON submission_record.id = submission_record_limited.id
                LEFT JOIN patient_case_id
                    ON submission_record.id = patient_case_id.id
                LEFT JOIN user AS patient_user
                    ON submission_record.patient_id = patient_user.id
                LEFT JOIN user AS osm_user
                    ON submission_record.sender_id = osm_user.id
            ) AS sr
            CROSS JOIN (
                SELECT 
                    COUNT(submission_record.id) AS full_count
                FROM (
                    SELECT id
                    FROM submission_record
                    WHERE ''' + group_member_sql + ''' AND channel = 'OSM'
                ) AS submission_record_limited
                INNER JOIN submission_record
                    ON submission_record.id = submission_record_limited.id
            ) AS c
            ORDER BY sr.created_at DESC;
            '''
        val = tuple(group_member_values + [records_per_page, offset] + group_member_values)

    cursor.execute(base_sql, val)
    paginated_data = cursor.fetchall()
    
    if len(paginated_data) > 0:
        data_count = {'full_count': paginated_data[0]['full_count']}
    else:
        data_count = {'full_count': 0}

    # Process each record
    for item in paginated_data:
        if item['channel'] == 'PATIENT':
            item['owner_id'] = item['patient_id']
        else:
            item['owner_id'] = item['sender_id']
        if item.get('birthdate'):
            item['age'] = calculate_age(item['birthdate'])

    return paginated_data, supplemental_data, data_count, osm_filter_data


# render osm group manage page
# region Group Manage Render
@bp.route('/member-manage/', methods=['GET'])
@login_required
def render_osm_group_manage():
    load_osm_group_info() # Load group info to g.user['group_info']
    # Prevent not supervisor accesses
    if(g.user['group_info']['is_supervisor'] == 0 or g.user['group_info']['group_id'] == -1 ):
        return render_template('newTemplate/osm_group_manage.html', group_id=-1, is_user_supervisor=0, group_name="ไม่มีข้อมูล")
    
    user_id = session['user_id']
    db, cursor = get_db()

    cursor.execute(
        """
        SELECT 
            og.group_id, 
            og.group_name, 
            (ogm.osm_id = og.osm_supervisor_id) AS is_supervisor
        FROM osm_group_member AS ogm
        JOIN osm_group AS og ON ogm.group_id = og.group_id
        WHERE ogm.osm_id = %s
        """,
        (user_id,)
    )
    user_data = cursor.fetchone()

    if not user_data:
        return render_template(
            'newTemplate/osm_group_manage.html',
            group_id=-1,
            is_user_supervisor=0,
            group_name="ไม่มีข้อมูล"
        )

    group_id = user_data['group_id']
    is_supervisor = user_data['is_supervisor']
    group_name = user_data['group_name']
    return render_template(
        'newTemplate/osm_group_manage.html',
        group_id=group_id,
        is_user_supervisor=is_supervisor,
        group_name=group_name
    )


#region get_group_users
@bp.route('/group/<int:group_id>', methods=['GET'])
@login_required
def get_group_users(group_id):
    if group_id == -1:
        return jsonify({'group_list': []})

    db, cursor = get_db()
    cursor.execute(
        """
        SELECT 
            oh.group_id, oh.osm_id, (oh.osm_id = og.osm_supervisor_id) as is_supervisor, u.name, u.surname, u.hospital, u.province, u.phone,
            (SELECT COUNT(*) FROM submission_record WHERE sender_id = oh.osm_id AND channel = 'OSM') AS submission_count,
            (SELECT created_at FROM submission_record WHERE sender_id = oh.osm_id ORDER BY created_at DESC LIMIT 1) AS last_activity
        FROM osm_group_member oh
        LEFT JOIN user u ON oh.osm_id = u.id
        LEFT JOIN osm_group og ON oh.group_id = og.group_id
        WHERE oh.group_id = %s
        ORDER BY CASE WHEN (oh.osm_id = og.osm_supervisor_id) = 1 THEN 1 ELSE 2 END
        """,
        (group_id,)
    )

    hierarchy = cursor.fetchall()
    group_list = [
        {
            'osm_id': item['osm_id'],
            'name': item['name'],
            'surname': item['surname'],
            'is_supervisor': item['is_supervisor'],
            'hospital': item['hospital'],
            'province': item['province'],
            'submission_count': item['submission_count'],
            'phone_number': item['phone'],
            'last_activity': format_thai_datetime(item['last_activity']) if item['last_activity'] else '-'
        }
        for item in hierarchy if item['name'] and item['surname']
    ]

    return jsonify({'group_list': group_list})

# region add_user_to_group
@bp.route('/add', methods=['POST'])
@login_required
def add_user_to_group():
    request_data = request.get_json()
    if not request_data:
        return json.dumps({'error': 'No request data provided'}), 400

    user_id = request_data.get('user_id')
    group_id = request_data.get('group_id')

    if not user_id or not group_id:
        return json.dumps({'error': 'No user_id/group_id provided'}), 400

    if group_id == -1:
        return json.dumps({'error': 'Invalid group_id'}), 400

    db, cursor = get_db()
    cursor.execute(
        "SELECT 1 FROM osm_group_member WHERE osm_id = %s",
        (user_id,)
    )
    existing_member = cursor.fetchone()
    if existing_member:
        return json.dumps({'error': 'User is already in another group'}), 400

    cursor.execute(
        "INSERT INTO osm_group_member (group_id, osm_id) VALUES (%s, %s)",
        (group_id, user_id)
    )
    return json.dumps({'message': 'User added to group'}), 200
    

# region remove_from_group
@bp.route('/remove', methods=['DELETE'])
@login_required
def remove_from_group():
    request_body = request.get_json()
    if not request_body or 'user_id' not in request_body or 'group_id' not in request_body:
        return json.dumps({'error': 'No user_id/group_id provided'}), 400
    user_id = request_body['user_id']
    group_id = request_body['group_id']

    if group_id == -1:
        return json.dumps({'error': 'Invalid group_id'}), 400

    db, cursor = get_db()
    cursor.execute(
        "DELETE FROM osm_group_member WHERE osm_id = %s AND group_id = %s",
        (user_id, group_id)
    )
    return json.dumps({"message": "User removed from group."}), 200

# region get_osm_for_search
@bp.route('/get_osm_for_search', methods=['GET'])
@login_required
def get_osm_for_search():
    user_id = session.get('user_id')
    db, cursor = get_db()

    # Get the current user's province
    cursor.execute("SELECT group_provinces FROM osm_group WHERE osm_supervisor_id = %s", (user_id,))
    provinces = cursor.fetchone()["group_provinces"]
    print("asdasdjnsadhasdhusauhd",provinces)
    if not provinces:
        return jsonify({'osm_list': []})
    
    sql = """
        SELECT id, name, surname, phone as phone_number, province, hospital
        FROM user
        WHERE is_osm = 1
        AND id NOT IN (SELECT osm_id FROM osm_group_member)
        """
    where_provinces = ""
    provinces_list = provinces.split(",")
    for province in provinces_list:
        where_provinces += f"province = '{province}' OR "
    sql += "AND (" + where_provinces[:-3] + ")"

    cursor.execute(sql)
    # Search for OSM users in the same province
    
    osm_users = cursor.fetchall()

    return jsonify({
        'osm_list': osm_users
    })

# region promote_supervisor
@bp.route('/promote_supervisor/', methods=['POST', 'DELETE', 'PUT',])
# @login_required
def promote_supervisor():
    user_id = request.get_json()['user_id']

    # Check if user_id is provided
    if not user_id:
        return jsonify({'error': 'No osm_id provided'}), 400

    db, cursor = get_db()

    
    if request.method == 'POST':
        # Check if user is already a supervisor
        cursor.execute(
            "SELECT group_id FROM osm_group WHERE osm_supervisor_id = %s",
            (user_id,)
        )
        existing_group = cursor.fetchone()
        if existing_group:
            return jsonify({'error': 'User is already a supervisor'}), 400

        # Check if user is a member remove from groups and add as supervisor
        cursor.execute(
            "SELECT group_id FROM osm_group_member WHERE osm_id = %s",
            (user_id,)
        )
        existing_member = cursor.fetchall()
        if existing_member:
            cursor.execute(
                "DELETE FROM osm_group_member WHERE osm_id = %s",
                (user_id,)
            )
        # group_provinces = request.get_json()['group_provinces_string'] if request.get_json()['group_provinces_string'] else ''
        # Create a new group and add the user as a member
        cursor.execute(
            "INSERT INTO osm_group (osm_supervisor_id, group_name) VALUES (%s, NULL)",
            (user_id,)
        )
        new_group_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO osm_group_member (group_id, osm_id) VALUES (%s, %s)",
            (new_group_id, user_id)
        )
    elif request.method == 'DELETE':
        # Remove the user from the group
        cursor.execute(
            "SELECT group_id FROM osm_group WHERE osm_supervisor_id = %s",
            (user_id,)
        )
        is_supervisor = cursor.fetchone()
        if not is_supervisor:
            return jsonify({'error': 'User is not a supervisor'}), 400
        
        # Remove the user from the group and delete the group
        cursor.execute(
            "DELETE osm_group_member FROM osm_group_member "
            "JOIN (SELECT group_id FROM osm_group WHERE osm_supervisor_id = %s) AS subquery "
            "ON osm_group_member.group_id = subquery.group_id",
            (user_id,)
        )
        cursor.execute(
            "DELETE FROM osm_group WHERE osm_supervisor_id = %s",
            (user_id,)
        )
    elif request.method == 'PUT':
        # Update provinces of the group
        group_provinces = request.get_json()['group_provinces_string']
        cursor.execute(
            "SELECT group_id FROM osm_group WHERE osm_supervisor_id = %s",
            (user_id,)
        )
        group_id = cursor.fetchone()

        cursor.execute(
            "UPDATE osm_group SET group_provinces = %s WHERE group_id = %s",
            (group_provinces, group_id["group_id"],)
        )
    return jsonify({'message': 'Supervisor removed successfully'}), 200

# region is_supervisor
@bp.route('/is_supervisor/<int:user_id>', methods=['GET'])
@login_required
def is_supervisor(user_id):
    is_supervisor = False
    group_provinces_list = [] 
    db, cursor = get_db()
    cursor.execute(
        """
            SELECT group_id, group_provinces FROM osm_group WHERE osm_supervisor_id = %s LIMIT 1;
        """,
        (user_id,)
    )
    data = cursor.fetchone()

    if data:
        is_supervisor = True
        group_provinces_list = data["group_provinces"].split(",") if data["group_provinces"] else []
    return jsonify({"is_supervisor": is_supervisor, "group_provinces": group_provinces_list}), 200

# region update_group_name
@bp.route('/update_group_name/', methods=['POST'])
@login_required
def update_group_name():
    group_id = request.json.get('group_id')
    group_name = request.json.get('group_name')

    if not group_id or not group_name:
        return jsonify({'error': 'Group ID and group_name are required'}), 400

    db, cursor = get_db()
    cursor.execute(
        "UPDATE osm_group SET group_name = %s WHERE group_id = %s",
        (group_name, group_id)
    )
    return jsonify({'message': 'Name updated successfully'}), 200

# region get_all_provinces
@bp.route('/get_all_provinces/', methods=['GET'])
# @login_required
def get_all_provinces():
    db, cursor = get_db()
    cursor.execute('SELECT name_th FROM thai_provinces')
    provinces = cursor.fetchall()
    if not provinces:
        return jsonify({'provinces': []}) 

    provinces_list = [province['name_th'] for province in provinces]
    return jsonify({'provinces': provinces_list}), 200


# region load osm group info
# load_osm_group_info
def load_osm_group_info():
    user = g.get('user')
    if not user:
        return
    group_info = load_osm_group_info_query(user['id'])
    session['g_user']['group_info'] = group_info
    g.user['group_info'] = group_info