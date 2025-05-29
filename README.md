# ai对话demo后端（flask）

## 项目简介
本项目是一个基于 Flask 的心理咨询平台后端服务，提供用户注册、登录、心理对话交互等核心功能，集成 OpenAI API 实现智能心理咨询响应。

## 目录结构
```
flask/
├── .git/               # Git 版本控制目录
├── __pycache__/        # Python 缓存文件
├── app.py              # 主应用入口
├── database.py         # 数据库配置
├── dump.rdb            # Redis 持久化文件
├── forms.py            # 表单验证（待补充）
├── models.py           # 数据模型定义
├── requirements.txt    # 依赖包列表
└── README.md           # 项目说明（当前文件）
```

## 依赖项
项目依赖以下 Python 包（版本固定）：
```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Login==0.6.3
Flask-Bcrypt==1.0.1
Flask-Mail==0.9.1
itsdangerous==2.1.2
mysql-connector-python==8.1.0
openai==1.76.0
redis==5.2.1
```

## 运行指南
### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置项修改
- 在 `app.py` 中替换以下配置：
  - `SECRET_KEY`：设置为安全的随机字符串
  - `SQLALCHEMY_DATABASE_URI`：修改为你的 MySQL 数据库连接地址
  - `api_key`：替换为有效的 OpenAI API 密钥
  - 邮件配置（`MAIL_SERVER`、`MAIL_USERNAME`、`MAIL_PASSWORD`）：根据实际邮箱服务调整

### 3. 启动服务
```bash
python app.py
```
服务默认运行在 `http://localhost:5001`，调试模式已开启（`debug=True`）。

## 功能说明
- **用户模块**：支持注册（含验证码验证）、登录（JWT 令牌）、登出、用户信息获取
- **对话模块**：基于 OpenAI API 实现流式心理咨询响应，支持历史对话管理
- **数据模型**：包含 `User`（用户）、`Conversation`（对话）、`Message`（消息）三张数据表，通过 SQLAlchemy 管理数据库
