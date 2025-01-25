import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-padrao'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///financial_app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configurações da sessão
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)  # Sessão dura 30 dias
    SESSION_PERMANENT = True  # Torna a sessão permanente
    SESSION_TYPE = 'filesystem'  # Armazena a sessão no sistema de arquivos 