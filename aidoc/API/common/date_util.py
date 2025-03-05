from datetime import datetime

def format_date_to_mmddyyyy_time(date):
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
    
    return date.strftime("%m/%d/%Y %H:%M")
