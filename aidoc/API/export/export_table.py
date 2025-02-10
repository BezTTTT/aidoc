from flask import Blueprint, request, jsonify, send_file, session
from aidoc.db import get_db
import pandas as pd
import io

export_bp = Blueprint('export_bp', __name__)

@export_bp.route('/<string:table_name>/<string:format>/<string:columns>', methods=['GET'])
def export_table(table_name, format, columns):

    df = db_query(columns | "*", table_name)

    if format == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)

        return send_file(
            output,
            download_name='exported_data.xlsx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    elif format == 'csv':
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0) 

        return send_file(
            io.BytesIO(output.getvalue().encode()),
            download_name='exported_data.csv',
            as_attachment=True,
            mimetype='text/csv'
        )

    return jsonify({"error": "Invalid format"}), 400


def db_query(columns, table_name, role):
    role = session['login_mode']
    # db, cursor = get_db()
    # cursor.execute(
    #     'SELECT {} FROM {} WHERE role = {}'.format(columns, table_name, role)
    # )
    # data = cursor.fetchall()
    data = {
        'id': [1, 2, 3],
        'name': ['John', 'Jane', 'Bob'],
        'age': [25, 30, 35]
    }
    df = pd.DataFrame(data)
    return df