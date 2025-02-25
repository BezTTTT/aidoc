from ... import db
import json
from decimal import Decimal
from ..common import common_mapper as cm
from datetime import datetime

def get_all_submission(province,start_date, end_date):
    connection, cursor = db.get_db()
    try:
        with cursor:
            ai_predict_query,total_pic = fetch_all_ai_predictions_count(cursor, province,start_date, end_date)
            
            ai_predict = cm.map_ai_prediction_list(ai_predict_query)
            if not ai_predict:
                ai_predict = {"normal": 0, "opmd": 0, "oscc": 0}
                total_pic = 0
            
            output = {
                'total_pic': total_pic,
                'ai_predict': ai_predict
            }

    except Exception as e:
        print(f"Error occurred: {e}")
        return {
            "ai_predict": {
                "normal": 0, "opmd": 0, "oscc": 0},
            "total_pic": 0
        }
        
    return output

def fetch_all_ai_predictions_count(cursor, province=None, start_date=None, end_date=None):
    # Handle default dates
    if start_date is None:
        cursor.execute("SELECT MIN(created_at) AS min_date FROM submission_record")
        result = cursor.fetchone()
        start_date = result['min_date']
    
    if end_date is None:
        cursor.execute("SELECT NOW() AS end_date")
        result = cursor.fetchone()
        end_date = result['end_date']

    # Prepare query based on whether province is provided
    if province is None:
        query = """
            SELECT ai_prediction, COUNT(*) as N 
            FROM submission_record AS sr
            WHERE sr.created_at >= %s
            AND sr.created_at <= %s
            GROUP BY ai_prediction
        """
        cursor.execute(query, (start_date, end_date))
    else:
        query = """
            SELECT ai_prediction, COUNT(*) as N 
            FROM submission_record AS sr
            WHERE sr.location_province = %s
            AND sr.created_at >= %s
            AND sr.created_at <= %s
            GROUP BY ai_prediction
        """
        cursor.execute(query, (province, start_date, end_date))

    ai_predict_query = cursor.fetchall()
    total_pic = sum(item['N'] for item in ai_predict_query)

    return ai_predict_query, total_pic


