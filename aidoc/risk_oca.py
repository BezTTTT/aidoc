from datetime import datetime
from flask import Blueprint, jsonify, request
from aidoc.db import get_db, get_db_risk_oca
import re

risk_oca_bp = Blueprint('risk_oca', __name__)



def get_questionnaire(cid):
    db, cursor = get_db_risk_oca()
    cursor.execute('''
        SELECT 
            id, cid, today
        FROM `questionnaire` WHERE cid = %s 
        ORDER BY today DESC, id DESC
        LIMIT 1;
        ''', (cid,))
    questionnaire = cursor.fetchone()
    if not questionnaire:
        return {'risk': 2, 'latest': None, 'qid': None} # no risk oca record
    
    if questionnaire['today']:
        # check if within 6 months
        try:
            if 'T' in questionnaire['today']:
                today = datetime.strptime(questionnaire['today'], '%Y-%m-%dT%H:%M:%S.%f')
            else:
                today = datetime.strptime(questionnaire['today'], '%Y-%m-%d %H:%M:%S.%f')
        except:
            return {'risk': 2, 'latest': None, 'qid': None} # if invalid format assume no record
        
        if (datetime.now() - today).days < 180: # within 6 months
            return {'risk': 0, 'latest': questionnaire['today'], 'qid': questionnaire['id']}
        else:
            return {'risk': 1, 'latest': questionnaire['today'], 'qid': questionnaire['id']}

    return {'risk': questionnaire_to_dict(questionnaire), 'latest': questionnaire['today'], 'qid': questionnaire['id']}

def questionnaire_to_dict(questionnaire):
    return 1 if questionnaire['c09_1'] == 'yes' else 0

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

@risk_oca_bp.route('/risk_oca', methods=['GET'])
def retrieve_and_update_risk_oca():
    patient_id = request.args.get('patient_id')
    print(patient_id)
    if not patient_id:
        return jsonify({'risk': -1, 'latest': '', 'error': 'patient_id is required'}), 400

    db, cursor = get_db()

    cursor.execute('''
        SELECT national_id, risk_oca_id 
        FROM `user` 
        LEFT JOIN `user_risk_oca` ON `user`.id = `user_risk_oca`.user_id 
        WHERE `user`.id = %s;
        ''', (patient_id,))
    
    patient = cursor.fetchone()

    ques = get_questionnaire(patient['national_id'])

    # if questionnaire is not exist in oralcancer, get it from user_risk_oca
    # if not ques:
    #     cursor.execute('''
    #         SELECT risk_oca_id, risk_oca, risk_oca_latest 
    #         FROM `user_risk_oca` 
    #         WHERE user_id = %s;
    #         ''', (patient_id,))
    #     ques = cursor.fetchone()

    # if not have new questionnaire data, save it to user_risk_oca aidoc
    if str(ques['qid']) != str(patient['risk_oca_id']):
        save_questionnaire(patient_id, ques)

    return jsonify({'risk':ques['risk'], 'latest':ques['latest'], 'qid':ques['qid']}), 200  



