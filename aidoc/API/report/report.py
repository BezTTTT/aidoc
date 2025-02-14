import json
from decimal import Decimal

from . import get_total_account
from . import get_summaries_by_day
from flask import jsonify
from . import get_table_patient_and_osm, get_table_specialist
from . import get_all_submission , get_province_list


def generate_report(province):
    patient_data = get_table_patient_and_osm.get_table("PATIENT", province)
    osm_data = get_table_patient_and_osm.get_table("OSM", province)
    dentist_data = get_table_specialist.get_table(province)
    total_pic = get_all_submission.get_all_submission(province)
    total_province = get_province_list. generate_province_list()
    total_account = get_total_account.generate_total_account(province)
    
    output = build_initial_output(province, patient_data, osm_data, dentist_data, total_pic,total_province,total_account)
    output = calculate_totals(patient_data, osm_data, dentist_data, output)

    return output


def build_initial_output(province, patient_data, osm_data, dentist_data, total_pic ,total_province,total_account):
    return {
        'patient_and_osm': {
            'patient': patient_data,
            'osm': osm_data,
            'total': {
                "accuracy": "-",
                "ai_predict": {"normal": 0, "opmd": 0, "oscc": 0},
                "dentist_diagnose": {"agree": 0, "disagree": 0},
                "total_pic": 0
            }
        },
        'province': province,
        'specialist': dentist_data,
        'total_pic': total_pic,
        'total_province': total_province,
        'total_account': total_account
    }


def calculate_totals(patient_data, osm_data, dentist_data, output):
    try:
        output['patient_and_osm']['total']['ai_predict'] = sum_dicts(
            osm_data.get('ai_predict', {}),
            patient_data.get('ai_predict', {})
        )
        output['patient_and_osm']['total']['dentist_diagnose'] = sum_dicts(
            osm_data.get('dentist_diagnose', {}),
            patient_data.get('dentist_diagnose', {})
        )

        output['patient_and_osm']['total']['accuracy'] = calculate_accuracy(osm_data, patient_data)

        output['patient_and_osm']['total']['total_pic'] = osm_data.get('total_pic', 0) + patient_data.get('total_pic', 0)

    except Exception as e:
        print(f"Error occurred while calculating total: {e}")
        reset_totals(output)

    return output


def calculate_accuracy(osm_data, patient_data):
    accuracy_values = []
    accuracy_divider = 0

    for data in [osm_data, patient_data]:
        accuracy = data.get("accuracy", "-")
        if accuracy != "-":
            accuracy_values.append(Decimal(accuracy))
            accuracy_divider += 1

    if accuracy_divider > 0:
        total_accuracy = sum(accuracy_values) / accuracy_divider
        return f"{total_accuracy:.2f}"
    return "-"


def reset_totals(output):
    output['patient_and_osm']['total'] = {
        "ai_predict": {"normal": 0, "opmd": 0, "oscc": 0},
        "dentist_diagnose": {"agree": 0, "disagree": 0},
        "accuracy": "-",
        "total_pic": 0
    }

def sum_dicts(dict1, dict2):
    result = {}
    for key in dict1:
        if isinstance(dict1[key], dict):
            result[key] = sum_dicts(dict1[key], dict2.get(key, {}))
        else:
            result[key] = dict1[key] + dict2.get(key, 0)
    return result

def summaries_by_day(year,start_date,end_date,province):
    output = get_summaries_by_day.generate_summaries_by_day(year,start_date,end_date,province)
    return output