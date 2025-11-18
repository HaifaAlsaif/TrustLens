import firebase_admin
from firebase_admin import credentials, db

# تحميل مفتاح الخدمة
cred = credentials.Certificate("service-account.json")

# إنشاء تطبيق Firebase مخصص للـ Realtime Database
try:
    rtdb_app = firebase_admin.get_app("rtdb")
except ValueError:
    rtdb_app = firebase_admin.initialize_app(
        cred,
        {"databaseURL": "https://trustlens-e9038-default-rtdb.firebaseio.com"},
        name="rtdb"
    )

# جذر قاعدة البيانات
rtdb_root = db.reference("/", app=rtdb_app)
