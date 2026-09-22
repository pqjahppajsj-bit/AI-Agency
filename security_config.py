import os

def configure_security(app):
    production = os.getenv("PRODUCTION", "0") == "1"

    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", app.config.get("SECRET_KEY")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=production,
        SESSION_COOKIE_NAME="ai_agency_session",
        PERMANENT_SESSION_LIFETIME=3600,
    )

    return app
