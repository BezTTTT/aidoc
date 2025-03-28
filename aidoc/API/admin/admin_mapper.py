from ..common import common_mapper as cm
from ..common import date_util as du
from ...utils import calculate_age as ca

def map_user_list_data(data):
    user_list = []

    for row in data:
        user = {
            "id": row["id"],
            "name": row["name"],
            "surname": row["surname"],
            "email": row["email"] if row["email"] else "None",
            "province": row["province"],
            "job_position": cm.map_job_position_to_th(row["job_position"]),
            "role": [],
            "total_submit": row["N"],
            "last_login": du.format_date_to_mmddyyyy_time(row["last_login"]) if row["last_login"] else "-"
        }


        if row["is_patient"] == 1:
            user["role"].append("patient")
        if row["is_osm"] == 1:
            user["role"].append("osm")
        if row["username"] is not None:
            user["role"].append("dentist")
        if row["is_specialist"] == 1:
            user["role"].append("specialist")
        if row["is_admin"] == 1:
            user["role"].append("admin")
        user_list.append(user)

    return user_list

def map_image_manage_list_data(data):
    image_manage_list = []
    for row in data:
        image = {
            "submission_id": row['id'],
            "file_name": row['fname'],
            "submission_date": du.format_date_to_mmddyyyy_time(row['created_at']),
            "ai_prediction": cm.map_ai_prediction_int(row['ai_prediction']).upper(),
            "sender_fullname": f"{row['user_name']} {row['user_surname']}",
            "sender_name": row['user_name'],
            "sender_surname": row['user_surname'],
            "is_special_req": row['special_request'],
            "province": row['location_province'],
            "dentist_fullname": f"{row['dentist_name']} {row['dentist_surname']}" if row['dentist_name'] and row['dentist_surname'] else "",
            "dentist_name": row['dentist_name'],
            "dentist_surname": row['dentist_surname'],
            "dentist_comment": row['dentist_feedback_comment'],
            "dentist_feedback": row['dentist_feedback_code'],
            "age": ca(row['birthdate']),
            "national_id": row['national_id'],
            "sender_job": cm.map_job_position_to_th(row['job_position']),
            "sender_id": row['sender_id']
        }
        image_manage_list.append(image)

    return image_manage_list


def map_dentist_send_list_data(data):
    dentist_send_list = []
    for row in data:
        dentist= {
            "dentist_fullname" : f"{row['name']} {row['surname']}",
            "dentist_license": row['license'],
            "dentist_id": row['id'],
        }

        dentist_send_list.append(dentist)
    return dentist_send_list