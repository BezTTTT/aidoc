import os
import tempfile
from flask import Blueprint, after_this_request, app, g, request, jsonify, send_file, session
from aidoc.auth import login_required, role_validation
from aidoc.db import get_db
import pandas as pd
import sys

from aidoc.osm_group import record_osm_group

export_bp = Blueprint('export_bp', __name__)

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
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}")


    if format == 'xlsx':
        with pd.ExcelWriter(tmp_file.name, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
    elif format == 'csv':
        df.to_csv(tmp_file.name, index=False)
    else:
        return jsonify({"error": "Invalid format"}), 400

    # delete the file **AFTER** the response is sent
    @after_this_request
    def cleanup(response):
        try:
            os.unlink(tmp_file.name)  # delete temp file after sending
        except Exception as e:
            print(f"Error deleting temp file: {e}")
        return response

    return send_file(
        tmp_file.name,
        as_attachment=True,
        download_name=f"exported_data.{format}",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if format == 'excel' else "text/csv",
        conditional=True
    )


def db_query(table_name,ref, columns):
    data = []
    if ref == "osm_group":
        if table_name == "osm_group_record":
            result = record_osm_group(1, sys.maxsize, 0)
            if isinstance(result, tuple) and len(result) >= 1:
                data = result[0]
            else:
                data = result 
    elif True: pass # for future use

    df = pd.DataFrame(data)

    if columns:
        valid_columns = [col for col in columns if col in df.columns]
        df = df[valid_columns]

    return df