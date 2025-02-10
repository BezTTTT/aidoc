from ... import db
import json
from decimal import Decimal
from ..common import common_mapper as cm

def get_table(channel, province):
    connection, cursor = db.get_db()
    try:
        with cursor:
            ai_predict_query, total_pic = fetch_ai_predictions_patient_osm_table(cursor, channel, province)
            ai_predict = cm.map_ai_prediction_list(ai_predict_query)

            dentist_diagnose_query = fetch_dentist_feedback(cursor, channel, province)
            dentist_diagnose = cm.map_dentist_diagnosis(dentist_diagnose_query)

            diagnosed_submission_query = fetch_diagnosed_submission(cursor, channel, province)
            true_predict = calculate_true_predict(diagnosed_submission_query)
            sum_dent_diagnose = sum_dent_diagnose = sum(value for key, value in dentist_diagnose.items() if key in ['normal', 'opmd', 'oscc'])
            if sum_dent_diagnose == 0:
                accuracy = "-"
            else:
                accuracy = Decimal(true_predict / sum_dent_diagnose * 100).quantize(Decimal('0.01'))

            output = {
                'ai_predict': ai_predict,
                'dentist_diagnose': dentist_diagnose,
                'total_pic': total_pic,
                'accuracy': accuracy
            }

    except Exception as e:
        print(f"Error occurred: {e}")
        output = {
            "accuracy": "-",
            "ai_predict": {"normal": 0, "opmd": 0, "oscc": 0},
            "dentist_diagnose": {"normal": 0, "not_diagnosed": 0, "opmd": 0, "oscc": 0, "others": 0, "poor_image": 0},
            "total_pic": 0
        }

    return output


def fetch_ai_predictions_patient_osm_table(cursor, channel, province):
    
    query ="""
    SELECT ai_prediction_mapping.ai_prediction, COUNT(sr.ai_prediction) AS N
    FROM (
        SELECT 0 AS ai_prediction
        UNION ALL
        SELECT 1
        UNION ALL
        SELECT 2
    ) AS ai_prediction_mapping
    LEFT JOIN submission_record sr
        ON sr.channel = %s 
        AND sr.ai_prediction = ai_prediction_mapping.ai_prediction
        AND (%s IS NULL OR sr.location_province = %s)  
    GROUP BY ai_prediction_mapping.ai_prediction
    ORDER BY ai_prediction_mapping.ai_prediction ASC;
    """
    cursor.execute(query, (channel, province,province,))

    ai_predict_query = cursor.fetchall()
    total_pic = sum(item['N'] for item in ai_predict_query)
    
    return ai_predict_query, total_pic


def fetch_dentist_feedback(cursor, channel, province):
    query = """
    SELECT dentist_feedback_code_mapping.dentist_feedback_code, 
           COALESCE(SUM(submission_counts.N), 0) AS N
    FROM (SELECT 'OSCC' AS dentist_feedback_code
          UNION ALL SELECT 'OPMD' 
          UNION ALL SELECT 'Normal' 
          UNION ALL SELECT 'BAD_IMG' 
          UNION ALL SELECT 'OTHER' 
          UNION ALL SELECT 'Not_diagnosed') AS dentist_feedback_code_mapping
    LEFT JOIN (SELECT dentist_feedback_code, COUNT(*) as N
               FROM submission_record sr 
               WHERE sr.channel = %s
               AND (%s IS NULL OR sr.location_province = %s)
            GROUP BY sr.dentist_feedback_code) AS submission_counts
    ON dentist_feedback_code_mapping.dentist_feedback_code = submission_counts.dentist_feedback_code
    OR (dentist_feedback_code_mapping.dentist_feedback_code = 'Not_diagnosed'
        AND submission_counts.dentist_feedback_code IS NULL)
    GROUP BY dentist_feedback_code_mapping.dentist_feedback_code;
        """
    cursor.execute(query, (channel, province, province,))

    return cursor.fetchall()


def fetch_diagnosed_submission(cursor, channel, province):
    query = """
        SELECT 
        ai_prediction, 
        dentist_feedback_code
        FROM submission_record sr
        WHERE sr.channel = %s
        AND (%s IS NULL OR sr.location_province = %s)  
        AND sr.dentist_feedback_code IS NOT NULL
        AND sr.dentist_feedback_code IN ('NORMAL', 'OPMD', 'OSCC');
        """
    cursor.execute(query, (channel, province, province,))

    return cursor.fetchall()

def calculate_true_predict(input_data):
    prediction_mapping = {0: "NORMAL", 1: "OPMD", 2: "OSCC"}
    true_predict = sum(
        1 for item in input_data
        if prediction_mapping.get(item['ai_prediction']) == item['dentist_feedback_code']
    )
    return true_predict

