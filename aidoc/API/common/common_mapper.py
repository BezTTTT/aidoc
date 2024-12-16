def map_ai_prediction_list(predictions):
    prediction_mapping = {0: "normal", 1: "opmd", 2: "oscc"}
    return {prediction_mapping.get(pred['ai_prediction'], "unknown"): pred['N'] for pred in predictions}

def map_ai_prediction_int(prediction):
    prediction_mapping = {0: "normal", 1: "opmd", 2: "oscc"}
    return prediction_mapping.get(prediction, "unknown")

def map_dentist_diagnosis(diagnoses):
    diagnosis_mapping = {
        "OSCC": "oscc", "OPMD": "opmd", "Normal": "normal",
        "BAD_IMG": "poor_image", "OTHER": "others", "Not_diagnosed": "not_diagnosed"
    }
    return {diagnosis_mapping.get(diag['dentist_feedback_code'], "unknown"): int(diag['N']) for diag in diagnoses}

def map_job_position_to_th(job_position):
    job_position_dict = {
        "OSM": "อสม.",
        "Dental Nurse": "ทันตาภิบาล/เจ้าพนักงานทันตสาธารณสุข",
        "Dentist": "ทันตแพทย์",
        "Oral Pathologist": "ทันตแพทย์เฉพาะทาง วิทยาการวินิจฉัยโรคช่องปาก",
        "Oral and Maxillofacial Surgeon": "ทันตแพทย์เฉพาะทาง ศัลยศาสตร์ช่องปากและแม็กซิลโลเฟเชียล",
        "Physician": "แพทย์",
        "Public Health Technical Officer": "นักวิชาการสาธารณสุข",
        "Computer Technical Officer": "นักวิชาการคอมพิวเตอร์/นักวิจัย/ผู้พัฒนาระบบ",
        "Other Public Health Officer": "ข้าราชการ/เจ้าพนักงานกระทรวงสาธารณสุข",
        "Other Government Officer": "เจ้าหน้าที่รัฐอื่น",
        "General Public": "บุคคลทั่วไป"
    }
    return job_position_dict.get(job_position, "ผู้ป่วย")
