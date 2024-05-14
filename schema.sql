CREATE TABLE `user` (
  `id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name` varchar(255) NOT NULL,
  `surname` varchar(255) NOT NULL,
  `national_id` varchar(255) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `phone` varchar(255) DEFAULT NULL,
  `sex` varchar(255) DEFAULT NULL,
  `birthdate` datetime DEFAULT NULL,
  `username` varchar(255) DEFAULT NULL,
  `password` varchar(255) DEFAULT NULL,
  `job_position` varchar(255) DEFAULT NULL,
  `osm_job` varchar(255) DEFAULT NULL,
  `hospital` varchar(255) DEFAULT NULL,
  `province` varchar(255) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `license` varchar(255) DEFAULT NULL,
  `is_patient` boolean DEFAULT FALSE,
  `is_osm` boolean DEFAULT FALSE,
  `is_specialist` boolean DEFAULT FALSE,
  `is_admin` boolean DEFAULT FALSE,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=UTF8MB4;

/*
  dentist_feedback_code (in dentist general system): AGREE, DISAGREE
  general_comment (in dentist general system)

  case_id is the running id only for the patient system (dentist system will be NULL)
*/

CREATE TABLE `submission_record` (
  `id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `case_id` int DEFAULT NULL,
  `fname` varchar(255) NOT NULL,
  `sender_id` int DEFAULT NULL,
  `sender_phone` varchar(255) DEFAULT NULL,
  `special_request` tinyint NOT NULL DEFAULT 0,
  `zip_code` varchar(255) DEFAULT NULL,
  `patient_id` varchar(255) DEFAULT NULL,
  `general_comment` varchar(255) NOT NULL DEFAULT '',
  `dentist_id` int DEFAULT NULL,
  `dentist_feedback_code` varchar(255) DEFAULT NULL,
  `dentist_feedback_comment` varchar(255) NOT NULL DEFAULT '',
  `dentist_feedback_lesion` tinyint DEFAULT NULL,
  `dentist_feedback_location` tinyint DEFAULT NULL,
  `dentist_feedback_date` datetime DEFAULT NULL,
  `biopsy_fname` varchar(255) DEFAULT NULL,
  `biopsy_comment` varchar(255) DEFAULT NULL,
  `ai_prediction` int DEFAULT NULL,
  `ai_scores` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL,
  `longitude` varchar(255) DEFAULT NULL,
  `latitude` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=UTF8MB4;

CREATE TABLE `patient_case_id` (
  `case_id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `id` int DEFAULT NULL,
) ENGINE=InnoDB DEFAULT CHARSET=UTF8MB4;