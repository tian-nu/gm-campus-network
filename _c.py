import subprocess
subprocess.run(["git", "add", "-A"], check=True)
subprocess.run(["git", "commit", "-m", "docs: 重写 README，简洁功能介绍 + 代理 Q&A"], check=True)
print("Commit done")
