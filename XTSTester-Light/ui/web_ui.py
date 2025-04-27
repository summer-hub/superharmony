import time

from flask import Flask, render_template, request, jsonify
import threading
import subprocess
import os
import locale
import uuid
from reports.ReportGenerator import register_completion_callback

# 创建Flask应用，指定模板文件夹路径
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# 获取系统默认编码
system_encoding = locale.getpreferredencoding()

# 全局变量存储所有测试进程的状态
test_processes = {}
process_lock = threading.Lock()

# 定义一个回调函数，在测试完成时重置状态
def reset_test_status(process_id):
    with process_lock:
        if process_id in test_processes:
            test_processes[process_id]["running"] = False
            test_processes[process_id]["logs"].append("测试和报告生成已完成，可以开始新的测试。")

# 注册回调函数 - 这里需要修改原有的回调机制以支持多进程
# 注意：这里假设ReportGenerator可以接受进程ID参数，如果不行需要另外处理
register_completion_callback(reset_test_status)

@app.route('/')
def index():
    return render_template('index.html')

# 添加新的API端点用于搜索库
@app.route('/api/search_libraries', methods=['POST'])
def search_libraries():
    data = request.json
    search_term = data.get("search_term", "")
    
    if not search_term:
        return jsonify({"status": "error", "message": "搜索词不能为空"})
    
    try:
        # 导入模糊匹配函数
        from core.ReadExcel import fuzzy_match_libraries
        
        # 执行模糊匹配
        matched_libraries = fuzzy_match_libraries(search_term)
        
        return jsonify({
            "status": "success", 
            "libraries": matched_libraries,
            "count": len(matched_libraries)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"搜索库时出错: {str(e)}"})

# 修改启动测试的API端点，支持特定库测试
@app.route('/api/start_test', methods=['POST'])
def start_test():
    data = request.json
    repo_type = data.get("repo_type")
    sdk_version = data.get("sdk_version")
    release_mode = data.get("release_mode", "n")
    specific_library = data.get("specific_library")  # 可能是逗号分隔的多个库
    
    # 创建新的进程ID
    process_id = str(uuid.uuid4())
    
    # 处理多个库的情况
    specific_libraries = None
    if specific_library:
        specific_libraries = [lib.strip() for lib in specific_library.split(',')]
    
    # 初始化测试状态
    with process_lock:
        test_processes[process_id] = {
            "running": True,
            "repo_type": "auto" if specific_libraries else repo_type,  # 如果指定了特定库，则使用auto模式
            "progress": 0,
            "total": 0,
            "current_lib": "",
            "logs": ["开始测试..."],
            "start_time": time.time(),
            "specific_libraries": specific_libraries  # 保存特定库信息
        }
    
    # 启动测试线程
    threading.Thread(target=run_test, args=(process_id, repo_type, sdk_version, release_mode, specific_libraries)).start()
    
    return jsonify({
        "status": "success", 
        "message": f"开始测试 {specific_library if specific_library else repo_type}", 
        "process_id": process_id
    })

@app.route('/api/stop_test', methods=['POST'])
def stop_test():
    data = request.json
    process_id = data.get("process_id")
    
    if not process_id or process_id not in test_processes:
        return jsonify({"status": "error", "message": "无效的进程ID"})
    
    if not test_processes[process_id]["running"]:
        return jsonify({"status": "error", "message": "当前没有测试在运行"})
    
    with process_lock:
        process = test_processes[process_id].get("process")
        if process is not None:
            try:
                # 在Windows上，使用taskkill命令强制终止进程树
                if hasattr(process, 'pid'):
                    # 向进程发送中断信号
                    import signal
                    # 先尝试发送SIGTERM信号
                    os.kill(process.pid, signal.SIGTERM)
                    # 等待一小段时间让信号处理程序执行
                    time.sleep(0.5)
                    # 然后使用taskkill强制终止进程树
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    test_processes[process_id]["logs"].append("无法获取进程PID，进程可能已经结束")
                
                test_processes[process_id]["logs"].append("测试已被用户中断")
                test_processes[process_id]["running"] = False
                test_processes[process_id]["process"] = None
                return jsonify({"status": "success", "message": "测试已中断"})
            except Exception as e:
                return jsonify({"status": "error", "message": f"中断测试失败: {str(e)}"})
        else:
            test_processes[process_id]["running"] = False
            return jsonify({"status": "warning", "message": "没有找到正在运行的测试进程"})

# 修改测试执行函数，支持多个特定库测试
def run_test(process_id, repo_type, sdk_version, release_mode, specific_libraries=None):
    try:
        # 构建命令
        cmd = [
            "python", "run.py",
            "--sdk-version", sdk_version,
            "--release-mode", release_mode
        ]
        
        # 如果指定了特定库，则使用auto模式并传递特定库参数
        if specific_libraries:
            cmd.extend(["--group", "auto"])
            # 将多个库作为命令行参数传递
            for lib in specific_libraries:
                cmd.extend(["--specific-libraries", lib])
        else:
            cmd.extend(["--group", repo_type])
        
        # 执行命令并捕获输出
        with process_lock:
            # 在Windows上，创建新进程组以便于后续终止整个进程树
            if os.name == 'nt':
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # 在Unix系统上，使用preexec_fn设置进程组
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    preexec_fn=os.setsid
                )
            
            # 存储进程对象
            test_processes[process_id]["process"] = process
        
        # 读取输出并更新状态
        while True:
            line_bytes = process.stdout.readline()
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
                with process_lock:
                    # 限制日志数量，防止内存占用过大
                    if len(test_processes[process_id]["logs"]) > 1000:
                        # 保留最新的900条日志
                        test_processes[process_id]["logs"] = test_processes[process_id]["logs"][-900:]
                        test_processes[process_id]["logs"].append("[...日志过多，已截断...]")
                    
                    test_processes[process_id]["logs"].append(line)
                
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
                            
                            with process_lock:
                                test_processes[process_id]["progress"] = current
                                test_processes[process_id]["total"] = total
                            
                            # 提取当前库名
                            lib_name = line.split(':')[-1].strip()
                            with process_lock:
                                test_processes[process_id]["current_lib"] = lib_name
                    except (ValueError, IndexError) as e:
                        # 解析错误时添加到日志但不中断
                        with process_lock:
                            test_processes[process_id]["logs"].append(f"解析进度信息出错: {str(e)}")
                
                # 检测测试完成信息
                if "所有测试报告已生成完成" in line:
                    with process_lock:
                        test_processes[process_id]["logs"].append("测试和报告生成已完成，可以开始新的测试。")
                        test_processes[process_id]["running"] = False
        
        process.wait()
        
        # 确保在进程结束后设置running为False
        with process_lock:
            if process_id in test_processes and test_processes[process_id]["running"]:
                test_processes[process_id]["logs"].append("测试进程已结束，可以开始新的测试。")
                test_processes[process_id]["running"] = False
                test_processes[process_id]["process"] = None
            
    except Exception as e:
        # 捕获所有异常并添加到日志
        error_msg = f"测试执行出错: {str(e)}"
        with process_lock:
            if process_id in test_processes:
                test_processes[process_id]["logs"].append(error_msg)
                import traceback
                test_processes[process_id]["logs"].append(traceback.format_exc())
                # 确保在出错时也设置running为False
                test_processes[process_id]["running"] = False
                test_processes[process_id]["process"] = None

@app.route('/api/status')
def get_status():
    process_id = request.args.get('process_id')
    
    # 如果提供了进程ID，返回该进程的详细信息
    if process_id and process_id in test_processes:
        # Create a serializable copy of the process data
        process_data = test_processes[process_id].copy()
        
        # Remove the non-serializable Popen object
        if 'process' in process_data:
            # Check if process is still running, but handle None case
            if process_data['process'] is not None:
                is_running = process_data['process'].poll() is None
                process_data['running'] = is_running
            # Always delete the process object as it's not serializable
            del process_data['process']
        
        return jsonify(process_data)
    
    # 如果没有提供进程ID或进程ID不存在，返回所有进程的摘要
    elif not process_id:
        with process_lock:
            process_summary = {}
            for pid, process_data in test_processes.items():
                # 只返回必要的信息，不包括完整日志
                process_summary[pid] = {
                    "running": process_data["running"],
                    "repo_type": process_data["repo_type"],
                    "progress": process_data["progress"],
                    "total": process_data["total"],
                    "current_lib": process_data["current_lib"],
                    "start_time": process_data.get("start_time", 0)
                }
            return jsonify({"processes": process_summary})
    
    # 如果进程ID不存在
    else:
        return jsonify({'error': 'Process not found'}), 404

@app.route('/api/logs')
def get_logs():
    process_id = request.args.get('process_id')
    start_index = int(request.args.get('start_index', 0))
    
    if not process_id or process_id not in test_processes:
        return jsonify({"status": "error", "message": "无效的进程ID"})
    
    with process_lock:
        logs = test_processes[process_id]["logs"]
        # 只返回请求的部分日志，减少数据传输量
        return jsonify({
            "logs": logs[start_index:],
            "total_logs": len(logs)
        })

@app.route('/api/cleanup', methods=['POST'])
def cleanup_process():
    data = request.json
    process_id = data.get("process_id")
    
    if not process_id or process_id not in test_processes:
        return jsonify({"status": "error", "message": "无效的进程ID"})
    
    with process_lock:
        # 如果进程仍在运行，先尝试停止它
        if test_processes[process_id]["running"]:
            return jsonify({"status": "error", "message": "进程仍在运行，请先停止测试"})
        
        # 删除进程数据
        del test_processes[process_id]
        return jsonify({"status": "success", "message": "进程数据已清理"})

def start_web_ui():
    """启动Web UI"""
    print("启动Web界面...")
    app.run(host='0.0.0.0', port=5000, debug=False)

# 在 web_ui.py 中添加测试状态接口
@app.route('/api/test_status/<process_id>')
def test_status(process_id):
    with process_lock:
        if process_id in test_processes:
            # 创建一个可序列化的副本
            process_data = test_processes[process_id].copy()
            
            # 移除不可序列化的 Popen 对象
            if 'process' in process_data:
                # 检查进程是否仍在运行，但处理 None 的情况
                if process_data['process'] is not None:
                    is_running = process_data['process'].poll() is None
                    process_data['running'] = is_running
                # 始终删除进程对象，因为它不可序列化
                del process_data['process']
            
            # 如果有 specific_libraries，转换为字符串以便于前端显示
            if 'specific_libraries' in process_data and process_data['specific_libraries']:
                process_data['specific_libraries_str'] = ', '.join(process_data['specific_libraries'])
            
            return jsonify({"status": "success", **process_data})
        else:
            return jsonify({"status": "error", "message": "找不到指定的测试进程"}), 404


@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')