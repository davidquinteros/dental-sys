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

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(patients_bp, url_prefix="/api/patients")
    app.register_blueprint(appointments_bp, url_prefix="/api/appointments")
    app.register_blueprint(treatments_bp, url_prefix="/api/treatments")
    app.register_blueprint(billing_bp, url_prefix="/api/billing")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(permissions_bp, url_prefix="/api/permissions")
    app.register_blueprint(consultorios_bp, url_prefix="/api/consultorios")

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
