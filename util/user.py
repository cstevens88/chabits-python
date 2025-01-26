def get_user_by_username(db_context, db_model, username):
    return db_context.session.execute(db_context.select(db_model).where(db_model.username == username)).scalars().first()

def get_all_users(db_context, db_model):
    return db_context.session.execute(db_context.select(db_model).order_by(db_model.username)).scalars()