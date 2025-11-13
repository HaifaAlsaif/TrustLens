
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from firebase_admin_setup import db
from firebase_admin import auth as admin_auth
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from auth_rest import signup as rest_signup, signin as rest_signin, send_password_reset
from datetime import datetime
from google.cloud import storage
import uuid
import json
# إعداد Flask
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "CHANGE_THIS_SECRET_IN_ENV_OR_CONFIG"  # غيّريه لقيمة آمنة

# ------------------ صفحات واجهة (GET) ------------------

# 1) استبدلي دالة index() كاملة بهذا الكود
@app.route("/")
def index():
    return render_template("HomePage.html")
    

    uid      = session["uid"]
    user_doc = db.collection("users").document(uid).get()
    role     = user_doc.to_dict().get("role", "user")

    if role == "examiner":
        return redirect(url_for("examiner_dashboard_page"))
    elif role == "owner":
        return redirect(url_for("owner_dashboard_page"))
    else:
        return render_template("HomePage.html")
@app.route("/login")
def login_page():
    return render_template("Login.html")

@app.route("/signup")
def signup_page():
    return render_template("signup.html")

@app.route("/forgot")
def forgot_page():
    return render_template("ForgotPassword.html")

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

@app.route("/projectdetailsowner")
def project_details_owner_page():
    return render_template("ProjectDetailsOwner.html")

@app.route("/projectdetailsexaminer")
def project_details_examiner_page():
    return render_template("ProjectDetailsExaminer.html")


@app.route("/feedback")
def feedback_page():
    return render_template("feedback.html")

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



# ------------------ Create Project (مع إنشاء سجلات invitations منفصلة) ------------------
@app.route("/api/create_project", methods=["POST"])
def api_create_project():
    if not session.get("idToken"):
        return jsonify({"error": "Unauthorized"}), 401

    uid = session.get("uid")
    if not uid:
        return jsonify({"error": "Missing user ID"}), 401

    data = request.form if request.form else request.json or {}

    project_name = data.get("project_name")
    description  = data.get("description")
    category     = data.get("category")
    domains      = data.getlist("domain") if hasattr(data, "getlist") else data.get("domain", [])

    # ✅ هذا الجزء المهم
    examiners_raw = data.get("invited_examiners", "[]")
    try:
        examiners = json.loads(examiners_raw) if isinstance(examiners_raw, str) else examiners_raw
    except json.JSONDecodeError:
        examiners = []

    if not project_name or not description or not category:
        return jsonify({"error": "Missing required fields"}), 400

    dataset_url = ""
    file = request.files.get("dataset")
    if file and file.filename:
        storage_client = storage.Client()
        bucket = storage_client.bucket("trustlens.appspot.com")
        blob_name = f"datasets/{uid}/{uuid.uuid4()}_{file.filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file, content_type="text/csv")
        blob.make_public()
        dataset_url = blob.public_url

    owner_doc = db.collection("users").document(uid).get()
    if not owner_doc.exists:
        return jsonify({"error": "Owner not found"}), 404

    owner_data = owner_doc.to_dict()
    owner_name = f"{owner_data.get('profile', {}).get('firstName', '')} {owner_data.get('profile', {}).get('lastName', '')}".strip()

    project_id = str(uuid.uuid4())
    project_doc = {
        "project_ID": project_id,
        "project_name": project_name,
        "description": description,
        "domain": domains,
        "category": category,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "owner_id": uid,
        "dataset_url": dataset_url,
        "invited_examiners": [ex.get("email") for ex in examiners],
        "status": "active"
    }

    # إنشاء الدعوات
    batch = db.batch()
    for ex in examiners:
        email = ex.get("email")
        if not email:
            continue

        examiner_docs = list(db.collection("users").where("email", "==", email).where("role", "==", "examiner").limit(1).stream())
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
            "examiner_email": email
        }
        batch.set(invitation_ref, invitation_data)

    batch.commit()
    db.collection("projects").document(project_id).set(project_doc)

    return jsonify({"message": "Project created successfully", "project_ID": project_id}), 201
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
    email        = data.get("email")
    password     = data.get("password")
    display_name = data.get("displayName", "")

    role         = data.get("role", "user")  # owner أو examiner
    first_name   = data.get("firstName", "")
    last_name    = data.get("lastName", "")
    gender       = data.get("gender", "")
    interests    = data.get("interests", "")
    github       = data.get("github", "")
    linkedin     = data.get("linkedin", "")

    volunteer_opt_in = str(data.get("volunteerOptIn", "false")).lower() == "true"
    specialization   = data.get("specialization", "")
    description      = data.get("description", "")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    try:
        res = rest_signup(email, password)  # إنشاء مستخدم في Firebase Auth
        uid = res["localId"]

        user_doc = {
            "uid": uid,
            "email": email,
            "displayName": display_name,
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
            # حقول إضافية للـ Examiner
            user_doc["profile"]["specialization"] = specialization
            user_doc["profile"]["description"]    = description
            user_doc["volunteer"] = {"optIn": volunteer_opt_in}

       

        db.collection("users").document(uid).set(user_doc)

             # حفظ التوكن والـ UID في الجلسة
        session["idToken"] = res["idToken"]
        session["uid"]     = uid

        # التوجيه حسب الدور
        if role == "owner":
            return redirect(url_for("owner_dashboard_page"))
        elif role == "examiner":
            return redirect(url_for("examiner_dashboard_page")) 
        else:
            return redirect(url_for("profile_page"))

    except Exception as e:
        try:
            return jsonify(e.response.json()), e.response.status_code
        except:
            return jsonify({"error": str(e)}), 500


# تسجيل الدخول
@app.route("/api/signin", methods=["POST"])
def api_signin():
    data = request.form if request.form else (request.json or {})
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return render_template("Login.html",
                               error="Email and password are required."), 400
    try:
        res = rest_signin(email, password)
        uid = res["localId"]

        # جلب بيانات المستخدم من Firestore
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            # مستخدم مسجل في Auth لكن مافيه document في Firestore
            session.clear()
            return render_template("Login.html",
                                   error="User data not found."), 401

        role = user_doc.to_dict().get("role", "user")  # افتراضي "user" إذا مافيش role

        # حفظ التوكن والـ UID في الجلسة
        session["idToken"] = res["idToken"]
        session["uid"] = uid

        # التوجيه حسب الدور
        if role == "owner":
            return redirect(url_for("owner_dashboard_page"))
        elif role == "examiner":
            return redirect(url_for("examiner_dashboard_page"))
        else:
            return redirect(url_for("profile_page"))

    except Exception:
        app.logger.exception("Signin failed")
        return render_template("Login.html",
                               error="Invalid email or password. Please try again."), 401

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

# التحقق من idToken (للاستخدام داخل صفحات محمية/طلبات AJAX)
@app.route("/api/verify", methods=["POST"])
def api_verify():
    id_token = request.form.get("idToken") or (request.json or {}).get("idToken") or session.get("idToken")
    if not id_token:
        return jsonify({"error": "idToken is required"}), 400
    try:
        decoded = admin_auth.verify_id_token(id_token)
        return jsonify({"uid": decoded["uid"], "email": decoded.get("email")})
    except Exception as e:
        return jsonify({"error": str(e)}), 401

# صحة الخادم
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True)