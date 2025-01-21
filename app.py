from datetime import datetime
from datetime import timedelta
from datetime import timezone
from flask import Flask
from flask import jsonify
from flask import request
from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from markupsafe import escape
from sqlalchemy import exc
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chabits.db'
db.init_app(app)

ACCESS_EXPIRES = timedelta(hours=1)
app.config['JWT_SECRET_KEY'] = 'test'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = ACCESS_EXPIRES
jwt = JWTManager(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    habits = db.relationship('Habit', backref='user', lazy=True)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    frequency = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class HabitTracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Boolean, nullable=False)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)

class TokenBlocklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False)

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
    return 'Homepage for Habit Tracker'

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
    user = User(username=username, password=password)
    try:
        db.session.add(user)
        db.session.commit()
    except exc.IntegrityError:
        return ({'msg': 'username is already taken'})
    return jsonify(msg='signup successful', data={'username': user.username, 'user_id': user.id}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    print(get_user(username).json)

    if password != get_user(username).json['data']['password']:
        return jsonify({'msg': 'invalid credentials'}), 401
    
    access_token = create_access_token(identity=username)

    return jsonify(msg='successfully logged in', data={'access_token': access_token}), 200

@app.route('/api/auth/logout', methods=['DELETE'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    now = datetime.now(timezone.utc)
    db.session.add(TokenBlocklist(jti=jti, created_at=now))
    db.session.commit()

    return jsonify(msg='successfully logged out (jwt revoked)', data={})

# users
@app.route('/api/users/<username>') # TODO: don't need this route, but it could be useful in the future for some feature
def get_user(username):
    user = db.session.execute(db.select(User).where(User.username == username)).scalars().first()
    try:
        return jsonify(msg='successfully got user', data={'id':user.id, 'username':user.username, 'password':user.password})
    except AttributeError:
        return jsonify(msg='no user with that id found', data={})
    
# TODO: i don't actually need this route, but perhaps it could be used in the future for something like an admin role
@app.route('/api/users')
def get_users():
    users = db.session.execute(db.select(User).order_by(User.username)).scalars()
    user_list = []
    for user in users:
        user_list.append({'id': user.id, 'username': user.username, 'password' : user.password})
    return user_list

# Habits
@app.route('/api/habits/<user_id>')
@jwt_required()
def get_habits(user_id):
    habits = db.session.execute(db.select(Habit).where(Habit.user_id == user_id)).scalars()
    habit_list = []
    for habit in habits:
        habit_list.append({'id': habit.id, 'name': habit.name, 'description': habit.description, 'frequency': habit.frequency})
    return jsonify(habit_list=habit_list), 200

@app.route('/api/habits', methods=['POST']) # TODO: Consider using '/api/habits/<user_id> for this route
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
                                              'user_id': habit.user_id}), 201

# https://docs.sqlalchemy.org/en/20/tutorial/orm_data_manipulation.html
# use the "unit of work" pattern mentioned in the link above
@app.route('/api/habits/<habit_id>', methods=['POST']) # Needs POST, DELETE for edit, delete
@jwt_required()
def update_habit(habit_id):
    habit = db.session.execute(db.select(Habit).where(Habit.id == habit_id)).scalars().first()

    habit.name = request.json.get('name', None)
    habit.description = request.json.get('description', None)
    habit.frequency = request.json.get('frequency', None)

    db.session.commit()
    
    return jsonify(msg='successfully updated habit', data={'name': habit.name,
                                     'description': habit.description,
                                     'frequency': habit.frequency})
    
def delete_habit():
    pass