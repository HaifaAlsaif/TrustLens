from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    abort,
)
from firebase_admin_setup import db
from google.cloud.firestore_v1 import SERVER_TIMESTAMP


def init_task_routes(app):

    # ======== صفحة قائمة التاسكات (لو حابة صفحة مستقلة) =========
    @app.route("/projects/<project_id>/tasks", methods=["GET"])
    def tasks_list_page(project_id):
        if not session.get("idToken"):
            return redirect(url_for("login_page"))

        owner_uid = session.get("uid")

        # نتأكد أن المشروع تابع للأونر
        proj_doc = db.collection("projects").document(project_id).get()
        if not proj_doc.exists:
            abort(404)
        if proj_doc.to_dict().get("owner_id") != owner_uid:
            abort(403)

        tasks_snap = (
            db.collection("tasks")
            .where("project_id", "==", project_id)
            .stream()
        )

        tasks = []
        for t in tasks_snap:
            d = t.to_dict() or {}
            d["id"] = t.id
            tasks.append(d)

        # لو ما عندك TasksOwner.html تقدري تشيل هذا الراوت أو ترجعيه
        return render_template("TasksOwner.html", project_id=project_id, tasks=tasks)

    # ======== صفحة إنشاء تاسك =========
    @app.route("/projects/<project_id>/tasks/create", methods=["GET", "POST"])
    def create_task(project_id):
        if not session.get("idToken"):
            return redirect(url_for("login_page"))

        owner_uid = session.get("uid")

        # نتأكد أن المشروع للأونر
        proj_doc = db.collection("projects").document(project_id).get()
        if not proj_doc.exists:
            abort(404)
        if proj_doc.to_dict().get("owner_id") != owner_uid:
            abort(403)

        # نجيب الـ examiners المقبولين عشان نعرضهم في CreateTask
        accepted = (
            db.collection("invitations")
            .where("project_id", "==", project_id)
            .where("status", "==", "accepted")
            .stream()
        )

        examiners = []
        for inv in accepted:
            data = inv.to_dict()
            ex_doc = db.collection("users").document(data["examiner_id"]).get()
            if ex_doc.exists:
                u = ex_doc.to_dict()
                email = u.get("email", "")
                if email:
                    examiners.append(email)

        # ========= POST: حفظ التاسك =========
        if request.method == "POST":
            title = (request.form.get("task_title") or "").strip()
            conv_type = request.form.get("conv_type", "human-ai")
            turns_raw = request.form.get("turns", "2")
            selected_examiners = request.form.getlist("examiner")

            if not title:
                flash("Task title is required.", "error")
                return render_template(
                    "CreateTask.html",
                    project_id=project_id,
                    examiners=examiners,
                )

            required = 2 if conv_type == "human-human" else 1
            if len(selected_examiners) != required:
                msg = (
                    "Human ↔ Human requires exactly 2 examiners."
                    if required == 2
                    else "Human ↔ AI requires exactly 1 examiner."
                )
                flash(msg, "error")
                return render_template(
                    "CreateTask.html",
                    project_id=project_id,
                    examiners=examiners,
                )

            try:
                turns = int(turns_raw)
            except ValueError:
                turns = 2

            # 👇 هنا نخزن الإيميلات مباشرة
            task_doc = {
                "project_id": project_id,
                "owner_id": owner_uid,
                "title": title,
                "conversationType": conv_type,
                "turns": turns,
                "examiners": selected_examiners,  # list of emails
                "status": "pending",  # تبدأ Pending
                "createdAt": SERVER_TIMESTAMP,
                "updatedAt": SERVER_TIMESTAMP,
            }

            db.collection("tasks").add(task_doc)

            flash("Task created successfully.", "success")
            return redirect(url_for("project_details_owner", project_id=project_id))

        # ========= GET: عرض صفحة الإنشاء =========
        return render_template(
            "CreateTask.html",
            project_id=project_id,
            examiners=examiners,
        )

    # ================ API: PROJECT TASKS LIST ================
    @app.route("/api/project_tasks/<project_id>")
    def api_project_tasks(project_id):
        """ترجع كل التاسكات التابعة لمشروع معيّن للأونر (لاستخدامها في الكروت داخل ProjectDetailsOwner)."""
        if not session.get("idToken"):
            return jsonify({"error": "Unauthorized"}), 401

        owner_uid = session.get("uid")

        proj_doc = db.collection("projects").document(project_id).get()
        if not proj_doc.exists:
            return jsonify({"error": "Project not found"}), 404
        if proj_doc.to_dict().get("owner_id") != owner_uid:
            return jsonify({"error": "Forbidden"}), 403

        docs = (
            db.collection("tasks")
            .where("project_id", "==", project_id)
            .stream()
        )

        tasks = []
        for d in docs:
            t = d.to_dict() or {}

            examiners_emails = t.get("examiners", []) or []
            primary_email = examiners_emails[0] if examiners_emails else ""

            tasks.append(
                {
                    "id": d.id,
                    "title": t.get("title", ""),
                    "status": (t.get("status") or "pending").lower(),
                    "conversationType": t.get("conversationType", "human-ai"),
                    "turns": t.get("turns", 2),
                    "examinerCount": len(examiners_emails),
                    "primaryExaminerEmail": primary_email,
                }
            )

        return jsonify({"tasks": tasks})

    # ================ API: DELETE TASK =================
    @app.route("/api/tasks/<task_id>/delete", methods=["POST"])
    def api_delete_task(task_id):
        if not session.get("idToken"):
            return jsonify({"error": "Unauthorized"}), 401

        owner_uid = session.get("uid")

        ref = db.collection("tasks").document(task_id)
        snap = ref.get()
        if not snap.exists:
            return jsonify({"error": "Task not found"}), 404

        if snap.to_dict().get("owner_id") != owner_uid:
            return jsonify({"error": "Forbidden"}), 403

        ref.delete()
        return jsonify({"success": True})

    # ================ API: UPDATE TASK (EDIT STATUS) =================
    @app.route("/api/tasks/<task_id>/update", methods=["POST"])
    def api_update_task(task_id):
        """حالياً نسمح بتعديل status فقط: pending / progress / completed"""
        if not session.get("idToken"):
            return jsonify({"error": "Unauthorized"}), 401

        owner_uid = session.get("uid")

        ref = db.collection("tasks").document(task_id)
        snap = ref.get()
        if not snap.exists:
            return jsonify({"error": "Task not found"}), 404

        if snap.to_dict().get("owner_id") != owner_uid:
            return jsonify({"error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        allowed_statuses = {"pending", "progress", "completed"}

        new_status = data.get("status")
        if new_status:
            new_status = str(new_status).lower().strip()
            if new_status not in allowed_statuses:
                return jsonify({"error": "Invalid status value"}), 400
        else:
            return jsonify({"error": "No status provided"}), 400

        ref.update(
            {
                "status": new_status,
                "updatedAt": SERVER_TIMESTAMP,
            }
        )

        return jsonify({"success": True, "status": new_status})
