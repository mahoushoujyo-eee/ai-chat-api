from flask import Flask, request, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, pre_prompt
import openai
from openai import OpenAI
import time
import jwt
import datetime
import json
import random
import redis

# 初始化 Flask 应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # 请替换为安全的密钥
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://'  # 替换为您的 MySQL 配置
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Redis配置
app.config['REDIS_HOST'] = '127.0.0.1'
app.config['REDIS_PORT'] = 6379
app.config['REDIS_DB'] = 0

# 初始化Redis连接
redis_client = redis.Redis(
    host=app.config['REDIS_HOST'],
    port=app.config['REDIS_PORT'],
    db=app.config['REDIS_DB'],
    decode_responses=True
)

# 邮件配置
app.config['MAIL_SERVER'] = 'smtp.qq.com'  # 替换为您的邮件服务器
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'wmrwkantskddhdmz@qq.com'  # 替换为您的邮箱
app.config['MAIL_PASSWORD'] = 'xxxxxxxx'    # 替换为您的邮箱密码

# 初始化扩展
from database import db
db.init_app(app)
bcrypt = Bcrypt(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 设置 OpenAI API 密钥
api_key = 'sk-a2h7anFytwbaw5fQ7hW9pNQz3SSq0ou683YAv55TO9LAaRQB'  # 替换为您的 OpenAI API 密钥
api_base = 'https://api2.aigcbest.top/v1'

client = OpenAI(
    api_key=api_key,
    base_url=api_base,
)

message_queue = []
message_queue_size = 15  # 聊天记录队列大小

# 用户加载函数
@login_manager.user_loader
def load_user(user_id):
    # 将 Query.get() 替换为 Session.get()
    return db.session.get(User, int(user_id))

# 生成密码重置令牌
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

def generate_reset_token(email):
    return s.dumps(email, salt='password-reset-salt')

# 验证密码重置令牌
def verify_reset_token(token, expiration=3600):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=expiration)
    except:
        return None
    return email

# 生成 AI 流式响应
def generate_ai_response(prompt, history=[]):
    message = [
        {"role": "system", "content": pre_prompt},
    ]
    if history:
        message.extend(history)

    message_queue.append({"role":"assistant","content":""})

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-nano",  # 使用正确的模型名称
            temperature=0.8,
            messages=message,
            stream=True
        )

        for chunk in response:
            if hasattr(chunk.choices[0].delta, "reasoning_content") and chunk.choices[0].delta.reasoning_content:
                print(chunk.choices[0].delta.reasoning_content, end="", flush=True)
                message_queue[-1]["content"] += chunk.choices[0].delta.reasoning_content
                yield f"{json.dumps({'message': chunk.choices[0].delta.reasoning_content})}\n\n"
            else:
                print(chunk.choices[0].delta.content, end="", flush=True)
                message_queue[-1]["content"] += chunk.choices[0].delta.content
                yield f"{json.dumps({'message': chunk.choices[0].delta.content})}\n\n"
        # for chunk in response:
        #     if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
        #         # 构造与前端期望格式相匹配的JSON响应
        #         yield f"data: {json.dumps({'message': chunk.choices[0].delta.content})}\n\n"
    except Exception as e:
        print(f"{json.dumps({'message': f'发生错误: {str(e)}'})}\n\n") 

# API 端点

# 注册
@app.route('/user/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    code = data.get('code')  # 获取验证码
    
    # 基本字段验证
    if not username or not email or not password or not code:
        return jsonify({'message': '缺少必要字段', 'code':400}), 200
        
    # 验证码验证
    stored_code = redis_client.get(f'register_code:{email}')
    if not stored_code or stored_code != code:
        return jsonify({'message': '验证码无效或已过期', 'code': 400}), 200
        
    # 用户查重
    if User.query.filter_by(email=email).first():
        return jsonify({'message': '邮箱已注册', 'code':400}), 200
    if User.query.filter_by(username=username).first():
        return jsonify({'message': '用户名已存在', 'code':400}), 200
        
    # 创建新用户
    hashed_password = generate_password_hash(password)
    user = User(username=username, email=email, password_hash=hashed_password)
    db.session.add(user)
    db.session.commit()
    
    # 注册成功后删除验证码
    redis_client.delete(f'reset_code:{email}')
    
    return jsonify({'message': '注册成功', 'code':200}), 200

# 登录
@app.route('/user/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        login_user(user)
        # 生成JWT token
        token = jwt.encode({
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'message': '登录成功',
            'code': 200,
            'data': {
                'token': token,
                'username': user.username
            }
        }), 200
    return jsonify({'message': '密码错误', 'code':400}), 200

# 登出
@app.route('/user/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': '登出成功', 'code':200}), 200

# 获取当前用户信息
@app.route('/user/data', methods=['GET'])
@login_required
def get_user():
    return jsonify({'username': current_user.username, 'email': current_user.email}), 200

# 请求密码重置
@app.route('/user/reset_code', methods=['POST'])
def reset_password_request():
    data = request.get_json()
    email = data.get('email')
    user = User.query.filter_by(email=email).first()
    if user:
        # 生成6位随机验证码
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        # 将验证码存储到Redis中，设置10分钟过期时间
        redis_client.setex(f'reset_code:{email}', 600, verification_code)
        
        # 发送验证码邮件
        msg = Message('密码重置验证码', sender='wmrwkantskddhdmz@qq.com', recipients=[user.email])
        msg.body = f'您的密码重置验证码是：{verification_code}\n此验证码将在10分钟内有效。'
        mail.send(msg)
        return jsonify({'message': '验证码已发送到您的邮箱', 'code':200}), 200
    return jsonify({'message': '未找到该邮箱', 'code':400}), 200

#验证码注册
@app.route('/user/register_code', methods=['POST'])
def generate_register_code():
    data = request.get_json()
    email = data.get('email')
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({'message': '该邮箱已存在', 'code':400}), 200
    else:
        # 生成6位随机验证码
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        # 将验证码存储到Redis中，设置10分钟过期时间
        redis_client.setex(f'register_code:{email}', 600, verification_code)
        
        # 发送验证码邮件
        msg = Message('解灵人注册验证码', sender='wmrwkantskddhdmz@qq.com', recipients=[email])
        msg.body = f'您的注册验证码是：{verification_code}\n此验证码将在10分钟内有效。'
        mail.send(msg)
        return jsonify({'message': '验证码已发送到您的邮箱', 'code':200}), 200
    

# 重置密码
@app.route('/user/reset', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')
    password = data.get('password')
    
    # 从Redis获取验证码并验证
    stored_code = redis_client.get(f'reset_code:{email}')
    if not stored_code or stored_code != code:
        return jsonify({'message': '验证码无效或已过期', 'code': 400}), 200
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': '用户未找到', 'code':404}), 200
    hashed_password = generate_password_hash(password)
    user.password_hash = hashed_password
    db.session.commit()
    return jsonify({'message': '密码已更新', 'code':200}), 200

# 流式传输 AI 响应
@app.route('/chat/stream', methods=['POST'])
@login_required
def stream():
    data = request.get_json()
    prompt = data.get('message')
    if not prompt:
        return Response("data: No prompt provided\n\n", mimetype='text/event-stream')

    message_queue.append({"role": "user", "content": prompt})
    if len(message_queue) > message_queue_size:
        message_queue.pop(0)

    def generate():
        for token in generate_ai_response(prompt, message_queue):
            yield f"data: {token}\n\n"
            time.sleep(0.01)  # 模拟流式传输的延迟
    return Response(generate(), mimetype='text/event-stream')

# 初始化数据库并运行应用
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
