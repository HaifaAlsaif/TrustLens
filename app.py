from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from firebase_admin_setup import db
from firebase_admin import auth as admin_auth
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from auth_rest import signup as rest_signup, signin as rest_signin, send_password_reset

# إعداد Flask
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "CHANGE_THIS_SECRET_IN_ENV_OR_CONFIG"  # غيّريه لقيمة آمنة

# ------------------ صفحات واجهة (GET) ------------------

@app.route("/")
def index():
    if session.get("idToken"):
        return render_template("HomePage.html")
    return render_template("index.html")

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
    return render_template("Profile.html")

@app.route("/createproject")
def create_project_page():
    return render_template("CreateProject.html")

@app.route("/myprojectowner")
def my_project_owner_page():
    return render_template("myprojectowner.html")

@app.route("/myprojectexaminer")
def my_project_examiner_page():
    return render_template("myprojectexaminer.html")

@app.route("/ownerdashboard")
def owner_dashboard_page():
    return render_template("Ownerdashboard.html")

@app.route("/projectdetailsowner")
def project_details_owner_page():
    return render_template("ProjectDetailsOwner.html")

@app.route("/projectdetailsexaminer")
def project_details_examiner_page():
    return render_template("ProjectDetailsExaminer.html")


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

        # owner ممكن تضيفي organization/description لاحقًا من صفحة Edit

        db.collection("users").document(uid).set(user_doc)

        session["idToken"] = res["idToken"]
        session["uid"] = uid
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
        # ما نكشف تفاصيل كثيرة للمستخدم
        return render_template("Login.html",
                               error="Email and password are required."), 400
    try:
        res = rest_signin(email, password)
        session["idToken"] = res["idToken"]
        session["uid"] = res["localId"]
        return redirect(url_for("profile_page"))
    except Exception:
        # نسجّل التفاصيل في اللوق لكن ما نعرضها للمستخدم
        app.logger.exception("Signin failed")
        # رسالة موحّدة وآمنة (لا تفصح هل الإيميل موجود أو لا)
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
