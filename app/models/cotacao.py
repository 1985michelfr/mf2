from datetime import datetime, timedelta
from app import db
import pytz

class Cotacao(db.Model):
    __tablename__ = 'cotacao'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String, nullable=False, unique=True)
    # Armazena sempre em UTC
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    valor = db.Column(db.Float, nullable=False)

    @staticmethod
    def get_datetime_sp():
        """Retorna o datetime atual no fuso horário de São Paulo"""
        fuso_horario_sp = pytz.timezone('America/Sao_Paulo')
        return datetime.now(fuso_horario_sp)

    def get_data_sp(self):
        """Retorna a data da cotação no fuso horário de São Paulo"""
        fuso_horario_sp = pytz.timezone('America/Sao_Paulo')
        return self.data.replace(tzinfo=pytz.UTC).astimezone(fuso_horario_sp)
    
    def get_data_e_hora_sp(self):
        """Retorna a data da cotação no fuso horário de São Paulo"""
        fuso_horario_sp = pytz.timezone('America/Sao_Paulo')
        return self.data.replace(tzinfo=pytz.UTC).astimezone(fuso_horario_sp).strftime('%d/%m/%Y %H:%M:%S')

    def cotacao_expirada(self, minutos=30):
        """Verifica se a cotação tem mais de X minutos"""
        if not self.data:
            return True
        
        agora_sp = self.get_datetime_sp()
        data_sp = self.get_data_sp()
        
        diferenca = agora_sp - data_sp
        return diferenca > timedelta(minutes=minutos)

    @staticmethod
    def get_cotacao(nome):
        """Busca uma cotação pelo nome"""
        return Cotacao.query.filter_by(nome=nome).first()

    @staticmethod
    def salvar_cotacao(nome, valor):
        """Salva ou atualiza uma cotação"""
        cotacao = Cotacao.get_cotacao(nome)
        
        if cotacao:
            cotacao.valor = valor
            cotacao.data = datetime.utcnow()  # Salva em UTC
        else:
            cotacao = Cotacao(nome=nome, valor=valor)
            db.session.add(cotacao)
            
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao salvar cotação: {str(e)}")
            return False

    @staticmethod
    def formatar_valor(valor, moeda='BRL'):
        """Formata o valor conforme a moeda"""
        if moeda == 'BRL':
            return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        elif moeda == 'USD':
            return f"$ {valor:,.2f}"
        elif moeda == 'EUR':
            return f"€ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        elif moeda == 'BTC':
            return f"₿ {valor:.8f}"
        return str(valor)

    @staticmethod
    def converter_moeda(valor, moeda_origem, moeda_destino):
        """Converte um valor entre duas moedas"""
        if moeda_origem == moeda_destino:
            return valor

        # Se a moeda de origem é BRL, basta dividir pela cotação da moeda destino
        if moeda_origem == 'BRL':
            cotacao = Cotacao.get_cotacao(f"{moeda_destino}BRL")
            if cotacao:
                return valor / cotacao.valor
            return None

        # Se a moeda destino é BRL, basta multiplicar pela cotação da moeda origem
        if moeda_destino == 'BRL':
            cotacao = Cotacao.get_cotacao(f"{moeda_origem}BRL")
            if cotacao:
                return valor * cotacao.valor
            return None

        # Se nenhuma das moedas é BRL, converte primeiro para BRL e depois para a moeda destino
        valor_brl = Cotacao.converter_moeda(valor, moeda_origem, 'BRL')
        if valor_brl is not None:
            return Cotacao.converter_moeda(valor_brl, 'BRL', moeda_destino)
        return None 