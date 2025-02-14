import json
import os
import pandas as pd
from ... import db
from datetime import datetime

from flask import current_app
def generate_summaries_by_day(year=None,start_date=None,end_date=None, province=None):
    connection, cursor = db.get_db()
    try:
        with cursor:
            # Base query
            sql = """
                SELECT
                    COUNT(*) AS count,
                    {}
                FROM
                    submission_record sr
                WHERE
                    1=1
            """
            # Initialize query parts
            where_clauses = []
            group_by = []
            select_by = []          

            group_by.append("DATE(sr.created_at)")
            select_by.append("DATE(sr.created_at) AS date")
                

            # Add province condition
            if province:
                where_clauses.append("sr.location_province = %s")
            else:
                group_by.append("sr.location_province")
                select_by.append("sr.location_province AS province")

            # Finalize WHERE and GROUP BY clauses
            if where_clauses:
                sql += " AND " + " AND ".join(where_clauses)
            if group_by:
                sql += " GROUP BY " + ", ".join(group_by)

            # Format the SELECT clause based on grouping
            select_fields = ", ".join(select_by) if select_by else "'All'"
            sql = sql.format(select_fields)

            # Execute query
            params = []
            if province:
                params.append(province)
            cursor.execute(sql, tuple(params))
            ai_predict_query = cursor.fetchall()
            ai_predict_query = filter_by_date_range(ai_predict_query, start_date, end_date)
            ai_predict_query = filter_by_year(ai_predict_query, year)
            # Extract column names from the first object in ai_predict_query
            columns = list(ai_predict_query[0].keys()) if ai_predict_query else []
            # Create DataFrame from query result
            df = pd.DataFrame(ai_predict_query, columns=columns)
            print(sql)
            filename = 'output.xlsx'  
            testDir = os.path.join(current_app.config['IMAGE_DATA_DIR'], 'test')
            filePath = os.path.join(testDir, filename)
            df.to_excel(filePath, index=False)
            
            if province:
                output_data = [{**entry, "province": province} for entry in ai_predict_query]
            else:
                output_data = ai_predict_query

    except Exception as e:
        print(f"Error occurred: {e}")
        return {}, 500

    return output_data

from datetime import datetime

def filter_by_date_range(data, start_date=None, end_date=None):
    """
    Filter objects based on date range.
    
    Args:
        data (list): List of dictionaries containing 'date' and 'count'
        start_date (str): Start date in format 'YYYY-MM-DD'
        end_date (str): End date in format 'YYYY-MM-DD'
    
    Returns:
        list: Filtered list of dictionaries
    """
    # If no dates provided, return original data
    if not start_date and not end_date:
        return data
    
    # Convert start_date and end_date strings to date objects
    start_dt = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
    
    # Filter the data
    filtered_data = []
    
    for item in data:
        try:
            # First try parsing as GMT format
            item_date = datetime.strptime(str(item['date']), '%a, %d %b %Y %H:%M:%S GMT').date()
        except ValueError:
            try:
                # If that fails, try parsing as YYYY-MM-DD format
                item_date = datetime.strptime(str(item['date']), '%Y-%m-%d').date()
            except ValueError as e:
                print(f"Could not parse date {item['date']}: {e}")
                continue
        
        # Check if date is within range
        is_after_start = True if not start_dt else item_date >= start_dt
        is_before_end = True if not end_dt else item_date <= end_dt
        
        if is_after_start and is_before_end:
            filtered_data.append(item)
    
    return filtered_data

def filter_by_year(data, year=None):
    """
    Filter objects based on a specific year.
    
    Args:
        data (list): List of dictionaries containing 'date' and 'count'.
        year (int): Year to filter data.
    
    Returns:
        list: Filtered list of dictionaries.
    """
    if not year:
        return data  # If no year is specified, return unfiltered data.

    filtered_data = []

    for item in data:
        try:
            # First try parsing as GMT format
            item_date = datetime.strptime(str(item['date']), '%a, %d %b %Y %H:%M:%S GMT').date()
        except ValueError:
            try:
                # If that fails, try parsing as YYYY-MM-DD format
                item_date = datetime.strptime(str(item['date']), '%Y-%m-%d').date()
            except ValueError as e:
                print(f"Could not parse date {item['date']}: {e}")
                continue

        # Check if the year matches
        if str(item_date.year) == str(year):
            filtered_data.append(item)

    return filtered_data