from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models.goal import Goal
from app.models.transaction import Transaction
from app import db
from datetime import datetime
import pytz
from app.models.cotacao import Cotacao
from app.models.patrimonio import Patrimonio
from app.routes.cotacoes import get_all_cotacoes
import json

bp = Blueprint('goals', __name__)

# Configura o fuso horário de Brasília
tz_br = pytz.timezone('America/Sao_Paulo')

def get_current_br_time():
    """Retorna a data/hora atual no fuso horário de Brasília"""
    return datetime.now(tz_br)

def has_pending_transactions(goal):
    """Verifica se a meta ou suas submetas têm transações pendentes"""
    # Verifica a própria meta
    if any(not t.confirmed for t in goal.transactions):
        return True
        
    # Verifica recursivamente as submetas
    for child in goal.children:
        if has_pending_transactions(child):
            return True
            
    return False

@bp.route('/goals')
@login_required
def list():
    get_all_cotacoes()#carrega as cotações para que os gráficos funcionem
    # Busca as metas principais do usuário
    goals = Goal.query.filter_by(user_id=current_user.id, parent_id=None).all()
    
    # Calcula e registra o patrimônio atual
    patrimonio = Patrimonio.calcular_patrimonio_total(current_user.id)
    
    # Busca o histórico de patrimônio dos últimos 30 dias
    historico = Patrimonio.get_historico_patrimonio(current_user.id)
    
    # Prepara dados para o gráfico
    dados_grafico = {
        'datas': [],
        'brl': [],
        'usd': [],
        'eur': [],
        'btc': []
    }
    
    # Se houver histórico, preenche os dados
    if historico:
        dados_grafico = {
            'datas': [p.date.astimezone(tz_br).strftime('%d/%m/%Y') for p in historico],
            'brl': [p.valor_brl for p in historico],
            'usd': [p.valor_usd for p in historico],
            'eur': [p.valor_eur for p in historico],
            'btc': [p.valor_btc for p in historico]
        }
    
    # Adiciona a informação de transações pendentes para cada meta
    for goal in goals:
        goal.has_pending = has_pending_transactions(goal)
    
    return render_template('goals/list.html', 
                         goals=goals, 
                         patrimonio=patrimonio,
                         dados_grafico=dados_grafico,
                         today=get_current_br_time())

@bp.route('/goals/create', methods=['GET', 'POST'])
@login_required
def create():


    def atualiar_current_value_meta_pai(parent_id):
        parent_goal = Goal.query.get(parent_id)
        new_current_value = 0
        for child in parent_goal.children:
            child_value = Cotacao.converter_moeda(child.current_value, child.currency, parent_goal.currency)
            if child_value is not None:
                new_current_value += child_value
        parent_goal.current_value = new_current_value

        print(f'>>>> atualiar_current_value_meta_pai: {parent_goal.title} - {parent_goal.current_value}')
        db.session.commit()



    if request.method == 'POST':


        

        title = request.form['title']
        description = request.form.get('description', '')
        is_debt = 'is_debt' in request.form
        
        # Se for dívida, o valor alvo é sempre 0 (objetivo é quitar)
        if is_debt:
            target_value = 0  # Meta é quitar a dívida (chegar a zero)
            target_percentage = None
            # O valor atual será o valor da dívida informado
            current_value = request.form.get('target_value', type=float) or 0
            #initial_value = current_value  # Para dívidas, o valor inicial é o valor da dívida
            initial_value = 0.0  # Para dívidas, o valor inicial é o valor da dívida
        else:
            # Verifica o tipo de meta (valor ou percentual)
            if request.form.get('target_type') == 'value':
                target_value = float(request.form.get('target_value', '0').replace('R$', '').replace('$', '').replace('€', '').replace('₿', '').replace('.', '').replace(',', '.').strip())
                target_percentage = None
            else:
                target_value = 0  # Será calculado depois
                target_percentage = float(request.form.get('target_percentage', '0').replace('%', '').replace(',', '.').strip())
            current_value = 0.0  # Metas normais começam com zero
            initial_value = 0.0  # Metas normais começam com zero
            
        target_date = request.form.get('target_date')
        currency = request.form.get('currency', 'BRL')
        parent_id = request.form.get('parent_id')
        
        # Converte parent_id para None se estiver vazio
        if not parent_id:
            parent_id = None
            
        # Se for dívida, verifica se a meta superior também é dívida
        if is_debt and parent_id:
            parent_goal = Goal.query.get(parent_id)
            if not parent_goal.is_debt:
                flash('Uma meta de dívida só pode ser submeta de outra meta de dívida', 'error')
                return redirect(url_for('goals.create'))
        
        # Converte a data para datetime apenas se não estiver vazia
        if target_date:
            target_date = datetime.strptime(target_date, '%Y-%m-%d')
        else:
            target_date = None

        # Verifica a coerência dos valores entre meta pai e filha
        if parent_id and not is_debt:
            parent_goal = Goal.query.get(parent_id)
            if (parent_goal.target_percentage is None and target_percentage is None and 
                parent_goal.target_value is not None and target_value is not None):
                # Converte o valor da meta filha para a moeda da meta pai
                child_value_in_parent_currency = Cotacao.converter_moeda(target_value, currency, parent_goal.currency)
                if child_value_in_parent_currency > parent_goal.target_value:
                    # Se o usuário não escolheu atualizar o valor da meta pai, mostra o modal
                    if request.form.get('update_parent_value') != 'yes':
                        # Retorna os dados do formulário e a informação de que precisa mostrar o modal
                        return render_template('goals/create.html',
                                            parent_goals=Goal.query.filter_by(user_id=current_user.id).all(),
                                            show_value_warning_modal=True,
                                            form_data=request.form,
                                            child_value=target_value,
                                            parent_value=parent_goal.target_value,
                                            child_currency=currency,
                                            parent_currency=parent_goal.currency,
                                            today=get_current_br_time())

        goal = Goal(
            title=title,
            description=description,
            target_value=target_value,
            target_percentage=target_percentage,
            target_date=target_date,
            currency=currency,
            is_debt=is_debt,
            parent_id=parent_id,
            user_id=current_user.id,
            current_value=current_value,
            initial_value=initial_value
        )

        try:
            # Verifica se a meta pai tem transações
            if parent_id:
                parent_goal = Goal.query.get(parent_id)
                if parent_goal.transactions:
                    # Se não foi feita uma escolha sobre as transações, redireciona de volta com o modal
                    if 'move_transactions' not in request.form:
                        # Redireciona mantendo os dados do formulário
                        query_params = {
                            'parent_id': parent_id,
                            'form_data': 'true',
                            'title': title,
                            'description': description,
                            'is_debt': str(is_debt).lower(),
                            'target_type': request.form.get('target_type', 'value'),
                            'target_value': request.form.get('target_value', ''),
                            'target_percentage': request.form.get('target_percentage', ''),
                            'currency': currency,
                            'target_date': target_date.strftime('%Y-%m-%d') if target_date else ''
                        }
                        return redirect(url_for('goals.create', **query_params))
                    
                    # Pergunta ao usuário se quer mover as transações para a nova meta
                    #move_to_new = request.form.get('move_transactions') == 'yes'
                    option_old_transactions = request.form.get('move_transactions')
                    #create_default - Criar uma submeta padrão para as transações antigas
                    #delete - apagar as transações antigas
                    #move - Mover para a nova meta
                    
                    
                    #if move_to_new:
                    if option_old_transactions == 'move':
                        # Primeiro commit para criar a meta
                        db.session.add(goal)
                        db.session.flush()  # Para obter o ID da nova meta
                        
                        # Move as transações para a nova meta
                        move_transactions(parent_goal, goal)

                        db.session.commit()

                        flash('As transações antigas foram movidas com sucesso para a nova meta!', 'success')
                    elif option_old_transactions == 'create_default':
                        # Cria uma submeta para as operações antigas
                        legacy_goal = create_legacy_subgoal(parent_goal)
                        
                        # Adiciona a nova meta
                        db.session.add(goal)

                        db.session.commit()

                        flash('As transações antigas foram movidas com sucesso para uma submeta padrão!', 'success')

                    elif option_old_transactions == 'delete':
                        # Apaga as transações antigas
                        #delete_transactions(parent_goal)

                        for transaction in parent_goal.transactions:
                            try:
                                # Remove a transação
                                db.session.delete(transaction)
                                
                                # Recalcula o valor da meta
                                recalculate_goal_value(goal)
                                
                                
                            except Exception as e:
                                db.session.rollback()
                                flash('Erro ao apagar transações antigas!', 'error')                 
                            
                    
                        flash('As transações antigas foram apagadas com sucesso!', 'success')

                    #atualiar_current_value_meta_pai(parent_goal.id)

                    
                else:
                    # Se não tem transações, apenas cria a meta normalmente
                    db.session.add(goal)
            else:
                # Se não tem pai, apenas cria a meta normalmente
                db.session.add(goal)
                
                db.session.flush()  # Para obter o ID da nova meta
                
                #se for uma meta de dívida
                if goal.is_debt:
                    #crie uma transação de aumento da dívida
                    transaction = Transaction(
                        goal_id=goal.id,
                        amount=current_value,
                        transaction_type='debt',
                        description='Abertura de dívida',
                        confirmed=True
                    )
                    db.session.add(transaction)
                    
                    if goal.is_debt:
                        reprocess_all_goals(current_user.id)
                     
            # Se o usuário escolheu atualizar o valor da meta pai
            if request.form.get('update_parent_value') == 'yes':
                # Primeiro commit para criar a meta
                db.session.add(goal)
                db.session.flush()  # Para obter o ID da nova meta
                
                # Recalcula o target_value da meta pai como a soma dos target_values das filhas
                parent_goal = Goal.query.get(parent_id)
                new_target_value = 0
                for child in parent_goal.children:
                    child_value = Cotacao.converter_moeda(child.target_value, child.currency, parent_goal.currency)
                    if child_value is not None:
                        new_target_value += child_value
                parent_goal.target_value = new_target_value
            
            # Commit final após todas as operações
            db.session.commit()
            
            # Se a meta tem pai, reprocessa toda a árvore de metas superiores
            if parent_id:
                parent = Goal.query.get(parent_id)
                while parent:
                    recalculate_goal_value(parent)
                    parent = parent.parent
                
                # Atualiza os target_values após o reprocessamento
                update_target_values(current_user.id)
                
                # Commit final após o reprocessamento
                db.session.commit()

                atualiar_current_value_meta_pai(parent_id)
                
            flash('Meta criada com sucesso!', 'success')
            return redirect(url_for('goals.list'))
        except Exception as e:
            db.session.rollback()
            flash('Erro ao criar meta. Por favor, verifique os dados.', 'error')
            print(f"Erro: {str(e)}")
            return redirect(url_for('goals.create'))

    # Para o GET, busca todas as metas do usuário
    parent_goals = Goal.query.filter_by(user_id=current_user.id).all()
    
    # Se estamos criando uma submeta, verifica se a meta pai tem transações
    parent_id = request.args.get('parent_id')
    show_transaction_modal = False
    if parent_id:
        parent_goal = Goal.query.get(parent_id)
        if parent_goal and parent_goal.transactions:
            show_transaction_modal = True
            # Se o modal será exibido, passa os dados do formulário de volta
            if request.args.get('form_data'):
                form_data = {
                    'title': request.args.get('title', ''),
                    'description': request.args.get('description', ''),
                    'is_debt': request.args.get('is_debt') == 'true',
                    'target_type': request.args.get('target_type', 'value'),
                    'target_value': request.args.get('target_value', ''),
                    'target_percentage': request.args.get('target_percentage', ''),
                    'currency': request.args.get('currency', 'BRL'),
                    'target_date': request.args.get('target_date', ''),
                    'parent_id': parent_id
                }
                return render_template('goals/create.html',
                                    parent_goals=parent_goals,
                                    show_transaction_modal=True,
                                    form_data=form_data,
                                    today=get_current_br_time())
    
    return render_template('goals/create.html', 
                         parent_goals=parent_goals,
                         show_transaction_modal=show_transaction_modal,
                         today=get_current_br_time())

@bp.route('/goals/<int:goal_id>/update', methods=['POST'])
@login_required
def update_value(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    
    if goal.children:
        flash('Não é possível atualizar diretamente uma meta que possui submetas', 'error')
        return redirect(url_for('goals.list'))
        
    try:
        new_value = request.form.get('value')
        if new_value is not None:
            new_value = float(new_value)
            
            # Adiciona uma transação de atualização
            transaction = Transaction(
                goal_id=goal.id,
                amount=new_value,
                transaction_type='update',
                description='Atualização manual de saldo',
                confirmed=True
            )
            db.session.add(transaction)
            
            # Recalcula o valor da meta
            recalculate_goal_value(goal)
            
            db.session.commit()
            flash('Valor atualizado com sucesso!', 'success')
    except ValueError:
        flash('Valor inválido', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao atualizar valor', 'error')
        print(f"Erro: {str(e)}")
    
    return redirect(url_for('goals.list'))

@bp.route('/goals/<int:goal_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        # Guarda o parent_id antigo para comparação
        old_parent_id = goal.parent_id
        
        goal.title = request.form['title']
        goal.description = request.form.get('description', '')
        
        # Se for dívida, atualiza o valor inicial
        if 'is_debt' in request.form:
            goal.is_debt = True
            if not goal.initial_value:  # Se ainda não tem valor inicial
                goal.initial_value = goal.current_value
            goal.target_value = 0  # Meta de dívida sempre tem target 0
            goal.target_percentage = None
        else:
            goal.is_debt = False
            # Verifica o tipo de meta (valor ou percentual)
            if request.form.get('target_type') == 'value':
                goal.target_value = request.form.get('target_value', type=float)
                goal.target_percentage = None
            else:
                goal.target_percentage = request.form.get('target_percentage', type=float)
                # target_value será calculado depois
        
        target_date = request.form.get('target_date')
        if target_date:
            goal.target_date = datetime.strptime(target_date, '%Y-%m-%d')
        else:
            goal.target_date = None
            
        goal.currency = request.form.get('currency', 'BRL')
        
        new_parent_id = request.form.get('parent_id')
        if new_parent_id:
            goal.parent_id = int(new_parent_id)
        else:
            goal.parent_id = None

        try:
            # Primeiro commit para salvar as alterações básicas
            db.session.commit()
            
            # Reprocessa a meta atual e todas as suas submetas
            def reprocess_goal_tree(current_goal):
                recalculate_goal_value(current_goal)
                for child in current_goal.children:
                    reprocess_goal_tree(child)
            
            # Se mudou de pai, reprocessa a antiga árvore também
            if old_parent_id and old_parent_id != goal.parent_id:
                old_parent = Goal.query.get(old_parent_id)
                if old_parent:
                    reprocess_goal_tree(old_parent)
            
            # Reprocessa a meta atual e sua nova árvore
            if goal.parent:
                reprocess_goal_tree(goal.parent)
            else:
                reprocess_goal_tree(goal)
            
            # Atualiza os target_values após o reprocessamento
            update_target_values(current_user.id)
            
            # Commit final após todos os reprocessamentos
            db.session.commit()
            flash('Meta atualizada com sucesso!', 'success')
            return redirect(url_for('goals.list'))
        except Exception as e:
            db.session.rollback()
            flash('Erro ao atualizar meta.', 'error')
            return redirect(url_for('goals.edit', goal_id=goal_id))
    
    # Busca todas as metas do usuário, exceto a meta atual e suas submetas
    available_parents = Goal.query.filter(
        Goal.user_id == current_user.id,
        Goal.id != goal_id
    ).all()
    
    # Remove as submetas da meta atual da lista de possíveis pais
    def get_all_children_ids(goal):
        children_ids = []
        for child in goal.children:
            children_ids.append(child.id)
            children_ids.extend(get_all_children_ids(child))
        return children_ids

    children_ids = get_all_children_ids(goal)
    parent_goals = [g for g in available_parents if g.id not in children_ids]
    
    return render_template('goals/edit.html', goal=goal, parent_goals=parent_goals)

@bp.route('/goals/<int:goal_id>/delete', methods=['POST'])
@login_required
def delete(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(goal)
        db.session.commit()
        flash('Meta excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao excluir meta.', 'error')
    
    return redirect(url_for('goals.list'))

def recalculate_goal_value(goal):
    """Recalcula o valor atual da meta baseado no valor inicial e suas transações."""
    if goal.is_debt:
        # Para dívidas, começa com zero
        goal.current_value = 0.0
        
        # Primeiro processa as transações de debt (abertura/aumento de dívida)
        for transaction in goal.transactions:
            if transaction.transaction_type == 'debt':
                goal.current_value += abs(transaction.amount)
        
        # Depois processa as amortizações e outros ajustes
        for transaction in goal.transactions:
            if transaction.transaction_type == 'amortize':
                goal.current_value -= abs(transaction.amount)
            elif transaction.transaction_type == 'increase':
                goal.current_value += abs(transaction.amount)
            elif transaction.transaction_type == 'update':
                goal.current_value = transaction.amount
    else:
        # Para investimentos, começa do zero
        goal.current_value = 0.0
        
        # Processa as transações de investimento
        for transaction in goal.transactions:
            if transaction.transaction_type == 'invest':
                goal.current_value += abs(transaction.amount)
            elif transaction.transaction_type == 'withdraw':
                goal.current_value -= abs(transaction.amount)
            elif transaction.transaction_type == 'update':
                goal.current_value = transaction.amount
    
    # Atualiza metas superiores
    parent = goal.parent
    while parent:
        parent.current_value = 0.0
        for child in parent.children:
            # Converte o valor da submeta para a moeda da meta pai
            child_value = Cotacao.converter_moeda(child.current_value, child.currency, parent.currency)
            if child_value is not None:
                parent.current_value += child_value
            else:
                print(f"Erro ao converter valor de {child.currency} para {parent.currency}")
        parent = parent.parent

def calculate_target_value(goal):
    """Calcula o target_value da meta baseado em suas características."""
    if goal.is_debt:
        # Para dívidas, o target é sempre 0, mas vamos atualizar o initial_value
        debt_transactions = [t for t in goal.transactions if t.transaction_type == 'debt']
        goal.initial_value = sum(t.amount for t in debt_transactions)
        return 0.0
    
    if goal.target_percentage is not None:
        # Meta baseada em percentual
        if goal.parent:
            # Calcula baseado no valor da meta superior
            parent_value = goal.parent.current_value
            # Converte o valor da meta pai para a moeda da meta atual
            base_value = Cotacao.converter_moeda(parent_value, goal.parent.currency, goal.currency)
        else:
            # Calcula baseado no patrimônio total
            patrimonio = Patrimonio.get_valor_total_by_currency(goal.user_id, goal.currency)
            base_value = patrimonio if patrimonio is not None else 0.0
        
        # Calcula o target_value como percentual do valor base
        return (base_value * goal.target_percentage / 100) if base_value is not None else 0.0
    
    # Se não é dívida nem percentual, retorna o target_value já definido
    return goal.target_value if goal.target_value is not None else 0.0

def update_target_values(user_id):
    """Atualiza o target_value de todas as metas do usuário."""
    goals = Goal.query.filter_by(user_id=user_id).all()
    for goal in goals:
        goal.target_value = calculate_target_value(goal)
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar target_values: {str(e)}")
        return False

def reprocess_all_goals(user_id):
    """Reprocessa todas as metas do usuário."""
    # Busca todas as metas do usuário
    goals = Goal.query.filter_by(user_id=user_id).all()
    
    # Primeiro, processa todas as metas que não têm submetas (folhas)
    leaf_goals = [g for g in goals if not g.children]
    for goal in leaf_goals:
        recalculate_goal_value(goal)
        
        # Se for dívida, atualiza o initial_value baseado nas transações 'debt'
        if goal.is_debt:
            debt_transactions = [t for t in goal.transactions if t.transaction_type == 'debt']
            goal.initial_value = sum(t.amount for t in debt_transactions)
    
    # Depois, processa as metas que têm submetas, de baixo para cima
    non_leaf_goals = [g for g in goals if g.children]
    processed = set()
    
    while non_leaf_goals:
        for goal in non_leaf_goals[:]:
            # Se todas as submetas já foram processadas
            if all(child.id in processed for child in goal.children):
                recalculate_goal_value(goal)
                
                # Se for dívida, atualiza o initial_value baseado nas transações 'debt'
                if goal.is_debt:
                    debt_transactions = [t for t in goal.transactions if t.transaction_type == 'debt']
                    goal.initial_value = sum(t.amount for t in debt_transactions)
                
                processed.add(goal.id)
                non_leaf_goals.remove(goal)
    
    # Atualiza os target_values após recalcular os valores atuais
    update_target_values(user_id)
    
    # Recalcula o patrimônio total
    Patrimonio.calcular_patrimonio_total(user_id)
    
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao reprocessar metas: {str(e)}")
        return False

@bp.route('/goals/reprocess', methods=['POST'])
@login_required
def reprocess():
    """Rota para reprocessar todas as metas do usuário."""
    if reprocess_all_goals(current_user.id):
        flash('Todas as metas foram reprocessadas com sucesso!', 'success')
    else:
        flash('Erro ao reprocessar as metas.', 'error')
    return redirect(url_for('goals.list'))

@bp.route('/goals/<int:goal_id>/invest', methods=['POST'])
@login_required
def invest(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    
    if goal.children:
        flash('Não é possível investir diretamente em uma meta que possui submetas', 'error')
        return redirect(url_for('goals.list'))
        
    try:
        value = request.form.get('value')
        date = request.form.get('date')
        description = request.form.get('description', '')

        if value is not None and date:
            value = float(value)
            date = datetime.strptime(date, '%Y-%m-%d')
            
            # Adiciona a transação ao histórico
            transaction = Transaction(
                goal_id=goal.id, 
                amount=abs(value), 
                transaction_type='amortize' if goal.is_debt else 'invest',
                date=date,
                description=description,
                confirmed=True
            )
            db.session.add(transaction)
            
            # Recalcula o valor da meta
            recalculate_goal_value(goal)
            
            db.session.commit()
            flash('Operação realizada com sucesso!', 'success')
    except ValueError:
        flash('Valor inválido', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao realizar operação', 'error')
        print(f"Erro: {str(e)}")
    
    return redirect(url_for('goals.details', goal_id=goal.id))

@bp.route('/goals/<int:goal_id>/withdraw', methods=['POST'])
@login_required
def withdraw(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    
    if goal.children:
        flash('Não é possível resgatar diretamente de uma meta que possui submetas', 'error')
        return redirect(url_for('goals.list'))
        
    try:
        value = request.form.get('value')
        date = request.form.get('date')
        description = request.form.get('description', '')

        if value is not None and date:
            value = float(value)
            date = datetime.strptime(date, '%Y-%m-%d')
            
            # Se não for dívida, verifica se há saldo suficiente
            if not goal.is_debt:
                # Simula o resgate para verificar se ficará negativo
                test_value = goal.current_value - value
                if test_value < 0:
                    flash('Saldo insuficiente para realizar o resgate', 'warning')
                    return redirect(url_for('goals.details', goal_id=goal.id))
            
            # Adiciona a transação ao histórico
            transaction = Transaction(
                goal_id=goal.id, 
                amount=abs(value), 
                transaction_type='increase' if goal.is_debt else 'withdraw',
                date=date,
                description=description,
                confirmed=True
            )
            db.session.add(transaction)
            
            # Recalcula o valor da meta
            recalculate_goal_value(goal)
            
            db.session.commit()
            flash('Operação realizada com sucesso!', 'success')
    except ValueError:
        flash('Valor inválido', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao realizar operação', 'error')
        print(f"Erro: {str(e)}")
    
    return redirect(url_for('goals.details', goal_id=goal.id))

def get_all_child_transactions(goal, parent_currency):
    """Busca recursivamente todas as transações das submetas"""
    transactions = []
    
    # Adiciona as transações da meta atual
    for t in goal.transactions:
        # Converte o valor para a moeda da meta pai
        converted_amount = Cotacao.converter_moeda(t.amount, goal.currency, parent_currency)
        if converted_amount is not None:
            transactions.append({
                'amount': converted_amount,
                'date': t.date,
                'type': t.transaction_type
            })
    
    # Busca recursivamente as transações das submetas
    for child in goal.children:
        transactions.extend(get_all_child_transactions(child, parent_currency))
    
    return transactions

@bp.route('/goals/<int:goal_id>')
@login_required
def details(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    
    # Prepara dados para o gráfico
    transactions_data = []
    for transaction in goal.transactions:
        transactions_data.append({
            'date': transaction.date.strftime('%d/%m/%Y'),
            'amount': transaction.amount,
            'converted_amount': transaction.amount,  # Mesma moeda, não precisa converter
            'type': transaction.transaction_type,
            'confirmed': transaction.confirmed
        })
    
    return render_template('goals/details.html', 
                         goal=goal,
                         transactions_data=transactions_data,
                         has_pending_transactions=has_pending_transactions,  # Passa a função para o template
                         today=get_current_br_time())  # Adiciona a data atual no fuso horário de Brasília

@bp.route('/goals/<int:goal_id>/transactions/<int:transaction_id>/edit', methods=['POST'])
@login_required
def edit_transaction(goal_id, transaction_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    transaction = Transaction.query.filter_by(id=transaction_id, goal_id=goal_id).first_or_404()
    
    try:
        value = request.form.get('value')
        date = request.form.get('date')
        description = request.form.get('description', '')

        confirmed = 'confirmed' in request.form
         

        if value is not None and date:
            new_value = float(value)   
            date = datetime.strptime(date, '%Y-%m-%d')
            
            # Atualiza a transação
            transaction.amount = new_value
            transaction.date = date
            transaction.description = description
            transaction.confirmed = confirmed
            
            # Recalcula o valor da meta
            recalculate_goal_value(goal)
            
            db.session.commit()
            flash('Transação atualizada com sucesso!', 'success')
    except ValueError:
        flash('Valor inválido', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao atualizar transação', 'error')
        print(f"Erro: {str(e)}")
    
    return redirect(url_for('goals.details', goal_id=goal_id))

@bp.route('/goals/<int:goal_id>/transactions/<int:transaction_id>/delete', methods=['POST'])
@login_required
def delete_transaction(goal_id, transaction_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    transaction = Transaction.query.filter_by(id=transaction_id, goal_id=goal_id).first_or_404()
    
    try:
        # Remove a transação
        db.session.delete(transaction)
        
        # Recalcula o valor da meta
        recalculate_goal_value(goal)
        
        db.session.commit()
        flash('Transação excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao excluir transação', 'error')
        print(f"Erro: {str(e)}")
    
    return redirect(url_for('goals.details', goal_id=goal_id))

def move_transactions(from_goal, to_goal):
    """Move todas as transações de uma meta para outra."""
    for transaction in from_goal.transactions:
        transaction.goal_id = to_goal.id

    db.session.commit() #grava no banco de dados

    recalculate_goal_value(to_goal)
    recalculate_goal_value(from_goal)

    db.session.commit()

def create_legacy_subgoal(parent_goal):
    """Cria uma submeta para armazenar as transações antigas da meta pai."""
    legacy_goal = Goal(
        title=f"Operações Antigas de {parent_goal.title}",
        description="Meta criada automaticamente para fins de consistência do sistema",
        target_value=parent_goal.target_value,
        target_percentage=parent_goal.target_percentage,
        target_date=parent_goal.target_date,
        currency=parent_goal.currency,
        is_debt=parent_goal.is_debt,
        parent_id=parent_goal.id,
        user_id=parent_goal.user_id,
        current_value=parent_goal.current_value,
        initial_value=parent_goal.initial_value,
        created_at=parent_goal.created_at
    )
    
    db.session.add(legacy_goal)
    db.session.flush()  # Para obter o ID da nova meta
    
    # Move as transações para a nova meta
    move_transactions(parent_goal, legacy_goal)
    
    return legacy_goal 

def format_currency_value(value, currency):
    if value is None:
        if currency == 'BRL':
            return 'R$ 0,00'
        elif currency == 'USD':
            return '$ 0.00'
        elif currency == 'EUR':
            return '€ 0,00'
        elif currency == 'BTC':
            return '₿ 0.00000000'
    else:
        if currency == 'BRL':
            return f"R$ {'{:,.2f}'.format(value).replace(',', 'X').replace('.', ',').replace('X', '.')}"
        elif currency == 'USD':
            return f"$ {'{:,.2f}'.format(value)}"
        elif currency == 'EUR':
            return f"€ {'{:,.2f}'.format(value).replace(',', 'X').replace('.', ',').replace('X', '.')}"
        elif currency == 'BTC':
            return f"₿ {'{:.8f}'.format(value)}"

@bp.route('/goals/suggest-investments', methods=['GET'])
@login_required
def suggest_investments():
    goals = Goal.query.filter_by(
        user_id=current_user.id,
        parent_id=None
    ).order_by(Goal.priority.desc()).all()
    
    return render_template('goals/suggest_investments.html',
                         goals=goals,
                         step='priority',
                         format_currency=format_currency_value)

@bp.route('/goals/save-priorities', methods=['POST'])
@login_required
def save_priorities():
    """Salva as prioridades definidas pelo usuário"""
    try:
        priorities = request.form.getlist('priorities[]')
        
        print(f"Prioridades recebidas: {priorities}")
        
        # Atualiza a prioridade de cada meta
        #for index, goal_id in enumerate(reversed(priorities)):
        for index, goal_id in enumerate(reversed(priorities)):
            goal = Goal.query.get(goal_id)
            print(f"Antes: Meta: {goal.title}, Prioridade: {index}")
            if goal and goal.user_id == current_user.id:
                goal.priority = index+1
            print(f"Depois: Meta: {goal.title}, Prioridade: {goal.priority }")
        
        db.session.commit()
        flash('Prioridades salvas com sucesso!', 'success')
        
        return render_template('goals/suggest_investments.html',
                             goals=Goal.query.filter_by(user_id=current_user.id).order_by(Goal.priority.desc()).all(),
                             step='suggest')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao salvar prioridades', 'error')
        return redirect(url_for('goals.suggest_investments'))

def serialize_suggestions(suggestions):
    """Serializa as sugestões para JSON"""
    return json.dumps([{
        'goal_id': s['goal_id'],
        'amount': s['amount'],
        'amount_original': s['amount_original'],
        'current_percentage': s['current_percentage'],
        'new_percentage': s['new_percentage']
    } for s in suggestions])

@bp.route('/goals/calculate-suggestion', methods=['POST'])
@login_required
def calculate_suggestion():
    """Calcula a sugestão de distribuição do investimento"""
    try:
        # Obtém o valor e a moeda do investimento
        currency = request.form.get('currency', 'BRL')
        amount_str = request.form.get('amount', '0')
        
        print(f"Valor recebido: {amount_str}, Moeda: {currency}")  # Debug
        
        # Remove os símbolos de moeda e converte para float
        amount_str = (amount_str.replace('R$', '')
                               .replace('$', '')
                               .replace('€', '')
                               .replace('₿', '')
                               .replace(' ', '')
                               .strip())
        
        print(f"Valor após remover símbolos: {amount_str}")  # Debug
        
        # Trata a formatação específica de cada moeda
        if currency in ['BRL', 'EUR']:
            amount = float(amount_str.replace('.', '').replace(',', '.'))
        else:  # USD e BTC usam . como separador decimal
            amount = float(amount_str.replace(',', ''))
        
        print(f"Valor convertido: {amount}")  # Debug
        
        # Busca as metas ordenadas por prioridade
        goals = Goal.query.filter_by(
            user_id=current_user.id,
            parent_id=None
        ).order_by(Goal.priority.desc()).all()
        
        print(f"Metas em que trabalharemos as sugestões: {goals}")
        
        suggestions = calculate_investment_distribution(goals, amount, currency)
        
        return render_template('goals/suggest_investments.html',
                             goals=goals,
                             step='suggest',
                             suggestions=suggestions,
                             serialized_suggestions=serialize_suggestions(suggestions),
                             format_currency=format_currency_value)
    except Exception as e:
        print(f"Erro ao calcular sugestão: {str(e)}")  # Debug
        flash(f'Erro ao calcular sugestão: {str(e)}', 'error')
        return redirect(url_for('goals.suggest_investments'))

def calculate_investment_distribution(goals, total_amount, investment_currency):
    """Calcula a distribuição ideal do investimento entre as metas"""
    suggestions = []
    remaining_amount = total_amount
    
    # Primeiro, trata as metas com valor fixo por ordem de prioridade
    for goal in goals:
        if not goal.target_percentage and goal.target_value >= 0:
            # Converte o valor restante para a moeda da meta
            remaining_in_goal_currency = Cotacao.converter_moeda(
                remaining_amount, 
                investment_currency, 
                goal.currency
            )
            
            if remaining_in_goal_currency is None:
                continue  # Pula se não conseguir converter
            
            if goal.is_debt:
                # Para dívidas, queremos amortizar o valor atual (current_value)
                missing_amount = goal.current_value  # O quanto falta para quitar a dívida
            else:
                # Para investimentos, queremos atingir o target_value
                missing_amount = goal.target_value - goal.current_value
                
            if missing_amount > 0:
                # Calcula quanto investir/amortizar na moeda da meta
                suggestion_in_goal = min(missing_amount, remaining_in_goal_currency)
                
                # Converte de volta para a moeda do investimento
                suggestion_amount = Cotacao.converter_moeda(
                    suggestion_in_goal,
                    goal.currency,
                    investment_currency
                )
                
                if suggestion_amount and suggestion_amount > 0:
                    # Calcula os percentuais
                    if goal.is_debt:
                        # Para dívidas: quanto já foi pago vs quanto será pago após a amortização
                        debt_transactions = [t for t in goal.transactions if t.transaction_type == 'debt']
                        if debt_transactions:
                            initial_debt = sum(t.amount for t in debt_transactions)
                            if initial_debt > 0:
                                current_percentage = ((initial_debt - goal.current_value) / initial_debt) * 100
                                new_percentage = ((initial_debt - (goal.current_value - suggestion_in_goal)) / initial_debt) * 100
                            else:
                                current_percentage = 0
                                new_percentage = 0
                        else:
                            current_percentage = 0
                            new_percentage = 0
                    else:
                        # Para investimentos: quanto já foi investido vs meta
                        if goal.target_value and goal.target_value > 0:
                            current_percentage = (goal.current_value / goal.target_value) * 100
                            new_percentage = ((goal.current_value + suggestion_in_goal) / goal.target_value) * 100
                        else:
                            current_percentage = 0
                            new_percentage = 0
                    
                    suggestions.append({
                        'goal': goal,
                        'goal_id': goal.id,
                        'amount': float(suggestion_in_goal),
                        'amount_original': float(suggestion_amount),
                        'current_percentage': float(current_percentage),
                        'new_percentage': float(new_percentage),
                        'is_debt': goal.is_debt
                    })
                    remaining_amount -= suggestion_amount


    print(f"Sugestões na primeira fase")
    for suggestion in suggestions:
        print(f"Sugestão: {suggestion['goal'].title}, Amount: {suggestion['amount']}, Current Percentage: {suggestion['current_percentage']}, New Percentage: {suggestion['new_percentage']}")
        
    # Depois, distribui o restante entre as metas percentuais
    percentage_goals = [g for g in goals if g.target_percentage]
    if percentage_goals and remaining_amount > 0:
        total_percentage = sum(g.target_percentage for g in percentage_goals)
        for goal in percentage_goals:
            if total_percentage > 0:
                # Calcula o valor na moeda do investimento
                suggestion_amount = (goal.target_percentage / total_percentage) * remaining_amount
                
                # Converte para a moeda da meta
                suggestion_in_goal = Cotacao.converter_moeda(
                    suggestion_amount,
                    investment_currency,
                    goal.currency
                )
                
                if suggestion_in_goal is not None:
                    suggestions.append({
                        'goal': goal,  # Mantemos o objeto goal apenas para exibição
                        'goal_id': goal.id,
                        'amount': float(suggestion_in_goal),
                        'amount_original': float(suggestion_amount),
                        'current_percentage': float(goal.target_percentage),
                        'new_percentage': float(goal.target_percentage)
                    })
                    
    print(f"Sugestões no final")
    for suggestion in suggestions:
        print(f"Sugestão: {suggestion['goal'].title}, Amount: {suggestion['amount']}, Current Percentage: {suggestion['current_percentage']}, New Percentage: {suggestion['new_percentage']}")
    
    return suggestions

@bp.route('/goals/apply-suggestion', methods=['POST'])
@login_required
def apply_suggestion():
    """Aplica a sugestão de investimento nas metas"""
    try:
        suggestions_data = request.form.get('suggestion_data')
        print(f'Dados recebidos em apply_suggestion: {suggestions_data}')  # Debug
        
        if not suggestions_data:
            raise ValueError("Nenhum dado de sugestão recebido")
            
        suggestions = json.loads(suggestions_data)
        print(f'Dados parseados: {suggestions}')  # Debug
        
        if len(suggestions) == 0:
            print(f'Dados não são uma lista: {type(suggestions)}')  # Debug
            raise ValueError("Formato de dados inválido")
            
        for suggestion in suggestions:
            if not all(key in suggestion for key in ['goal_id', 'amount']):
                print(f'Sugestão inválida: {suggestion}')  # Debug
                continue
                
            goal_id = suggestion.get('goal_id')
            amount = suggestion.get('amount')
            
            if goal_id is None or amount is None:
                print(f'Dados inválidos - goal_id: {goal_id}, amount: {amount}')  # Debug
                continue
                
            goal = Goal.query.get(goal_id)
            if goal and goal.user_id == current_user.id:
                print(f'É o mesmo usuário que está logado. Criando transação para meta {goal.title} com valor {amount}')  # Debug
                
                # Define o tipo de transação baseado no tipo da meta
                transaction_type = 'amortize' if goal.is_debt else 'invest'
                description = 'Amortização via sugestão automática' if goal.is_debt else 'Investimento via sugestão automática'
                
                # Cria a transação
                transaction = Transaction(
                    goal_id=goal.id,
                    amount=float(amount),
                    transaction_type=transaction_type,
                    description=description,
                    date=datetime.now(),
                    confirmed=False
                )
                db.session.add(transaction)
                
                # Recalcula o valor da meta
                recalculate_goal_value(goal)
                print(f'Transação criada para meta {goal.title}: {amount} ({transaction_type})')  # Debug
        
        db.session.commit()
        flash('Operações aplicadas com sucesso!', 'success')

        # Reprocessa todas as metas do usuário que está logado
        reprocess_all_goals(current_user.id)
        
    except json.JSONDecodeError as e:
        db.session.rollback()
        flash(f'Erro ao decodificar dados da sugestão: {str(e)}', 'error')
        print(f'Erro de JSON: {str(e)}')  # Debug
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao aplicar operações: {str(e)}', 'error')
        print(f'Erro detalhado: {str(e)}')  # Debug
    
    return redirect(url_for('goals.list')) 