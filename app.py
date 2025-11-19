from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from firebase_admin_setup import db
from firebase_admin import db as rtdb  # Realtime Database
from firebase_admin import auth as admin_auth
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from auth_rest import signup as rest_signup, signin as rest_signin, send_password_reset
from datetime import datetime
from google.cloud import storage
from flask import flash
import uuid
import json
import csv
import io
import requests
from tasks_routes import init_task_routes

# إعداد Flask
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "CHANGE_THIS_SECRET_IN_ENV_OR_CONFIG"  

# ✅ تسجيل راوتس التاسكات
init_task_routes(app)



# 1) استبدلي دالة index() كاملة بهذا الكود
@app.route("/")
def index():
    return render_template("HomePage.html")
    

    uid      = session["uid"]
    user_doc = db.collection("users").document(uid).get()
    role     = user_doc.to_dict().get("role", "user")

@app.route("/login")
def login_page():
    return render_template("Login.html")

@app.route("/signup")
def signup_page():
    return render_template("signup.html")

@app.route("/verified")
def verified():
    # بعد التحقق، نعيد توجيهه لصفحة نجاح التفعيل
    return render_template("Verified.html")

@app.route("/profile")
def profile_page():
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
    

    uid = session.get("uid")
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        return redirect(url_for("login_page"))

    user_data = user_doc.to_dict()
    first_name = user_data.get("profile", {}).get("firstName", "")
    last_name  = user_data.get("profile", {}).get("lastName", "")
    full_name  = f"{first_name} {last_name}".strip() or "User"

    return render_template("Profile.html", user_data=user_data, user_name=full_name)

@app.route("/createproject")
def create_project_page():
    return render_template("CreateProject.html")

@app.route("/myprojectowner")
def my_project_owner_page():
    if not session.get("idToken"):
        return redirect(url_for("login_page"))

    uid = session.get("uid")
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        return redirect(url_for("login_page"))

    user_data  = user_doc.to_dict()
    first_name = user_data.get("profile", {}).get("firstName", "")
    last_name  = user_data.get("profile", {}).get("lastName", "")
    full_name  = f"{first_name} {last_name}".strip() or "User"

    return render_template("myprojectowner.html", user_name=full_name)

@app.route("/myprojectexaminer")
def myprojectexaminer_page():
    if not session.get("idToken"):
        return redirect(url_for("login_page"))

    uid = session.get("uid")
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        return redirect(url_for("login_page"))

    user_data  = user_doc.to_dict()
    first_name = user_data.get("profile", {}).get("firstName", "")
    last_name  = user_data.get("profile", {}).get("lastName", "")
    full_name  = f"{first_name} {last_name}".strip() or "User"

    return render_template("myprojectexaminer.html", user_name=full_name)


@app.route("/ownerdashboard")
def owner_dashboard_page():
    # 1) نتحقق أن المستخدم مسجل دخول
    if not session.get("idToken"):
        return redirect(url_for("login_page"))

    # 2) نجيب الـ UID من الـ session
    uid = session.get("uid")

    # 3) نجيب بيانات المستخدم من Firestore
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        return redirect(url_for("login_page"))

    # 4) نستخرج الاسم
    user_data  = user_doc.to_dict()
    first_name = user_data.get("profile", {}).get("firstName", "")
    last_name  = user_data.get("profile", {}).get("lastName", "")
    full_name  = f"{first_name} {last_name}".strip() or "User"

    # 5) نرسل الاسم للصفحة
    return render_template("Ownerdashboard.html", user_name=full_name)

@app.route("/examinerdashboard")
def examiner_dashboard_page():
    if not session.get("idToken"):
        return redirect(url_for("login_page"))

    uid = session.get("uid")
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        return redirect(url_for("login_page"))

    user_data = user_doc.to_dict()
    first_name = user_data.get("profile", {}).get("firstName", "")
    last_name = user_data.get("profile", {}).get("lastName", "")
    full_name = f"{first_name} {last_name}".strip() or "User"

    return render_template("Examinerdashboard.html", user_name=full_name)

@app.route("/projectdetailsowner/<project_id>")
def project_details_owner(project_id):
    if not session.get("idToken"):
        return redirect(url_for("login_page"))

    owner_uid = session["uid"]

    # نتحقق أن المشروع فعلاً للـ owner
    proj_doc = db.collection("projects").document(project_id).get()
    if not proj_doc.exists:
        abort(404)

    proj_data = proj_doc.to_dict()
    if proj_data.get("owner_id") != owner_uid:
        abort(403)

    # نجيب بيانات المستخدم لعرض الاسم في الهيدر
    user_doc = db.collection("users").document(owner_uid).get()
    if not user_doc.exists:
        abort(404)

    user_data = user_doc.to_dict()
    first_name = user_data.get("profile", {}).get("firstName", "")
    last_name  = user_data.get("profile", {}).get("lastName", "")
    full_name  = f"{first_name} {last_name}".strip() or "User"

    return render_template(
        "ProjectDetailsOwner.html",
        user_name=full_name,
        project_id=project_id
    )
    
@app.route("/api/project_json_owner/<project_id>")
def api_project_json_owner(project_id):
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    owner_uid = session["uid"]

    # نتأكد أن المشروع للـ owner
    proj_doc = db.collection("projects").document(project_id).get()
    if not proj_doc.exists:
        return jsonify({"error": "Project not found"}), 404

    proj = proj_doc.to_dict()
    if proj.get("owner_id") != owner_uid:
        return jsonify({"error": "Forbidden"}), 403

    # 🔥 نجيب معلومات الـ Owner (نفس طريقة examiner)
    owner_doc = db.collection("users").document(owner_uid).get()
    if not owner_doc.exists:
        return jsonify({"error": "Owner not found"}), 404

    owner_data = owner_doc.to_dict()
    prof = owner_data.get("profile", {})

    owner_name = f"{prof.get('firstName', '')} {prof.get('lastName', '')}".strip()
    owner_email = owner_data.get("email", "")

    # 🔥 نجيب عدد المقبولين
    accepted_count = sum(
        1
        for _ in db.collection("invitations")
        .where("project_id", "==", project_id)
        .where("status", "==", "accepted")
        .stream()
    )

    return jsonify({
        "project_name": proj.get("project_name"),
        "description": proj.get("description"),
        "domain": proj.get("domain", []),
        "category": proj.get("category"),
        "dataset_url": proj.get("dataset_url", ""),
        "examiners_accepted": accepted_count,

        # 🔥🔥 أهم شي أضفناهم:
        "owner_name": owner_name,
        "owner_email": owner_email
    })
# ------------- قائمة Examiners المقبولين (للـ Owner) -------------
@app.route("/api/project_examiners_owner/<project_id>")
def api_project_examiners_owner(project_id):
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    owner_uid = session["uid"]

    # تأكيد أن المشروع ملك للـ owner
    proj_doc = db.collection("projects").document(project_id).get()
    if not proj_doc.exists:
        return jsonify({"error": "Project not found"}), 404

    proj_data = proj_doc.to_dict()
    if proj_data.get("owner_id") != owner_uid:
        return jsonify({"error": "Forbidden"}), 403

    # نجيب جميع المقبولين
    accepted = (
        db.collection("invitations")
        .where("project_id", "==", project_id)
        .where("status", "==", "accepted")
        .stream()
    )

    examiners = []
    for inv in accepted:
        d = inv.to_dict()
        ex_id = d.get("examiner_id")
        user_doc = db.collection("users").document(ex_id).get()
        if not user_doc.exists:
            continue

        u = user_doc.to_dict()
        prof = u.get("profile", {})

        name = f"{prof.get('firstName', '')} {prof.get('lastName', '')}".strip()
        email = u.get("email", "")

        examiners.append({
            "id": ex_id,
            "name": name,
            "email": email
        })

    return jsonify({"examiners": examiners})

# --------------------------------------------------
# صفحة تفاصيل المشروع للمُقيّم (Examiner)
# --------------------------------------------------
@app.route("/projectdetailsexaminer/<project_id>")
def project_details_examiner(project_id):
   
    if not session.get("idToken"):
        return redirect(url_for("login_page"))

    examiner_uid = session["uid"]

    # نتحقق أن الم examiner قبل الدعوة
    inv = (
        db.collection("invitations")
        .where("project_id", "==", project_id)
        .where("examiner_id", "==", examiner_uid)
        .where("status", "==", "accepted")
        .limit(1)
        .get()
    )
    if not inv:
        abort(404)  # أو redirect 404 page

    # نجيب بياناته لعرض الاسم بالهيدر
    user_doc = db.collection("users").document(examiner_uid).get()
    if not user_doc.exists:
        abort(404)

    user_data = user_doc.to_dict()
    first_name = user_data.get("profile", {}).get("firstName", "")
    last_name = user_data.get("profile", {}).get("lastName", "")
    full_name = f"{first_name} {last_name}".strip() or "User"

    return render_template("ProjectDetailsExaminer.html",
                         user_name=full_name,
                         project_id=project_id)
# ------------------ صفحة تفاصيل المشروع للمُقيّم (Examiner) ------------------
# --------------------------------------------------

def _get_owner_info(owner_uid):
    owner_doc = db.collection("users").document(owner_uid).get()
    if not owner_doc.exists:
        return {"name": "Unknown", "email": ""}

    data = owner_doc.to_dict()
    prof = data.get("profile", {})
    name = f"{prof.get('firstName', '')} {prof.get('lastName', '')}".strip()
    email = data.get("email", "")

    return {"name": name, "email": email}

    
@app.route("/api/project_json/<project_id>")
def api_project_json(project_id):
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    examiner_uid = session["uid"]

    # نتحقق أن ال examiner قبل الدعوة
    inv = (
        db.collection("invitations")
        .where("project_id", "==", project_id)
        .where("examiner_id", "==", examiner_uid)
        .where("status", "==", "accepted")
        .limit(1)
        .get()
    )
    if not inv:
        return jsonify({"error": "Project not found or you are not a member"}), 404

    proj_doc = db.collection("projects").document(project_id).get()
    if not proj_doc.exists:
        return jsonify({"error": "Project not found"}), 404
    proj = proj_doc.to_dict()

    # نجيب بيانات الأونر
    owner_info = _get_owner_info(proj["owner_id"])

    # نعدّ عدد الـ examiners الذين قبلوا الدعوة
    accepted_count = sum(
        1
        for _ in db.collection("invitations")
        .where("project_id", "==", project_id)
        .where("status", "==", "accepted")
        .stream()
    )

    return jsonify(
        {
            "project_name": proj.get("project_name"),
            "description": proj.get("description"),
            "owner_name": owner_info["name"],
            "owner_email": owner_info["email"],
            "domain": proj.get("domain", []),
            "category": proj.get("category"),
            "examiners_accepted": accepted_count,
            "dataset_url": proj.get("dataset_url", ""),
        }
    )
@app.route("/feedback")
def feedback_page():
    return render_template("feedback.html")
# ------------- قائمة Examiners المقبولين في مشروع معين -------------
@app.route("/api/project_examiners/<project_id>")
def api_project_examiners(project_id):
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    # نتحقق أن السائل مقبول هو الآخر
    examiner_uid = session["uid"]
    inv = (
        db.collection("invitations")
        .where("project_id", "==", project_id)
        .where("examiner_id", "==", examiner_uid)
        .where("status", "==", "accepted")
        .limit(1)
        .get()
    )
    if not inv:
        return jsonify({"error": "Forbidden"}), 403

    # نجيب كل المقبولين
    accepted = (
        db.collection("invitations")
        .where("project_id", "==", project_id)
        .where("status", "==", "accepted")
        .stream()
    )

    examiners = []
    for a in accepted:
        ex_id = a.to_dict().get("examiner_id")
        ex_doc = db.collection("users").document(ex_id).get()
        if not ex_doc.exists:
            continue
        prof = ex_doc.to_dict().get("profile", {})
        name = f"{prof.get('firstName', '')} {prof.get('lastName', '')}".strip() or "Unknown"
        email = ex_doc.to_dict().get("email", "")
        examiners.append({
            "id": ex_id,
            "name": name,
            "email": email,
            "is_you": ex_id == examiner_uid
        })

    return jsonify({"examiners": examiners})
# ============= INVITATIONS APIs =============

@app.route("/invitation")
def invitation_page():
    """صفحة Invitations (GET)"""
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
    uid = session["uid"]
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        return redirect(url_for("login_page"))
    first_name = user_doc.to_dict().get("profile", {}).get("firstName", "")
    last_name = user_doc.to_dict().get("profile", {}).get("lastName", "")
    full_name = f"{first_name} {last_name}".strip() or "User"
    return render_template("invitation.html", user_name=full_name)

@app.route("/api/invitations", methods=["GET"])
def api_invitations():
    """جلب الدعوات (JSON)"""
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401
    uid = session["uid"]
    docs = (
        db.collection("invitations")
        .where("examiner_id", "==", uid)
        .where("status", "==", "pending")
        .stream()
    )
    out = []
    for d in docs:
        data = d.to_dict()
        out.append({
            "id": d.id,
            "project_name": data.get("project_name"),
            "owner_name": data.get("owner_name"),
            "status": data.get("status"),
        })
    return jsonify({"invitations": out})

@app.route("/api/invitations/<invitation_id>", methods=["PATCH"])
def api_update_invitation(invitation_id):
    """قبول أو رفض دعوة"""
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    uid = session["uid"]
    data = request.get_json() or {}
    new_status = data.get("status", "").strip().lower()  # تنظيف الإدخال

    # ✅ توحيد الحالة إلى accepted / declined
    if new_status in ["accept", "accepted"]:
        new_status = "accepted"
    elif new_status in ["decline", "declined"]:
        new_status = "declined"
    else:
        return jsonify({"error": "Invalid status"}), 400

    inv_ref = db.collection("invitations").document(invitation_id)
    inv_doc = inv_ref.get()
    if not inv_doc.exists:
        return jsonify({"error": "Invitation not found"}), 404
    if inv_doc.to_dict().get("examiner_id") != uid:
        return jsonify({"error": "Forbidden"}), 403

    inv_ref.update({"status": new_status})
    return jsonify({"message": f"Invitation {new_status}ed successfully"}), 200

@app.route("/api/volunteers", methods=["GET"])
def api_volunteers():
    # نجيب المستخدمين اللي دورهم examiner واللي مفعلين volunteer.optIn
    docs = (
        db.collection("users")
        .where("role", "==", "examiner")
        .where("volunteer.optIn", "==", True)
        .stream()
    )

    volunteers = []
    for d in docs:
        data = d.to_dict()
        prof = data.get("profile", {})
        volunteers.append({
            "name": f"{prof.get('firstName','')} {prof.get('lastName','')}".strip(),
            "handle": "@" + prof.get("firstName","").lower(),
            "email": data.get("email", ""),
            "tag": prof.get("specialization", "Volunteer")
        })

    return jsonify({"volunteers": volunteers})

# ------------------ Examiner Accepted Projects ------------------
@app.route("/api/accepted_projects", methods=["GET"])
def api_accepted_projects():
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    examiner_id = session["uid"]

    invitations = db.collection("invitations") \
        .where("examiner_id", "==", examiner_id) \
        .where("status", "==", "accepted") \
        .stream()

    projects = []
    for inv in invitations:
        inv_data = inv.to_dict()
        project_id = inv_data.get("project_id")
        project_doc = db.collection("projects").document(project_id).get()
        if project_doc.exists:
            proj = project_doc.to_dict()
            projects.append({
                "project_id": project_id,
                "project_name": proj.get("project_name"),
                "owner_name": inv_data.get("owner_name"),
                "domain": proj.get("domain", []),
                "category": proj.get("category"),
                "status": proj.get("status"),
            })

    return jsonify({"projects": projects})

# ------------------ هنا عشان تطلع المشاريع في صفحة الاونر ماي بروجكت------------------
@app.route("/api/my_projects", methods=["GET"])
def api_my_projects():
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    uid = session.get("uid")
    projects_ref = db.collection("projects").where("owner_id", "==", uid).stream()

    projects = []
    for doc in projects_ref:
        data = doc.to_dict()
        project_id = doc.id

        # 🔹 نحسب عدد الـ examiners اللي قبلوا المشروع
        accepted_invitations = db.collection("invitations") \
            .where("project_id", "==", project_id) \
            .where("status", "==", "accepted") \
            .stream()
        accepted_count = sum(1 for _ in accepted_invitations)

        projects.append({
            "project_id": project_id,
            "project_name": data.get("project_name"),
            "domain": data.get("domain", []),
            "category": data.get("category"),
            "examiners": accepted_count,  # ✅ العدد الحقيقي
            "status": data.get("status", "active"),
        })

    return jsonify({"projects": projects})

def ingest_owner_dataset_to_rtdb(category, owner_id, project_id, dataset_id, raw_bytes):
    """
    تخزّن ملف CSV في Realtime Database تحت:
      datasets/uploaded_news أو datasets/uploaded_conversations

    - كل ديتاست لها dataset_id واحد ثابت
    - كل صف داخل الديتاست ينحفظ تحت auto key
    - نستخدم payload للصف كامل زي ما هو من CSV
    """
    if not raw_bytes:
        return 0

    # نحدد الفرع حسب نوع الديتاست
    cat = (category or "").strip().lower()
    if cat in ("news", "article", "articles"):
        branch = "uploaded_news"
    elif cat in ("conversation", "conversations", "chat", "chats"):
        branch = "uploaded_conversations"
    else:
        print(f"[ingest] Unknown category '{category}', skipping RTDB ingest.")
        return 0

    # نقرأ الـ CSV كنص
    text = raw_bytes.decode("utf-8", errors="ignore")
    f = io.StringIO(text)
    reader = csv.DictReader(f)

    base_ref = rtdb.reference("datasets").child(branch).child(dataset_id)
    count = 0

    for row in reader:
        data = {
            "dataset_id": dataset_id,      # 👈 ثابت لكل الصفوف اللي من نفس الديتاست
            "project_id": project_id,
            "owner_id": owner_id,
            "payload": row,                # الصف كامل
            "created_at": datetime.utcnow().isoformat() + "Z",
            "source_type": "owner_upload",
        }
        base_ref.push(data)  # auto key من Realtime
        count += 1

    print(f"[ingest] Inserted {count} rows into datasets/{branch} for dataset_id={dataset_id}")
    return count

# ------------------ Create Project (مع إنشاء سجلات invitations منفصلة) ------------------
@app.route("/api/create_project", methods=["POST"])
def api_create_project():
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    uid = session.get("uid")
    if not uid:
        return jsonify({"error": "Missing user ID"}), 401

    # نقرأ البيانات سواء من form أو JSON
    data = request.form if request.form else (request.json or {})

    project_name = data.get("project_name")
    description  = data.get("description")
    category     = data.get("category")
    dataset_id = str(uuid.uuid4())
    

    if hasattr(data, "getlist"):
        domains = data.getlist("domain")
    else:
        domains = data.get("domain", [])

    examiners_raw = data.get("invited_examiners", "[]")
    try:
        examiners = json.loads(examiners_raw) if isinstance(examiners_raw, str) else examiners_raw
    except json.JSONDecodeError:
        examiners = []

    if not project_name or not description or not category:
        return jsonify({"error": "Missing required fields"}), 400

    # نقرأ ملف الديتاست دون تخزينه في Storage
    dataset_url = ""   # ما نستخدم Storage حالياً
    raw_bytes   = None

    file = request.files.get("dataset")
    if file and file.filename:
        raw_bytes = file.read()
        file.seek(0)

    # جلب بيانات الأونر من Firestore
    owner_doc = db.collection("users").document(uid).get()
    if not owner_doc.exists:
        return jsonify({"error": "Owner not found"}), 404

    owner_data = owner_doc.to_dict()
    owner_name = f"{owner_data.get('profile', {}).get('firstName', '')} {owner_data.get('profile', {}).get('lastName', '')}".strip()

    # إنشاء سجل المشروع
    project_id = str(uuid.uuid4())
    project_doc = {
    "project_ID": project_id,
    "project_name": project_name,
    "description": description,
    "domain": domains,
    "category": category,
    "created_at": datetime.utcnow().isoformat() + "Z",
    "owner_id": uid,
    "dataset_id": dataset_id,
    "invited_examiners": [ex.get("email") for ex in examiners],
    "status": "active",
}


    db.collection("projects").document(project_id).set(project_doc)

    # إنشاء الدعوات في Collection منفصل
    batch = db.batch()
    for ex in examiners:
        email = ex.get("email")
        if not email:
            continue

        examiner_docs = list(
            db.collection("users")
              .where("email", "==", email)
              .where("role", "==", "examiner")
              .limit(1)
              .stream()
        )
        if not examiner_docs:
            continue

        examiner_uid = examiner_docs[0].id
        invitation_ref = db.collection("invitations").document()
        invitation_data = {
            "project_id": project_id,
            "project_name": project_name,
            "owner_id": uid,
            "owner_name": owner_name,
            "examiner_id": examiner_uid,
            "status": "pending",
            "created_at": SERVER_TIMESTAMP,
            "examiner_email": email,
        }
        batch.set(invitation_ref, invitation_data)

    if examiners:
        batch.commit()

    # إدخال الديتاست إلى Realtime Database لو فيه ملف
    if raw_bytes:
        try:
            ingest_owner_dataset_to_rtdb(category, uid, project_id, dataset_id, raw_bytes)
        except Exception as e:
            app.logger.exception("Failed to ingest owner dataset into Realtime: %s", e)

    # ✅ في النهاية لازم نرجّع Response واضح دائماً
    return jsonify({
        "message": "Project created successfully",
        "project_ID": project_id,
        "dataset_id": dataset_id,
    }), 201
# ------------------ حذف مشروع ------------------
@app.route("/api/delete_project/<project_id>", methods=["DELETE"])
def api_delete_project(project_id):
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    uid = session.get("uid")
    project_ref = db.collection("projects").document(project_id)
    project_doc = project_ref.get()

    if not project_doc.exists:
        return jsonify({"error": "Project not found"}), 404

    if project_doc.to_dict().get("owner_id") != uid:
        return jsonify({"error": "Forbidden"}), 403

    invitations = db.collection("invitations").where("project_id", "==", project_id).stream()
    batch = db.batch()
    for inv in invitations:
        batch.delete(db.collection("invitations").document(inv.id))
    batch.delete(project_ref)
    batch.commit()

    return jsonify({"message": "Project deleted successfully"}), 200

# ========== إرسال دعوة جديدة للـ Examiner ==========
@app.route("/api/send_invitation", methods=["POST"])
def api_send_invitation():
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    owner_uid = session["uid"]
    data       = request.get_json() or {}
    examiner_email = data.get("examiner_email")   # أو id حسب تصميمك
    project_id     = data.get("project_id")

    if not examiner_email or not project_id:
        return jsonify({"error": "Missing examiner_email or project_id"}), 400

    # نجيب بيانات الـ Examiner من Firestore بالـ email
    examiner_docs = list(db.collection("users").where("email", "==", examiner_email).limit(1).stream())
    if not examiner_docs:
        return jsonify({"error": "Examiner email not found"}), 404
    examiner_uid = examiner_docs[0].id

    # نجيب بيانات الـ Project للتأكد أنه تابع للـ Owner
    proj_doc = db.collection("projects").document(project_id).get()
    if not proj_doc.exists or proj_doc.to_dict().get("owner_id") != owner_uid:
        return jsonify({"error": "Project not found or not yours"}), 403

    # نجيب اسم الـ Owner للعرض
    owner_doc = db.collection("users").document(owner_uid).get()
    owner_name = f"{owner_doc.to_dict()['profile']['firstName']} {owner_doc.to_dict()['profile']['lastName']}".strip()

    # ننشئ الدعوة
    inv_doc = {
        "project_id":   project_id,
        "project_name": proj_doc.to_dict().get("project_name"),
        "owner_id":     owner_uid,
        "owner_name":   owner_name,
        "examiner_id":  examiner_uid,
        "status":       "pending",
        "created_at":   SERVER_TIMESTAMP
    }
    db.collection("invitations").add(inv_doc)

    return jsonify({"message": "Invitation sent successfully"}), 201

# ------------------ مصادقة (POST APIs) ------------------

# إنشاء حساب جديد
@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.form if request.form else (request.json or {})

    email    = data.get("email")
    password = data.get("password")

    # 👈 نقرأ اليوزر نيم من الفورم
    username = data.get("username") or data.get("displayName", "")

    role       = data.get("role", "user")
    first_name = data.get("firstName", "")
    last_name  = data.get("lastName", "")
    gender     = data.get("gender", "")
    interests  = data.get("interests", "")
    github     = data.get("github", "")
    linkedin   = data.get("linkedin", "")

    volunteer_opt_in = str(data.get("volunteerOptIn", "false")).lower() == "true"
    specialization   = data.get("specialization", "")
    description      = data.get("description", "")

    # ✅ نتأكد من كل القيم الأساسية
    if not email or not password or not username:
        return jsonify({"error": "email, password and username are required"}), 400

    # ✅ نتأكد أن اليوزر نيم يونيك
    existing = list(
        db.collection("users")
          .where("username", "==", username)
          .limit(1)
          .stream()
    )
    if existing:
        return jsonify({
            "error": "USERNAME_TAKEN",
            "message": "This username is already in use."
        }), 409


    volunteer_opt_in = str(data.get("volunteerOptIn", "false")).lower() == "true"
    specialization   = data.get("specialization", "")
    description      = data.get("description", "")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    try:
        res = rest_signup(email, password)  # Firebase
        uid = res["localId"]

        # إرسال رابط التحقق
        send_verification_email(res["idToken"])

        user_doc = {
            "uid": uid,
            "email": email,
             "username": username,  
            "role": role,
            "createdAt": SERVER_TIMESTAMP,
            "updatedAt": SERVER_TIMESTAMP,
            "profile": {
                "firstName": first_name,
                "lastName":  last_name,
                "gender":    gender,
                "interests": interests,
                "github":    github,
                "linkedin":  linkedin,
            }
        }

        if role == "examiner":
            user_doc["profile"]["specialization"] = specialization
            user_doc["profile"]["description"]    = description
            user_doc["volunteer"] = {"optIn": volunteer_opt_in}

        db.collection("users").document(uid).set(user_doc)

        # حفظ بيانات التسجيل مؤقتاً
        session["email"] = email
        session["temp_password"] = password

        # توجيه صفحة التحقق
        return render_template("CheckEmail.html")

    except Exception as e:
        try:
            return jsonify(e.response.json()), e.response.status_code
        except:
            return jsonify({"error": str(e)}), 500

# verification_email هنا كل مايخص
def send_verification_email(id_token):
    url = "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key=AIzaSyChtQ2FaenDwe7k7bfRB8Cw5G_5C4f_xt4"
    payload = {
        "requestType": "VERIFY_EMAIL",
        "idToken": id_token,
        "continueUrl": "http://127.0.0.1:5000/verified"
    }
    headers = {"Content-Type": "application/json"}

    r = requests.post(url, json=payload, headers=headers)

    print("\n🔥 VERIFY EMAIL RESPONSE 🔥")
    print("Status:", r.status_code)
    print("Body:", r.text)
    print("🔥 ----------------------🔥\n")

    return r

@app.route("/auto-login")
def auto_login():
    email = session.get("email")
    password = session.get("temp_password")

    if not email or not password:
        return redirect(url_for("login_page"))

    try:
        res = rest_signin(email, password)

        session["idToken"] = res["idToken"]
        session["uid"] = res["localId"]

        role = db.collection("users").document(res["localId"]).get().to_dict().get("role")

        if role == "owner":
            return redirect(url_for("owner_dashboard_page"))
        elif role == "examiner":
            return redirect(url_for("examiner_dashboard_page"))
        else:
            return redirect(url_for("profile_page"))

    except:
        return redirect(url_for("login_page"))

# تسجيل الدخول
@app.route("/api/signin", methods=["POST"])
def api_signin():
    data = request.form if request.form else (request.json or {})

    # المستخدم يقدر يكتب email أو username في نفس الحقل
    identifier = (data.get("identifier") or data.get("email") or "").strip()
    password   = data.get("password")

    if not identifier or not password:
        return render_template(
            "Login.html",
            error="Email/username and password are required."
        ), 400

    # 1) نحدّد الإيميل
    email = identifier

    # لو ما فيه @ نفترض أنه Username ونبحث عنه في Firestore
    if "@" not in identifier:
        # تأكدّي أن عندك حقل اسمه "username" داخل وثيقة المستخدم في Firestore
        user_q = (
            db.collection("users")
              .where("username", "==", identifier)
              .limit(1)
              .stream()
        )
        user_docs = list(user_q)
        if not user_docs:
            # Username غير صحيح
            return render_template(
                "Login.html",
                error="Invalid username or password. Please try again."
            ), 401

        user_data = user_docs[0].to_dict()
        email = user_data.get("email")
        if not email:
            return render_template(
                "Login.html",
                error="User record is missing email."
            ), 500

    try:
        # 2) نسجّل الدخول في Firebase Auth باستخدام الإيميل اللي استخرجناه
        res = rest_signin(email, password)

        # 3) نتأكد من تفعيل الإيميل من Firebase (نفس كودك السابق)
        url = "https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=AIzaSyChtQ2FaenDwe7k7bfRB8Cw5G_5C4f_xt4"
        r = requests.post(url, json={"idToken": res["idToken"]})
        user_info = r.json()

        email_verified = user_info["users"][0]["emailVerified"]
        if not email_verified:
            return render_template(
                "Login.html",
                error="Please verify your email before logging in."
            )

        uid = res["localId"]
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            session.clear()
            return render_template(
                "Login.html",
                error="User data not found."
            ), 401

        role = user_doc.to_dict().get("role", "user")

        session["idToken"] = res["idToken"]
        session["uid"] = uid

        if role == "owner":
            return redirect(url_for("owner_dashboard_page"))
        elif role == "examiner":
            return redirect(url_for("examiner_dashboard_page"))
        else:
            return redirect(url_for("profile_page"))

    except Exception:
        app.logger.exception("Signin failed")
        return render_template(
            "Login.html",
            error="Invalid email/username or password. Please try again."
        ), 401


# تسجيل الخروج
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# إرسال رابط إعادة تعيين كلمة المرور
@app.route("/api/reset", methods=["POST"])
def api_reset():
    email = request.form.get("email") or (request.json or {}).get("email")
    if not email:
        return jsonify({"error": "email is required"}), 400
    try:
        send_password_reset(email)
        return jsonify({"message": "Password reset email sent"})
    except Exception as e:
        try:
            return jsonify(e.response.json()), e.response.status_code
        except:
            return jsonify({"error": str(e)}), 500



# صحة الخادم
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/update-profile", methods=["POST"])
def api_update_profile():
    # لازم يكون مسجل دخول
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    uid = session.get("uid")
    user_ref = db.collection("users").document(uid)
    snap = user_ref.get()
    if not snap.exists:
        return jsonify({"error": 'User not found'}), 404

    data = request.get_json() or {}

    first_name     = (data.get("firstName") or "").strip()
    last_name      = (data.get("lastName") or "").strip()
    gender         = (data.get("gender") or "").strip()
    specialization = (data.get("specialization") or "").strip()
    github         = (data.get("github") or "").strip()
    linkedin       = (data.get("linkedin") or "").strip()
    description    = (data.get("description") or "").strip()
    interests      = (data.get("interests") or "").strip()

    updates = {
        "updatedAt": SERVER_TIMESTAMP,
        "profile.firstName": first_name,
        "profile.lastName": last_name,
        "profile.gender": gender,
        "profile.specialization": specialization,
        "profile.github": github,
        "profile.linkedin": linkedin,
        "profile.description": description,
        "profile.interests": interests,
    }

   

    user_ref.update(updates)

    return jsonify({"message": "Profile updated successfully"}), 200



@app.route("/forgot", methods=["GET", "POST"])
def forgot_page():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Please enter your email address.", "error")
            return render_template("ForgotPassword.html")

        try:
            # تستخدمين نفس الفنكشن اللي عندك في auth_rest
            send_password_reset(email)
            flash("If this email is registered, we’ve sent a reset link.", "success")
        except Exception as e:
            print("Reset error:", e)
            flash("Something went wrong. Please try again.", "error")

        return render_template("ForgotPassword.html", email=email)

    # GET
    return render_template("ForgotPassword.html")




if __name__ == "__main__":
    app.run(debug=True)