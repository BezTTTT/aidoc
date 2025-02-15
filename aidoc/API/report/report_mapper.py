from collections import defaultdict
from decimal import Decimal
from ..common import common_mapper

def map_query_to_output_specialist(ai_predict_query, dentist_diagnose_query):
    prediction_mapping = {
        0: "normal",
        1: "opmd",
        2: "oscc"
    }

    ai_predict = defaultdict(lambda: {"normal": 0, "opmd": 0, "oscc": 0})
    total_pics = defaultdict(int)

    for entry in ai_predict_query:
        specialist = common_mapper.map_job_position_to_th(entry['job_position'])
        pred_key = entry['ai_prediction']
        score = entry['N']
        label = prediction_mapping[pred_key]
        ai_predict[specialist][label] += int(score)
        total_pics[specialist] += int(score)

    dentist_diagnose = defaultdict(lambda: {"agree": 0, "disagree": 0})

    for entry in dentist_diagnose_query:
        specialist = common_mapper.map_job_position_to_th(entry['job_position'])
        diag = entry['dentist_feedback_code']
        score = entry['N']
        if diag is not None:
            diag = diag.lower()
            dentist_diagnose[specialist][diag] += int(score)

    total_ai_predict = {"normal": 0, "opmd": 0, "oscc": 0}
    total_dentist_diagnose = {"agree": 0, "disagree": 0}
    total_total_pic = 0

    output = []

    for specialist in set(ai_predict.keys()).union(dentist_diagnose.keys()):
        specialist_data = {
            "job": specialist,
            "ai_predict": ai_predict[specialist],
            "dentist_diagnose": dentist_diagnose[specialist],
            "total_pic": total_pics[specialist]
        }
        output.append(specialist_data)

        for key in total_ai_predict:
            total_ai_predict[key] += ai_predict[specialist][key]
        for key in total_dentist_diagnose:
            total_dentist_diagnose[key] += dentist_diagnose[specialist][key]
        total_total_pic += total_pics[specialist]

    output.append({
        "job": "total",
        "ai_predict": total_ai_predict,
        "dentist_diagnose": total_dentist_diagnose,
        "total_pic": total_total_pic
    })
    return output
