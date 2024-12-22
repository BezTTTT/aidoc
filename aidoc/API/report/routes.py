from flask import request, Blueprint

from . import report

report_bp = Blueprint('report', __name__)

@report_bp.route('/report_api/', methods=['GET'])
def get_report():
    province = request.args.get('province')
    return report.generate_report(province)
