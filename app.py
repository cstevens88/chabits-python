import bcrypt
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required, JWTManager
import os
from sqlalchemy import exc

from models.models import db, Habit, TokenBlocklist, User
from util.user import get_user_by_username, get_all_users

load_dotenv()

SQLALCHEMY_DATABASE_URI = os.getenv('SQLITE_DATABASE_URI')
JWT_TOKEN_EXPIRATION_HOURS = int(os.getenv('JWT_TOKEN_EXPIRATION_HOURS'))
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')

app = Flask(__name__)
CORS(app, resources={'/*': {'origins': 'http://localhost:3000'}})

app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
db.init_app(app)

ACCESS_EXPIRES = timedelta(hours=JWT_TOKEN_EXPIRATION_HOURS)
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = ACCESS_EXPIRES
jwt = JWTManager(app)

with app.app_context():
    db.create_all()

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload: dict) -> bool:
    jti = jwt_payload['jti']
    token = db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar()
    return token is not None

# routes are GETs by default, so you only need to pass a methods param in the
# decorator if the route uses a verb other than that, e.g. @app.route(' /route', methods=['POST'])
@app.route('/')
def index():
    return jsonify(msg='Homepage for Habit Tracker', data={})

@app.route('/protected')
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(msg='got protected route', data={'logged_in_as': current_user}), 200

# user auth
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(14))
    user = User(username=username, password=hashed)
    try:
        db.session.add(user)
        db.session.commit()
    except exc.IntegrityError:
        return jsonify(msg='username is already taken', data={}), 200
    return jsonify(msg='signup successful', data={'username': user.username, 'user_id': user.id}), 201

@app.route('/api/auth/reset_password', methods=['POST'])
@jwt_required()
def reset_password():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    new_password = request.json.get('new_password', None)

    if password == new_password:
        return jsonify(msg='new password must be different than current password', data={})
    
    user = get_user_by_username(db, User, username)

    try:
        if not bcrypt.checkpw(password.encode(), user.password):
            return jsonify(msg='invalid credentials', data={}), 401
    except KeyError:
        return jsonify(msg='invalid credentials', data={}), 401

    user.password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())

    db.session.commit()

    return jsonify(msg='successfully updated password', data={})

@app.route('/api/auth/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    try:
        if not bcrypt.checkpw(password.encode(), get_user_by_username(db, User, username).password):
            return jsonify(msg='invalid credentials', data={}), 401
    except KeyError:
        return jsonify(msg='invalid credentials', data={}), 401
    
    access_token = create_access_token(identity=username)

    return jsonify(msg='successfully logged in', data={'access_token': access_token}), 200

@app.route('/api/auth/logout', methods=['DELETE'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    now = datetime.now(timezone.utc)
    db.session.add(TokenBlocklist(jti=jti, created_at=now))
    db.session.commit()

    return jsonify(msg='successfully logged out (jwt revoked)', data={}), 200

# users
@app.route('/api/users/<username>') # TODO: don't need this route, but it could be useful in the future for some feature
def get_user(username):
    user = get_user_by_username(db, User, username)
    try:
        return jsonify(msg='successfully got user', data={'id':user.id, 'username':user.username})
    except AttributeError:
        return jsonify(msg='no user with that id found', data={})
    
# TODO: i don't actually need this route, but perhaps it could be used in the future for something like an admin role
@app.route('/api/users')
def get_users():
    users = get_all_users(db, User)
    user_list = []
    for user in users:
        print(user)
        user_list.append({'id': user.id, 'username': user.username}), 200
    return user_list

# Habits
@app.route('/api/habits/<user_id>')
@jwt_required()
def get_habits(user_id):
    habits = db.session.execute(db.select(Habit).where(Habit.user_id == user_id)).scalars()
    habit_list = []
    for habit in habits:
        print(habit)
        habit_list.append({'id': habit.id, 'name': habit.name, 'description': habit.description, 'frequency': habit.frequency})
    return jsonify(msg="successfully got user habits", data={"habits": habit_list}), 200

@app.route('/api/habits', methods=['POST'])
@jwt_required()
def create_habit():
    habit = Habit(name=request.json.get('name', None),
                description=request.json.get('description', None),
                frequency=request.json.get('frequency', None),
                user_id=request.json.get('user_id', None))
    db.session.add(habit)
    db.session.commit()
    return jsonify(msg='habit created', data={'name': habit.name,
                                              'description': habit.description,
                                              'frequency': habit.frequency,
                                              'user_id': habit.user_id,
                                              'id': habit.id}), 201

# https://docs.sqlalchemy.org/en/20/tutorial/orm_data_manipulation.html
# use the "unit of work" pattern mentioned in the link above
@app.route('/api/habits/<habit_id>', methods=['POST'])
@jwt_required()
def update_habit(habit_id):
    habit = db.session.execute(db.select(Habit).where(Habit.id == habit_id)).scalars().first()

    habit.name = request.json.get('name', None)
    habit.description = request.json.get('description', None)
    habit.frequency = request.json.get('frequency', None)

    db.session.commit()
    
    return jsonify(msg='successfully updated habit', data={'name': habit.name,
                                     'description': habit.description,
                                     'frequency': habit.frequency,
                                     'id': habit.id}), 200

@app.route('/api/habits/<habit_id>', methods=['DELETE'])
@jwt_required()
def delete_habit(habit_id):
    habit = db.session.execute(db.select(Habit).where(Habit.id == habit_id)).scalars().first()
    db.session.delete(habit)
    db.session.commit()

    return jsonify(msg='successfully deleted habit', data={'name': habit.name,
                                                           'description': habit.description,
                                                           'frequency': habit.frequency,
                                                           'user_id': habit.user_id,
                                                           'id': habit.id}), 200