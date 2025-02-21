from ... import db
import json
from collections import defaultdict
from datetime import datetime

from .report_mapper import map_query_to_output_specialist

def get_table(province, start_date, end_date):
    connection, cursor = db.get_db()
    try:
        with cursor:
            ai_predict_query, dentist_diagnose_query = fetch_data(cursor, province, start_date, end_date)
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

def fetch_data(cursor, province, start_date, end_date):
    ai_predict_query = fetch_ai_predictions_dentist_table(cursor, province, start_date, end_date)
    dentist_diagnose_query = fetch_dentist_diagnoses(cursor, province, start_date, end_date)
    return ai_predict_query, dentist_diagnose_query

def fetch_ai_predictions_dentist_table(cursor, province, start_date, end_date):
    if start_date is None or end_date is None:
        if start_date is None:
            cursor.execute("SELECT MIN(created_at) AS min_date FROM submission_record WHERE channel = 'DENTIST'")
            result = cursor.fetchone()
            start_date = result['min_date']
        if end_date is None:
            cursor.execute("SELECT NOW() AS end_date")
            result = cursor.fetchone()
            end_date = result['end_date']
        
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
            AND (%s IS NULL OR sr.location_province = %s)
            AND sr.created_at >= %s
            AND sr.created_at <= %s) AS job_position_mapping
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
            AND sr.created_at >= %s
            AND sr.created_at <= %s
            GROUP BY u.job_position, sr.ai_prediction) AS submission_counts
        ON 
            job_position_mapping.job_position = submission_counts.job_position 
            AND ai_prediction_mapping.ai_prediction <=> submission_counts.ai_prediction
        GROUP BY 
            job_position_mapping.job_position, 
            ai_prediction_mapping.ai_prediction;
    """
    cursor.execute(query, (
        province, province, start_date, end_date,  # First subquery parameters
        province, province, start_date, end_date   # Second subquery parameters
    ))
    return cursor.fetchall()

def fetch_dentist_diagnoses(cursor, province, start_date, end_date):
    if start_date is None or end_date is None:
        if start_date is None:
            cursor.execute("SELECT MIN(created_at) AS min_date FROM submission_record WHERE channel = 'DENTIST'")
            result = cursor.fetchone()
            start_date = result['min_date']
        if end_date is None:
            cursor.execute("SELECT NOW() AS end_date")
            result = cursor.fetchone()
            end_date = result['end_date']
    
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
            AND (%s IS NULL OR sr.location_province = %s)
            AND sr.created_at >= %s
            AND sr.created_at <= %s) AS job_position_mapping
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
            AND sr.created_at >= %s
            AND sr.created_at <= %s
            GROUP BY u.job_position, sr.dentist_feedback_code) AS submission_counts
        ON 
            job_position_mapping.job_position = submission_counts.job_position 
            AND dentist_feedback_code_mapping.dentist_feedback_code <=> submission_counts.dentist_feedback_code
        GROUP BY 
            job_position_mapping.job_position, 
            dentist_feedback_code_mapping.dentist_feedback_code;
    """
    # Execute query with all parameters
    cursor.execute(query, (
        province, province, start_date, end_date,  # First subquery parameters
        province, province, start_date, end_date   # Second subquery parameters
    ))
    return cursor.fetchall()

