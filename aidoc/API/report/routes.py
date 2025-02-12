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
