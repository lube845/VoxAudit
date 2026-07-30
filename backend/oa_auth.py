"""
OA免登录认证模块
处理OA系统的免登录跳转和用户信息获取
"""

import hashlib
import time
import requests
import json
from typing import Dict, Optional, Tuple

import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

# 导入配置
import os

OA_CONFIG = {
    'base_url': os.getenv('OA_BASE_URL', 'http://oa.com:8000'),
    'secret_key': os.getenv('OA_SECRET_KEY', 'OA_SECRET_KEY'),
    'api_identifier': os.getenv('OA_API_IDENTIFIER', 'voxaudit'),
    'token_expire_minutes': int(os.getenv('OA_TOKEN_EXPIRE_MINUTES', '5')),
    'time_offset_seconds': int(os.getenv('OA_TIME_OFFSET_SECONDS', '0'))
}


def get_user_info_from_oa(loginid: str) -> Optional[Dict[str, str]]:
    """
    从OA系统API获取用户信息

    参数:
        loginid: 员工登录名（员工号）

    返回:
        用户信息字典，包含工号、姓名、部门等，失败返回None
    """
    try:
        # 1. 构造请求URL（已设白名单，无需token）
        url = f"{OA_CONFIG['base_url']}/api/hrm/resful/getHrmUserInfoWithPage"

        # 2. 构造请求数据
        data = {
            "params": {
                "pagesize": 1,
                "workcode": loginid
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        # 3. 发送POST请求
        print(f"[OA API] 正在查询用户信息: workcode={loginid}")
        response = requests.post(url, headers=headers, json=data, timeout=10)

        # 6. 解析响应
        if response.status_code == 200:
            result = response.json()
            print(f"[OA API] 响应: {result}")

            if result.get("code") == "1":
                user_list = result.get("data", {}).get("dataList", [])

                if user_list and len(user_list) > 0:
                    user = user_list[0]

                    # 提取用户信息
                    user_info = {
                        "工号": user.get("workcode", loginid),
                        "姓名": user.get("lastname", "未知"),
                        "部门": user.get("departmentname", "未知"),
                        "loginid": user.get("loginid", loginid),
                        "分部": user.get("subcompanyname", ""),
                        "岗位": user.get("jobtitle", ""),
                        "邮箱": user.get("email", ""),
                        "手机": user.get("mobile", ""),
                        "状态": user.get("status", "")
                    }

                    print(f"[OA API] 成功获取用户信息: {user_info['姓名']} ({user_info['部门']})")
                    return user_info
                else:
                    print(f"[OA API] 未找到用户: loginid={loginid}")
                    return None
            else:
                print(f"[OA API] API返回失败: code={result.get('code')}")
                return None
        else:
            print(f"[OA API] HTTP请求失败: status={response.status_code}")
            return None

    except requests.Timeout:
        print(f"[OA API] 请求超时")
        return None
    except requests.RequestException as e:
        print(f"[OA API] 网络请求错误: {str(e)}")
        return None
    except json.JSONDecodeError:
        print(f"[OA API] JSON解析失败")
        return None
    except Exception as e:
        print(f"[OA API] 获取用户信息失败: {str(e)}")
        return None



def oa_login_with_password(loginid: str, password: str) -> Tuple[bool, Optional[Dict], str]:
    """
    Authenticate a normal user against OA via the checkLogin API.
    Replaces the Playwright browser simulation approach.

    Steps:
      1. POST to /api/hrm/login/checkLogin
      2. On success, fetch user info via getHrmUserInfoWithPage

    Returns:
        (success, user_info, message)
    """
    base_url = OA_CONFIG['base_url']

    # Step 1: call checkLogin
    try:
        login_url = f"{base_url}/api/hrm/login/checkLogin"
        payload = {
            "loginid": loginid,
            "userpassword": password,
            "logintype": "1",
            "islangueid": "7",
            "isRememberPassword": "false",
            "validatecode": "",
            "validateCodeKey": "",
            "dynamicPassword": "",
            "messages": "",
            "isie": "false",
            "appid": "",
            "service": "",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        login_resp = requests.post(login_url, data=payload, headers=headers, timeout=10)
        login_resp.raise_for_status()
        result = login_resp.json()
        print(f"[OA Login] checkLogin response: {result}")
    except Exception as e:
        return False, None, f"OA登录接口请求失败: {e}"

    # checkLogin returns loginstatus="true" or msgcode="0" on success
    login_ok = (
        str(result.get("loginstatus")).lower() == "true"
        or str(result.get("msgcode")) == "0"
        or str(result.get("code")) == "1"
    )
    if not login_ok:
        msg = result.get("msg") or result.get("message") or "账号或密码错误"
        return False, None, msg

    # Step 2: fetch user info
    user_info = get_user_info_from_oa(loginid)
    if user_info is None:
        return False, None, "登录成功但无法获取员工信息，请联系管理员"

    return True, user_info, "登录成功"
