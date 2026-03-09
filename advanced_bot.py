# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║     🔥 ULTIMATE GADGET HOSTING BOT - ADVANCED VERSION 🔥      ║
║                     Version 3.0.0 Ultimate                    ║
║                                                               ║
║  Features:                                                    ║
║  • Beautiful Modern UI with Advanced Inline Keyboards         ║
║  • Multi-Language Support (English, Hindi, Russian)           ║
║  • Advanced Admin Dashboard                                   ║
║  • Real-time System Monitoring                                ║
║  • User Analytics & Activity Tracking                         ║
║  • Database Backup/Restore System                             ║
║  • Rate Limiting & Anti-Spam                                  ║
║  • Premium Subscription Tiers                                 ║
║  • Scheduled Tasks & Auto-Cleanup                            ║
║  • Health Monitoring & Auto-Recovery                         ║
║  • Advanced Security System                                   ║
║  • Detailed Logs Viewer                                       ║
║  • Resource Usage Analytics                                   ║
║  • API Key Management                                         ║
║  • Multi-Admin Support with Roles                            ║
╚══════════════════════════════════════════════════════════════╝
"""

import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import json
import logging
import signal
import threading
import re
import sys
import atexit
import requests
import hashlib
import secrets
import asyncio
from collections import defaultdict
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import traceback
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION SECTION
# ═══════════════════════════════════════════════════════════════

TOKEN = os.getenv('TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', 7857957075))
ADMIN_ID = int(os.getenv('ADMIN_ID', 7857957075))
YOUR_USERNAME = os.getenv('YOUR_USERNAME', 'mrseller_00')
UPDATE_CHANNEL = os.getenv('UPDATE_CHANNEL', 'gadgetpremiumzone')

# Limits Configuration
FREE_USER_LIMIT = int(os.getenv('FREE_USER_LIMIT', 2))
SUBSCRIBED_USER_LIMIT = int(os.getenv('SUBSCRIBED_USER_LIMIT', 20))
PREMIUM_USER_LIMIT = int(os.getenv('PREMIUM_USER_LIMIT', 50))
VIP_USER_LIMIT = int(os.getenv('VIP_USER_LIMIT', 100))
ADMIN_LIMIT = int(os.getenv('ADMIN_LIMIT', 999))
OWNER_LIMIT = float('inf')

# Folder Setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

# Create directories
for directory in [UPLOAD_BOTS_DIR, IROTECH_DIR, BACKUP_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Initialize Bot
bot = telebot.TeleBot(TOKEN)

# ═══════════════════════════════════════════════════════════════
# ENUMS AND DATACLASSES
# ═══════════════════════════════════════════════════════════════

class UserTier(Enum):
    FREE = "free"
    SUBSCRIBED = "subscribed"
    PREMIUM = "premium"
    VIP = "vip"
    ADMIN = "admin"
    OWNER = "owner"

class AdminRole(Enum):
    MODERATOR = "moderator"      # Can ban users, view logs
    ADMIN = "admin"              # Can manage subscriptions
    SUPER_ADMIN = "super_admin"  # Full access except owner settings
    OWNER = "owner"              # Full access

class Language(Enum):
    ENGLISH = "en"
    HINDI = "hi"
    RUSSIAN = "ru"

@dataclass
class UserInfo:
    user_id: int
    username: str = ""
    first_name: str = ""
    join_date: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    tier: UserTier = UserTier.FREE
    language: Language = Language.ENGLISH
    files_count: int = 0
    total_uploads: int = 0
    warnings: int = 0
    is_banned: bool = False
    ban_reason: str = ""

@dataclass
class ScriptInfo:
    script_key: str
    file_name: str
    file_type: str
    process: Any = None
    log_file: Any = None
    start_time: datetime = field(default_factory=datetime.now)
    user_folder: str = ""
    script_owner_id: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    restart_count: int = 0

@dataclass
class SystemStats:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_sent: int = 0
    network_recv: int = 0
    uptime: float = 0.0
    total_processes: int = 0

# ═══════════════════════════════════════════════════════════════
# GLOBAL DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

# Core Data
bot_scripts: Dict[str, ScriptInfo] = {}
user_subscriptions: Dict[int, Dict] = {}
user_files: Dict[int, List[Tuple[str, str]]] = {}
active_users: Dict[int, UserInfo] = {}
admin_ids: set = {ADMIN_ID, OWNER_ID}
banned_users: set = set()
user_limits: Dict[int, int] = {}
bot_locked = False

# Admin Roles
admin_roles: Dict[int, AdminRole] = {OWNER_ID: AdminRole.OWNER}
if ADMIN_ID != OWNER_ID:
    admin_roles[ADMIN_ID] = AdminRole.SUPER_ADMIN

# Mandatory Channels
mandatory_channels: Dict[str, Dict] = {}

# Rate Limiting
user_requests: Dict[int, List[float]] = defaultdict(list)
RATE_LIMITS = {
    UserTier.FREE: 10,       # requests per minute
    UserTier.SUBSCRIBED: 30,
    UserTier.PREMIUM: 60,
    UserTier.VIP: 100,
    UserTier.ADMIN: 500,
    UserTier.OWNER: 9999
}

# Pending Actions
pending_zip_files: Dict[int, Dict[str, bytes]] = {}
pending_actions: Dict[int, Dict] = {}

# API Keys
api_keys: Dict[str, Dict] = {}  # api_key -> {user_id, created, permissions}

# User Activity Tracking
user_activity: Dict[int, Dict] = defaultdict(lambda: {
    'commands': 0,
    'uploads': 0,
    'downloads': 0,
    'errors': 0,
    'last_commands': [],
    'daily_activity': defaultdict(int)
})

# System Monitoring
system_stats = SystemStats()
start_time = datetime.now()

# Database Lock
DB_LOCK = threading.Lock()

# ═══════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════

log_file_path = os.path.join(LOGS_DIR, f'bot_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('GADGET_BOT')

# ═══════════════════════════════════════════════════════════════
# MULTI-LANGUAGE SUPPORT
# ═══════════════════════════════════════════════════════════════

LANGUAGES = {
    Language.ENGLISH: {
        'welcome': "Welcome, {name}!",
        'your_id': "Your User ID: {id}",
        'your_status': "Your Status: {status}",
        'files_uploaded': "Files Uploaded: {current}/{limit}",
        'upload_file': "📤 Upload File",
        'check_files': "📂 Check Files",
        'bot_speed': "⚡ Bot Speed",
        'statistics': "📊 Statistics",
        'contact_owner': "📞 Contact Owner",
        'manual_install': "📦 Manual Install",
        'help': "🆘 Help",
        'admin_panel': "👑 Admin Panel",
        'user_management': "👥 User Management",
        'subscriptions': "💳 Subscriptions",
        'broadcast': "📢 Broadcast",
        'lock_bot': "🔒 Lock Bot",
        'unlock_bot': "🔓 Unlock Bot",
        'settings': "⚙️ Settings",
        'back': "🔙 Back",
        'cancel': "❌ Cancel",
        'confirm': "✅ Confirm",
        'success': "✅ Success!",
        'error': "❌ Error!",
        'banned': "🚫 You are banned from using this bot.",
        'not_authorized': "⚠️ You don't have permission.",
        'bot_locked': "🔒 Bot is locked. Please try again later.",
        'subscription_expired': "⏰ Your subscription has expired.",
        'file_limit_reached': "⚠️ File limit reached: {current}/{limit}",
        'upload_prompt': "📤 Send your Python (.py), JavaScript (.js), or ZIP (.zip) file.",
        'no_files': "📂 You haven't uploaded any files yet.",
        'running': "🟢 Running",
        'stopped': "🔴 Stopped",
        'start': "🟢 Start",
        'stop': "🔴 Stop",
        'restart': "🔄 Restart",
        'delete': "🗑️ Delete",
        'logs': "📜 Logs",
        'add_admin': "➕ Add Admin",
        'remove_admin': "➖ Remove Admin",
        'list_admins': "📋 List Admins",
        'ban_user': "🚫 Ban User",
        'unban_user': "✅ Unban User",
        'user_info': "📊 User Info",
        'all_users': "👥 All Users",
        'set_limit': "🔧 Set User Limit",
        'remove_limit': "🗑️ Remove Limit",
        'system_info': "💻 System Info",
        'performance': "📈 Performance",
        'backup': "💾 Backup",
        'cleanup': "🧹 Cleanup",
        'api_keys': "🔑 API Keys",
        'analytics': "📊 Analytics",
        'activity_log': "📝 Activity Log",
        'health_check': "🏥 Health Check",
    },
    Language.HINDI: {
        'welcome': "स्वागत है, {name}!",
        'your_id': "आपका User ID: {id}",
        'your_status': "आपकी स्थिति: {status}",
        'files_uploaded': "अपलोड की गई फ़ाइलें: {current}/{limit}",
        'upload_file': "📤 फ़ाइल अपलोड करें",
        'check_files': "📂 फ़ाइलें देखें",
        'bot_speed': "⚡ बॉट स्पीड",
        'statistics': "📊 आंकड़े",
        'contact_owner': "📞 मालिक से संपर्क करें",
        'manual_install': "📦 मैन्युअल इंस्टॉल",
        'help': "🆘 मदद",
        'admin_panel': "👑 एडमिन पैनल",
        'user_management': "👥 यूजर मैनेजमेंट",
        'subscriptions': "💳 सब्सक्रिप्शन",
        'broadcast': "📢 ब्रॉडकास्ट",
        'lock_bot': "🔒 बॉट लॉक करें",
        'unlock_bot': "🔓 बॉट अनलॉक करें",
        'settings': "⚙️ सेटिंग्स",
        'back': "🔙 वापस",
        'cancel': "❌ रद्द करें",
        'confirm': "✅ पुष्टि करें",
        'success': "✅ सफल!",
        'error': "❌ त्रुटि!",
        'banned': "🚫 आप इस बॉट का उपयोग करने से प्रतिबंधित हैं।",
        'not_authorized': "⚠️ आपको अनुमति नहीं है।",
        'bot_locked': "🔒 बॉट लॉक है। कृपया बाद में प्रयास करें।",
        'subscription_expired': "⏰ आपकी सब्सक्रिप्शन समाप्त हो गई है।",
        'file_limit_reached': "⚠️ फ़ाइल सीमा पहुंच गई: {current}/{limit}",
        'upload_prompt': "📤 अपनी Python (.py), JavaScript (.js), या ZIP (.zip) फ़ाइल भेजें।",
        'no_files': "📂 आपने अभी तक कोई फ़ाइल अपलोड नहीं की है।",
        'running': "🟢 चल रहा है",
        'stopped': "🔴 बंद",
        'start': "🟢 शुरू करें",
        'stop': "🔴 रोकें",
        'restart': "🔄 पुनरारंभ करें",
        'delete': "🗑️ हटाएं",
        'logs': "📜 लॉग्स",
    },
    Language.RUSSIAN: {
        'welcome': "Добро пожаловать, {name}!",
        'your_id': "Ваш ID: {id}",
        'your_status': "Ваш статус: {status}",
        'files_uploaded': "Загружено файлов: {current}/{limit}",
        'upload_file': "📤 Загрузить файл",
        'check_files': "📂 Мои файлы",
        'bot_speed': "⚡ Скорость бота",
        'statistics': "📊 Статистика",
        'contact_owner': "📞 Связаться",
        'manual_install': "📦 Установка",
        'help': "🆘 Помощь",
        'admin_panel': "👑 Админ панель",
        'user_management': "👥 Пользователи",
        'subscriptions': "💳 Подписки",
        'broadcast': "📢 Рассылка",
        'lock_bot': "🔒 Заблокировать",
        'unlock_bot': "🔓 Разблокировать",
        'settings': "⚙️ Настройки",
        'back': "🔙 Назад",
        'cancel': "❌ Отмена",
        'confirm': "✅ Подтвердить",
        'success': "✅ Успешно!",
        'error': "❌ Ошибка!",
        'banned': "🚫 Вы заблокированы.",
        'not_authorized': "⚠️ Нет доступа.",
        'bot_locked': "🔒 Бот заблокирован.",
        'subscription_expired': "⏰ Подписка истекла.",
        'file_limit_reached': "⚠️ Лимит файлов: {current}/{limit}",
        'upload_prompt': "📤 Отправьте Python, JavaScript или ZIP файл.",
        'no_files': "📂 Файлы не загружены.",
        'running': "🟢 Работает",
        'stopped': "🔴 Остановлен",
    }
}

def get_text(key: str, lang: Language = Language.ENGLISH, **kwargs) -> str:
    """Get localized text with placeholder support"""
    texts = LANGUAGES.get(lang, LANGUAGES[Language.ENGLISH])
    text = texts.get(key, LANGUAGES[Language.ENGLISH].get(key, key))
    try:
        return text.format(**kwargs)
    except KeyError:
        return text

# ═══════════════════════════════════════════════════════════════
# SECURITY CONFIGURATION
# ═══════════════════════════════════════════════════════════════

SECURITY_CONFIG = {
    'blocked_modules': [
        'os.system', 'subprocess.Popen', 'eval', 'exec', 'compile', '__import__',
        'os.remove', 'os.unlink', 'shutil.rmtree', 'os.walk'
    ],
    'max_file_size': 20 * 1024 * 1024,  # 20MB
    'max_script_runtime': 3600,  # 1 hour
    'allowed_extensions': ['.py', '.js', '.zip'],
    'dangerous_patterns': [
        # System Commands
        r'\bos\.system\b', r'\bsubprocess\.(Popen|call|run)\b',
        r'\beval\b', r'\bexec\b', r'\bcompile\b', r'\b__import__\b',
        # File System
        r'\bos\.(remove|unlink|rmdir)\b', r'\bshutil\.rmtree\b',
        # Network (basic blocking for security)
        r'\bsocket\.socket\b', r'\bnc\s+-e\b',
        # Code Injection
        r'\b__builtins__\b', r'\bgetattr\s*\(\s*["\']__',
        # Privilege Escalation
        r'\bsudo\b', r'\bsu\s+\w+', r'\bchmod\s+777',
        # System Information Leak
        r'/etc/passwd', r'/etc/shadow', r'\.ssh/',
        # Dangerous Shell Commands
        r'rm\s+-rf\s+/', r'dd\s+if=', r':>\s*',
    ]
}

# ═══════════════════════════════════════════════════════════════
# DATABASE FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def init_db():
    """Initialize database with all required tables"""
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Users table with extended fields
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TEXT,
            last_seen TEXT,
            tier TEXT DEFAULT 'free',
            language TEXT DEFAULT 'en',
            files_count INTEGER DEFAULT 0,
            total_uploads INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            ban_reason TEXT,
            banned_by INTEGER,
            ban_date TEXT
        )''')
        
        # Subscriptions table
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            tier TEXT,
            expiry TEXT,
            created TEXT,
            payment_id TEXT
        )''')
        
        # User files table
        c.execute('''CREATE TABLE IF NOT EXISTS user_files (
            user_id INTEGER,
            file_name TEXT,
            file_type TEXT,
            upload_date TEXT,
            file_size INTEGER,
            PRIMARY KEY (user_id, file_name)
        )''')
        
        # Admins table with roles
        c.execute('''CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'admin',
            added_by INTEGER,
            added_date TEXT,
            permissions TEXT
        )''')
        
        # User limits table
        c.execute('''CREATE TABLE IF NOT EXISTS user_limits (
            user_id INTEGER PRIMARY KEY,
            file_limit INTEGER,
            set_by INTEGER,
            set_date TEXT
        )''')
        
        # Mandatory channels table
        c.execute('''CREATE TABLE IF NOT EXISTS mandatory_channels (
            channel_id TEXT PRIMARY KEY,
            channel_username TEXT,
            channel_name TEXT,
            added_by INTEGER,
            added_date TEXT
        )''')
        
        # Install logs table
        c.execute('''CREATE TABLE IF NOT EXISTS install_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            module_name TEXT,
            package_name TEXT,
            status TEXT,
            log TEXT,
            install_date TEXT
        )''')
        
        # Activity logs table
        c.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT
        )''')
        
        # API keys table
        c.execute('''CREATE TABLE IF NOT EXISTS api_keys (
            api_key TEXT PRIMARY KEY,
            user_id INTEGER,
            permissions TEXT,
            created TEXT,
            last_used TEXT,
            is_active INTEGER DEFAULT 1
        )''')
        
        # Scripts history table
        c.execute('''CREATE TABLE IF NOT EXISTS script_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_name TEXT,
            action TEXT,
            timestamp TEXT,
            details TEXT
        )''')
        
        # Broadcast history
        c.execute('''CREATE TABLE IF NOT EXISTS broadcast_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            message_text TEXT,
            sent_count INTEGER,
            failed_count INTEGER,
            timestamp TEXT
        )''')
        
        # Add owner as admin
        c.execute('INSERT OR IGNORE INTO admins (user_id, role, added_by, added_date) VALUES (?, ?, ?, ?)',
                  (OWNER_ID, 'owner', OWNER_ID, datetime.now().isoformat()))
        
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id, role, added_by, added_date) VALUES (?, ?, ?, ?)',
                      (ADMIN_ID, 'super_admin', OWNER_ID, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)
        return False

def load_data():
    """Load all data from database into memory"""
    logger.info("Loading data from database...")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Load users
        c.execute('SELECT * FROM users')
        for row in c.fetchall():
            user_id, username, first_name, join_date, last_seen, tier, lang, files_count, total_uploads, warnings, is_banned, ban_reason, banned_by, ban_date = row
            active_users[user_id] = UserInfo(
                user_id=user_id,
                username=username or "",
                first_name=first_name or "",
                join_date=datetime.fromisoformat(join_date) if join_date else datetime.now(),
                last_seen=datetime.fromisoformat(last_seen) if last_seen else datetime.now(),
                tier=UserTier(tier) if tier else UserTier.FREE,
                language=Language(lang) if lang else Language.ENGLISH,
                files_count=files_count or 0,
                total_uploads=total_uploads or 0,
                warnings=warnings or 0,
                is_banned=bool(is_banned),
                ban_reason=ban_reason or ""
            )
            if is_banned:
                banned_users.add(user_id)
        
        # Load subscriptions
        c.execute('SELECT user_id, tier, expiry FROM subscriptions')
        for user_id, tier, expiry in c.fetchall():
            try:
                user_subscriptions[user_id] = {
                    'tier': tier,
                    'expiry': datetime.fromisoformat(expiry) if expiry else None
                }
            except ValueError:
                logger.warning(f"Invalid expiry date for user {user_id}")
        
        # Load user files
        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id].append((file_name, file_type))
        
        # Load admins with roles
        c.execute('SELECT user_id, role FROM admins')
        for user_id, role in c.fetchall():
            admin_ids.add(user_id)
            admin_roles[user_id] = AdminRole(role) if role else AdminRole.ADMIN
        
        # Load user limits
        c.execute('SELECT user_id, file_limit FROM user_limits')
        for user_id, file_limit in c.fetchall():
            user_limits[user_id] = file_limit
        
        # Load mandatory channels
        c.execute('SELECT channel_id, channel_username, channel_name FROM mandatory_channels')
        for channel_id, channel_username, channel_name in c.fetchall():
            mandatory_channels[channel_id] = {
                'username': channel_username,
                'name': channel_name
            }
        
        # Load API keys
        c.execute('SELECT api_key, user_id, permissions, created, is_active FROM api_keys')
        for api_key, user_id, permissions, created, is_active in c.fetchall():
            if is_active:
                api_keys[api_key] = {
                    'user_id': user_id,
                    'permissions': json.loads(permissions) if permissions else [],
                    'created': created,
                    'last_used': None
                }
        
        conn.close()
        logger.info(f"✅ Data loaded: {len(active_users)} users, {len(user_subscriptions)} subscriptions, {len(admin_ids)} admins")
        return True
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}", exc_info=True)
        return False

# Initialize DB and Load Data
init_db()
load_data()

# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_user_folder(user_id: int) -> str:
    """Get or create user's folder"""
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_tier(user_id: int) -> UserTier:
    """Get user's tier"""
    if user_id == OWNER_ID:
        return UserTier.OWNER
    if user_id in admin_ids:
        return UserTier.ADMIN
    if user_id in user_subscriptions:
        sub = user_subscriptions[user_id]
        if sub.get('expiry') and sub['expiry'] > datetime.now():
            tier = sub.get('tier', 'subscribed')
            return UserTier(tier) if tier in [t.value for t in UserTier] else UserTier.SUBSCRIBED
    return UserTier.FREE

def get_user_file_limit(user_id: int) -> int:
    """Get file upload limit for user"""
    if user_id == OWNER_ID:
        return OWNER_LIMIT
    if user_id in admin_ids:
        return ADMIN_LIMIT
    if user_id in user_limits:
        return user_limits[user_id]
    
    tier = get_user_tier(user_id)
    limits = {
        UserTier.FREE: FREE_USER_LIMIT,
        UserTier.SUBSCRIBED: SUBSCRIBED_USER_LIMIT,
        UserTier.PREMIUM: PREMIUM_USER_LIMIT,
        UserTier.VIP: VIP_USER_LIMIT,
        UserTier.ADMIN: ADMIN_LIMIT,
        UserTier.OWNER: OWNER_LIMIT
    }
    return limits.get(tier, FREE_USER_LIMIT)

def get_user_file_count(user_id: int) -> int:
    """Get number of files uploaded by user"""
    return len(user_files.get(user_id, []))

def check_rate_limit(user_id: int) -> Tuple[bool, int]:
    """Check if user is within rate limit. Returns (is_allowed, remaining)"""
    tier = get_user_tier(user_id)
    limit = RATE_LIMITS.get(tier, 10)
    
    now = time.time()
    minute_ago = now - 60
    
    # Clean old requests
    user_requests[user_id] = [t for t in user_requests[user_id] if t > minute_ago]
    
    current_count = len(user_requests[user_id])
    remaining = max(0, limit - current_count)
    
    if current_count >= limit:
        return False, 0
    
    user_requests[user_id].append(now)
    return True, remaining - 1

def is_user_banned(user_id: int) -> bool:
    """Check if user is banned"""
    return user_id in banned_users

def has_permission(user_id: int, required_role: AdminRole) -> bool:
    """Check if user has required admin role"""
    if user_id == OWNER_ID:
        return True
    
    user_role = admin_roles.get(user_id)
    if not user_role:
        return False
    
    role_hierarchy = {
        AdminRole.MODERATOR: 1,
        AdminRole.ADMIN: 2,
        AdminRole.SUPER_ADMIN: 3,
        AdminRole.OWNER: 4
    }
    
    return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_role, 0)

def log_activity(user_id: int, action: str, details: str = ""):
    """Log user activity"""
    try:
        with DB_LOCK:
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)',
                      (user_id, action, details, datetime.now().isoformat()))
            conn.commit()
            conn.close()
        
        # Update in-memory tracking
        user_activity[user_id]['commands'] += 1
        user_activity[user_id]['last_commands'].append({
            'action': action,
            'time': datetime.now().isoformat()
        })
        if len(user_activity[user_id]['last_commands']) > 50:
            user_activity[user_id]['last_commands'] = user_activity[user_id]['last_commands'][-50:]
    except Exception as e:
        logger.error(f"Error logging activity: {e}")

def update_system_stats():
    """Update system statistics"""
    global system_stats
    try:
        system_stats.cpu_percent = psutil.cpu_percent(interval=0.1)
        system_stats.memory_percent = psutil.virtual_memory().percent
        system_stats.disk_percent = psutil.disk_usage('/').percent
        system_stats.uptime = (datetime.now() - start_time).total_seconds()
        system_stats.total_processes = len(psutil.pids())
        
        net_io = psutil.net_io_counters()
        system_stats.network_sent = net_io.bytes_sent
        system_stats.network_recv = net_io.bytes_recv
    except Exception as e:
        logger.error(f"Error updating system stats: {e}")

# ═══════════════════════════════════════════════════════════════
# SECURITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def check_code_security(file_path: str, file_type: str) -> Tuple[bool, str]:
    """Check code for dangerous patterns"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        found_patterns = []
        for pattern in SECURITY_CONFIG['dangerous_patterns']:
            if re.search(pattern, content, re.IGNORECASE):
                found_patterns.append(pattern)
        
        if found_patterns:
            logger.warning(f"🚨 Dangerous patterns in {file_path}: {found_patterns[:3]}")
            return False, f"Found {len(found_patterns)} security issues"
        
        return True, "Code is safe"
    except Exception as e:
        logger.error(f"Security check error: {e}")
        return False, f"Security check error: {str(e)}"

def scan_zip_security(zip_path: str) -> Tuple[bool, str]:
    """Scan ZIP file for security issues"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith(('.py', '.js', '.sh', '.bat')):
                    with zip_ref.open(file_info.filename) as f:
                        content = f.read().decode('utf-8', errors='ignore')
                        for pattern in SECURITY_CONFIG['dangerous_patterns']:
                            if re.search(pattern, content, re.IGNORECASE):
                                return False, f"Security issue in {file_info.filename}"
        return True, "Archive is safe"
    except Exception as e:
        return False, f"Scan error: {str(e)}"

# ═══════════════════════════════════════════════════════════════
# BEAUTIFUL UI KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def create_main_menu_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Create beautiful main menu with role-based buttons"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    lang = active_users.get(user_id, UserInfo(user_id)).language if user_id in active_users else Language.ENGLISH
    tier = get_user_tier(user_id)
    
    # Top section - Channel
    markup.add(types.InlineKeyboardButton(
        f"📢 {UPDATE_CHANNEL}",
        url=f'https://t.me/{UPDATE_CHANNEL.replace("@", "")}'
    ))
    
    # Main actions
    markup.row(
        types.InlineKeyboardButton(get_text('upload_file', lang), callback_data='upload'),
        types.InlineKeyboardButton(get_text('check_files', lang), callback_data='check_files')
    )
    
    # Status section
    markup.row(
        types.InlineKeyboardButton(get_text('bot_speed', lang), callback_data='speed'),
        types.InlineKeyboardButton(get_text('statistics', lang), callback_data='stats')
    )
    
    # Tools section
    markup.row(
        types.InlineKeyboardButton(get_text('manual_install', lang), callback_data='manual_install'),
        types.InlineKeyboardButton(get_text('help', lang), callback_data='help')
    )
    
    # Admin section
    if tier in [UserTier.ADMIN, UserTier.OWNER]:
        markup.add(types.InlineKeyboardButton("━" * 10 + " 👑 ADMIN " + "━" * 10, callback_data='none'))
        
        markup.row(
            types.InlineKeyboardButton(get_text('admin_panel', lang), callback_data='admin_panel'),
            types.InlineKeyboardButton(get_text('user_management', lang), callback_data='user_management')
        )
        
        markup.row(
            types.InlineKeyboardButton(get_text('subscriptions', lang), callback_data='subscriptions'),
            types.InlineKeyboardButton(get_text('broadcast', lang), callback_data='broadcast')
        )
        
        lock_text = get_text('unlock_bot', lang) if bot_locked else get_text('lock_bot', lang)
        markup.row(
            types.InlineKeyboardButton(lock_text, callback_data='toggle_lock'),
            types.InlineKeyboardButton("🟢 Run All", callback_data='run_all')
        )
        
        markup.row(
            types.InlineKeyboardButton("📢 Channels", callback_data='channels'),
            types.InlineKeyboardButton(get_text('settings', lang), callback_data='admin_settings')
        )
        
        markup.row(
            types.InlineKeyboardButton("📊 Analytics", callback_data='analytics'),
            types.InlineKeyboardButton("💾 Backup", callback_data='backup')
        )
        
        if has_permission(user_id, AdminRole.SUPER_ADMIN):
            markup.row(
                types.InlineKeyboardButton("🔑 API Keys", callback_data='api_keys'),
                types.InlineKeyboardButton("🏥 Health", callback_data='health_check')
            )
    
    # Contact
    markup.add(types.InlineKeyboardButton(
        get_text('contact_owner', lang),
        url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}'
    ))
    
    return markup

def create_admin_dashboard() -> types.InlineKeyboardMarkup:
    """Create beautiful admin dashboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(types.InlineKeyboardButton("━" * 8 + " 👑 ADMIN PANEL " + "━" * 8, callback_data='none'))
    
    markup.row(
        types.InlineKeyboardButton("➕ Add Admin", callback_data='add_admin'),
        types.InlineKeyboardButton("➖ Remove Admin", callback_data='remove_admin')
    )
    
    markup.row(
        types.InlineKeyboardButton("📋 List Admins", callback_data='list_admins'),
        types.InlineKeyboardButton("🔑 Admin Roles", callback_data='admin_roles')
    )
    
    markup.row(
        types.InlineKeyboardButton("📊 Admin Stats", callback_data='admin_stats'),
        types.InlineKeyboardButton("📝 Admin Logs", callback_data='admin_logs')
    )
    
    markup.add(types.InlineKeyboardButton(get_text('back'), callback_data='back_to_main'))
    
    return markup

def create_user_management_keyboard() -> types.InlineKeyboardMarkup:
    """Create user management keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(types.InlineKeyboardButton("━" * 7 + " 👥 USER MANAGEMENT " + "━" * 7, callback_data='none'))
    
    markup.row(
        types.InlineKeyboardButton("🚫 Ban User", callback_data='ban_user'),
        types.InlineKeyboardButton("✅ Unban User", callback_data='unban_user')
    )
    
    markup.row(
        types.InlineKeyboardButton("📊 User Info", callback_data='user_info'),
        types.InlineKeyboardButton("👥 All Users", callback_data='all_users')
    )
    
    markup.row(
        types.InlineKeyboardButton("🔧 Set Limit", callback_data='set_limit'),
        types.InlineKeyboardButton("🗑️ Remove Limit", callback_data='remove_limit')
    )
    
    markup.row(
        types.InlineKeyboardButton("⚠️ User Warnings", callback_data='user_warnings'),
        types.InlineKeyboardButton("📈 User Activity", callback_data='user_activity')
    )
    
    markup.row(
        types.InlineKeyboardButton("🔍 Search User", callback_data='search_user'),
        types.InlineKeyboardButton("📤 Export Users", callback_data='export_users')
    )
    
    markup.add(types.InlineKeyboardButton(get_text('back'), callback_data='back_to_main'))
    
    return markup

def create_settings_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Create settings keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(types.InlineKeyboardButton("━" * 9 + " ⚙️ SETTINGS " + "━" * 9, callback_data='none'))
    
    markup.row(
        types.InlineKeyboardButton("💻 System Info", callback_data='system_info'),
        types.InlineKeyboardButton("📈 Performance", callback_data='performance')
    )
    
    markup.row(
        types.InlineKeyboardButton("🧹 Cleanup Files", callback_data='cleanup'),
        types.InlineKeyboardButton("📋 Install Logs", callback_data='install_logs')
    )
    
    markup.row(
        types.InlineKeyboardButton("🎨 Bot Appearance", callback_data='appearance'),
        types.InlineKeyboardButton("🌐 Language", callback_data='language_settings')
    )
    
    if has_permission(user_id, AdminRole.SUPER_ADMIN):
        markup.row(
            types.InlineKeyboardButton("🔒 Security Settings", callback_data='security_settings'),
            types.InlineKeyboardButton("📊 Rate Limits", callback_data='rate_limits')
        )
    
    markup.add(types.InlineKeyboardButton(get_text('back'), callback_data='back_to_main'))
    
    return markup

def create_subscription_keyboard() -> types.InlineKeyboardMarkup:
    """Create subscription management keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(types.InlineKeyboardButton("━" * 7 + " 💳 SUBSCRIPTIONS " + "━" * 7, callback_data='none'))
    
    markup.row(
        types.InlineKeyboardButton("➕ Add Subscription", callback_data='add_subscription'),
        types.InlineKeyboardButton("➖ Remove Subscription", callback_data='remove_subscription')
    )
    
    markup.row(
        types.InlineKeyboardButton("🔍 Check Subscription", callback_data='check_subscription'),
        types.InlineKeyboardButton("📋 All Subscriptions", callback_data='all_subscriptions')
    )
    
    markup.row(
        types.InlineKeyboardButton("⭐ Premium Users", callback_data='premium_users'),
        types.InlineKeyboardButton("💎 VIP Users", callback_data='vip_users')
    )
    
    markup.row(
        types.InlineKeyboardButton("📅 Expiring Soon", callback_data='expiring_soon'),
        types.InlineKeyboardButton("📤 Export Data", callback_data='export_subscriptions')
    )
    
    markup.add(types.InlineKeyboardButton(get_text('back'), callback_data='back_to_main'))
    
    return markup

def create_file_control_keyboard(script_owner_id: int, file_name: str, is_running: bool) -> types.InlineKeyboardMarkup:
    """Create file control keyboard with running status"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if is_running:
        markup.row(
            types.InlineKeyboardButton("🔴 Stop", callback_data=f'stop_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f'restart_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("📜 Logs", callback_data=f'logs_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("📊 Stats", callback_data=f'stats_{script_owner_id}_{file_name}')
        )
    else:
        markup.row(
            types.InlineKeyboardButton("🟢 Start", callback_data=f'start_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("📜 View Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    
    markup.row(
        types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}'),
        types.InlineKeyboardButton("📥 Download", callback_data=f'download_{script_owner_id}_{file_name}')
    )
    
    markup.add(types.InlineKeyboardButton(get_text('back'), callback_data='check_files'))
    
    return markup

def create_analytics_keyboard() -> types.InlineKeyboardMarkup:
    """Create analytics keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(types.InlineKeyboardButton("━" * 8 + " 📊 ANALYTICS " + "━" * 8, callback_data='none'))
    
    markup.row(
        types.InlineKeyboardButton("📈 Daily Stats", callback_data='daily_stats'),
        types.InlineKeyboardButton("📉 Weekly Stats", callback_data='weekly_stats')
    )
    
    markup.row(
        types.InlineKeyboardButton("👥 User Growth", callback_data='user_growth'),
        types.InlineKeyboardButton("📁 File Stats", callback_data='file_stats')
    )
    
    markup.row(
        types.InlineKeyboardButton("🔥 Popular Commands", callback_data='popular_commands'),
        types.InlineKeyboardButton("⏰ Peak Hours", callback_data='peak_hours')
    )
    
    markup.row(
        types.InlineKeyboardButton("💻 System Usage", callback_data='system_usage'),
        types.InlineKeyboardButton("🌐 Network Stats", callback_data='network_stats')
    )
    
    markup.add(types.InlineKeyboardButton(get_text('back'), callback_data='back_to_main'))
    
    return markup

def create_backup_keyboard() -> types.InlineKeyboardMarkup:
    """Create backup management keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(types.InlineKeyboardButton("━" * 8 + " 💾 BACKUP " + "━" * 8, callback_data='none'))
    
    markup.row(
        types.InlineKeyboardButton("📦 Create Backup", callback_data='create_backup'),
        types.InlineKeyboardButton("📂 List Backups", callback_data='list_backups')
    )
    
    markup.row(
        types.InlineKeyboardButton("🔄 Restore Backup", callback_data='restore_backup'),
        types.InlineKeyboardButton("🗑️ Delete Backup", callback_data='delete_backup')
    )
    
    markup.row(
        types.InlineKeyboardButton("⚙️ Auto Backup", callback_data='auto_backup'),
        types.InlineKeyboardButton("📤 Download Backup", callback_data='download_backup')
    )
    
    markup.add(types.InlineKeyboardButton(get_text('back'), callback_data='back_to_main'))
    
    return markup

def create_api_keys_keyboard() -> types.InlineKeyboardMarkup:
    """Create API keys management keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(types.InlineKeyboardButton("━" * 7 + " 🔑 API KEYS " + "━" * 7, callback_data='none'))
    
    markup.row(
        types.InlineKeyboardButton("➕ Generate Key", callback_data='generate_api_key'),
        types.InlineKeyboardButton("📋 List Keys", callback_data='list_api_keys')
    )
    
    markup.row(
        types.InlineKeyboardButton("🗑️ Revoke Key", callback_data='revoke_api_key'),
        types.InlineKeyboardButton("📊 Key Stats", callback_data='api_key_stats')
    )
    
    markup.add(types.InlineKeyboardButton(get_text('back'), callback_data='back_to_main'))
    
    return markup

# ═══════════════════════════════════════════════════════════════
# SCRIPT EXECUTION FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def is_bot_running(script_owner_id: int, file_name: str) -> bool:
    """Check if a bot script is running"""
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    
    if script_info and script_info.process:
        try:
            proc = psutil.Process(script_info.process.pid)
            is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            if not is_running:
                cleanup_script(script_key)
            return is_running
        except psutil.NoSuchProcess:
            cleanup_script(script_key)
            return False
    return False

def cleanup_script(script_key: str):
    """Clean up script resources"""
    if script_key in bot_scripts:
        script_info = bot_scripts[script_key]
        if script_info.log_file and hasattr(script_info.log_file, 'close'):
            try:
                script_info.log_file.close()
            except:
                pass
        del bot_scripts[script_key]

def kill_process_tree(process_info: ScriptInfo):
    """Kill process and all children"""
    try:
        if process_info.log_file and hasattr(process_info.log_file, 'close'):
            try:
                process_info.log_file.close()
            except:
                pass
        
        if process_info.process and hasattr(process_info.process, 'pid'):
            try:
                parent = psutil.Process(process_info.process.pid)
                children = parent.children(recursive=True)
                
                for child in children:
                    try:
                        child.terminate()
                    except:
                        try:
                            child.kill()
                        except:
                            pass
                
                gone, alive = psutil.wait_procs(children, timeout=1)
                for p in alive:
                    try:
                        p.kill()
                    except:
                        pass
                
                try:
                    parent.terminate()
                    parent.wait(timeout=1)
                except:
                    try:
                        parent.kill()
                    except:
                        pass
                        
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        logger.error(f"Error killing process tree: {e}")

# Telegram Modules Mapping
TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI',
    'telegram': 'python-telegram-bot',
    'aiogram': 'aiogram',
    'pyrogram': 'pyrogram',
    'telethon': 'telethon',
    'bs4': 'beautifulsoup4',
    'requests': 'requests',
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv',
    'psutil': 'psutil',
    # Core modules
    'asyncio': None, 'json': None, 'datetime': None,
    'os': None, 'sys': None, 're': None, 'time': None,
    'math': None, 'random': None, 'logging': None,
    'threading': None, 'subprocess': None, 'sqlite3': None,
}

def attempt_install_pip(module_name: str, message, manual_request: bool = False) -> Tuple[bool, str]:
    """Install Python package via pip"""
    package_name = TELEGRAM_MODULES.get(module_name.lower(), module_name)
    
    if package_name is None:
        return False, "Core module - no installation needed"
    
    try:
        if manual_request:
            bot.reply_to(message, f"🔄 Installing `{package_name}`...", parse_mode='Markdown')
        
        command = [sys.executable, '-m', 'pip', 'install', package_name]
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore')
        
        if result.returncode == 0:
            bot.reply_to(message, f"✅ `{package_name}` installed successfully!", parse_mode='Markdown')
            return True, f"Installed {package_name}"
        else:
            error_msg = f"❌ Failed to install `{package_name}`\n```\n{result.stderr[:500]}\n```"
            bot.reply_to(message, error_msg, parse_mode='Markdown')
            return False, result.stderr
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")
        return False, str(e)

def run_script(script_path: str, script_owner_id: int, user_folder: str, file_name: str, message_obj, attempt: int = 1):
    """Run Python script with auto-install support"""
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(message_obj, f"❌ Failed to run '{file_name}' after {max_attempts} attempts.")
        return
    
    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Running Python script: {script_key} (attempt {attempt})")
    
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj, f"❌ Script '{file_name}' not found!")
            remove_user_file_db(script_owner_id, file_name)
            return
        
        # Pre-check for missing modules
        if attempt == 1:
            check_proc = subprocess.Popen(
                [sys.executable, script_path],
                cwd=user_folder,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            try:
                stdout, stderr = check_proc.communicate(timeout=5)
                if check_proc.returncode != 0 and stderr:
                    match = re.search(r"ModuleNotFoundError: No module named '(.+?)'", stderr)
                    if match:
                        module_name = match.group(1).strip()
                        success, _ = attempt_install_pip(module_name, message_obj)
                        if success:
                            bot.reply_to(message_obj, f"🔄 Retrying '{file_name}'...")
                            time.sleep(2)
                            threading.Thread(target=run_script, args=(script_path, script_owner_id, user_folder, file_name, message_obj, attempt + 1)).start()
                            return
                        else:
                            bot.reply_to(message_obj, f"❌ Cannot run '{file_name}' - module install failed.")
                            return
            except subprocess.TimeoutExpired:
                check_proc.kill()
                check_proc.communicate()
        
        # Start long-running process
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        
        startupinfo = None
        creationflags = 0
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        
        process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=user_folder,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.PIPE,
            startupinfo=startupinfo,
            creationflags=creationflags,
            encoding='utf-8',
            errors='ignore'
        )
        
        bot_scripts[script_key] = ScriptInfo(
            script_key=script_key,
            file_name=file_name,
            file_type='py',
            process=process,
            log_file=log_file,
            start_time=datetime.now(),
            user_folder=user_folder,
            script_owner_id=script_owner_id
        )
        
        bot.reply_to(message_obj, f"✅ Python script '{file_name}' started!\n🆔 PID: {process.pid}")
        log_activity(script_owner_id, 'script_start', f"Started {file_name} (PID: {process.pid})")
        
    except Exception as e:
        logger.error(f"Error running script {script_key}: {e}", exc_info=True)
        bot.reply_to(message_obj, f"❌ Error: {str(e)}")

def run_js_script(script_path: str, script_owner_id: int, user_folder: str, file_name: str, message_obj, attempt: int = 1):
    """Run JavaScript/Node.js script"""
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(message_obj, f"❌ Failed to run '{file_name}' after {max_attempts} attempts.")
        return
    
    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Running JS script: {script_key} (attempt {attempt})")
    
    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj, f"❌ Script '{file_name}' not found!")
            remove_user_file_db(script_owner_id, file_name)
            return
        
        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        
        process = subprocess.Popen(
            ['node', script_path],
            cwd=user_folder,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore'
        )
        
        bot_scripts[script_key] = ScriptInfo(
            script_key=script_key,
            file_name=file_name,
            file_type='js',
            process=process,
            log_file=log_file,
            start_time=datetime.now(),
            user_folder=user_folder,
            script_owner_id=script_owner_id
        )
        
        bot.reply_to(message_obj, f"✅ JS script '{file_name}' started!\n🆔 PID: {process.pid}")
        log_activity(script_owner_id, 'script_start', f"Started {file_name} (PID: {process.pid})")
        
    except FileNotFoundError:
        bot.reply_to(message_obj, "❌ Node.js not installed on this system.")
    except Exception as e:
        logger.error(f"Error running JS script {script_key}: {e}", exc_info=True)
        bot.reply_to(message_obj, f"❌ Error: {str(e)}")

# ═══════════════════════════════════════════════════════════════
# DATABASE HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def save_user_file(user_id: int, file_name: str, file_type: str = 'py'):
    """Save user file record"""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type, upload_date) VALUES (?, ?, ?, ?)',
                      (user_id, file_name, file_type, datetime.now().isoformat()))
            conn.commit()
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
            user_files[user_id].append((file_name, file_type))
        except Exception as e:
            logger.error(f"Error saving file: {e}")
        finally:
            conn.close()

def remove_user_file_db(user_id: int, file_name: str):
    """Remove user file record"""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
            conn.commit()
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
        except Exception as e:
            logger.error(f"Error removing file: {e}")
        finally:
            conn.close()

def ban_user_db(user_id: int, reason: str, banned_by: int) -> bool:
    """Ban user in database"""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        try:
            ban_date = datetime.now().isoformat()
            c.execute('INSERT OR REPLACE INTO users (user_id, is_banned, ban_reason, banned_by, ban_date) VALUES (?, 1, ?, ?, ?)',
                      (user_id, reason, banned_by, ban_date))
            conn.commit()
            banned_users.add(user_id)
            if user_id in active_users:
                active_users[user_id].is_banned = True
                active_users[user_id].ban_reason = reason
            return True
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            return False
        finally:
            conn.close()

def unban_user_db(user_id: int) -> bool:
    """Unban user in database"""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        try:
            c.execute('UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?', (user_id,))
            conn.commit()
            banned_users.discard(user_id)
            if user_id in active_users:
                active_users[user_id].is_banned = False
                active_users[user_id].ban_reason = ""
            return True
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            return False
        finally:
            conn.close()

def add_active_user(user_id: int, username: str = "", first_name: str = ""):
    """Add or update active user"""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        try:
            now = datetime.now().isoformat()
            if user_id in active_users:
                c.execute('UPDATE users SET last_seen = ?, username = ?, first_name = ? WHERE user_id = ?',
                          (now, username, first_name, user_id))
                active_users[user_id].last_seen = datetime.now()
                active_users[user_id].username = username
                active_users[user_id].first_name = first_name
            else:
                c.execute('INSERT INTO users (user_id, username, first_name, join_date, last_seen) VALUES (?, ?, ?, ?, ?)',
                          (user_id, username, first_name, now, now))
                active_users[user_id] = UserInfo(
                    user_id=user_id,
                    username=username,
                    first_name=first_name
                )
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding active user: {e}")
        finally:
            conn.close()

def add_admin_db(admin_id: int, role: str, added_by: int) -> bool:
    """Add admin to database"""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO admins (user_id, role, added_by, added_date) VALUES (?, ?, ?, ?)',
                      (admin_id, role, added_by, datetime.now().isoformat()))
            conn.commit()
            admin_ids.add(admin_id)
            admin_roles[admin_id] = AdminRole(role)
            return True
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
            return False
        finally:
            conn.close()

def remove_admin_db(admin_id: int) -> bool:
    """Remove admin from database"""
    if admin_id == OWNER_ID:
        return False
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
            conn.commit()
            admin_ids.discard(admin_id)
            if admin_id in admin_roles:
                del admin_roles[admin_id]
            return True
        except Exception as e:
            logger.error(f"Error removing admin: {e}")
            return False
        finally:
            conn.close()

def save_subscription(user_id: int, tier: str, expiry: datetime):
    """Save subscription to database"""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO subscriptions (user_id, tier, expiry, created) VALUES (?, ?, ?, ?)',
                      (user_id, tier, expiry.isoformat(), datetime.now().isoformat()))
            conn.commit()
            user_subscriptions[user_id] = {'tier': tier, 'expiry': expiry}
        except Exception as e:
            logger.error(f"Error saving subscription: {e}")
        finally:
            conn.close()

def remove_subscription_db(user_id: int):
    """Remove subscription from database"""
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
            conn.commit()
            if user_id in user_subscriptions:
                del user_subscriptions[user_id]
        except Exception as e:
            logger.error(f"Error removing subscription: {e}")
        finally:
            conn.close()

# ═══════════════════════════════════════════════════════════════
# MESSAGE HANDLERS
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Handle /start command"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name or "User"
    username = message.from_user.username or ""
    
    # Check if banned
    if is_user_banned(user_id):
        bot.send_message(chat_id, "🚫 You are banned from using this bot.")
        return
    
    # Check mandatory channels
    is_subscribed, not_joined = check_mandatory_subscription(user_id)
    if not is_subscribed and user_id not in admin_ids:
        subscription_message, markup = create_subscription_check_message(not_joined)
        bot.send_message(chat_id, subscription_message, reply_markup=markup, parse_mode='Markdown')
        return
    
    # Check bot lock
    if bot_locked and user_id not in admin_ids:
        bot.send_message(chat_id, "🔒 Bot is locked. Please try again later.")
        return
    
    # Add/update user
    add_active_user(user_id, username, user_name)
    
    # Notify owner of new user
    if user_id not in active_users or active_users[user_id].join_date > datetime.now() - timedelta(seconds=10):
        try:
            bot.send_message(OWNER_ID, f"🎉 New user!\n👤 {user_name}\n🆔 `{user_id}`\n👤 @{username}", parse_mode='Markdown')
        except:
            pass
    
    # Get user info
    tier = get_user_tier(user_id)
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    lang = active_users.get(user_id, UserInfo(user_id)).language
    
    # Status emoji
    status_emoji = {
        UserTier.OWNER: "👑 Owner",
        UserTier.ADMIN: "🛡️ Admin",
        UserTier.VIP: "💎 VIP",
        UserTier.PREMIUM: "⭐ Premium",
        UserTier.SUBSCRIBED: "🌟 Subscribed",
        UserTier.FREE: "🆓 Free"
    }
    
    # Expiry info
    expiry_info = ""
    if user_id in user_subscriptions:
        expiry = user_subscriptions[user_id].get('expiry')
        if expiry and expiry > datetime.now():
            days_left = (expiry - datetime.now()).days
            expiry_info = f"\n⏳ Expires in: {days_left} days"
    
    limit_str = str(file_limit) if file_limit != float('inf') else "∞"
    
    welcome_msg = f"""
╔══════════════════════════════════════╗
║     🔥 GADGET HOSTING BOT 🔥          ║
╚══════════════════════════════════════╝

👋 Welcome, <b>{user_name}</b>!

🆔 <b>User ID:</b> <code>{user_id}</code>
🔰 <b>Status:</b> {status_emoji.get(tier, "🆓 Free")}{expiry_info}
📁 <b>Files:</b> {current_files}/{limit_str}

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ <b>FEATURES:</b>
┃ • Host Python & JavaScript bots
┃ • Auto-install dependencies
┃ • 24/7 uptime
┃ • Real-time logs
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

👇 <b>Use the buttons below to get started!</b>
"""
    
    markup = create_main_menu_keyboard(user_id)
    bot.send_message(chat_id, welcome_msg, reply_markup=markup, parse_mode='HTML')
    log_activity(user_id, 'start', "Started the bot")

@bot.message_handler(commands=['help'])
def handle_help(message):
    """Handle /help command"""
    user_id = message.from_user.id
    
    if is_user_banned(user_id):
        bot.reply_to(message, "🚫 You are banned.")
        return
    
    help_text = """
╔══════════════════════════════════════╗
║          🆘 HELP CENTER               ║
╚══════════════════════════════════════╝

<b>📌 BASIC COMMANDS:</b>
• /start - Start the bot
• /help - Show this help message
• /status - View bot statistics
• /settings - Your preferences

<b>📁 FILE MANAGEMENT:</b>
• Upload .py or .js files directly
• Upload .zip archives with multiple files
• Auto-installs dependencies

<b>📦 MODULE INSTALLATION:</b>
• Auto-install missing modules
• Manual install via button

<b>💳 SUBSCRIPTION TIERS:</b>
• 🆓 Free - 2 files
• 🌟 Subscribed - 20 files
• ⭐ Premium - 50 files
• 💎 VIP - 100 files

<b>💡 TIPS:</b>
1. Make sure scripts are safe
2. Join required channels
3. Contact owner for upgrades

<b>📞 SUPPORT:</b> @{YOUR_USERNAME}
<b>📢 UPDATES:</b> @{UPDATE_CHANNEL}
"""
    bot.reply_to(message, help_text, parse_mode='HTML')

@bot.message_handler(commands=['status'])
def handle_status(message):
    """Handle /status command"""
    user_id = message.from_user.id
    
    if is_user_banned(user_id):
        bot.reply_to(message, "🚫 You are banned.")
        return
    
    update_system_stats()
    
    total_users = len(active_users)
    total_files = sum(len(files) for files in user_files.values())
    running_bots = sum(1 for s in bot_scripts.values() if is_bot_running(s.script_owner_id, s.file_name))
    uptime = str(timedelta(seconds=int(system_stats.uptime)))
    
    status_msg = f"""
╔══════════════════════════════════════╗
║         📊 BOT STATUS                 ║
╚══════════════════════════════════════╝

👥 <b>Total Users:</b> {total_users}
🚫 <b>Banned Users:</b> {len(banned_users)}
📁 <b>Total Files:</b> {total_files}
🟢 <b>Running Bots:</b> {running_bots}

<b>💻 SYSTEM:</b>
⚡ CPU: {system_stats.cpu_percent}%
💾 RAM: {system_stats.memory_percent}%
💿 Disk: {system_stats.disk_percent}%
⏱️ Uptime: {uptime}

🔒 <b>Status:</b> {'🔴 Locked' if bot_locked else '🟢 Active'}
"""
    bot.reply_to(message, status_msg, parse_mode='HTML')

@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Handle file uploads"""
    user_id = message.from_user.id
    
    # Checks
    if is_user_banned(user_id):
        bot.reply_to(message, "🚫 You are banned.")
        return
    
    is_subscribed, not_joined = check_mandatory_subscription(user_id)
    if not is_subscribed and user_id not in admin_ids:
        subscription_message, markup = create_subscription_check_message(not_joined)
        bot.reply_to(message, subscription_message, reply_markup=markup, parse_mode='Markdown')
        return
    
    if bot_locked and user_id not in admin_ids:
        bot.reply_to(message, "🔒 Bot is locked.")
        return
    
    # Check rate limit
    allowed, remaining = check_rate_limit(user_id)
    if not allowed:
        bot.reply_to(message, "⚠️ Rate limit exceeded. Please wait.")
        return
    
    # Check file limit
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    if current_files >= file_limit:
        bot.reply_to(message, f"⚠️ File limit reached: {current_files}/{file_limit}")
        return
    
    # Process file
    file_info = message.document
    file_name = file_info.file_name
    file_size = file_info.file_size
    
    if file_size > SECURITY_CONFIG['max_file_size']:
        bot.reply_to(message, "❌ File too large. Max 20MB.")
        return
    
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in SECURITY_CONFIG['allowed_extensions']:
        bot.reply_to(message, f"❌ Invalid file type. Allowed: {', '.join(SECURITY_CONFIG['allowed_extensions'])}")
        return
    
    # Download file
    status_msg = bot.reply_to(message, f"📥 Downloading `{file_name}`...", parse_mode='Markdown')
    
    try:
        file_info_obj = bot.get_file(file_info.file_id)
        downloaded_file = bot.download_file(file_info_obj.file_path)
        
        user_folder = get_user_folder(user_id)
        
        if file_ext == '.zip':
            # Handle ZIP
            handle_zip_file(downloaded_file, file_name, message, user_id, user_folder)
        elif file_ext == '.py':
            # Handle Python
            file_path = os.path.join(user_folder, file_name)
            with open(file_path, 'wb') as f:
                f.write(downloaded_file)
            
            # Security check
            is_safe, sec_msg = check_code_security(file_path, 'py')
            if not is_safe:
                bot.reply_to(message, f"⚠️ Security issue: {sec_msg}\nFile needs admin approval.")
                # Request admin approval
                request_admin_approval(user_id, file_name, downloaded_file, 'py')
            else:
                save_user_file(user_id, file_name, 'py')
                bot.reply_to(message, f"✅ File uploaded. Starting `{file_name}`...", parse_mode='Markdown')
                threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, message)).start()
                
        elif file_ext == '.js':
            # Handle JavaScript
            file_path = os.path.join(user_folder, file_name)
            with open(file_path, 'wb') as f:
                f.write(downloaded_file)
            
            save_user_file(user_id, file_name, 'js')
            bot.reply_to(message, f"✅ File uploaded. Starting `{file_name}`...", parse_mode='Markdown')
            threading.Thread(target=run_js_script, args=(file_path, user_id, user_folder, file_name, message)).start()
        
        log_activity(user_id, 'file_upload', f"Uploaded {file_name}")
        bot.delete_message(message.chat.id, status_msg.message_id)
        
    except Exception as e:
        logger.error(f"Error handling document: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error: {str(e)}")

def handle_zip_file(file_content: bytes, file_name: str, message, user_id: int, user_folder: str):
    """Handle ZIP file extraction"""
    temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_")
    try:
        zip_path = os.path.join(temp_dir, file_name)
        with open(zip_path, 'wb') as f:
            f.write(file_content)
        
        # Security check
        is_safe, sec_msg = scan_zip_security(zip_path)
        if not is_safe:
            bot.reply_to(message, f"⚠️ Security issue: {sec_msg}\nFile needs admin approval.")
            request_admin_approval(user_id, file_name, file_content, 'zip')
            return
        
        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find main script
        py_files = [f for f in os.listdir(temp_dir) if f.endswith('.py')]
        js_files = [f for f in os.listdir(temp_dir) if f.endswith('.js')]
        
        main_script = None
        file_type = None
        for preferred in ['main.py', 'bot.py', 'app.py']:
            if preferred in py_files:
                main_script = preferred
                file_type = 'py'
                break
        if not main_script and py_files:
            main_script = py_files[0]
            file_type = 'py'
        elif js_files:
            main_script = js_files[0]
            file_type = 'js'
        
        if not main_script:
            bot.reply_to(message, "❌ No valid script found in archive.")
            return
        
        # Install requirements if exists
        req_file = os.path.join(temp_dir, 'requirements.txt')
        if os.path.exists(req_file):
            bot.reply_to(message, "📦 Installing requirements...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', req_file], capture_output=True)
        
        # Move files to user folder
        for item in os.listdir(temp_dir):
            src = os.path.join(temp_dir, item)
            dst = os.path.join(user_folder, item)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            elif os.path.exists(dst):
                os.remove(dst)
            shutil.move(src, dst)
        
        save_user_file(user_id, main_script, file_type)
        
        script_path = os.path.join(user_folder, main_script)
        bot.reply_to(message, f"✅ Extracted. Starting `{main_script}`...", parse_mode='Markdown')
        
        if file_type == 'py':
            threading.Thread(target=run_script, args=(script_path, user_id, user_folder, main_script, message)).start()
        else:
            threading.Thread(target=run_js_script, args=(script_path, user_id, user_folder, main_script, message)).start()
            
    except Exception as e:
        logger.error(f"Error handling ZIP: {e}", exc_info=True)
        bot.reply_to(message, f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def request_admin_approval(user_id: int, file_name: str, file_content: bytes, file_type: str):
    """Request admin approval for suspicious file"""
    if user_id not in pending_zip_files:
        pending_zip_files[user_id] = {}
    pending_zip_files[user_id][file_name] = file_content
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}_{file_name}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}_{file_name}")
    )
    
    for admin_id in admin_ids:
        try:
            bot.send_message(admin_id, f"🚨 <b>File Approval Required</b>\n\n👤 User: {user_id}\n📁 File: {file_name}\n📄 Type: {file_type}", reply_markup=markup, parse_mode='HTML')
        except:
            pass

def check_mandatory_subscription(user_id: int) -> Tuple[bool, List]:
    """Check if user is subscribed to mandatory channels"""
    if not mandatory_channels:
        return True, []
    
    not_joined = []
    for channel_id, channel_info in mandatory_channels.items():
        if not is_user_member(user_id, channel_id):
            not_joined.append((channel_id, channel_info))
    
    return len(not_joined) == 0, not_joined

def is_user_member(user_id: int, channel_id: str) -> bool:
    """Check if user is member of channel"""
    try:
        member = bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def create_subscription_check_message(not_joined_channels: List) -> Tuple[str, types.InlineKeyboardMarkup]:
    """Create subscription check message"""
    message = "📢 <b>Join Required Channels First:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for channel_id, channel_info in not_joined_channels:
        username = channel_info.get('username', '')
        name = channel_info.get('name', 'Channel')
        
        link = f"https://t.me/{username.replace('@', '')}" if username else f"https://t.me/c/{channel_id.replace('-100', '')}"
        message += f"• {name}\n"
        markup.add(types.InlineKeyboardButton(f"Join {name}", url=link))
    
    markup.add(types.InlineKeyboardButton("✅ Verify Subscription", callback_data='check_subscription'))
    
    return message, markup

# ═══════════════════════════════════════════════════════════════
# CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Handle all callback queries"""
    user_id = call.from_user.id
    data = call.data
    
    # Banned check
    if is_user_banned(user_id) and data not in ['check_subscription']:
        bot.answer_callback_query(call.id, "🚫 You are banned.")
        return
    
    # Parse callback data
    if data == 'none':
        bot.answer_callback_query(call.id)
        return
    
    elif data == 'back_to_main':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        handle_start(call.message)
    
    elif data == 'upload':
        bot.answer_callback_query(call.id)
        file_limit = get_user_file_limit(user_id)
        current = get_user_file_count(user_id)
        bot.send_message(call.message.chat.id, f"📤 Send your file\n\n📁 Current: {current}/{file_limit}")
    
    elif data == 'check_files':
        bot.answer_callback_query(call.id)
        show_user_files(call.message, user_id)
    
    elif data == 'speed':
        bot.answer_callback_query(call.id)
        show_speed_test(call.message, user_id)
    
    elif data == 'stats':
        bot.answer_callback_query(call.id)
        handle_status(call.message)
    
    elif data == 'admin_panel':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            show_admin_panel(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'user_management':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            show_user_management(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'subscriptions':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            show_subscription_panel(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'broadcast':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            init_broadcast(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'toggle_lock':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            toggle_bot_lock(call.message, user_id)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'run_all':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            run_all_scripts(call.message, user_id)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'admin_settings':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            show_admin_settings(call.message, user_id)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'analytics':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            show_analytics(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'backup':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            show_backup_panel(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'api_keys':
        if has_permission(user_id, AdminRole.SUPER_ADMIN):
            bot.answer_callback_query(call.id)
            show_api_keys_panel(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'health_check':
        if has_permission(user_id, AdminRole.SUPER_ADMIN):
            bot.answer_callback_query(call.id)
            show_health_check(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'system_info':
        bot.answer_callback_query(call.id)
        show_system_info(call.message)
    
    elif data == 'performance':
        bot.answer_callback_query(call.id)
        show_performance(call.message)
    
    elif data == 'cleanup':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            perform_cleanup(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'create_backup':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id, "Creating backup...")
            create_backup(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'manual_install':
        bot.answer_callback_query(call.id)
        init_manual_install(call.message)
    
    elif data == 'help':
        bot.answer_callback_query(call.id)
        handle_help(call.message)
    
    elif data == 'check_subscription':
        bot.answer_callback_query(call.id)
        is_subscribed, not_joined = check_mandatory_subscription(user_id)
        if is_subscribed:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            handle_start(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Please join all required channels")
    
    # File actions
    elif data.startswith('start_'):
        parts = data.split('_', 2)
        if len(parts) == 3:
            owner_id = int(parts[1])
            file_name = parts[2]
            start_script(call.message, owner_id, file_name, user_id)
    
    elif data.startswith('stop_'):
        parts = data.split('_', 2)
        if len(parts) == 3:
            owner_id = int(parts[1])
            file_name = parts[2]
            stop_script(call.message, owner_id, file_name, user_id)
    
    elif data.startswith('restart_'):
        parts = data.split('_', 2)
        if len(parts) == 3:
            owner_id = int(parts[1])
            file_name = parts[2]
            restart_script(call.message, owner_id, file_name, user_id)
    
    elif data.startswith('delete_'):
        parts = data.split('_', 2)
        if len(parts) == 3:
            owner_id = int(parts[1])
            file_name = parts[2]
            delete_script(call.message, owner_id, file_name, user_id)
    
    elif data.startswith('logs_'):
        parts = data.split('_', 2)
        if len(parts) == 3:
            owner_id = int(parts[1])
            file_name = parts[2]
            show_logs(call.message, owner_id, file_name, user_id)
    
    elif data.startswith('file_'):
        parts = data.split('_', 2)
        if len(parts) == 3:
            owner_id = int(parts[1])
            file_name = parts[2]
            show_file_details(call.message, owner_id, file_name, user_id)
    
    # Admin actions
    elif data == 'add_admin':
        if has_permission(user_id, AdminRole.SUPER_ADMIN):
            bot.answer_callback_query(call.id)
            init_add_admin(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'remove_admin':
        if has_permission(user_id, AdminRole.SUPER_ADMIN):
            bot.answer_callback_query(call.id)
            init_remove_admin(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'list_admins':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            list_admins(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'ban_user':
        if has_permission(user_id, AdminRole.MODERATOR):
            bot.answer_callback_query(call.id)
            init_ban_user(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'unban_user':
        if has_permission(user_id, AdminRole.MODERATOR):
            bot.answer_callback_query(call.id)
            init_unban_user(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'user_info':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            init_user_info(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'all_users':
        if user_id in admin_ids:
            bot.answer_callback_query(call.id)
            list_all_users(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'set_limit':
        if has_permission(user_id, AdminRole.ADMIN):
            bot.answer_callback_query(call.id)
            init_set_limit(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data == 'add_subscription':
        if has_permission(user_id, AdminRole.ADMIN):
            bot.answer_callback_query(call.id)
            init_add_subscription(call.message)
        else:
            bot.answer_callback_query(call.id, "⚠️ Not authorized")
    
    elif data.startswith('approve_'):
        parts = data.split('_', 2)
        if len(parts) == 3 and user_id in admin_ids:
            target_user = int(parts[1])
            file_name = parts[2]
            approve_file(call.message, target_user, file_name)
    
    elif data.startswith('reject_'):
        parts = data.split('_', 2)
        if len(parts) == 3 and user_id in admin_ids:
            target_user = int(parts[1])
            file_name = parts[2]
            reject_file(call.message, target_user, file_name)

# ═══════════════════════════════════════════════════════════════
# ACTION FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def show_user_files(message, user_id: int):
    """Show user's files"""
    files = user_files.get(user_id, [])
    
    if not files:
        bot.send_message(message.chat.id, "📂 <b>Your Files:</b>\n\n<i>No files uploaded yet.</i>", parse_mode='HTML')
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in sorted(files):
        is_running = is_bot_running(user_id, file_name)
        status = "🟢" if is_running else "🔴"
        markup.add(types.InlineKeyboardButton(f"{status} {file_name} ({file_type})", callback_data=f'file_{user_id}_{file_name}'))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main'))
    bot.send_message(message.chat.id, f"📂 <b>Your Files:</b> ({len(files)})", reply_markup=markup, parse_mode='HTML')

def show_file_details(message, owner_id: int, file_name: str, requester_id: int):
    """Show file details and controls"""
    if owner_id != requester_id and requester_id not in admin_ids:
        bot.answer_callback_query(message.id, "⚠️ Not authorized")
        return
    
    is_running = is_bot_running(owner_id, file_name)
    status = "🟢 Running" if is_running else "🔴 Stopped"
    file_type = "Python" if file_name.endswith('.py') else "JavaScript"
    
    script_key = f"{owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    
    uptime = ""
    if script_info and is_running:
        uptime_seconds = (datetime.now() - script_info.start_time).total_seconds()
        uptime = f"\n⏱️ Uptime: {str(timedelta(seconds=int(uptime_seconds)))}"
    
    details = f"""
📄 <b>File Details</b>

📁 <b>Name:</b> {file_name}
📝 <b>Type:</b> {file_type}
📊 <b>Status:</b> {status}{uptime}
"""
    
    markup = create_file_control_keyboard(owner_id, file_name, is_running)
    bot.edit_message_text(details, message.chat.id, message.message_id, reply_markup=markup, parse_mode='HTML')

def show_speed_test(message, user_id: int):
    """Show speed test results"""
    start = time.time()
    wait = bot.send_message(message.chat.id, "🏃 Testing...")
    
    time.sleep(0.5)
    
    response_time = round((time.time() - start) * 1000, 2)
    tier = get_user_tier(user_id)
    
    status_emoji = {
        UserTier.OWNER: "👑 Owner",
        UserTier.ADMIN: "🛡️ Admin",
        UserTier.VIP: "💎 VIP",
        UserTier.PREMIUM: "⭐ Premium",
        UserTier.SUBSCRIBED: "🌟 Subscribed",
        UserTier.FREE: "🆓 Free"
    }
    
    speed_msg = f"""
⚡ <b>Speed Test Results</b>

⏱️ <b>Response Time:</b> {response_time} ms
🚦 <b>Bot Status:</b> {'🔴 Locked' if bot_locked else '🟢 Active'}
👤 <b>Your Level:</b> {status_emoji.get(tier, 'Free')}
"""
    
    bot.edit_message_text(speed_msg, message.chat.id, wait.message_id, parse_mode='HTML')

def show_admin_panel(message):
    """Show admin panel"""
    admin_count = len(admin_ids)
    user_count = len(active_users)
    running = sum(1 for s in bot_scripts.values() if is_bot_running(s.script_owner_id, s.file_name))
    
    panel_msg = f"""
👑 <b>Admin Panel</b>

👥 <b>Total Users:</b> {user_count}
🛡️ <b>Total Admins:</b> {admin_count}
🟢 <b>Running Bots:</b> {running}
🔒 <b>Bot Status:</b> {'Locked' if bot_locked else 'Unlocked'}
"""
    
    markup = create_admin_dashboard()
    bot.send_message(message.chat.id, panel_msg, reply_markup=markup, parse_mode='HTML')

def show_user_management(message):
    """Show user management panel"""
    markup = create_user_management_keyboard()
    bot.send_message(message.chat.id, "👥 <b>User Management</b>", reply_markup=markup, parse_mode='HTML')

def show_subscription_panel(message):
    """Show subscription management panel"""
    markup = create_subscription_keyboard()
    bot.send_message(message.chat.id, "💳 <b>Subscription Management</b>", reply_markup=markup, parse_mode='HTML')

def show_admin_settings(message, user_id: int):
    """Show admin settings"""
    markup = create_settings_keyboard(user_id)
    bot.send_message(message.chat.id, "⚙️ <b>Settings</b>", reply_markup=markup, parse_mode='HTML')

def show_analytics(message):
    """Show analytics panel"""
    markup = create_analytics_keyboard()
    bot.send_message(message.chat.id, "📊 <b>Analytics Dashboard</b>", reply_markup=markup, parse_mode='HTML')

def show_backup_panel(message):
    """Show backup panel"""
    markup = create_backup_keyboard()
    bot.send_message(message.chat.id, "💾 <b>Backup Management</b>", reply_markup=markup, parse_mode='HTML')

def show_api_keys_panel(message):
    """Show API keys panel"""
    markup = create_api_keys_keyboard()
    bot.send_message(message.chat.id, "🔑 <b>API Keys Management</b>", reply_markup=markup, parse_mode='HTML')

def show_health_check(message):
    """Show health check results"""
    update_system_stats()
    
    issues = []
    if system_stats.cpu_percent > 80:
        issues.append("⚠️ High CPU usage")
    if system_stats.memory_percent > 80:
        issues.append("⚠️ High memory usage")
    if system_stats.disk_percent > 90:
        issues.append("⚠️ Low disk space")
    
    status = "✅ Healthy" if not issues else "⚠️ Issues Found"
    
    health_msg = f"""
🏥 <b>Health Check</b>

📊 <b>Status:</b> {status}

💻 <b>System Metrics:</b>
• CPU: {system_stats.cpu_percent}%
• Memory: {system_stats.memory_percent}%
• Disk: {system_stats.disk_percent}%
• Processes: {system_stats.total_processes}

{''.join(chr(10) + i for i in issues) if issues else ''}
"""
    
    bot.send_message(message.chat.id, health_msg, parse_mode='HTML')

def show_system_info(message):
    """Show system information"""
    update_system_stats()
    
    info_msg = f"""
💻 <b>System Information</b>

🖥️ <b>Platform:</b> {sys.platform}
🐍 <b>Python:</b> {sys.version.split()[0]}

📊 <b>Resources:</b>
• CPU: {system_stats.cpu_percent}%
• Memory: {system_stats.memory_percent}%
• Disk: {system_stats.disk_percent}%

⏱️ <b>Uptime:</b> {str(timedelta(seconds=int(system_stats.uptime)))}
"""
    
    bot.send_message(message.chat.id, info_msg, parse_mode='HTML')

def show_performance(message):
    """Show performance metrics"""
    update_system_stats()
    
    running = sum(1 for s in bot_scripts.values() if is_bot_running(s.script_owner_id, s.file_name))
    
    perf_msg = f"""
📈 <b>Performance Metrics</b>

🟢 <b>Running Scripts:</b> {running}
👥 <b>Active Users:</b> {len(active_users)}
📁 <b>Total Files:</b> {sum(len(f) for f in user_files.values())}

💻 <b>System Load:</b>
• CPU: {system_stats.cpu_percent}%
• Memory: {system_stats.memory_percent}%

🌐 <b>Network:</b>
• Sent: {system_stats.network_sent / 1024 / 1024:.2f} MB
• Received: {system_stats.network_recv / 1024 / 1024:.2f} MB
"""
    
    bot.send_message(message.chat.id, perf_msg, parse_mode='HTML')

def perform_cleanup(message):
    """Perform system cleanup"""
    cleaned = 0
    
    # Clean temp directories
    temp_dir = tempfile.gettempdir()
    for item in os.listdir(temp_dir):
        if item.startswith('user_') and '_zip_' in item:
            try:
                shutil.rmtree(os.path.join(temp_dir, item))
                cleaned += 1
            except:
                pass
    
    # Clean old logs
    logs_dir = LOGS_DIR
    for log_file in os.listdir(logs_dir):
        if log_file.endswith('.log'):
            file_path = os.path.join(logs_dir, log_file)
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            if (datetime.now() - file_time).days > 7:
                try:
                    os.remove(file_path)
                    cleaned += 1
                except:
                    pass
    
    bot.send_message(message.chat.id, f"🧹 <b>Cleanup Complete</b>\n\n✅ Cleaned {cleaned} items", parse_mode='HTML')

def create_backup(message):
    """Create database backup"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")
    
    try:
        shutil.copy(DATABASE_PATH, backup_file)
        bot.send_message(message.chat.id, f"✅ <b>Backup Created</b>\n\n📁 File: backup_{timestamp}.db", parse_mode='HTML')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ <b>Backup Failed</b>\n\n{str(e)}", parse_mode='HTML')

def toggle_bot_lock(message, user_id: int):
    """Toggle bot lock status"""
    global bot_locked
    bot_locked = not bot_locked
    status = "locked" if bot_locked else "unlocked"
    bot.send_message(message.chat.id, f"🔒 Bot has been <b>{status}</b>", parse_mode='HTML')
    logger.warning(f"Bot {status} by admin {user_id}")

def run_all_scripts(message, admin_id: int):
    """Run all user scripts"""
    bot.send_message(message.chat.id, "⏳ Starting all user scripts...")
    
    started = 0
    for user_id, files in user_files.items():
        user_folder = get_user_folder(user_id)
        for file_name, file_type in files:
            if not is_bot_running(user_id, file_name):
                file_path = os.path.join(user_folder, file_name)
                if os.path.exists(file_path):
                    if file_type == 'py':
                        threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, message)).start()
                    else:
                        threading.Thread(target=run_js_script, args=(file_path, user_id, user_folder, file_name, message)).start()
                    started += 1
                    time.sleep(0.5)
    
    bot.send_message(message.chat.id, f"✅ <b>Started {started} scripts</b>", parse_mode='HTML')

def start_script(message, owner_id: int, file_name: str, requester_id: int):
    """Start a script"""
    if owner_id != requester_id and requester_id not in admin_ids:
        bot.answer_callback_query(message.id, "⚠️ Not authorized")
        return
    
    if is_bot_running(owner_id, file_name):
        bot.answer_callback_query(message.id, "⚠️ Already running")
        return
    
    user_folder = get_user_folder(owner_id)
    file_path = os.path.join(user_folder, file_name)
    
    if not os.path.exists(file_path):
        bot.answer_callback_query(message.id, "❌ File not found")
        return
    
    file_type = 'py' if file_name.endswith('.py') else 'js'
    if file_type == 'py':
        threading.Thread(target=run_script, args=(file_path, owner_id, user_folder, file_name, message)).start()
    else:
        threading.Thread(target=run_js_script, args=(file_path, owner_id, user_folder, file_name, message)).start()
    
    bot.answer_callback_query(message.id, f"✅ Starting {file_name}")

def stop_script(message, owner_id: int, file_name: str, requester_id: int):
    """Stop a script"""
    if owner_id != requester_id and requester_id not in admin_ids:
        bot.answer_callback_query(message.id, "⚠️ Not authorized")
        return
    
    script_key = f"{owner_id}_{file_name}"
    if script_key in bot_scripts:
        kill_process_tree(bot_scripts[script_key])
        cleanup_script(script_key)
        bot.answer_callback_query(message.id, f"✅ Stopped {file_name}")
        show_file_details(message, owner_id, file_name, requester_id)
    else:
        bot.answer_callback_query(message.id, "⚠️ Not running")

def restart_script(message, owner_id: int, file_name: str, requester_id: int):
    """Restart a script"""
    if owner_id != requester_id and requester_id not in admin_ids:
        bot.answer_callback_query(message.id, "⚠️ Not authorized")
        return
    
    script_key = f"{owner_id}_{file_name}"
    if script_key in bot_scripts:
        kill_process_tree(bot_scripts[script_key])
        cleanup_script(script_key)
    
    user_folder = get_user_folder(owner_id)
    file_path = os.path.join(user_folder, file_name)
    
    file_type = 'py' if file_name.endswith('.py') else 'js'
    time.sleep(1)
    
    if file_type == 'py':
        threading.Thread(target=run_script, args=(file_path, owner_id, user_folder, file_name, message)).start()
    else:
        threading.Thread(target=run_js_script, args=(file_path, owner_id, user_folder, file_name, message)).start()
    
    bot.answer_callback_query(message.id, f"🔄 Restarting {file_name}")

def delete_script(message, owner_id: int, file_name: str, requester_id: int):
    """Delete a script"""
    if owner_id != requester_id and requester_id not in admin_ids:
        bot.answer_callback_query(message.id, "⚠️ Not authorized")
        return
    
    # Stop if running
    script_key = f"{owner_id}_{file_name}"
    if script_key in bot_scripts:
        kill_process_tree(bot_scripts[script_key])
        cleanup_script(script_key)
    
    # Delete file
    user_folder = get_user_folder(owner_id)
    file_path = os.path.join(user_folder, file_name)
    
    if os.path.exists(file_path):
        os.remove(file_path)
    
    remove_user_file_db(owner_id, file_name)
    bot.answer_callback_query(message.id, f"🗑️ Deleted {file_name}")
    show_user_files(message, requester_id)

def show_logs(message, owner_id: int, file_name: str, requester_id: int):
    """Show script logs"""
    if owner_id != requester_id and requester_id not in admin_ids:
        bot.answer_callback_query(message.id, "⚠️ Not authorized")
        return
    
    user_folder = get_user_folder(owner_id)
    log_file = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
    
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            logs = f.read()[-4000:]  # Last 4000 chars
        
        bot.send_message(message.chat.id, f"📜 <b>Logs for {file_name}:</b>\n\n<code>{logs}</code>", parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, "📜 No logs found.")

def init_broadcast(message):
    """Initialize broadcast"""
    msg = bot.send_message(message.chat.id, "📢 Send the message to broadcast:\n/cancel to abort")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    """Process broadcast message"""
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Broadcast cancelled")
        return
    
    admin_id = message.from_user.id
    broadcast_text = message.text
    
    sent = 0
    failed = 0
    
    status_msg = bot.send_message(message.chat.id, "📢 Broadcasting...")
    
    for user_id in list(active_users.keys()):
        try:
            bot.send_message(user_id, f"📢 <b>Broadcast:</b>\n\n{broadcast_text}", parse_mode='HTML')
            sent += 1
        except:
            failed += 1
        time.sleep(0.1)
    
    bot.edit_message_text(f"✅ <b>Broadcast Complete</b>\n\n📤 Sent: {sent}\n❌ Failed: {failed}", status_msg.chat.id, status_msg.message_id, parse_mode='HTML')

def init_manual_install(message):
    """Initialize manual module install"""
    msg = bot.send_message(message.chat.id, "📦 Send module name to install:\n/cancel to abort")
    bot.register_next_step_handler(msg, process_manual_install)

def process_manual_install(message):
    """Process manual install"""
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Installation cancelled")
        return
    
    module_name = message.text.strip()
    attempt_install_pip(module_name, message, manual_request=True)

def init_add_admin(message):
    """Initialize add admin"""
    msg = bot.send_message(message.chat.id, "➕ Send user ID to add as admin:\n/cancel to abort")
    bot.register_next_step_handler(msg, process_add_admin)

def process_add_admin(message):
    """Process add admin"""
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Cancelled")
        return
    
    try:
        admin_id = int(message.text.strip())
        if add_admin_db(admin_id, 'admin', message.from_user.id):
            bot.send_message(message.chat.id, f"✅ Added `{admin_id}` as admin", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "❌ Failed to add admin")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID")

def init_remove_admin(message):
    """Initialize remove admin"""
    msg = bot.send_message(message.chat.id, "➖ Send user ID to remove from admins:\n/cancel to abort")
    bot.register_next_step_handler(msg, process_remove_admin)

def process_remove_admin(message):
    """Process remove admin"""
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Cancelled")
        return
    
    try:
        admin_id = int(message.text.strip())
        if remove_admin_db(admin_id):
            bot.send_message(message.chat.id, f"✅ Removed `{admin_id}` from admins", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "❌ Cannot remove this admin")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID")

def list_admins(message):
    """List all admins"""
    admin_list = []
    for admin_id in admin_ids:
        role = admin_roles.get(admin_id, AdminRole.ADMIN)
        role_emoji = {
            AdminRole.OWNER: "👑",
            AdminRole.SUPER_ADMIN: "⭐",
            AdminRole.ADMIN: "🛡️",
            AdminRole.MODERATOR: "👮"
        }
        admin_list.append(f"{role_emoji.get(role, '🛡️')} `{admin_id}` - {role.value}")
    
    bot.send_message(message.chat.id, "📋 <b>Admin List:</b>\n\n" + "\n".join(admin_list), parse_mode='HTML')

def init_ban_user(message):
    """Initialize ban user"""
    msg = bot.send_message(message.chat.id, "🚫 Send user ID and reason:\nFormat: `user_id reason`\n/cancel to abort", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_ban_user)

def process_ban_user(message):
    """Process ban user"""
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Cancelled")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Format: `user_id reason`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(parts[0])
        reason = parts[1]
        
        if ban_user_db(user_id, reason, message.from_user.id):
            bot.send_message(message.chat.id, f"✅ Banned `{user_id}`\nReason: {reason}", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "❌ Failed to ban user")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID")

def init_unban_user(message):
    """Initialize unban user"""
    msg = bot.send_message(message.chat.id, "✅ Send user ID to unban:\n/cancel to abort")
    bot.register_next_step_handler(msg, process_unban_user)

def process_unban_user(message):
    """Process unban user"""
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Cancelled")
        return
    
    try:
        user_id = int(message.text.strip())
        if unban_user_db(user_id):
            bot.send_message(message.chat.id, f"✅ Unbanned `{user_id}`", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "❌ Failed to unban user")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID")

def init_user_info(message):
    """Initialize user info lookup"""
    msg = bot.send_message(message.chat.id, "📊 Send user ID to view info:\n/cancel to abort")
    bot.register_next_step_handler(msg, process_user_info)

def process_user_info(message):
    """Process user info lookup"""
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Cancelled")
        return
    
    try:
        user_id = int(message.text.strip())
        user = active_users.get(user_id)
        
        if user:
            tier = get_user_tier(user_id)
            files = get_user_file_count(user_id)
            limit = get_user_file_limit(user_id)
            
            info = f"""
📊 <b>User Information</b>

🆔 <b>User ID:</b> <code>{user_id}</code>
👤 <b>Name:</b> {user.first_name}
📝 <b>Username:</b> @{user.username or 'N/A'}
🔰 <b>Tier:</b> {tier.value}
📁 <b>Files:</b> {files}/{limit}
📅 <b>Joined:</b> {user.join_date.strftime('%Y-%m-%d')}
⏰ <b>Last Seen:</b> {user.last_seen.strftime('%Y-%m-%d %H:%M')}
🚫 <b>Banned:</b> {'Yes' if user.is_banned else 'No'}
"""
            if user.is_banned:
                info += f"\n📝 <b>Ban Reason:</b> {user.ban_reason}"
            
            bot.send_message(message.chat.id, info, parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "❌ User not found")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid user ID")

def list_all_users(message):
    """List all users with pagination"""
    users = list(active_users.values())
    total = len(users)
    
    msg = f"👥 <b>All Users</b> ({total})\n\n"
    
    for i, user in enumerate(users[:20]):  # Show first 20
        tier = get_user_tier(user.user_id)
        msg += f"{i+1}. `{user.user_id}` - {user.first_name} ({tier.value})\n"
    
    if total > 20:
        msg += f"\n... and {total - 20} more users"
    
    bot.send_message(message.chat.id, msg, parse_mode='HTML')

def init_set_limit(message):
    """Initialize set limit"""
    msg = bot.send_message(message.chat.id, "🔧 Send user ID and limit:\nFormat: `user_id limit`\n/cancel to abort", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_set_limit)

def process_set_limit(message):
    """Process set limit"""
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Cancelled")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ Format: `user_id limit`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(parts[0])
        limit = int(parts[1])
        
        user_limits[user_id] = limit
        
        with DB_LOCK:
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO user_limits (user_id, file_limit, set_by, set_date) VALUES (?, ?, ?, ?)',
                      (user_id, limit, message.from_user.id, datetime.now().isoformat()))
            conn.commit()
            conn.close()
        
        bot.send_message(message.chat.id, f"✅ Set limit for `{user_id}` to {limit}", parse_mode='Markdown')
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid values")

def init_add_subscription(message):
    """Initialize add subscription"""
    msg = bot.send_message(message.chat.id, "💳 Send subscription details:\nFormat: `user_id tier days`\nTiers: subscribed, premium, vip\n/cancel to abort", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_add_subscription)

def process_add_subscription(message):
    """Process add subscription"""
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Cancelled")
        return
    
    parts = message.text.split()
    if len(parts) != 3:
        bot.send_message(message.chat.id, "❌ Format: `user_id tier days`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(parts[0])
        tier = parts[1].lower()
        days = int(parts[2])
        
        if tier not in ['subscribed', 'premium', 'vip']:
            bot.send_message(message.chat.id, "❌ Invalid tier. Use: subscribed, premium, vip")
            return
        
        expiry = datetime.now() + timedelta(days=days)
        save_subscription(user_id, tier, expiry)
        
        bot.send_message(message.chat.id, f"✅ Added {tier} subscription for `{user_id}` ({days} days)", parse_mode='Markdown')
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid values")

def approve_file(message, user_id: int, file_name: str):
    """Approve pending file"""
    if user_id in pending_zip_files and file_name in pending_zip_files[user_id]:
        file_content = pending_zip_files[user_id][file_name]
        user_folder = get_user_folder(user_id)
        
        del pending_zip_files[user_id][file_name]
        
        try:
            bot.send_message(user_id, f"✅ Your file `{file_name}` has been approved!", parse_mode='Markdown')
        except:
            pass
        
        if file_name.endswith('.zip'):
            handle_zip_file(file_content, file_name, message, user_id, user_folder)
        else:
            file_path = os.path.join(user_folder, file_name)
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            file_type = 'py' if file_name.endswith('.py') else 'js'
            save_user_file(user_id, file_name, file_type)
            
            if file_type == 'py':
                threading.Thread(target=run_script, args=(file_path, user_id, user_folder, file_name, message)).start()
            else:
                threading.Thread(target=run_js_script, args=(file_path, user_id, user_folder, file_name, message)).start()
        
        bot.edit_message_text(f"✅ Approved `{file_name}` for user {user_id}", message.chat.id, message.message_id, parse_mode='Markdown')

def reject_file(message, user_id: int, file_name: str):
    """Reject pending file"""
    if user_id in pending_zip_files and file_name in pending_zip_files[user_id]:
        del pending_zip_files[user_id][file_name]
        
        try:
            bot.send_message(user_id, f"❌ Your file `{file_name}` was rejected.", parse_mode='Markdown')
        except:
            pass
        
        bot.edit_message_text(f"❌ Rejected `{file_name}` for user {user_id}", message.chat.id, message.message_id, parse_mode='Markdown')

# ═══════════════════════════════════════════════════════════════
# FLASK KEEP ALIVE
# ═══════════════════════════════════════════════════════════════

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return """
    <html>
    <head><title>GADGET Hosting Bot</title></head>
    <body style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; font-family: Arial, sans-serif;">
        <div style="text-align: center; color: white;">
            <h1>🔥 GADGET HOSTING BOT 🔥</h1>
            <p>Version 3.0.0 Ultimate</p>
            <p>✅ Bot is Running!</p>
        </div>
    </body>
    </html>
    """

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    logger.info("✅ Flask Keep-Alive server started")

# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    keep_alive()
    
    logger.info("=" * 50)
    logger.info("🔥 GADGET HOSTING BOT - ULTIMATE VERSION 🔥")
    logger.info("Version 3.0.0")
    logger.info("=" * 50)
    
    # Start bot polling
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            time.sleep(5)
