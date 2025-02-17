from flask import request, Blueprint
from ... import auth
from . import report
report_bp = Blueprint('report', __name__)

@auth.login_required
@auth.admin_only
@report_bp.route('/report_api/', methods=['GET'])
def get_report():
    province = request.args.get('province')
    return report.generate_report(province)

@report_bp.route('/summaries_by_day/', methods=['GET'])
def get_summaries_by_day():
    year = request.args.get('year')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')     
    province = request.args.get('province')
    return report.summaries_by_day(year,start_date,end_date,province)