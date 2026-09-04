# Access-check compatibility layer for the deployed English Academy backend.
# Gunicorn loads this file automatically when running `gunicorn app:app`.

def post_worker_init(worker):
    from flask import jsonify
    import app as application

    def session_info_fixed():
        user, error = application.authenticated_user(False)
        if error:
            return jsonify({"authenticated": False, "error": error}), 401

        try:
            profile = (
                application.supabase.table("profiles")
                .select("is_subscribed")
                .eq("id", user.id)
                .maybe_single()
                .execute()
            )
            subscribed = bool(profile.data and profile.data.get("is_subscribed"))
        except Exception as exc:
            print(f"[SESSION PROFILE] {exc}")
            return jsonify({"authenticated": False, "error": "No se pudo comprobar el acceso."}), 500

        return jsonify({
            "authenticated": True,
            "email": user.email,
            "user_id": user.id,
            "is_subscribed": subscribed,
        })

    # Replace the existing /api/session view without changing app.py.
    for rule in application.app.url_map.iter_rules():
        if rule.rule == "/api/session":
            application.app.view_functions[rule.endpoint] = session_info_fixed
            print("[OK] /api/session access check patched with subscription status.")
            break
