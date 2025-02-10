from ... import db
import json
from collections import defaultdict

from .report_mapper import map_query_to_output_specialist

def get_table(province):
    connection, cursor = db.get_db()
    try:
        with cursor:
            ai_predict_query, dentist_diagnose_query = fetch_data(cursor, province)
            output =  map_query_to_output_specialist(ai_predict_query, dentist_diagnose_query)
    except Exception as e:
        print(f"Error: {e}")
        return {
            "accuracy": "-",
            "ai_predict": {"normal": 0, "opmd": 0, "oscc": 0},
            "dentist_diagnose": {"agree": 0, "disagree": 0},
            "total_pic": 0
        }
        
    return output

def fetch_data(cursor, province):
    ai_predict_query = fetch_ai_predictions_dentist_table(cursor, province)
    dentist_diagnose_query = fetch_dentist_diagnoses(cursor, province)
    return ai_predict_query, dentist_diagnose_query

def fetch_ai_predictions_dentist_table(cursor, province):
    query = """
        SELECT 
            job_position_mapping.job_position,
            ai_prediction_mapping.ai_prediction, 
            COALESCE(SUM(submission_counts.N), 0) AS N
        FROM 
            (SELECT DISTINCT u.job_position 
            FROM submission_record sr 
            LEFT JOIN user u
            ON u.id = sr.sender_id 
            WHERE u.job_position IS NOT NULL 
            AND sr.channel = 'DENTIST' 
            AND (%s IS NULL OR sr.location_province = %s)) AS job_position_mapping
        CROSS JOIN 
            (SELECT 0 AS ai_prediction
            UNION ALL
            SELECT 1
            UNION ALL
            SELECT 2) AS ai_prediction_mapping
        LEFT JOIN 
            (SELECT 
                u.job_position, 
                sr.ai_prediction, 
                COUNT(*) AS N 
            FROM submission_record sr 
            LEFT JOIN user u 
            ON u.id = sr.sender_id 
            WHERE sr.channel = 'DENTIST' 
            AND (%s IS NULL OR sr.location_province = %s)
            GROUP BY u.job_position, sr.ai_prediction) AS submission_counts
        ON 
            job_position_mapping.job_position = submission_counts.job_position 
            AND ai_prediction_mapping.ai_prediction <=> submission_counts.ai_prediction
        GROUP BY 
            job_position_mapping.job_position, 
            ai_prediction_mapping.ai_prediction;
    """
    cursor.execute(query, (province, province, province, province,))
    return cursor.fetchall()

def fetch_dentist_diagnoses(cursor, province):
    query = """
        SELECT 
            job_position_mapping.job_position,
            dentist_feedback_code_mapping.dentist_feedback_code, 
            COALESCE(SUM(submission_counts.N), 0) AS N
        FROM 
            (SELECT DISTINCT u.job_position 
            FROM submission_record sr 
            LEFT JOIN user u
            ON u.id = sr.sender_id 
            WHERE u.job_position IS NOT NULL 
            AND sr.channel = 'DENTIST' 
            AND (%s IS NULL OR sr.location_province = %s)) AS job_position_mapping
        CROSS JOIN 
            (SELECT 'AGREE' AS dentist_feedback_code
            UNION ALL
            SELECT 'DISAGREE'
            UNION ALL
            SELECT NULL) AS dentist_feedback_code_mapping
        LEFT JOIN 
            (SELECT 
                u.job_position, 
                sr.dentist_feedback_code, 
                COUNT(*) AS N
            FROM submission_record sr
            LEFT JOIN user u 
            ON u.id = sr.sender_id 
            WHERE sr.channel = 'DENTIST' 
            AND (%s IS NULL OR sr.location_province = %s)
            GROUP BY u.job_position, sr.dentist_feedback_code) AS submission_counts
        ON 
            job_position_mapping.job_position = submission_counts.job_position 
            AND dentist_feedback_code_mapping.dentist_feedback_code <=> submission_counts.dentist_feedback_code
        GROUP BY 
            job_position_mapping.job_position, 
            dentist_feedback_code_mapping.dentist_feedback_code;
    """
    cursor.execute(query, (province, province, province, province,))
    return cursor.fetchall()

