import requests
from bs4 import BeautifulSoup

# 使用 Session 保持 Cookies
session = requests.Session()

# 设置 headers（User-Agent 需更新为有效值）
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

# 首次获取登录页，提取 lt 和 execution
login_page_url = 'https://cas.gzittc.com/lyuapServer/login'
try:
    response = session.get(login_page_url, headers=headers, timeout=10)
    response.raise_for_status()  # 检查请求是否成功

    # 解析 HTML 获取表单参数
    soup = BeautifulSoup(response.text, 'html.parser')
    lt = soup.find('input', {'name': 'lt'}).get('value')
    execution = soup.find('input', {'name': 'execution'}).get('value')

except Exception as e:
    print(f"获取登录页失败: {e}")
    exit()

# 构造认证数据（替换为你的账号密码）
auth_data = {
    'username': "23031901151",
    'password': "123qweasdzxc",
    'lt': lt,
    'execution': execution,
    '_eventId': 'submit',
    'submit': '登录'
}

# 提交登录请求
try:
    cas_res = session.post(
        url=login_page_url,
        data=auth_data,
        headers=headers,
        timeout=10,
        allow_redirects=True  # 允许重定向以跟踪登录结果
    )
    print(f"状态码: {cas_res.status_code}")
    print("响应内容:", cas_res.text)

except requests.exceptions.Timeout:
    print("请求超时，请检查网络或调整超时时间。")
except Exception as e:
    print(f"登录请求异常: {e}")

# res = requests.get(url, headers=headers)  # 获取json数据（获取后为字典）
# res = res.json()
# items = []
#
# for item in res['data']['item']:  # 找到字典里data里的item
#     title = item['title']  # 找到item里的title（标题）
#     pic_url = item['pic']  # 找到item里的pic（图片链接）
#     print(f"标题: {title}")
#     print(f"图片链接: {pic_url}")
#     print()  # 打印一个空行以分隔不同的视频信息
#     items.append({'title': title, 'img_url': pic_url})  # 将字典添加到列表中
#
#
# # 读取HTML模板内容
# env = Environment(loader=FileSystemLoader('.'))  # 假设模板文件在当前目录下
# template = env.get_template('重新装填.html')  # 加载模板文件
#
# # 渲染模板并传递数据
# final_content = template.render(items=items)  # 注意这里我们使用items变量来传递数据
#
# # 步骤 4: 保存HTML文件
# with open('index.html', 'w', encoding='utf-8') as f:
#     f.write(final_content)
#
# print('HTML文件已生成，请在浏览器中打开index.html文件。')