/*
  user is a patient if 'is_patient' is TRUE or 1
  user is a osm     if 'is_osm' is TRUE or 1
  user is a specialist if 'is_specialist' is TRUE or 1
  user is a admin if 'is_admin' is TRUE or 1
  but the user is a dentist (or general users) if 'username' is not null
*/

CREATE TABLE `user` (
  `id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name` varchar(255) NOT NULL,
  `surname` varchar(255) NOT NULL,
  `national_id` varchar(255) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `phone` varchar(255) DEFAULT NULL,
  `sex` varchar(255) DEFAULT NULL,
  `birthdate` date DEFAULT NULL,
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
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login` datetime DEFAULT NULL,
  `default_sender_phone` varchar(255) DEFAULT NULL,
  `default_location` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=UTF8MB4;

/*
  channel: 'PATIENT', 'OSM', 'DENTIST' (general submission is in a separate table)

  For dentist system,
  dentist_feedback_code (in the dentist general system, type: string): AGREE, DISAGREE
  dentist_feedback_lesion (int): 1.White 2.Red 3.White and Red 4.Abrasion 5.Tumor
  dentist_feedback_location (int): 1.Lip 2.Buccal mucosa 3.Gingiva 4.Retromolar Area 5.Hard Palate 6.Soft Palate 7.Dorsal and lateral tongue 8.Ventral tongue 9.Floor of mouth

  For specialist system,
  dentist_feedback_code (in the specialist system, type: string): NORMAL, OPMD, OSCC, BAD_IMG, OTHER
  dentist_feedback_lesion (in the case of BAD_IMG, type: string): NON_STANDARD, BLUR, DARK, SMALL
  dentist_feedback_lesion (type: int): 1.White 2.Red 3.White and Red 4.Abrasion 5.Tumor
  dentist_feedback_location (type: int): 1.Lip 2.Buccal mucosa 3.Gingiva 4.Retromolar Area 5.Hard Palate 6.Soft Palate 7.Dorsal and lateral tongue 8.Ventral tongue 9.Floor of mouth
*/

CREATE TABLE `submission_record` (
  `id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `channel` varchar(255) NOT NULL,
  `fname` varchar(255) NOT NULL,
  `sender_id` int DEFAULT NULL,
  `sender_phone` varchar(255) DEFAULT NULL,
  `special_request` tinyint NOT NULL DEFAULT 0,
  `patient_id` int DEFAULT NULL,
  `patient_national_id` varchar(255) DEFAULT NULL,
  `dentist_id` int DEFAULT NULL,
  `dentist_feedback_code` varchar(255) DEFAULT NULL,
  `dentist_feedback_comment` varchar(255) NOT NULL DEFAULT '',
  `dentist_feedback_lesion` tinyint DEFAULT NULL,
  `dentist_feedback_location` tinyint DEFAULT NULL,
  `dentist_feedback_date` datetime DEFAULT NULL,
  `case_report` varchar(255) NOT NULL DEFAULT '',
  `biopsy_fname` varchar(255) DEFAULT NULL,
  `biopsy_comment` varchar(255) DEFAULT NULL,
  `ai_prediction` int DEFAULT NULL,
  `ai_scores` varchar(255) DEFAULT NULL,
  `location_district` varchar(255) DEFAULT NULL,
  `location_amphoe` varchar(255) DEFAULT NULL,
  `location_province` varchar(255) DEFAULT NULL,
  `location_zipcode` int DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=UTF8MB4;

CREATE TABLE `patient_case_id` (
  `case_id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `id` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=UTF8MB4;

CREATE TABLE `general_user` (
  `id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name` varchar(255) NOT NULL,
  `surname` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `job_position` varchar(255) DEFAULT NULL,
  `workplace` varchar(255) DEFAULT NULL,
  `city` varchar(255) DEFAULT NULL,
  `country` varchar(255) DEFAULT NULL,
  `ip_address` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=UTF8MB4;

CREATE TABLE `general_submission_record` (
  `id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `fname` varchar(255) NOT NULL,
  `general_sender_id` int DEFAULT NULL,
  `ai_prediction` int DEFAULT NULL,
  `ai_scores` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=UTF8MB4;

/*
  retrain_request_status: 'Requested', 'Processing', 'Done'
*/

CREATE TABLE `retrain_request` (
  `id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `submission_id` int NOT NULL,
  `retrain_requester` int NOT NULL,
  `retrain_request_date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `retrain_request_status` varchar(256) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

/*
  followup_request_status: 'Initiated', 'On Specialist', 'On Contact', 'On Treatment', 'Closed'
  contact_person: name, hospital, role, telephone or line contact
*/

CREATE TABLE `followup_request` (
  `id` int NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `submission_id` int NOT NULL,
  `followup_requester` int NOT NULL,
  `followup_request_date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `followup_request_status` varchar(256) NOT NULL,
  `contact_person` varchar(256),
  `followup_note` varchar(256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

/*
 Source Server         : rockpi
 Source Server Type    : MariaDB
 Source Server Version : 100808 (10.8.8-MariaDB-1:10.8.8+maria~ubu2204)
 Source Host           : rockpi.lan:3308
 Source Schema         : thai_data

 Target Server Type    : MariaDB
 Target Server Version : 100808 (10.8.8-MariaDB-1:10.8.8+maria~ubu2204)
 File Encoding         : 65001

 Date: 21/12/2023 19:32:26
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for thai_provinces
-- ----------------------------
DROP TABLE IF EXISTS `thai_provinces`;
CREATE TABLE `thai_provinces` (
  `id` int(11) NOT NULL,
  `name_th` varchar(150) NOT NULL,
  `name_en` varchar(150) NOT NULL,
  `geography_id` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Records of thai_provinces
-- ----------------------------
BEGIN;
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (1, 'กรุงเทพมหานคร', 'Bangkok', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (2, 'สมุทรปราการ', 'Samut Prakan', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (3, 'นนทบุรี', 'Nonthaburi', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (4, 'ปทุมธานี', 'Pathum Thani', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (5, 'พระนครศรีอยุธยา', 'Phra Nakhon Si Ayutthaya', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (6, 'อ่างทอง', 'Ang Thong', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (7, 'ลพบุรี', 'Loburi', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (8, 'สิงห์บุรี', 'Sing Buri', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (9, 'ชัยนาท', 'Chai Nat', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (10, 'สระบุรี', 'Saraburi', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (11, 'ชลบุรี', 'Chon Buri', 5, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (12, 'ระยอง', 'Rayong', 5, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (13, 'จันทบุรี', 'Chanthaburi', 5, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (14, 'ตราด', 'Trat', 5, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (15, 'ฉะเชิงเทรา', 'Chachoengsao', 5, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (16, 'ปราจีนบุรี', 'Prachin Buri', 5, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (17, 'นครนายก', 'Nakhon Nayok', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (18, 'สระแก้ว', 'Sa Kaeo', 5, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (19, 'นครราชสีมา', 'Nakhon Ratchasima', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (20, 'บุรีรัมย์', 'Buri Ram', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (21, 'สุรินทร์', 'Surin', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (22, 'ศรีสะเกษ', 'Si Sa Ket', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (23, 'อุบลราชธานี', 'Ubon Ratchathani', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (24, 'ยโสธร', 'Yasothon', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (25, 'ชัยภูมิ', 'Chaiyaphum', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (26, 'อำนาจเจริญ', 'Amnat Charoen', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (27, 'หนองบัวลำภู', 'Nong Bua Lam Phu', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (28, 'ขอนแก่น', 'Khon Kaen', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (29, 'อุดรธานี', 'Udon Thani', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (30, 'เลย', 'Loei', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (31, 'หนองคาย', 'Nong Khai', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (32, 'มหาสารคาม', 'Maha Sarakham', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (33, 'ร้อยเอ็ด', 'Roi Et', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (34, 'กาฬสินธุ์', 'Kalasin', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (35, 'สกลนคร', 'Sakon Nakhon', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (36, 'นครพนม', 'Nakhon Phanom', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (37, 'มุกดาหาร', 'Mukdahan', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (38, 'เชียงใหม่', 'Chiang Mai', 1, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (39, 'ลำพูน', 'Lamphun', 1, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (40, 'ลำปาง', 'Lampang', 1, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (41, 'อุตรดิตถ์', 'Uttaradit', 1, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (42, 'แพร่', 'Phrae', 1, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (43, 'น่าน', 'Nan', 1, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (44, 'พะเยา', 'Phayao', 1, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (45, 'เชียงราย', 'Chiang Rai', 1, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (46, 'แม่ฮ่องสอน', 'Mae Hong Son', 1, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (47, 'นครสวรรค์', 'Nakhon Sawan', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (48, 'อุทัยธานี', 'Uthai Thani', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (49, 'กำแพงเพชร', 'Kamphaeng Phet', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (50, 'ตาก', 'Tak', 4, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (51, 'สุโขทัย', 'Sukhothai', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (52, 'พิษณุโลก', 'Phitsanulok', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (53, 'พิจิตร', 'Phichit', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (54, 'เพชรบูรณ์', 'Phetchabun', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (55, 'ราชบุรี', 'Ratchaburi', 4, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (56, 'กาญจนบุรี', 'Kanchanaburi', 4, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (57, 'สุพรรณบุรี', 'Suphan Buri', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (58, 'นครปฐม', 'Nakhon Pathom', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (59, 'สมุทรสาคร', 'Samut Sakhon', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (60, 'สมุทรสงคราม', 'Samut Songkhram', 2, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (61, 'เพชรบุรี', 'Phetchaburi', 4, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (62, 'ประจวบคีรีขันธ์', 'Prachuap Khiri Khan', 4, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (63, 'นครศรีธรรมราช', 'Nakhon Si Thammarat', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (64, 'กระบี่', 'Krabi', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (65, 'พังงา', 'Phangnga', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (66, 'ภูเก็ต', 'Phuket', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (67, 'สุราษฎร์ธานี', 'Surat Thani', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (68, 'ระนอง', 'Ranong', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (69, 'ชุมพร', 'Chumphon', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (70, 'สงขลา', 'Songkhla', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (71, 'สตูล', 'Satun', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (72, 'ตรัง', 'Trang', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (73, 'พัทลุง', 'Phatthalung', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (74, 'ปัตตานี', 'Pattani', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (75, 'ยะลา', 'Yala', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (76, 'นราธิวาส', 'Narathiwat', 6, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
INSERT INTO `thai_provinces` (`id`, `name_th`, `name_en`, `geography_id`, `created_at`, `updated_at`, `deleted_at`) VALUES (77, 'บึงกาฬ', 'Bueng Kan', 3, '2019-08-09 03:33:09', '2022-05-16 06:31:03', NULL);
COMMIT;

SET FOREIGN_KEY_CHECKS = 1;