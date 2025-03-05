from datetime import datetime
from flask import Blueprint, jsonify, request
from aidoc.auth import login_required
from aidoc.db import get_db, get_db_risk_oca
import re

from aidoc.utils import get_app_metadata, save_app_metadata

risk_oca_bp = Blueprint('risk_oca', __name__)

def questionnaire_date_status(questionnaire_date):
    if questionnaire_date and questionnaire_date != '':
        try:
            dt = datetime.strptime(questionnaire_date, '%Y-%m-%dT%H:%M:%S.%f')
            if (datetime.now() - dt).days < 180:  # within 6 months
                return 0, questionnaire_date
            else: return 1, questionnaire_date
        except ValueError:
            if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}$', questionnaire_date):
                return 1, questionnaire_date # format 2020-00-00 00:00:00.000000 is invalid assume outdated data and not save date to db
    return 2, None

def save_questionnaire(user_id, data):
    db, cursor = get_db()
    cursor.execute('''
        INSERT INTO `user_risk_oca` (user_id, risk_oca_id, risk_oca, risk_oca_latest)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            risk_oca_id = %s,
            risk_oca = %s,
            risk_oca_latest = %s
    ''', (user_id, data['qid'], data['risk'], data['latest'], data['qid'], data['risk'], data['latest']))

def fetch_patients():
    db, cursor = get_db()
    cursor.execute('''
        SELECT DISTINCT id, national_id, risk_oca_id 
        FROM user 
        LEFT JOIN user_risk_oca ON user.id = user_risk_oca.user_id 
        WHERE user.is_patient = 1 AND user.national_id IS NOT NULL AND user.national_id != "";
        ''')
    return cursor.fetchall()


def fetch_questionnaires(patient):
    db_risk, cursor_risk = get_db_risk_oca()
    patient_ids = set(p['national_id'] for p in patient)
    cid_where = "cid IN ({})".format(",".join(["%s"] * len(patient_ids)))
    sql = f'''
            SELECT id, cid, today
            FROM questionnaire q1
            WHERE {cid_where}
            AND id = (
                SELECT id
                FROM questionnaire q2
                WHERE q2.cid = q1.cid
                ORDER BY today DESC, id DESC
                LIMIT 1
            )
        '''
    cursor_risk.execute(sql, tuple(patient_ids))
    return cursor_risk.fetchall()

def join_questionnaires(patient, questionnaires):
    questionnaire_dict = {q['cid']: q for q in questionnaires}
    data = [
        {
            'patient_id': p['id'],
            'qid': q['id'],
            'latest': q['today'],
            'risk': None
        }
        for p in patient 
        if p['national_id'] in questionnaire_dict
        for q in [questionnaire_dict[p['national_id']]]
    ]
    return data

def update_user_risk_oca(data, patient):
    update_count = 0
    for d in data:
        stored_qid = next((p['risk_oca_id'] for p in patient if p['id'] == d['patient_id']), None)
        if stored_qid is None or stored_qid != d['qid']:
            risk, latest = questionnaire_date_status(d['latest'])
            d['risk'] = risk
            d['latest'] = latest
            save_questionnaire(d['patient_id'], d)
            update_count += 1
    return update_count

@risk_oca_bp.route('/sync_risk_oca', methods=['POST'])
@login_required
def retrieve_and_update_risk_oca():
    patient = fetch_patients()
    questionnaires = fetch_questionnaires(patient)

    data = join_questionnaires(patient, questionnaires)
        
    update_count = update_user_risk_oca(data, patient)

    save_app_metadata('last_risk_oca_update', datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"))

    return jsonify({"update_count" : update_count, "update_date": get_app_metadata('last_risk_oca_update')}), 200