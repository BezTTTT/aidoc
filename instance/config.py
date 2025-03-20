# import secrets; print(secrets.token_hex())
SECRET_KEY='e3c527ed9640360190aea4b8438bf000351c648a46cfdaffa3a1dbfeda64db6d'

DB_HOST='localhost' # To use ICOHOLD database, change this to 'icohold.anamai.moph.go.th' or 'localhost'
DB_DATABASE='aidoc_development'
DB_USER='root'  # To use ICOHOLD database, change this to 'patiwet' or 'root'
DB_PASSWORD='riskOCA@50200' # To use ICOHOLD database, change this to 'icoh2017p@ssw0rd' or 'riskOCA@50200'

DB_DATABASE_RISK_OCA='oralcancer'

LINE_CHANNEL_ACCESS_TOKEN = 'HpDlTrSjLzd4ZpzFSIffOES4G0WlEFngd//xgd4+zfEaZnL5kPpxO8iqGUes3rRr5p8lYKpWDS74qdu1anldEiNDackfIKvTt41aNWdQiykWXKEsBpLLIEsOSYyL16o/Ql1B0qdp+8MhY1bADQ0UfgdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = 'cdc04533bfb5620b60dbbc0c9ae6c39b'
LINE_CHANNEL_ID = '2006847697'

# Versions
AI_LESION_VER = '2.0'
AI_QUALITY_VER = '1.4'
WEB_VER = '3.1'
CURRENT_AGREEMENT_VER = '0'
CURRENT_CONSENT_VER = '0'

# Base URL for the FastAPI AI inference service.
FASTAPI_AI_BASE_URL = "http://localhost:8401"

# Maximum fize size to be uploaded (15MB)
MAX_CONTENT_LENGTH = 100 * 2**20

# Clear imageData/temp folder if #files in the temp folder is more than the threshold
CLEAR_TEMP_THRESHOLD = 1000

# IMAGE_DATA_DIR is defined in the Flask factory (__init__.py)

# Admin password is 'riskOCA@50200' with a hash of scrypt:32768:8:1$fpQAbOlvB2esNbcl$b4458c49c97a506c51e4305c1e56dc67a2618eec7231fe5bf4eea35e9842405890632035c05c157013ef0e005cd5723a9c1d55478895718f9318b1cd80708d86
# Do not assign admin role to an account with patient or osm to prevent data leak (their login is less secured)
# The attacker might login using just ID or phone number then he will have access to all admin privileges
ADMIN_USER_INSERT_SQL = "INSERT INTO `user` (`id`, `name`, `surname`, `national_id`, `email`, `phone`, `sex`, `birthdate`, `username`, `password`, `job_position`, `osm_job`, `hospital`, `province`, `address`, `license`, `is_patient`, `is_osm`, `is_specialist`, `is_admin`, `created_at`, `updated_at`, `default_sender_phone`, `default_location`) VALUES (NULL, 'ผู้ดูแลระบบ', 'Administrator', NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP, 'admin', 'scrypt:32768:8:1$fpQAbOlvB2esNbcl$b4458c49c97a506c51e4305c1e56dc67a2618eec7231fe5bf4eea35e9842405890632035c05c157013ef0e005cd5723a9c1d55478895718f9318b1cd80708d86', 'Computer Technical Officer', NULL, 'มหาวิทยาลัยเชียงใหม่', 'เชียงใหม่', NULL, NULL, '0', '0', '1', '1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, NULL)"
