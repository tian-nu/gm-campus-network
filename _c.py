import subprocess
subprocess.run(["git", "add", "-A"], check=True)
subprocess.run(["git", "commit", "-m", "fix: 修正学校名称为广州市工贸技师学院"], check=True)
subprocess.run(["git", "push", "origin", "main"], check=True)
print("Done")
