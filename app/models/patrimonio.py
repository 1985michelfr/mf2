from app import db
from datetime import datetime
from app.models.cotacao import Cotacao

class Patrimonio(db.Model):
    __tablename__ = 'patrimonio'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Valores em cada moeda
    valor_brl = db.Column(db.Float, nullable=False)
    valor_usd = db.Column(db.Float, nullable=False)
    valor_eur = db.Column(db.Float, nullable=False)
    valor_btc = db.Column(db.Float, nullable=False)
    
    # Relacionamento com o usuário
    user = db.relationship('User', backref=db.backref('patrimonio', lazy=True))
    
    @staticmethod
    def calcular_patrimonio_total(user_id):
        """Calcula o patrimônio total do usuário em todas as moedas."""
        from app.models.goal import Goal
        
        #printprint(">>>> Calculando patrimônio total")
        
        # Busca todas as metas do usuário
        #goals = Goal.query.filter_by(user_id=user_id).all()
        goals = Goal.query.filter_by(user_id=user_id).filter(Goal.parent_id.is_(None)).all()
        #print(f">>>> Total de metas: {len(goals)}")
        
        # Inicializa os totais em BRL
        total_investimentos_brl = 0.0
        total_dividas_brl = 0.0
        
        # Calcula o total em BRL
        for goal in goals:
            # Converte o valor da meta para BRL
            valor_brl = Cotacao.converter_moeda(goal.current_value, goal.currency, 'BRL')
            #print(f">>>> Meta: {goal.title}")
            #print(f">>>> Valor original: {goal.current_value} {goal.currency}")
            #print(f">>>> Valor em BRL: {valor_brl}")
            
            if valor_brl is not None:
                if goal.is_debt:
                    total_dividas_brl += valor_brl
                else:
                    total_investimentos_brl += valor_brl
        
        """ print(f">>>> Total investimentos BRL: {total_investimentos_brl}")
        print(f">>>> Total dívidas BRL: {total_dividas_brl}") """
        
        # Calcula o patrimônio líquido em BRL
        patrimonio_brl = total_investimentos_brl - total_dividas_brl
        #print(f">>>> Patrimônio líquido BRL: {patrimonio_brl}")
        
        # Converte para outras moedas
        patrimonio_usd = Cotacao.converter_moeda(patrimonio_brl, 'BRL', 'USD')
        patrimonio_eur = Cotacao.converter_moeda(patrimonio_brl, 'BRL', 'EUR')
        patrimonio_btc = Cotacao.converter_moeda(patrimonio_brl, 'BRL', 'BTC')
        
        #print(f">>>> Patrimônio USD: {patrimonio_usd}")
        #print(f">>>> Patrimônio EUR: {patrimonio_eur}")
        #print(f">>>> Patrimônio BTC: {patrimonio_btc}")
        
        # Cria novo registro de patrimônio
        if None not in [patrimonio_usd, patrimonio_eur, patrimonio_btc]:
            patrimonio = Patrimonio(
                user_id=user_id,
                valor_brl=patrimonio_brl,
                valor_usd=patrimonio_usd,
                valor_eur=patrimonio_eur,
                valor_btc=patrimonio_btc
            )
            
            try:
                db.session.add(patrimonio)
                db.session.commit()
                #print(">>>> Patrimônio salvo com sucesso")
                return patrimonio
            except Exception as e:
                db.session.rollback()
                print(f"Erro ao salvar patrimônio: {str(e)}")
                return None
        else:
            print(">>>> Erro: Alguma conversão retornou None")
        
        return None
    
    @staticmethod
    def get_historico_patrimonio(user_id, dias=30):
        """Retorna o histórico de patrimônio dos últimos X dias."""
        from datetime import timedelta
        data_limite = datetime.utcnow() - timedelta(days=dias)
        
        return Patrimonio.query.filter(
            Patrimonio.user_id == user_id,
            Patrimonio.date >= data_limite
        ).order_by(Patrimonio.date.asc()).all()

    @classmethod
    def get_valor_total_by_currency(cls, user_id, currency):
        """Retorna o valor total do patrimônio na moeda especificada."""
        patrimonio = cls.query.filter_by(user_id=user_id).order_by(cls.date.desc()).first()
        if not patrimonio:
            return 0.0
            
        if currency == 'BRL':
            return patrimonio.valor_brl
        elif currency == 'USD':
            return patrimonio.valor_usd
        elif currency == 'EUR':
            return patrimonio.valor_eur
        elif currency == 'BTC':
            return patrimonio.valor_btc
        else:
            return 0.0 