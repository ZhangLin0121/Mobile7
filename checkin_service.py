#!/usr/bin/env python3
"""
E-Mobile 7 打卡服务
支持多用户、定时打卡
"""

import yaml
import requests
import schedule
import time
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('checkin.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class User:
    """用户类"""
    def __init__(self, config: Dict):
        self.username = config['username']
        self.password = config['password']
        self.display_name = config['display_name']
        self.enabled = config.get('enabled', True)
        self.location = config['location']
        self.session: Optional[requests.Session] = None

    def __str__(self):
        return self.display_name

class CheckinService:
    """打卡服务"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config = self.load_config(config_file)
        self.users = [User(user_config) for user_config in self.config['users'] if user_config.get('enabled', True)]
        self.base_url = self.config['server']['base_url']
        self.auth_url = self.config['server']['auth_url']
        logger.info(f"加载 {len(self.users)} 个启用用户")
    
    def load_config(self, config_file: str) -> Dict:
        """加载配置"""
        if not Path(config_file).exists():
            self.create_default_config(config_file)
            logger.info(f"已创建默认配置文件: {config_file}")
            
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def create_default_config(self, config_file: str):
        """创建默认配置"""
        config = {
            'server': {
                'base_url': 'http://223.76.229.248:11032',
                'auth_url': 'http://223.76.229.248:8999'
            },
            'users': [
                {
                    'username': '请修改为你的用户名',
                    'password': '请修改为你的密码',
                    'display_name': '请修改为显示名称',
                    'enabled': True,
                    'location': {
                        'latitude': '30.487572428385416',
                        'longitude': '114.50522216796875',
                        'position': '中国武汉市洪山区高新大道772号武汉东湖新技术开发区'
                    }
                }
                # 可添加更多用户：
                # {
                #     'username': 'user2',
                #     'password': 'password2',
                #     'display_name': '用户2',
                #     'enabled': True,
                #     'location': {
                #         'latitude': '30.487572428385416',
                #         'longitude': '114.50522216796875',
                #         'position': '中国武汉市洪山区高新大道772号武汉东湖新技术开发区'
                #     }
                # }
            ],
            'schedule': {
                'morning': {
                    'start': '06:00',    # 上班打卡开始时间
                    'end': '07:00'       # 上班打卡结束时间
                },
                'evening': {
                    'start': '17:30',    # 下班打卡开始时间
                    'end': '18:00'       # 下班打卡结束时间
                }
            }
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    def authenticate(self, user: User) -> bool:
        """用户认证"""
        try:
            user.session = requests.Session()
            user.session.proxies = {'http': '', 'https': ''}
            user.session.trust_env = False
            
            login_url = f"{self.auth_url}/emp/passport/login"
            login_data = {
                'loginid': user.username,
                'password': user.password,
                'device_type': '1',
                'client_type': '2'
            }
            
            response = user.session.post(login_url, json=login_data, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('errcode') == 0:
                    user_id = data.get('base_user_id')
                    access_token = data.get('access_token')
                    
                    user.session.cookies.set('loginidweaver', str(user_id))
                    user.session.headers.update({
                        'emheadercode': access_token,
                        'emaccesstk': access_token,
                        'emheaderuserid': str(user_id),
                        'device_type': '1',
                        'adpn': 'com.weaver.emobile7'
                    })
                    
                    logger.info(f"✅ {user} 认证成功")
                    return True
                else:
                    logger.error(f"❌ {user} 登录失败: {data.get('errmsg')}")
            else:
                logger.error(f"❌ {user} HTTP请求失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ {user} 认证异常: {e}")
        
        return False
    
    def punch_clock(self, user: User, sign_type: str) -> bool:
        """执行打卡"""
        try:
            if not user.session:
                if not self.authenticate(user):
                    return False
            
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
            
            if user.session is None:
                logger.error(f"{user} 会话未初始化")
                return False
                
            response = user.session.post(url, data=punch_data, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "1" and data.get("success") == "1":
                    message = data.get('message', '打卡成功!')
                    sign_time = f"{data.get('signdate')} {data.get('signtime')}"
                    
                    logger.info(f"✅ {user} {message} - {sign_time}")
                    self.log_success(user, sign_type, sign_time, message)
                    return True
                else:
                    logger.error(f"❌ {user} 打卡失败: {data.get('message')}")
            else:
                logger.error(f"❌ {user} HTTP请求失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ {user} 打卡异常: {e}")
        
        return False
    
    def log_success(self, user: User, sign_type: str, sign_time: str, message: str):
        """记录打卡成功"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "user": user.display_name,
            "type": sign_type,
            "time": sign_time,
            "message": message
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
        records = records[-100:]  # 保留最近100条
        
        with open(records_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    
    def morning_checkin(self):
        """上班打卡"""
        logger.info("🌅 开始上班打卡")
        for user in self.users:
            if user.enabled:
                success = self.punch_clock(user, "on")
                if success:
                    logger.info(f"✅ {user} 上班打卡成功")
                else:
                    logger.error(f"❌ {user} 上班打卡失败")
                time.sleep(2)  # 间隔2秒
    
    def evening_checkin(self):
        """下班打卡"""
        logger.info("🌆 开始下班打卡")
        for user in self.users:
            if user.enabled:
                success = self.punch_clock(user, "off")
                if success:
                    logger.info(f"✅ {user} 下班打卡成功")
                else:
                    logger.error(f"❌ {user} 下班打卡失败")
                time.sleep(2)  # 间隔2秒
    
    def get_random_time_in_range(self, time_range: Dict[str, str]) -> str:
        """在时间范围内生成随机时间"""
        start_time = datetime.strptime(time_range['start'], '%H:%M')
        end_time = datetime.strptime(time_range['end'], '%H:%M')
        
        # 计算时间差的总分钟数
        time_diff = (end_time - start_time).total_seconds() / 60
        
        # 生成随机分钟偏移
        random_minutes = random.randint(0, int(time_diff))
        
        # 计算随机时间
        random_time = start_time + timedelta(minutes=random_minutes)
        
        return random_time.strftime('%H:%M')
    
    def setup_schedule(self):
        """设置定时任务"""
        morning_range = self.config['schedule']['morning']
        evening_range = self.config['schedule']['evening']
        
        # 为每天生成随机打卡时间
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
            morning_time = self.get_random_time_in_range(morning_range)
            evening_time = self.get_random_time_in_range(evening_range)
            
            # 设置上班打卡
            getattr(schedule.every(), day).at(morning_time).do(self.morning_checkin)
            
            # 设置下班打卡  
            getattr(schedule.every(), day).at(evening_time).do(self.evening_checkin)
            
            logger.info(f"📅 {day}: 上班 {morning_time}, 下班 {evening_time}")
        
        logger.info(f"📅 定时任务设置完成")
    
    def test_users(self, sign_type: str = "off"):
        """测试所有用户打卡"""
        logger.info(f"🧪 测试所有用户{'上班' if sign_type == 'on' else '下班'}打卡")
        for user in self.users:
            if user.enabled:
                logger.info(f"测试用户: {user}")
                success = self.punch_clock(user, sign_type)
                logger.info(f"测试结果: {'成功' if success else '失败'}")
                time.sleep(1)
    
    def run(self):
        """运行服务"""
        logger.info("🚀 打卡服务启动")
        self.setup_schedule()
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            logger.info("🛑 服务停止")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='E-Mobile 7 打卡服务')
    parser.add_argument('--config', '-c', default='config.yaml', help='配置文件')
    parser.add_argument('--test', '-t', action='store_true', help='测试打卡')
    parser.add_argument('--type', choices=['on', 'off'], default='off', help='测试类型')
    
    args = parser.parse_args()
    
    service = CheckinService(args.config)
    
    if args.test:
        service.test_users(args.type)
    else:
        service.run()

if __name__ == "__main__":
    main() 