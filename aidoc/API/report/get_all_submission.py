from ... import db
import json
from decimal import Decimal
from ..common import common_mapper as cm

def get_all_submission(province):
    connection, cursor = db.get_db()
    try:
        with cursor:
            ai_predict_query,total_pic = fetch_all_ai_predictions_count(cursor, province)
            
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
    
    finally:
        db.close_db()
        
    return output

def fetch_all_ai_predictions_count(cursor, province):
    if province is None:
        query = """
            SELECT ai_prediction, COUNT(*) as N 
            FROM submission_record
            GROUP BY ai_prediction
        """
        cursor.execute(query)
    else:
        query = """
            SELECT ai_prediction, COUNT(*) as N 
            FROM submission_record
            WHERE location_province = %s
            GROUP BY ai_prediction
        """
        cursor.execute(query, (province,))

    ai_predict_query = cursor.fetchall()
    
    total_pic = sum(item['N'] for item in ai_predict_query)

    return ai_predict_query, total_pic


