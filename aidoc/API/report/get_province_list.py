import json
from ... import db


def generate_province_list():
    connection, cursor = db.get_db()
    try:
        with cursor:
            province_list = fetch_informed_province(cursor)
            output = [row['location_province'] for row in province_list]
    except Exception as e:
        print(f"Error occurred: {e}")
        return json.dumps({"error": f"An error occurred while generate province list: {e}"}), 500
        
    return output

def fetch_informed_province(cursor):
    query = """
        SELECT location_province 
        FROM (
            SELECT location_province, COUNT(*) AS record_count
            FROM submission_record sr
            GROUP BY location_province
        ) AS province_counts  -- Alias added for the subquery
        ORDER BY record_count DESC
    """
    cursor.execute(query)
    return cursor.fetchall()