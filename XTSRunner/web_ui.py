# 添加一个简单的Web界面
from flask import Flask, render_template, request, jsonify
import threading
import subprocess
import os
import sys
import locale
import signal
from ReportGenerator import register_completion_callback

# 创建Flask应用，指定模板文件夹路径
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)

# 获取系统默认编码
system_encoding = locale.getpreferredencoding()

# 全局变量存储测试状态
test_status = {
    "running": False,
    "repo_type": None,
    "progress": 0,
    "total": 0,
    "current_lib": "",
    "logs": []
}

# 全局变量存储当前运行的进程
current_process = None
process_lock = threading.Lock()

# 定义一个回调函数，在测试完成时重置状态
def reset_test_status():
    global test_status
    test_status["running"] = False
    test_status["logs"].append("测试和报告生成已完成，可以开始新的测试。")

# 注册回调函数
register_completion_callback(reset_test_status)

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
    
    # 重置测试状态
    test_status["running"] = True
    test_status["repo_type"] = repo_type
    test_status["progress"] = 0
    test_status["total"] = 0
    test_status["current_lib"] = ""
    test_status["logs"] = ["开始测试..."]
    
    # 启动测试线程
    threading.Thread(target=run_test, args=(repo_type, sdk_version, release_mode)).start()
    
    return jsonify({"status": "success", "message": f"开始测试 {repo_type}"})

@app.route('/api/stop_test', methods=['POST'])
def stop_test():
    global current_process, test_status
    
    if not test_status["running"]:
        return jsonify({"status": "error", "message": "当前没有测试在运行"})
    
    with process_lock:
        if current_process is not None:
            try:
                # 在Windows上，使用taskkill命令强制终止进程树
                if os.name == 'nt':
                    # 向main.py发送中断信号
                    import signal
                    # 先尝试发送SIGTERM信号，让main.py有机会设置interrupted标志
                    os.kill(current_process.pid, signal.SIGTERM)
                    # 等待一小段时间让信号处理程序执行
                    time.sleep(0.5)
                    # 然后使用taskkill强制终止进程树
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(current_process.pid)], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    # 在Unix系统上使用SIGTERM信号
                    os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
                
                test_status["logs"].append("测试已被用户中断")
                test_status["running"] = False
                current_process = None
                return jsonify({"status": "success", "message": "测试已中断"})
            except Exception as e:
                return jsonify({"status": "error", "message": f"中断测试失败: {str(e)}"})
        else:
            test_status["running"] = False
            return jsonify({"status": "warning", "message": "没有找到正在运行的测试进程"})

def run_test(repo_type, sdk_version, release_mode):
    global test_status, current_process
    
    try:
        # 构建命令
        cmd = [
            "python", "run.py",
            "--group", repo_type,
            "--sdk-version", sdk_version,
            "--release-mode", release_mode
        ]
        
        # 执行命令并捕获输出
        with process_lock:
            # 在Windows上，创建新进程组以便于后续终止整个进程树
            if os.name == 'nt':
                current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # 在Unix系统上，使用preexec_fn设置进程组
                current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    preexec_fn=os.setsid
                )
        
        # 读取输出并更新状态
        while True:
            line_bytes = current_process.stdout.readline()
            if not line_bytes:
                break
                
            # 先尝试UTF-8，然后系统编码，最后latin-1
            try:
                line = line_bytes.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    line = line_bytes.decode(system_encoding)
                except UnicodeDecodeError:
                    line = line_bytes.decode('latin-1')
                
            line = line.rstrip('\r\n')
            if line:  # 只添加非空行
                test_status["logs"].append(line)
                
                # 解析进度信息
                if "开始执行第" in line and "个库" in line:
                    try:
                        parts = line.split('/')
                        if len(parts) >= 2:
                            current_part = parts[0].split('第')[-1].strip()
                            total_part = parts[1].split('个')[0].strip()
                            
                            # 确保提取的是数字
                            current = int(current_part)
                            total = int(total_part)
                            
                            test_status["progress"] = current
                            test_status["total"] = total
                            
                            # 提取当前库名
                            lib_name = line.split(':')[-1].strip()
                            test_status["current_lib"] = lib_name
                    except (ValueError, IndexError) as e:
                        # 解析错误时添加到日志但不中断
                        test_status["logs"].append(f"解析进度信息出错: {str(e)}")
                
                # 检测测试完成信息
                if "所有测试报告已生成完成" in line:
                    test_status["logs"].append("测试和报告生成已完成，可以开始新的测试。")
                    test_status["running"] = False
        
        current_process.wait()
        
        # 确保在进程结束后设置running为False
        if test_status["running"]:
            test_status["logs"].append("测试进程已结束，可以开始新的测试。")
            test_status["running"] = False
            
        # 清理进程引用
        with process_lock:
            current_process = None
            
    except Exception as e:
        # 捕获所有异常并添加到日志
        error_msg = f"测试执行出错: {str(e)}"
        test_status["logs"].append(error_msg)
        import traceback
        test_status["logs"].append(traceback.format_exc())
        # 确保在出错时也设置running为False
        test_status["running"] = False

@app.route('/api/status')
def get_status():
    return jsonify(test_status)

def start_web_ui():
    """启动Web UI"""
    print("启动Web界面...")
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
