from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flasgger import Swagger
from dotenv import load_dotenv
from app.swagger_spec import SWAGGER_CONFIG, SWAGGER_TEMPLATE
import os

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
bcrypt = Bcrypt()


def create_app(config=None):
    app = Flask(__name__)

    # Configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "postgresql://postgres:password@localhost:5432/dental_clinic_db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Each gunicorn worker (see entrypoint.sh) gets its own pool of this size;
    # pool_recycle keeps connections from going stale against a managed
    # Postgres (e.g. Supabase) that can drop idle connections server-side.
    # Defaults are conservative (small/free-tier DB plans) — see
    # backend/.env.example for suggested values once on a bigger plan.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": int(os.getenv("DB_POOL_SIZE", 3)),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 2)),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", 30)),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", 280)),
        "pool_pre_ping": True,
    }
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-in-prod")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 3600))

    if config:
        app.config.update(config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})
    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)

    # Multi-tenancy: resolve the current clinic once per request, and register
    # the session-level event listener that auto-filters every clinic-scoped
    # query, plus the connection-pool checkout listener that mirrors it into
    # Postgres session GUCs for RLS. See app/middleware/tenancy.py.
    from app.middleware.tenancy import resolve_request_clinic  # noqa: F401 (registers event listeners on import)
    app.before_request(resolve_request_clinic)

    # JWT error handlers
    @jwt.unauthorized_loader
    def unauthorized_callback(reason):
        from flask import jsonify
        return jsonify({"error": "Token requerido", "message": reason}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        from flask import jsonify
        return jsonify({"error": "Token expirado", "message": "Por favor inicie sesión nuevamente"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        from flask import jsonify
        return jsonify({"error": "Token inválido", "message": reason}), 422

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.users import users_bp
    from app.routes.patients import patients_bp
    from app.routes.appointments import appointments_bp
    from app.routes.treatments import treatments_bp
    from app.routes.billing import billing_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.permissions import permissions_bp
    from app.routes.consultorios import consultorios_bp
    from app.routes.appointment_types import appointment_types_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(patients_bp, url_prefix="/api/patients")
    app.register_blueprint(appointments_bp, url_prefix="/api/appointments")
    app.register_blueprint(treatments_bp, url_prefix="/api/treatments")
    app.register_blueprint(billing_bp, url_prefix="/api/billing")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(permissions_bp, url_prefix="/api/permissions")
    app.register_blueprint(consultorios_bp, url_prefix="/api/consultorios")
    app.register_blueprint(appointment_types_bp, url_prefix="/api/appointment-types")

    # Health check
    @app.route("/api/health")
    def health():
        """
        Estado del servicio
        ---
        tags:
          - Sistema
        responses:
          200:
            description: El servicio está funcionando correctamente
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: ok
                version:
                  type: string
                  example: 1.0.0
        """
        from flask import jsonify
        return jsonify({"status": "ok", "version": "1.0.0"})

    return app
