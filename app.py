from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from firebase_admin_setup import db
from firebase_admin import auth as admin_auth
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from auth_rest import signup as rest_signup, signin as rest_signin, send_password_reset
from llm_service import generate_reply
 
# ===================================================================
# إعداد Flask
# ===================================================================
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "CHANGE_THIS_SECRET_IN_ENV_OR_CONFIG"  # غيّريه لقيمة آمنة في .env مثلاً
 
# ===================================================================
# دوال مساعدة عامة
# ===================================================================
 
def get_current_user_doc():
    """
    دالة مساعدة صغيرة لإرجاع document المستخدم الحالي من Firestore
    أو None إذا ما كان مسجّل دخول.
    """
    uid = session.get("uid")
    if not uid:
        return None
 
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        return None
 
    return user_doc
 
def get_user_full_name(user_doc):
    """
    استخراج الاسم الكامل للمستخدم من حقل profile في Firestore
    """
    user_data = user_doc.to_dict()
    first_name = user_data.get("profile", {}).get("firstName", "")
    last_name = user_data.get("profile", {}).get("lastName", "")
    full_name = f"{first_name} {last_name}".strip() or "User"
    return full_name
 
# ===================================================================
# ------------------ صفحات واجهة (GET) ------------------
# ===================================================================
 
@app.route("/")
def index():
    """
    الصفحة الرئيسية العامة (قبل تسجيل الدخول).
    ملاحظة: الكود القديم بعد return كان غير قابل للتنفيذ، لذا أبقيناه بسيطًا.
    """
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
    # يجب أن يكون المستخدم مسجّل دخول
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
 
    user_doc = get_current_user_doc()
    if not user_doc:
        return redirect(url_for("login_page"))
 
    user_data = user_doc.to_dict()
    full_name = get_user_full_name(user_doc)
 
    return render_template("Profile.html", user_data=user_data, user_name=full_name)
 
@app.route("/createproject")
def create_project_page():
    # بإمكانك إضافة تحقق تسجيل دخول لاحقًا لو حبيتي
    return render_template("CreateProject.html")
 
@app.route("/myprojectowner")
def my_project_owner_page():
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
 
    user_doc = get_current_user_doc()
    if not user_doc:
        return redirect(url_for("login_page"))
 
    full_name = get_user_full_name(user_doc)
    return render_template("myprojectowner.html", user_name=full_name)
 
@app.route("/myprojectexaminer")
def my_project_examiner_page():
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
 
    user_doc = get_current_user_doc()
    if not user_doc:
        return redirect(url_for("login_page"))
 
    full_name = get_user_full_name(user_doc)
    return render_template("myprojectexaminer.html", user_name=full_name)
 
@app.route("/ownerdashboard")
def owner_dashboard_page():
    # 1) نتحقق أن المستخدم مسجل دخول
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
 
    # 2) نحضّر بيانات المستخدم
    user_doc = get_current_user_doc()
    if not user_doc:
        return redirect(url_for("login_page"))
 
    full_name = get_user_full_name(user_doc)
    return render_template("Ownerdashboard.html", user_name=full_name)
 
@app.route("/examinerdashboard")
def examiner_dashboard_page():
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
 
    user_doc = get_current_user_doc()
    if not user_doc:
        return redirect(url_for("login_page"))
 
    full_name = get_user_full_name(user_doc)
    return render_template("Examinerdashboard.html", user_name=full_name)
 
@app.route("/projectdetailsowner")
def project_details_owner_page():
    return render_template("ProjectDetailsOwner.html")
 
@app.route("/createtask")
def create_task_page():
    # نتأكد أن الأونر مسجل دخول
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
 
    user_doc = get_current_user_doc()
    user_name = get_user_full_name(user_doc) if user_doc else "User"
 
    return render_template("CreateTask.html", user_name=user_name)
 
@app.route("/projectdetailsexaminer")
def project_details_examiner_page():
    return render_template("ProjectDetailsExaminer.html")
 
@app.route("/invitation")
def invitation_page():
    return render_template("invitation.html")
 
@app.route("/feedback")
def feedback_page():
    return render_template("feedback.html")
 
# ===================================================================
#              ------------- CreateTask ---------------
# ===================================================================
 
 
@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    """
    إنشاء تاسك جديد في Firestore.
    البيانات المتوقعة من الواجهة:
    - title: عنوان/وصف التاسك
    - conversationType: "human-ai" أو "human-human"
    - turns: عدد الـ turns (int)
    - examiners: قائمة إيميلات examiners
    """
    if not session.get("idToken"):
        return jsonify({"error": "unauthorized"}), 401
 
    data = request.get_json() or {}
 
    title = (data.get("title") or "").strip()
    conversation_type = (data.get("conversationType") or "human-ai").strip()
    turns = int(data.get("turns") or 2)
    examiners = data.get("examiners") or []
 
    if not title:
        return jsonify({"error": "Task title is required."}), 400
 
    # عدد المقيّمين المطلوب حسب نوع المحادثة
    required_examiners = 2 if conversation_type == "human-human" else 1
    if len(examiners) != required_examiners:
        return jsonify({
            "error": f"Invalid number of examiners. Expected {required_examiners}, got {len(examiners)}"
        }), 400
 
    owner_uid = session.get("uid")
 
    task_doc = {
        "title": title,
        "conversationType": conversation_type,
        "turns": turns,
        "examiners": examiners,
        "ownerUid": owner_uid,
        "status": "draft",           # ممكن تغيرينها لاحقاً
        "createdAt": SERVER_TIMESTAMP,
        "updatedAt": SERVER_TIMESTAMP,
    }
 
    # حالياً نخزنها في collection بإسم "tasks"
    doc_ref = db.collection("tasks").add(task_doc)[1]
 
    return jsonify({
        "message": "Task created successfully.",
        "taskId": doc_ref.id
 
    }), 201
 
# ===================================================================
# ------------- صفحة Human ↔ AI Conversation (Front) ---------------
# ===================================================================
 
@app.route("/conversation-ai")
def conversation_ai_page():
    """
    صفحة المحادثة Human ↔ AI.
    - تقبل taskId اختياريًا من الـ query string
      مثل: /conversation-ai?taskId=ABC123
    - إذا موجود taskId نحاول نقرأ التاسك من Firestore
      ونستخدم عدد الـ turns والعنوان من هناك.
    """
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
 
    user_doc = get_current_user_doc()
    user_name = get_user_full_name(user_doc) if user_doc else "User"
 
    # نقرأ taskId من الرابط (اختياري)
    task_id = request.args.get("taskId")
 
    # قيم افتراضية لو ما وجدنا تاسك
    max_turns = 6
    task_title = "Conversation task topic"
 
    if task_id:
        try:
            task_snapshot = db.collection("tasks").document(task_id).get()
            if task_snapshot.exists:
                task_data = task_snapshot.to_dict()
                max_turns = int(task_data.get("turns", 6))
                task_title = task_data.get("title", task_title)
        except Exception as e:
            app.logger.exception("Error loading task in conversation_ai_page: %s", e)
 
    return render_template(
        "ConversationH-AI.html",
        user_name=user_name,
        max_turns=max_turns,
        task_title=task_title,
        task_id=task_id,
)

# ===================================================================
# ------------- صفحة Human ↔ Human Conversation (Front) ------------
# ===================================================================
 
@app.route("/conversation-hh")
def conversation_hh_page():
    """
    صفحة المحادثة Human ↔ Human.
 
    - تستقبل taskId من الـ query string (اختياري):
        /conversation-hh?taskId=ABC123
 
    - إذا وُجد taskId نحاول نقرأ التاسك من Firestore
      ونستخدم عدد الـ turns والعنوان من هناك.
 
    - هذه الصفحة لا تستدعي أي موديل AI ولا تخزن الرسائل حالياً.
    """
    # يجب أن يكون المستخدم مسجّل دخول
    if not session.get("idToken"):
        return redirect(url_for("login_page"))
 
    # نجيب اسم المستخدم الحالي
    user_doc = get_current_user_doc()
    user_name = get_user_full_name(user_doc) if user_doc else "User"
 
    # نقرأ taskId من الرابط (اختياري)
    task_id = request.args.get("taskId")
 
    # قيم افتراضية لو ما وجدنا تاسك
    max_turns = 6
    task_title = "Human ↔ Human conversation task"
 
    if task_id:
        try:
            task_snapshot = db.collection("tasks").document(task_id).get()
            if task_snapshot.exists:
                task_data = task_snapshot.to_dict()
                max_turns = int(task_data.get("turns", 6))
                task_title = task_data.get("title", task_title)
 
                # لو نوع المحادثة في التاسك ليس human-human
                conv_type = task_data.get("conversationType")
                if conv_type != "human-human":
                    # نوجّه المستخدم لصفحة الـ AI لو التاسك من نوع human-ai
                    return redirect(url_for("conversation_ai_page", taskId=task_id))
        except Exception as e:
            app.logger.exception(
                "Error loading task in conversation_hh_page: %s", e
            )
 
    return render_template(
        "ConversationH-H.html",
        user_name=user_name,
        max_turns=max_turns,
        task_title=task_title,
        task_id=task_id,
    )
 
# ===================================================================
# ------------------ مصادقة (POST APIs) ------------------
# ===================================================================
 
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
    email    = data.get("email")
    password = data.get("password")
 
    if not email or not password:
        return render_template(
            "Login.html",
            error="Email and password are required."
        ), 400
 
    try:
        res = rest_signin(email, password)
        uid = res["localId"]
 
        # جلب بيانات المستخدم من Firestore
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            # مستخدم مسجل في Auth لكن لا يوجد document في Firestore
            session.clear()
            return render_template(
                "Login.html",
                error="User data not found."
            ), 401
 
        role = user_doc.to_dict().get("role", "user")  # افتراضي "user" إذا ما فيه role
 
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
 
    except Exception:
        app.logger.exception("Signin failed")
        return render_template(
            "Login.html",
            error="Invalid email or password. Please try again."
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
 
# التحقق من idToken (للاستخدام داخل صفحات محمية/طلبات AJAX)
@app.route("/api/verify", methods=["POST"])
def api_verify():
    id_token = (
        request.form.get("idToken")
        or (request.json or {}).get("idToken")
        or session.get("idToken")
    )
    if not id_token:
        return jsonify({"error": "idToken is required"}), 400
    try:
        decoded = admin_auth.verify_id_token(id_token)
        return jsonify({"uid": decoded["uid"], "email": decoded.get("email")})
    except Exception as e:
        return jsonify({"error": str(e)}), 401
 
# ===================================================================
# -------- API للمحادثة Human ↔ AI (الجزء المهم ) ----------
# ===================================================================
 
def generate_ai_response(user_message: str) -> str:
    """
    تستدعي موديل Llama 2 من خلال الدالة generate_reply في ملف llm_service.py
    """
    user_message = (user_message or "").strip()
    if not user_message:
        return "I didn't receive any message. Could you please write it again."
    try:
        # نستخدم الموديل الفعلي
        return generate_reply(user_message)
    except Exception as e:
        print("⚠️ AI error in generate_ai_response:", e)
        return "Error: unable to generate a response right now. Please try again later   ."
 
@app.route("/api/conversation-ai", methods=["POST"])
def api_conversation_ai():
    """
    هذه الـ API تستقبل رسالة من المستخدم وتعيد رد AI بصيغة JSON.
 
    البيانات المتوقعة من الـ Front:
    - message : نص رسالة المستخدم
    - taskId  : (اختياري) رقم/معرّف التاسك الحالي
    - turn    : رقم التورن الحالي بعد إرسال هذه الرسالة
    """
    data = request.get_json() or {}
 
    message = (data.get("message") or "").strip()
    task_id = data.get("taskId")
    turn = data.get("turn")
 
    if not message:
        return jsonify({"error": "message is required"}), 400
 
    # لوج بسيط يساعدك لاحقاً في الديبق أو التخزين في Firestore
    app.logger.info(
        "Conversation | taskId=%s | turn=%s | text=%s",
        task_id,
        turn,
        message[:80],
    )
 
    ai_reply = generate_ai_response(message)
    return jsonify({"reply": ai_reply})
 
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    مسار إضافي متوافق مع الفرونت الحالي.
    يعيد نفس منطق /api/conversation-ai تمامًا.
    """
    return api_conversation_ai()
 
# ===================================================================
# صحة الخادم
# ===================================================================
 
@app.route("/health")
def health():
    return jsonify({"status": "ok"})
 
if __name__ == "__main__":
    # شغّل الخادم في وضع التطوير
    app.run(debug=True)
 
 

