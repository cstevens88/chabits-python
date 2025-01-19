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
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import exc

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

@app.route('/')
def index():
    return 'Homepage for Habit Tracker'

@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200

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
        return jsonify(msg='username is already taken')
    return jsonify(username=username), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    if password != get_user(username)['password']:
        return jsonify(msg='invalid credentials'), 401
    
    access_token = create_access_token(identity=username)

    return jsonify(access_token=access_token), 200

@app.route('/api/auth/logout', methods=['DELETE'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    now = datetime.now(timezone.utc)
    db.session.add(TokenBlocklist(jti=jti, created_at=now))
    db.session.commit()
    return jsonify(msg='successfully logged out (jwt revoked)')

# users
@app.route('/api/user/<username>')
def get_user(username):
    user = db.session.execute(db.select(User).where(User.username == username)).scalars().first()
    return jsonify(id=user.id, username=user.username, password=user.password)

@app.route('/api/users')
def get_users():
    users = db.session.execute(db.select(User).order_by(User.username)).scalars()
    user_list = []
    for user in users:
        user_list.append({'id': user.id, 'username': user.username, 'password' : user.password})
    return jsonify(user_list=user_list)

# Habits
@app.route('/api/habits')
@jwt_required()
def get_habits():
    habits = db.session.execute(db.select(Habit).where(Habit.user_id == '1')).scalars()
    habit_list = []
    for habit in habits:
        habit_list.append({'id': habit.id, 'name': habit.name, 'description': habit.description, 'frequency': habit.frequency})
    return jsonify(habit_list=habit_list), 200

@app.route('/api/habits', methods=['POST'])
@jwt_required()
def create_habit():
    habit = Habit(name=request.json.get('name', None),
                description=request.json.get('description', None),
                frequency=request.json.get('frequency', None),
                user_id=request.json.get('user_id', None))
    db.session.add(habit)
    db.session.commit()
    return jsonify(msg='habit created'), 201
    

@app.route('/api/habits/<id>') # Needs PUT, DELETE for edit, delete
def edit_habit():
    pass
def delete_habit():
    pass