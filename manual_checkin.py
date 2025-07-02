#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E-Mobile 7 手动打卡工具
用于补打漏掉的卡或手动执行打卡
"""

import sys
import argparse
import yaml
import requests
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ManualCheckin:
    """手动打卡工具"""
    
    def __init__(self, config_file: str = "production_config.yaml"):
        """初始化"""
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.base_url = self.config['server']['base_url']
        self.auth_url = self.config['server']['auth_url']
        self.users = self.config['users']
    
    def authenticate_user(self, user_config: dict) -> Optional[requests.Session]:
        """用户认证"""
        session = requests.Session()
        
        # 禁用代理
        session.proxies = {'http': '', 'https': ''}
        session.trust_env = False
        
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        })
        
        # 登录API
        login_url = f"{self.auth_url}/emp/passport/login"
        login_data = {
            'loginid': user_config['username'],
            'password': user_config['password'],
            'device_type': '1',
            'client_type': '2'
        }
        
        login_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }
        
        logger.info(f"正在认证用户: {user_config['display_name']}")
        
        response = session.post(login_url, json=login_data, headers=login_headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('errcode') == 0:
                user_id = data.get('base_user_id')
                access_token = data.get('access_token')
                user_name = data.get('base_user_name')
                
                if user_id and access_token:
                    # 设置认证信息
                    session.cookies.set('loginidweaver', str(user_id))
                    session.headers.update({
                        'emheadercode': access_token,
                        'emaccesstk': access_token,
                        'emheaderuserid': str(user_id),
                        'device_type': '1',
                        'adpn': 'com.weaver.emobile7'
                    })
                    
                    logger.info(f"✅ 用户 {user_config['display_name']} 认证成功")
                    return session
                else:
                    logger.error(f"❌ 登录响应中缺少用户ID或访问token")
                    return None
            else:
                error_msg = data.get('errmsg') or '登录失败'
                logger.error(f"❌ 用户 {user_config['display_name']} 登录失败: {error_msg}")
                return None
        else:
            logger.error(f"❌ HTTP请求失败: {response.status_code}")
            return None
    
    def punch_clock(self, user_config: dict, sign_type: str, custom_date: Optional[str] = None, custom_time: Optional[str] = None) -> bool:
        """执行打卡"""
        session = self.authenticate_user(user_config)
        if not session:
            return False
        
        # 设置打卡时间
        if custom_date and custom_time:
            punch_datetime = datetime.strptime(f"{custom_date} {custom_time}", "%Y-%m-%d %H:%M:%S")
        else:
            punch_datetime = datetime.now()
        
        url = f"{self.base_url}/api/hrm/kq/attendanceButton/punchButton"
        
        punch_data = {
            "signdate": punch_datetime.strftime("%Y-%m-%d"),
            "signtime": punch_datetime.strftime("%H:%M:%S"),
            "belongdate": punch_datetime.strftime("%Y-%m-%d"),
            "active": "1",
            "time": "",
            "needSign": "1",
            "type": sign_type,
            "canSignTime": "23:59:59" if sign_type == "off" else "00:00:00",
            "locationshowaddress": "",
            "longitude": user_config["location"]["longitude"],
            "latitude": user_config["location"]["latitude"],
            "position": user_config["location"]["position"],
            "browser": "1"
        }
        
        logger.info(f"正在为 {user_config['display_name']} 执行{'上班' if sign_type == 'on' else '下班'}打卡...")
        logger.info(f"打卡时间: {punch_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        response = session.post(url, data=punch_data, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("status") == "1" and data.get("success") == "1":
                message = data.get('message', '打卡成功!')
                sign_time = f"{data.get('signdate')} {data.get('signtime')}"
                
                logger.info(f"✅ {user_config['display_name']} {message}")
                logger.info(f"   实际打卡时间: {sign_time}")
                
                # 记录到文件
                self.log_punch_success(user_config, sign_type, sign_time, message)
                return True
            else:
                error_msg = data.get('message', '未知错误')
                logger.error(f"❌ {user_config['display_name']} 打卡失败: {error_msg}")
                return False
        else:
            logger.error(f"❌ HTTP请求失败: {response.status_code}")
            return False
    
    def log_punch_success(self, user_config: dict, sign_type: str, sign_time: str, message: str):
        """记录打卡成功"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_config['user_id'],
            "display_name": user_config['display_name'],
            "sign_type": sign_type,
            "sign_time": sign_time,
            "message": message,
            "status": "success",
            "manual": True  # 标记为手动打卡
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
        
        # 按时间排序，只保留最近100条记录
        records = sorted(records, key=lambda x: x['timestamp'])[-100:]
        
        with open(records_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    
    def makeup_checkin(self, target_date: str, sign_type: str):
        """补打卡"""
        logger.info(f"开始补打 {target_date} 的{'上班' if sign_type == 'on' else '下班'}卡")
        
        # 设置补打卡的时间
        if sign_type == "on":
            # 上班卡设置为上午8点
            custom_time = "08:00:00"
        else:
            # 下班卡设置为晚上6点
            custom_time = "18:00:00"
        
        for user_config in self.users:
            if user_config.get('enabled', True):
                logger.info(f"为用户 {user_config['display_name']} 补打卡...")
                success = self.punch_clock(user_config, sign_type, target_date, custom_time)
                if success:
                    logger.info(f"✅ {user_config['display_name']} 补打卡成功")
                else:
                    logger.error(f"❌ {user_config['display_name']} 补打卡失败")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='E-Mobile 7 手动打卡工具')
    parser.add_argument('--config', '-c', default='production_config.yaml', help='配置文件路径')
    parser.add_argument('--type', '-t', choices=['on', 'off'], required=True, help='打卡类型：on=上班，off=下班')
    parser.add_argument('--date', '-d', help='补打卡日期 (格式: YYYY-MM-DD)，不指定则为当前时间打卡')
    parser.add_argument('--time', help='指定打卡时间 (格式: HH:MM:SS)，仅在指定日期时有效')
    
    args = parser.parse_args()
    
    try:
        tool = ManualCheckin(args.config)
        
        if args.date:
            # 补打卡模式
            if args.time:
                # 指定了具体时间
                for user_config in tool.users:
                    if user_config.get('enabled', True):
                        success = tool.punch_clock(user_config, args.type, args.date, args.time)
                        if success:
                            logger.info(f"✅ {user_config['display_name']} 打卡成功")
                        else:
                            logger.error(f"❌ {user_config['display_name']} 打卡失败")
            else:
                # 使用默认时间补打卡
                tool.makeup_checkin(args.date, args.type)
        else:
            # 当前时间打卡
            for user_config in tool.users:
                if user_config.get('enabled', True):
                    success = tool.punch_clock(user_config, args.type)
                    if success:
                        logger.info(f"✅ {user_config['display_name']} 打卡成功")
                    else:
                        logger.error(f"❌ {user_config['display_name']} 打卡失败")
        
    except Exception as e:
        logger.error(f"程序运行异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 