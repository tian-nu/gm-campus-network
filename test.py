import requests
from bs4 import BeautifulSoup
import time
import logging

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def cas_login(username, password, service_params):
    session = requests.Session()

    # 模拟浏览器请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
        "Referer": f"https://cas.gzittc.com/lyuapServer/login?service={requests.utils.quote(service_params['service'])}",
        "Origin": "https://cas.gzittc.com",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    # 第一步：获取登录页动态参数（自动处理JSESSIONID）
    login_url = "https://cas.gzittc.com/lyuapServer/login"
    try:
        response = session.get(login_url, params=service_params, headers=headers)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"获取登录页失败: {e}")
        return None

    # 提取动态参数（lt/execution，若存在）
    soup = BeautifulSoup(response.text, 'html.parser')
    lt = soup.find('input', {'name': 'lt'}).get('value', '') if soup.find('input', {'name': 'lt'}) else ''
    execution = soup.find('input', {'name': 'execution'}).get('value', '') if soup.find('input',
                                                                                        {'name': 'execution'}) else ''

    # 第二步：提交登录表单（启用自动重定向）
    post_data = {
        'username': username,
        'password': password,
        'lt': lt,
        'execution': execution,
        '_eventId': 'submit'
    }

    try:
        response = session.post(
            login_url,
            data=post_data,
            params=service_params,
            headers=headers,
            allow_redirects=True  # 关键！自动跟踪重定向
        )
        response.raise_for_status()
    except Exception as e:
        logging.error(f"登录请求失败: {e}")
        return None

    # 检查关键Cookies和最终URL
    if 'CASTGC' in session.cookies and 'portal.gzittc.com' in response.url:
        logging.info("登录成功！当前会话Cookies: %s", session.cookies.get_dict())
        return session
    else:
        logging.error("登录失败，最终URL: %s", response.url)
        return None


# 配置参数
service_params = {
    "service": "http://xykd.gzittc.edu.cn/portalCasAuth.do",
    "wlanuserip": "10.111.32.101",
    "wlanacname": "Ne8000-M14",
    "usermac": "74:d4:dd:36:15:6c",
    "rand": str(int(time.time() * 1000))  # 动态生成随机数
}

# 执行登录
session = cas_login("你的账号", "你的密码", service_params)

if session:
    # 心跳维持会话
    while True:
        try:
            check_url = "http://xykd.gzittc.edu.cn/portalCasAuth.do"
            resp = session.get(check_url, params=service_params, timeout=10)
            if resp.status_code == 200 and "认证成功" in resp.text:
                logging.info("会话活跃中...")
            else:
                logging.warning("会话可能过期，尝试重新登录...")
                session = cas_login("你的账号", "你的密码", service_params)
                if not session:
                    break
            time.sleep(1700)  # 28分钟检查一次
        except Exception as e:
            logging.error("心跳请求异常: %s", e)
            time.sleep(60)