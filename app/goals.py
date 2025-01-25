""" @bp.route('/create', methods=['GET', 'POST'])
def create():


    print('ESSE ARQUIVO FOI ABANDONADO PELA APLICAÇAÕ >>>>>>>>>>>>>>>>>>>>>>>>')

    parent_goals = Goal.query.filter_by(parent_id=None).all()
    today = datetime.now(tz=timezone('America/Sao_Paulo')).date()
    
    if request.method == 'POST':


        print('>>>> entrou no POST')

        title = request.form.get('title')
        description = request.form.get('description')
        is_debt = request.form.get('is_debt') == 'on'
        target_type = request.form.get('target_type')
        target_value = request.form.get('target_value')
        target_percentage = request.form.get('target_percentage')
        currency = request.form.get('currency')
        target_date = datetime.strptime(request.form.get('target_date'), '%Y-%m-%d').date()
        parent_id = request.form.get('parent_id')


        title = 'teste'
        
        # Converte os valores para float
        if target_value:
            target_value = float(target_value)
        if target_percentage:
            target_percentage = float(target_percentage)
            
        # Cria a nova meta
        goal = Goal(
            title='Elefante',
            description=description,
            is_debt=is_debt,
            target_type=target_type,
            target_value=target_value,
            target_percentage=target_percentage,
            currency=currency,
            target_date=target_date,
            parent_id=parent_id if parent_id else None,
            user_id=current_user.id
        )
        
        db.session.add(goal)
        db.session.flush()  # Gera o ID da meta
        
        # Se houver uma meta superior
        if parent_id:
            print('entrou no if parent_id')
            print(f'>>> parent_id: {parent_id}')    
            parent_goal = Goal.query.get(parent_id)
            
            # Se a meta superior tiver transações
            if parent_goal.transactions:
                move_transactions = request.form.get('move_transactions')

                print(f'>>> move_transactions: {move_transactions}')
                
                if move_transactions == 'move':
                    # Move as transações para a nova meta
                    for old_transaction in parent_goal.transactions[:]:  # Cria uma cópia da lista
                        # Cria uma nova transação na meta filha
                        new_transaction = Transaction(
                            goal_id=goal.id,
                            amount=old_transaction.amount,
                            transaction_type=old_transaction.transaction_type,
                            description=old_transaction.description,
                            date=old_transaction.date
                        )
                        db.session.add(new_transaction)
                        
                        # Deleta a transação antiga
                        db.session.delete(old_transaction)
                    
                    db.session.flush()  # Força a atualização do banco
                    
                    # Atualiza o valor atual da meta filha
                    goal.current_value = sum(t.amount for t in goal.transactions)
                    if goal.is_debt:
                        goal.initial_value = goal.current_value
                
                elif move_transactions == 'create_default':
                    # Cria uma submeta padrão para as transações antigas
                    default_submeta = Goal(
                        title=f"Operações Antigas de {parent_goal.title}",
                        description="Meta criada automaticamente para manter a consistência do sistema",
                        is_debt=parent_goal.is_debt,
                        target_type='value',
                        target_value=parent_goal.current_value,
                        currency=parent_goal.currency,
                        parent_id=parent_goal.id,
                        user_id=current_user.id
                    )
                    db.session.add(default_submeta)
                    db.session.flush()  # Gera o ID da submeta
                    
                    # Move as transações para a submeta padrão
                    for old_transaction in parent_goal.transactions[:]:  # Cria uma cópia da lista
                        # Cria uma nova transação na submeta padrão
                        new_transaction = Transaction(
                            goal_id=default_submeta.id,
                            amount=old_transaction.amount,
                            transaction_type=old_transaction.transaction_type,
                            description=old_transaction.description,
                            date=old_transaction.date
                        )
                        db.session.add(new_transaction)
                        
                        # Deleta a transação antiga
                        db.session.delete(old_transaction)
                    
                    db.session.flush()  # Força a atualização do banco
                    
                    # Atualiza o valor atual da submeta padrão
                    default_submeta.current_value = sum(t.amount for t in default_submeta.transactions)
                    if default_submeta.is_debt:
                        default_submeta.initial_value = default_submeta.current_value
                
                elif move_transactions == 'delete':
                    # Deleta todas as transações antigas
                    for transaction in parent_goal.transactions[:]:  # Cria uma cópia da lista
                        db.session.delete(transaction)
                    
                    db.session.flush()  # Força a atualização do banco
            
            # Se o valor alvo da meta filha for maior que o da meta superior
            if (goal.target_type == 'value' and 
                goal.currency == parent_goal.currency and 
                goal.target_value > parent_goal.target_value):
                update_parent_value = request.form.get('update_parent_value') == 'yes'
                if update_parent_value:
                    parent_goal.target_value = goal.target_value
            
            # Atualiza o valor atual da meta pai
            parent_goal.current_value = 0
            for child in parent_goal.children:
                if child.currency == parent_goal.currency:
                    parent_goal.current_value += child.current_value
                else:
                    # Converte o valor da moeda da meta filha para a moeda da meta pai
                    converted_value = Cotacao.converter_moeda(
                        child.current_value,
                        child.currency,
                        parent_goal.currency
                    )
                    if converted_value is not None:
                        parent_goal.current_value += converted_value
        else:
            print(f'>>> parent_id: {parent_id}')

        db.session.commit()
        flash('Meta criada com sucesso!', 'success')
        return redirect(url_for('goals.details', goal_id=goal.id))
    
    
        
    return render_template('goals/create.html', 
                         parent_goals=parent_goals,
                         today=today)  """