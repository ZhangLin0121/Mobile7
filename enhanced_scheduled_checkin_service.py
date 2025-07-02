#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E-Mobile 7 企业级定时打卡服务
支持多用户、随机时间、自动重新登录、节假日检测、周末打卡的生产级打卡服务
"""

try:
    import schedule
except ImportError:
    print("请安装 schedule 库: pip install schedule")
    exit(1)

try:
    import yaml
except ImportError:
    print("请安装 PyYAML 库: pip install PyYAML")
    exit(1)

import time
import random
import json
import logging
import threading
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
import requests
from typing import Dict, List, Optional, Union
import argparse
from logging.handlers import RotatingFileHandler
from http.server import HTTPServer, BaseHTTPRequestHandler
import traceback

# 配置日志轮转
def setup_logging():
    """设置日志配置"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 清除现有处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        'emobile_checkin.log', 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

class HolidayChecker:
    """节假日检测器"""
    
    def __init__(self):
        self.cache = {}
        self.cache_expiry = {}
        
    def is_holiday(self, date: datetime) -> bool:
        """检查指定日期是否为节假日"""
        date_str = date.strftime('%Y-%m-%d')
        
        # 检查缓存
        if date_str in self.cache and datetime.now() < self.cache_expiry.get(date_str, datetime.min):
            return self.cache[date_str]
        
        try:
            # 使用免费的中国节假日API
            url = f"http://timor.tech/api/holiday/info/{date_str}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                is_holiday = data.get('holiday', False)
                
                # 缓存结果（缓存24小时）
                self.cache[date_str] = is_holiday
                self.cache_expiry[date_str] = datetime.now() + timedelta(hours=24)
                
                logger.debug(f"节假日检查 {date_str}: {'是' if is_holiday else '否'}")
                return is_holiday
            else:
                logger.warning(f"节假日API请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"节假日检查异常: {e}")
            return False
    
    def should_work_today(self) -> bool:
        """检查今天是否应该工作（非节假日）"""
        today = datetime.now()
        return not self.is_holiday(today)

class EMobileUser:
    """E-Mobile用户类"""
    
    def __init__(self, config: Dict):
        self.username = config['username']
        self.password = config['password']
        self.user_id = config['user_id']
        self.display_name = config['display_name']
        self.location = config['location']
        self.enabled = config.get('enabled', True)
        self.checkin_rules = config.get('checkin_rules', {})
        
        # 运行时状态
        self.session: Optional[requests.Session] = None
        self.last_login_time: Optional[datetime] = None
        self.login_token: Optional[str] = None
        self.consecutive_failures = 0
        
    def __str__(self):
        return f"EMobileUser({self.display_name}[{self.user_id}])"

class HealthCheckHandler(BaseHTTPRequestHandler):
    """健康检查 HTTP 处理器"""
    
    def __init__(self, service_instance, *args, **kwargs):
        self.service = service_instance
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """处理 GET 请求"""
        if self.path == '/health':
            try:
                health_status = self.service.health_check()
                response = json.dumps(health_status, ensure_ascii=False, indent=2)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(response.encode('utf-8'))))
                self.end_headers()
                self.wfile.write(response.encode('utf-8'))
            except Exception as e:
                error_response = json.dumps({
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }, ensure_ascii=False, indent=2)
                
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(error_response.encode('utf-8'))))
                self.end_headers()
                self.wfile.write(error_response.encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def log_message(self, format, *args):
        """重写日志方法，避免在控制台输出过多信息"""
        pass

def create_health_check_handler(service):
    """创建健康检查处理器工厂"""
    def handler(*args, **kwargs):
        return HealthCheckHandler(service, *args, **kwargs)
    return handler

class EnhancedScheduledCheckinService:
    """增强版定时打卡服务"""
    
    def __init__(self, config_file: str = "production_config.yaml"):
        """初始化服务"""
        self.config_file = config_file
        self.config = self.load_config()
        self.users: List[EMobileUser] = []
        self.running = False
        self.holiday_checker = HolidayChecker()
        
        # 服务器配置
        self.server_config = self.config.get('server', {})
        self.base_url = self.server_config.get('base_url', 'http://223.76.229.248:11032')
        self.auth_url = self.server_config.get('auth_url', 'http://223.76.229.248:8999')
        
        # 定时配置
        self.schedule_config = self.config.get('schedule', {})
        
        # 监控配置
        self.health_check_port = self.config.get('monitoring', {}).get('health_check_port', 8080)
        self.http_server = None
        self.http_thread = None
        
        # 注册信号处理器
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # 如果配置文件不存在，创建默认配置
        if not Path(config_file).exists():
            logger.warning(f"配置文件 {config_file} 不存在，创建默认配置")
            self.create_default_config()
            sys.exit(1)
        
        # 加载用户和设置定时任务
        self.load_users()
        self.setup_schedules()
        
        logger.info(f"增强版定时打卡服务初始化完成，加载 {len(self.users)} 个用户")

    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，准备优雅关闭服务...")
        self.stop_service()
        sys.exit(0)

    def load_config(self) -> Dict:
        """加载配置文件"""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            self.create_default_config()
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}

    def create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            'server': {
                'base_url': 'http://223.76.229.248:11032',
                'auth_url': 'http://223.76.229.248:8999'
            },
            'schedule': {
                'workday': {
                    'morning': {
                        'enabled': True,
                        'time_range': ['07:30', '08:00'],
                        'type': 'on'
                    },
                    'evening': {
                        'enabled': True, 
                        'time_range': ['18:00', '19:00'],
                        'type': 'off'
                    }
                },
                'weekend': {
                    'morning': {
                        'enabled': True,
                        'time_range': ['08:00', '08:30'],
                        'type': 'on'
                    },
                    'evening': {
                        'enabled': True,
                        'time_range': ['17:30', '18:30'],
                        'type': 'off'
                    }
                },
                'holiday_check': True,
                'timezone': 'Asia/Shanghai'
            },
            'users': [
                {
                    'username': '你的用户名',
                    'password': '你的密码', 
                    'user_id': '585',
                    'display_name': '张志远',
                    'enabled': True,
                    'location': {
                        'latitude': '30.487572428385416',
                        'longitude': '114.50522216796875',
                        'position': '中国武汉市洪山区高新大道772号武汉东湖新技术开发区'
                    },
                    'checkin_rules': {
                        'workday_morning_enabled': True,
                        'workday_evening_enabled': True,
                        'weekend_morning_enabled': True,
                        'weekend_evening_enabled': True
                    }
                }
            ],
            'monitoring': {
                'health_check_port': 8080,
                'max_consecutive_failures': 5
            },
            'notification': {
                'enabled': False,
                'webhook_url': '',
                'email': {
                    'enabled': False,
                    'smtp_server': '',
                    'username': '',
                    'password': '',
                    'to_emails': []
                }
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
        
        logger.info(f"已创建默认配置文件: {self.config_file}")

    def load_users(self):
        """加载用户配置"""
        users_config = self.config.get('users', [])
        
        for user_config in users_config:
            if user_config.get('enabled', True):
                try:
                    user = EMobileUser(user_config)
                    self.users.append(user)
                    logger.info(f"加载用户: {user}")
                except Exception as e:
                    logger.error(f"加载用户配置失败: {e}")

    def setup_schedules(self):
        """设置定时任务"""
        workday_config = self.schedule_config.get('workday', {})
        weekend_config = self.schedule_config.get('weekend', {})
        
        # 工作日打卡设置
        self._setup_workday_schedules(workday_config)
        
        # 周末打卡设置
        self._setup_weekend_schedules(weekend_config)
        
        logger.info("定时任务设置完成")

    def _setup_workday_schedules(self, workday_config: Dict):
        """设置工作日打卡任务"""
        morning_config = workday_config.get('morning', {})
        evening_config = workday_config.get('evening', {})
        
        # 工作日上班打卡
        if morning_config.get('enabled', True):
            time_range = morning_config.get('time_range', ['07:30', '08:00'])
            for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
                getattr(schedule.every(), day).at(self.get_random_time(time_range)).do(
                    self.run_workday_morning_checkin
                )
            logger.info(f"设置工作日上班打卡时间: {time_range[0]} - {time_range[1]}")
        
        # 工作日下班打卡
        if evening_config.get('enabled', True):
            time_range = evening_config.get('time_range', ['18:00', '19:00'])
            for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
                getattr(schedule.every(), day).at(self.get_random_time(time_range)).do(
                    self.run_workday_evening_checkin
                )
            logger.info(f"设置工作日下班打卡时间: {time_range[0]} - {time_range[1]}")

    def _setup_weekend_schedules(self, weekend_config: Dict):
        """设置周末打卡任务"""
        morning_config = weekend_config.get('morning', {})
        evening_config = weekend_config.get('evening', {})
        
        # 周末上班打卡
        if morning_config.get('enabled', True):
            time_range = morning_config.get('time_range', ['08:00', '08:30'])
            schedule.every().saturday.at(self.get_random_time(time_range)).do(
                self.run_weekend_morning_checkin
            )
            schedule.every().sunday.at(self.get_random_time(time_range)).do(
                self.run_weekend_morning_checkin
            )
            logger.info(f"设置周末上班打卡时间: {time_range[0]} - {time_range[1]}")
        
        # 周末下班打卡
        if evening_config.get('enabled', True):
            time_range = evening_config.get('time_range', ['17:30', '18:30'])
            schedule.every().saturday.at(self.get_random_time(time_range)).do(
                self.run_weekend_evening_checkin
            )
            schedule.every().sunday.at(self.get_random_time(time_range)).do(
                self.run_weekend_evening_checkin
            )
            logger.info(f"设置周末下班打卡时间: {time_range[0]} - {time_range[1]}")

    def get_random_time(self, time_range: List[str]) -> str:
        """获取时间范围内的随机时间"""
        start_time = datetime.strptime(time_range[0], '%H:%M')
        end_time = datetime.strptime(time_range[1], '%H:%M')
        
        time_diff = (end_time - start_time).total_seconds() / 60
        random_minutes = random.randint(0, int(time_diff))
        random_time = start_time + timedelta(minutes=random_minutes)
        
        return random_time.strftime('%H:%M')

    def should_checkin_today(self) -> bool:
        """检查今天是否应该打卡（非节假日）"""
        if not self.schedule_config.get('holiday_check', True):
            return True
        
        return self.holiday_checker.should_work_today()

    def authenticate_user(self, user: EMobileUser) -> bool:
        """用户认证登录"""
        logger.info(f"开始认证用户: {user}")
        
        # 添加重试机制
        max_retries = 3
        retry_delay = [2, 5, 10]  # 重试延迟时间（秒）
        
        for attempt in range(max_retries):
            try:
                user.session = requests.Session()
                
                # 禁用代理
                user.session.proxies = {
                    'http': '',
                    'https': ''
                }
                user.session.trust_env = False
                
                user.session.headers.update({
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive"
                })
                
                # 调用真正的登录API
                login_url = f"{self.auth_url}/emp/passport/login"
                login_data = {
                    'loginid': user.username,
                    'password': user.password,
                    'device_type': '1',
                    'client_type': '2'
                }
                
                # 设置登录请求的headers
                login_headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15',
                    'Accept': 'application/json, text/plain, */*',
                    'Content-Type': 'application/json',
                    'Accept-Language': 'zh-CN,zh;q=0.9'
                }
                
                if attempt > 0:
                    logger.info(f"第 {attempt + 1} 次重试认证用户: {user}")
                
                response = user.session.post(login_url, json=login_data, headers=login_headers, timeout=30)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        # 检查登录是否成功
                        if data.get('errcode') == 0:
                            # 提取用户信息
                            user_id = data.get('base_user_id')
                            access_token = data.get('access_token')
                            user_name = data.get('base_user_name')
                            
                            if user_id and access_token:
                                # 设置认证信息
                                user.session.cookies.set('loginidweaver', str(user_id))
                                user.session.headers.update({
                                    'emheadercode': access_token,
                                    'emaccesstk': access_token,
                                    'emheaderuserid': str(user_id),
                                    'device_type': '1',
                                    'adpn': 'com.weaver.emobile7'
                                })
                                
                                user.last_login_time = datetime.now()
                                user.login_token = access_token
                                user.consecutive_failures = 0
                                
                                logger.info(f"✅ 用户 {user} 认证成功")
                                logger.info(f"   用户ID: {user_id}")
                                logger.info(f"   姓名: {user_name}")
                                if attempt > 0:
                                    logger.info(f"   重试 {attempt + 1} 次后成功")
                                return True
                            else:
                                logger.error(f"❌ 登录响应中缺少用户ID或访问token")
                                logger.error(f"   响应数据: {data}")
                                if attempt < max_retries - 1:
                                    logger.info(f"   将在 {retry_delay[attempt]} 秒后重试...")
                                    time.sleep(retry_delay[attempt])
                                    continue
                        else:
                            error_msg = data.get('errmsg') or '登录失败'
                            logger.error(f"❌ 用户 {user} 登录失败: {error_msg}")
                            logger.error(f"   错误码: {data.get('errcode')}")
                            logger.error(f"   完整响应: {data}")
                            if attempt < max_retries - 1:
                                logger.info(f"   将在 {retry_delay[attempt]} 秒后重试...")
                                time.sleep(retry_delay[attempt])
                                continue
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ 用户 {user} 登录响应不是有效的JSON格式")
                        logger.error(f"   JSON解析错误: {str(e)}")
                        logger.error(f"   响应内容: {response.text[:500]}...")
                        if attempt < max_retries - 1:
                            logger.info(f"   将在 {retry_delay[attempt]} 秒后重试...")
                            time.sleep(retry_delay[attempt])
                            continue
                else:
                    logger.error(f"❌ 用户 {user} 登录请求失败: HTTP {response.status_code}")
                    logger.error(f"   响应头: {dict(response.headers)}")
                    logger.error(f"   响应内容: {response.text[:500]}...")
                    if attempt < max_retries - 1:
                        logger.info(f"   将在 {retry_delay[attempt]} 秒后重试...")
                        time.sleep(retry_delay[attempt])
                        continue
                
            except requests.exceptions.Timeout as e:
                logger.error(f"❌ 用户 {user} 认证超时: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"   将在 {retry_delay[attempt]} 秒后重试...")
                    time.sleep(retry_delay[attempt])
                    continue
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ 用户 {user} 网络连接错误: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"   将在 {retry_delay[attempt]} 秒后重试...")
                    time.sleep(retry_delay[attempt])
                    continue
            except Exception as e:
                logger.error(f"❌ 用户 {user} 认证异常: {str(e)}")
                logger.error(f"   异常类型: {type(e).__name__}")
                logger.error(f"   异常详情: {traceback.format_exc()}")
                if attempt < max_retries - 1:
                    logger.info(f"   将在 {retry_delay[attempt]} 秒后重试...")
                    time.sleep(retry_delay[attempt])
                    continue
        
        # 所有重试都失败了
        logger.error(f"❌ 用户 {user} 认证失败，已重试 {max_retries} 次")
        user.consecutive_failures += 1
        return False

    def punch_clock_for_user(self, user: EMobileUser, sign_type: str) -> bool:
        """为指定用户执行打卡"""
        logger.info(f"开始为用户 {user} 执行{'上班' if sign_type == 'on' else '下班'}打卡")
        
        # 检查用户连续失败次数
        max_failures = self.config.get('monitoring', {}).get('max_consecutive_failures', 5)
        if user.consecutive_failures >= max_failures:
            logger.warning(f"用户 {user} 连续失败次数过多({user.consecutive_failures})，跳过本次打卡")
            return False
        
        try:
            # 检查是否需要重新登录
            if not user.session or not user.last_login_time or \
               (datetime.now() - user.last_login_time).total_seconds() > 3600:
                if not self.authenticate_user(user):
                    return False
            
            # 执行打卡
            url = f"{self.base_url}/api/hrm/kq/attendanceButton/punchButton"
            
            current_time = datetime.now()
            punch_data = {
                "signdate": current_time.strftime("%Y-%m-%d"),
                "signtime": current_time.strftime("%H:%M:%S"),
                "belongdate": current_time.strftime("%Y-%m-%d"),
                "active": "1",
                "time": "",
                "needSign": "1", 
                "type": sign_type,
                "canSignTime": "23:59:59" if sign_type == "off" else "00:00:00",
                "locationshowaddress": "",
                "longitude": user.location["longitude"],
                "latitude": user.location["latitude"], 
                "position": user.location["position"],
                "browser": "1"
            }
            
            response = user.session.post(url, data=punch_data, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("status") == "1" and data.get("success") == "1":
                    message = data.get('message', '打卡成功!')
                    sign_time = f"{data.get('signdate')} {data.get('signtime')}"
                    
                    logger.info(f"✅ 用户 {user} {message}")
                    logger.info(f"   打卡时间: {sign_time}")
                    
                    user.consecutive_failures = 0
                    self.log_punch_success(user, sign_type, sign_time, message)
                    self.send_notification(user, sign_type, sign_time, message, True)
                    
                    return True
                else:
                    error_msg = data.get('message', '未知错误')
                    logger.error(f"❌ 用户 {user} 打卡失败: {error_msg}")
                    user.consecutive_failures += 1
                    self.send_notification(user, sign_type, "", error_msg, False)
                    return False
            else:
                logger.error(f"用户 {user} HTTP请求失败: {response.status_code}")
                user.consecutive_failures += 1
                return False
                
        except Exception as e:
            logger.error(f"用户 {user} 打卡异常: {e}")
            user.consecutive_failures += 1
            return False

    def run_workday_morning_checkin(self):
        """执行工作日上班打卡"""
        if not self.should_checkin_today():
            logger.info("今天是节假日，跳过工作日上班打卡")
            return
        
        logger.info("🌅 开始执行工作日上班打卡任务")
        for user in self.users:
            if user.enabled and user.checkin_rules.get('workday_morning_enabled', True):
                self.punch_clock_for_user(user, "on")
                time.sleep(random.randint(5, 15))  # 随机延迟

    def run_workday_evening_checkin(self):
        """执行工作日下班打卡"""
        if not self.should_checkin_today():
            logger.info("今天是节假日，跳过工作日下班打卡")
            return
        
        logger.info("🌆 开始执行工作日下班打卡任务")
        for user in self.users:
            if user.enabled and user.checkin_rules.get('workday_evening_enabled', True):
                self.punch_clock_for_user(user, "off")
                time.sleep(random.randint(5, 15))

    def run_weekend_morning_checkin(self):
        """执行周末上班打卡"""
        if not self.should_checkin_today():
            logger.info("今天是节假日，跳过周末上班打卡")
            return
        
        logger.info("🏖️ 开始执行周末上班打卡任务")
        for user in self.users:
            if user.enabled and user.checkin_rules.get('weekend_morning_enabled', True):
                self.punch_clock_for_user(user, "on")
                time.sleep(random.randint(5, 15))

    def run_weekend_evening_checkin(self):
        """执行周末下班打卡"""
        if not self.should_checkin_today():
            logger.info("今天是节假日，跳过周末下班打卡")
            return
        
        logger.info("🏖️ 开始执行周末下班打卡任务")
        for user in self.users:
            if user.enabled and user.checkin_rules.get('weekend_evening_enabled', True):
                self.punch_clock_for_user(user, "off")
                time.sleep(random.randint(5, 15))

    def log_punch_success(self, user: EMobileUser, sign_type: str, sign_time: str, message: str):
        """记录打卡成功"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user.user_id,
            "display_name": user.display_name,
            "sign_type": sign_type,
            "sign_time": sign_time,
            "message": message,
            "status": "success"
        }
        
        records_file = Path("punch_records.json")
        records = []
        
        if records_file.exists():
            try:
                with open(records_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
            except:
                records = []
        
        records.append(record)
        
        # 只保留最近100条记录
        records = records[-100:]
        
        with open(records_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def send_notification(self, user: EMobileUser, sign_type: str, sign_time: str, message: str, success: bool):
        """发送通知"""
        notification_config = self.config.get('notification', {})
        
        if not notification_config.get('enabled', False):
            return
        
        webhook_url = notification_config.get('webhook_url')
        if webhook_url:
            try:
                payload = {
                    "user": user.display_name,
                    "type": "上班" if sign_type == "on" else "下班",
                    "time": sign_time,
                    "message": message,
                    "success": success,
                    "timestamp": datetime.now().isoformat()
                }
                
                requests.post(webhook_url, json=payload, timeout=10)
            except Exception as e:
                logger.warning(f"发送Webhook通知失败: {e}")

    def health_check(self) -> Dict:
        """健康检查"""
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "users_count": len(self.users),
            "running": self.running,
            "next_jobs": []
        }
        
        # 获取下次任务时间
        for job in schedule.jobs:
            status["next_jobs"].append({
                "job": str(job.job_func.__name__),
                "next_run": job.next_run.isoformat() if job.next_run else None
            })
        
        return status

    def run_service(self):
        """运行服务"""
        logger.info("🚀 定时打卡服务启动")
        self.running = True
        
        # 启动健康检查服务器
        self.start_health_check_server()
        
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            logger.info("收到中断信号，停止服务")
        finally:
            self.stop_service()

    def stop_service(self):
        """停止服务"""
        logger.info("🛑 定时打卡服务停止")
        self.running = False
        
        # 停止健康检查服务器
        self.stop_health_check_server()
        
        # 清理资源
        for user in self.users:
            if user.session:
                user.session.close()

    def test_all_users(self, sign_type: str = "off"):
        """测试所有用户打卡"""
        logger.info(f"🧪 开始测试所有用户{'上班' if sign_type == 'on' else '下班'}打卡")
        
        for user in self.users:
            if user.enabled:
                logger.info(f"测试用户: {user}")
                success = self.punch_clock_for_user(user, sign_type)
                logger.info(f"测试结果: {'成功' if success else '失败'}")
                time.sleep(2)

    def start_health_check_server(self):
        """启动健康检查 HTTP 服务器"""
        try:
            handler = create_health_check_handler(self)
            self.http_server = HTTPServer(('0.0.0.0', self.health_check_port), handler)
            
            def run_server():
                logger.info(f"🌡️ 健康检查服务启动在端口 {self.health_check_port}")
                self.http_server.serve_forever()
            
            self.http_thread = threading.Thread(target=run_server, daemon=True)
            self.http_thread.start()
            
        except Exception as e:
            logger.error(f"启动健康检查服务器失败: {e}")

    def stop_health_check_server(self):
        """停止健康检查 HTTP 服务器"""
        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server.server_close()
                logger.info("🌡️ 健康检查服务器已停止")
            except Exception as e:
                logger.error(f"停止健康检查服务器失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='E-Mobile 7 增强版定时打卡服务')
    parser.add_argument('--config', '-c', default='production_config.yaml', help='配置文件路径')
    parser.add_argument('--test', '-t', action='store_true', help='测试模式')
    parser.add_argument('--test-type', choices=['on', 'off'], default='off', help='测试打卡类型')
    
    args = parser.parse_args()
    
    try:
        service = EnhancedScheduledCheckinService(args.config)
        
        if args.test:
            service.test_all_users(args.test_type)
        else:
            service.run_service()
            
    except Exception as e:
        logger.error(f"服务运行异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 