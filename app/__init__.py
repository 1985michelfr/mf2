from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_session import Session
from config import Config
from sqlalchemy import inspect, text
from sqlalchemy import Column, Integer

db = SQLAlchemy()
login_manager = LoginManager()
session = Session()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.config['DEBUG'] = True

    # Configuração do cookie de sessão
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE='Lax'
    )

    db.init_app(app)
    login_manager.init_app(app)
    session.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.routes import auth
    from app.routes import goals
    from app.routes import cotacoes
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(goals.bp)
    app.register_blueprint(cotacoes.bp)

    with app.app_context():
        # Primeiro, cria todas as tabelas
        db.create_all()
        
        # Depois, verifica e adiciona a coluna priority se não existir
        try:
            add_column(db.engine, 'goal', Column('priority', Integer()))
            db.session.commit()
        except Exception as e:
            print(f"Aviso: {str(e)}")
            # Não levanta erro pois a coluna pode já existir
            db.session.rollback()

    return app 

def add_column(engine, table_name, column):
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    if column.name not in columns:
        column_name = column.compile(dialect=engine.dialect)
        column_type = column.type.compile(engine.dialect)
        sql = text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}')
        with engine.connect() as conn:
            conn.execute(sql)
            conn.commit() 