from flask import Blueprint, render_template
from flask_login import login_required
import requests
from app.models.cotacao import Cotacao

bp = Blueprint('cotacoes', __name__)

def get_cotacao_awesomeapi(moeda_origem, moeda_destino='BRL'):
    """Busca cotação na API"""
    par = f"{moeda_origem}-{moeda_destino}"
    url = f"https://economia.awesomeapi.com.br/json/last/{par}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        dados = response.json()
        
        cotacao = float(dados[f"{moeda_origem}{moeda_destino}"]["bid"])
        variacao = float(dados[f"{moeda_origem}{moeda_destino}"]["pctChange"])
        
        return cotacao, variacao
        
    except Exception as e:
        print(f"Erro ao obter cotação {par}:", e)
        return None, None

def get_cotacao_atualizada(nome, moeda_origem, moeda_destino='BRL'):
    """Busca cotação no banco ou na API se necessário"""
    cotacao_db = Cotacao.get_cotacao(nome)
    
    # Se não existe no banco ou está expirada, busca na API
    if not cotacao_db or cotacao_db.cotacao_expirada():
        cotacao, variacao = get_cotacao_awesomeapi(moeda_origem, moeda_destino)
        if cotacao:
            Cotacao.salvar_cotacao(nome, cotacao)
            return cotacao, variacao
        
        # Se não encontrou na API, busca no banco
        cotacao_db = Cotacao.get_cotacao(nome)
        if cotacao_db:
            return cotacao_db.valor, None
            

    # Retorna do banco se existe e não está expirada
    if cotacao_db:
        return cotacao_db.valor, None
        
    return None, None


def get_all_cotacoes():
    get_cotacao_atualizada('EURBRL', 'EUR')
    get_cotacao_atualizada('USDBRL', 'USD')
    get_cotacao_atualizada('BTCBRL', 'BTC')
    

@bp.route('/cotacoes')
@login_required
def index():
    # Busca cotações
    cotacoes = {}
    
    # EUR-BRL
    valor, variacao = get_cotacao_atualizada('EURBRL', 'EUR')
    if valor:
        cotacoes['EUR'] = {
            'valor': Cotacao.formatar_valor(valor, 'BRL'),
            'variacao': float(variacao) if variacao is not None else None
        }
    
    # USD-BRL
    valor, variacao = get_cotacao_atualizada('USDBRL', 'USD')
    if valor:
        cotacoes['USD'] = {
            'valor': Cotacao.formatar_valor(valor, 'BRL'),
            'variacao': float(variacao) if variacao is not None else None
        }
    
    # BTC-BRL
    valor, variacao = get_cotacao_atualizada('BTCBRL', 'BTC')
    if valor:
        cotacoes['BTC'] = {
            'valor': Cotacao.formatar_valor(valor, 'BRL'),
            'variacao': float(variacao) if variacao is not None else None
        }
    
    return render_template('cotacoes/index.html', cotacoes=cotacoes, data=Cotacao.get_cotacao('BTCBRL').get_data_e_hora_sp()) 