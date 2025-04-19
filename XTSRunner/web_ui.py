# 添加一个简单的Web界面
from flask import Flask, render_template, request, jsonify
import threading
import subprocess
import os

# 创建Flask应用，指定模板文件夹路径
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)

# 全局变量存储测试状态
test_status = {
    "running": False,
    "repo_type": None,
    "progress": 0,
    "total": 0,
    "current_lib": "",
    "logs": []
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start_test', methods=['POST'])
def start_test():
    if test_status["running"]:
        return jsonify({"status": "error", "message": "测试已在运行中"})
    
    data = request.json
    repo_type = data.get("repo_type")
    sdk_version = data.get("sdk_version")
    release_mode = data.get("release_mode", "n")
    
    # 启动测试线程
    threading.Thread(target=run_test, args=(repo_type, sdk_version, release_mode)).start()
    
    return jsonify({"status": "success", "message": f"开始测试 {repo_type}"})

def run_test(repo_type, sdk_version, release_mode):
    global test_status
    test_status["running"] = True
    test_status["repo_type"] = repo_type
    test_status["progress"] = 0
    test_status["logs"] = []
    
    try:
        # 构建命令
        cmd = [
            "python", "run.py",
            "--group", repo_type,
            "--sdk-version", sdk_version,
            "--release-mode", release_mode
        ]
        
        # 执行命令并捕获输出
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 读取输出并更新状态
        for line in iter(process.stdout.readline, ''):
            test_status["logs"].append(line)
            
            # 解析进度信息
            if "开始执行第" in line and "个库" in line:
                parts = line.split('/')
                if len(parts) >= 2:
                    current = int(parts[0].split('第')[-1].strip())
                    total = int(parts[1].split('个')[0].strip())
                    test_status["progress"] = current
                    test_status["total"] = total
                    
                    # 提取当前库名
                    lib_name = line.split(':')[-1].strip()
                    test_status["current_lib"] = lib_name
        
        process.wait()
    finally:
        test_status["running"] = False

@app.route('/api/status')
def get_status():
    return jsonify(test_status)

if __name__ == '__main__':
    app.run(debug=True, port=5000)