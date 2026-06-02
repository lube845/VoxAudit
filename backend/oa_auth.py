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
try:
    from backend.core.config import settings as _cfg
    OA_CONFIG = {
        'base_url': _cfg.OA_BASE_URL,
        'secret_key': _cfg.OA_SECRET_KEY,
        'api_identifier': _cfg.OA_API_IDENTIFIER,
        'token_expire_minutes': _cfg.OA_TOKEN_EXPIRE_MINUTES,
        'time_offset_seconds': _cfg.OA_TIME_OFFSET_SECONDS,
    }
except ImportError:
    print("警告: 未找到config.py，使用默认配置")
    OA_CONFIG = {
        'base_url': 'http://oa.bgzchina.com:8000',
        'secret_key': 'lyOINc',
        'api_identifier': '5936562a-d47c-4a29-9b74-b310e6c971b7',
        'token_expire_minutes': 5,
        'time_offset_seconds': 0,
    }


def verify_oa_sso_token(loginid: str, stamp: str, token: str) -> Tuple[bool, str]:
    """
    验证OA免登录token

    参数:
        loginid: 员工号
        stamp: 时间戳（毫秒）
        token: OA传递的token

    返回:
        (是否验证通过, 错误信息)
    """
    try:
        # 1. 检查时间戳是否在有效期内（考虑服务器时间差）
        time_offset_ms = OA_CONFIG.get('time_offset_seconds', 0) * 1000
        current_timestamp = int(time.time() * 1000) - time_offset_ms
        stamp_int = int(stamp)
        time_diff_minutes = abs(current_timestamp - stamp_int) / 1000 / 60

        if time_diff_minutes > OA_CONFIG['token_expire_minutes']:
            return False, f"链接已过期（超过{OA_CONFIG['token_expire_minutes']}分钟，时间差{time_diff_minutes:.1f}分钟）"

        # 2. 计算期望的token: SHA1(密钥+loginid+stamp)
        raw_string = OA_CONFIG['secret_key'] + loginid + stamp
        expected_token = hashlib.sha1(raw_string.encode()).hexdigest()

        # 3. 比对token（不区分大小写）
        if token.lower() != expected_token.lower():
            return False, "token验证失败，可能链接被篡改"

        return True, "验证成功"

    except ValueError:
        return False, "时间戳格式错误"
    except Exception as e:
        return False, f"验证过程出错: {str(e)}"


def generate_api_token() -> Dict[str, str]:
    """
    生成OA API调用所需的token

    返回:
        包含key和ts的字典
    """
    # 当前时间戳（毫秒）
    ts = str(int(time.time() * 1000))

    # 计算key: MD5(标识+时间戳) 转大写
    key_string = OA_CONFIG['api_identifier'] + ts
    api_key = hashlib.md5(key_string.encode()).hexdigest().upper()

    return {
        "key": api_key,
        "ts": ts
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


def _rsa_encrypt(value: str, rsa_pub: str, rsa_code: str, rsa_flag: str) -> str:
    """
    Encrypt value using OA's RSA scheme:
    encrypt(value + rsa_code) + rsa_flag
    Supports segmented encryption for values longer than 240 chars.
    """
    # Load PEM public key (add header/footer if missing)
    pub_pem = rsa_pub.strip()
    if not pub_pem.startswith("-----"):
        pub_pem = f"-----BEGIN PUBLIC KEY-----\n{pub_pem}\n-----END PUBLIC KEY-----"
    public_key = serialization.load_pem_public_key(pub_pem.encode(), backend=default_backend())

    def encrypt_chunk(chunk: str) -> str:
        plaintext = (chunk + rsa_code).encode("utf-8")
        ciphertext = public_key.encrypt(plaintext, padding.PKCS1v15())
        return base64.b64encode(ciphertext).decode("utf-8")

    group_length = 240
    if len(value) > group_length:
        parts = []
        for i in range(0, len(value), group_length):
            chunk = value[i:i + group_length]
            if chunk:
                parts.append(encrypt_chunk(chunk))
        return rsa_flag.join(parts) + rsa_flag
    else:
        return encrypt_chunk(value) + rsa_flag


def oa_login_with_password(loginid: str, password: str) -> Tuple[bool, Optional[Dict], str]:
    """
    Authenticate a normal user against OA via the checkLogin API.
    Replaces the Playwright browser simulation approach.

    Steps:
      1. Fetch RSA public key from OA
      2. Encrypt loginid and password
      3. POST to /api/hrm/login/checkLogin
      4. On success, fetch user info via getHrmUserInfoWithPage

    Returns:
        (success, user_info, message)
    """
    base_url = OA_CONFIG['base_url']

    # Step 1: fetch RSA key info
    try:
        ts = int(time.time() * 1000)
        rsa_url = f"{base_url}/rsa/weaver.rsa.GetRsaInfo?ts={ts}"
        rsa_resp = requests.get(rsa_url, timeout=10)
        rsa_resp.raise_for_status()
        rsa_data = rsa_resp.json()
        rsa_pub = rsa_data.get("rsa_pub", "")
        rsa_code = rsa_data.get("rsa_code", "")
        rsa_flag = rsa_data.get("rsa_flag", "")
        print(f"[OA Login] RSA key fetched, flag={repr(rsa_flag)}")
    except Exception as e:
        return False, None, f"获取OA RSA公钥失败: {e}"

    # Step 2: encrypt credentials
    try:
        encrypted_loginid = _rsa_encrypt(loginid, rsa_pub, rsa_code, rsa_flag)
        encrypted_password = _rsa_encrypt(password, rsa_pub, rsa_code, rsa_flag)
    except Exception as e:
        return False, None, f"RSA加密失败: {e}"

    # Step 3: call checkLogin
    try:
        login_url = f"{base_url}/api/hrm/login/checkLogin"
        payload = {
            "loginid": encrypted_loginid,
            "userpassword": encrypted_password,
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

    # Step 4: fetch user info
    user_info = get_user_info_from_oa(loginid)
    if user_info is None:
        return False, None, "登录成功但无法获取员工信息，请联系管理员"

    return True, user_info, "登录成功"


def oa_sso_login(loginid: str, stamp: str, token: str) -> Tuple[bool, Optional[Dict], str]:
    """
    OA免登录流程

    参数:
        loginid: 员工号
        stamp: 时间戳
        token: OA传递的token

    返回:
        (是否成功, 用户信息, 错误信息)
    """
    # 第1步：验证token
    is_valid, message = verify_oa_sso_token(loginid, stamp, token)

    if not is_valid:
        return False, None, message

    # 第2步：从OA API获取用户详细信息
    user_info = get_user_info_from_oa(loginid)

    if user_info is None:
        return False, None, f"无法从OA系统获取员工 {loginid} 的信息，可能该员工不存在"

    return True, user_info, "登录成功"


if __name__ == "__main__":
    # 测试代码
    print("=== OA认证模块测试 ===")

    # 测试1：生成API token
    print("\n1. 测试生成API token:")
    api_token = generate_api_token()
    print(f"   Token: {api_token}")

    # 测试2：验证SSO token
    print("\n2. 测试验证SSO token:")
    test_loginid = "test123"
    test_stamp = str(int(time.time() * 1000))
    test_token = hashlib.sha1((OA_CONFIG['secret_key'] + test_loginid + test_stamp).encode()).hexdigest()

    is_valid, msg = verify_oa_sso_token(test_loginid, test_stamp, test_token)
    print(f"   验证结果: {is_valid}, 消息: {msg}")

    print("\n=== 测试完成 ===")
