import datetime
import json
import os
from ... import db
import requests

from . import migratepatient, migratedentist,migrateosm
from .aicompute import upload_submission_module
from flask import jsonify, request, Blueprint, current_app

migration_bp = Blueprint('migration', __name__)

@migration_bp.route('/migrate_patient/', methods=['POST'])
def migrate_patient():
    migratepatient.migrate_patient()
    return {}

@migration_bp.route('/migrate_dentist/', methods=['POST'])
def migrate_dentist():
    migratedentist.migrate_dentist()
    return {}

@migration_bp.route('/migrate_osm/', methods=['POST'])
def migrate_osm():
    return migrateosm.migrate_osm()

@migration_bp.route('/migrate/', methods=['POST'])
def migrate():
    migratepatient.migrate_patient()
    print("******************************************************************")
    print("Migrated patient finished!")
    print("******************************************************************")
    migrateosm.migrate_osm()
    print("******************************************************************")
    print("Migrated osm finished!")
    print("******************************************************************")
    migratedentist.migrate_dentist()
    print("******************************************************************")
    print("Migrated dentist finished!")
    print("******************************************************************")
    return {}

@migration_bp.route('/migrate_get_pat/', methods=['GET'])
def get_pat():
    return migratepatient.get_patient_id_with_submission()

@migration_bp.route('/migrate_get_dent/', methods=['GET'])
def get_dent():
    return migratedentist.get_user_id_with_submission_that_not_osm()

@migration_bp.route('/test_pull_db_3/', methods=['GET'])
def pull_db_3():
    db.close_db()
    connection, cursor = db.get_db_3()
    try:
        with cursor:
            sql = """
            SELECT * FROM thai_provinces """
            user_id = cursor.execute(sql)
            output = cursor.fetchall()
    except Exception as e:
        return json.dumps({"error": f"An error occurred while fetching image records: {e}"}), 500
    return output