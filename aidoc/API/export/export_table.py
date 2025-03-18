import os
import tempfile
from flask import Blueprint, after_this_request, g, request, jsonify, send_file
from aidoc.auth import login_required
import pandas as pd
import sys
import threading
import time

from aidoc.osm_group import record_osm_group

export_bp = Blueprint('export_bp', __name__)

TEMP_DIR = os.path.join(os.getcwd(), "aidoc/API/export/tmp")
os.makedirs(TEMP_DIR, exist_ok=True)

@export_bp.route('/<string:table_name>/', methods=['GET'])
@login_required
def export_table(table_name):
    if not g.user.get('group_info') or (g.user['group_info']['is_supervisor'] == 0 or g.user['group_info']['group_id'] == -1):
        return jsonify({"error": "You don't have permission to export this table"}), 403
    
    format = request.args.get("format", "csv")  # Default to CSV
    columns = request.args.get("columns", "").split(",")

    # Fetch data
    df = db_query(table_name, "osm_group", columns)

    # Create a temporary file
    fd, tmp_file_path = tempfile.mkstemp(suffix=f".{format}", dir=TEMP_DIR)
    os.close(fd)

    if format == 'xlsx':
        with pd.ExcelWriter(tmp_file_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
    elif format == 'csv':
        df.to_csv(tmp_file_path, index=False)
    else:
        return jsonify({"error": "Invalid format"}), 400
    
    def async_cleanup(file_path):
        time.sleep(5)  # Delay to ensure file is sent
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error removing temporary file: {e}")

    @after_this_request
    def cleanup(response):
        threading.Thread(target=async_cleanup, args=(tmp_file_path,), daemon=True).start()
        return response

    return send_file(
        tmp_file_path,
        as_attachment=True,
        download_name=f"exported_data.{format}",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if format == 'xlsx' else "text/csv",
        conditional=True
    )


def db_query(table_name,ref, columns):
    if columns != "":
        data = []
        if ref == "osm_group":
            if table_name == "osm_group_record":
                result = record_osm_group(1, sys.maxsize) # get all group records
                if isinstance(result, tuple) and len(result) >= 1:
                    data = result[0]
                else:
                    data = result 

                if data:
                    for i, d in enumerate(data): # add image url to data
                        img_url = f"{request.host_url}load_image/upload/{d['sender_id']}/{d['fname']}"
                        data[i]["fname"] = f'=HYPERLINK("{img_url}","{data[i]["fname"]}")' # construct image url for excel
                        #print(data[i]["fname"])
                
        else: pass # for future use

        df = pd.DataFrame(data) 

        valid_columns = [col for col in columns if col in df.columns]
        df = df[valid_columns]
    else: # return empty if no columns specified
        df = pd.DataFrame()

    return df