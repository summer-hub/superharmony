import sys
import os
import json
import time
import threading
import subprocess
import uuid
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QTreeWidget, QTreeWidgetItem, QProgressBar, 
                             QSplitter, QFrame, QTextEdit, QMessageBox,
                             QComboBox, QGroupBox, QRadioButton, QLineEdit,
                             QTabWidget, QStatusBar, QCheckBox)
from PyQt5.QtCore import Qt, QSize, QSettings, pyqtSignal, QThread, QMutex
from PyQt5.QtGui import QIcon, QColor, QFont, QTextCursor

# 确保能够导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import config
from ui.config_gui import show_config_dialog

# 尝试导入模糊匹配函数
try:
    from core.ReadExcel import fuzzy_match_libraries
except ImportError:
    def fuzzy_match_libraries(search_term):
        return []

class TestOutputThread(QThread):
    """测试输出线程，用于实时显示测试输出"""
    output_received = pyqtSignal(str)
    test_completed = pyqtSignal(bool, str)
    progress_updated = pyqtSignal(int, int, str)
    
    def __init__(self, cmd, parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self.process = None
        self.running = True
        self.mutex = QMutex()
    
    def run(self):
        try:
            # 在Windows上，创建新进程组以便于后续终止整个进程树
            if os.name == 'nt':
                self.process = subprocess.Popen(
                    self.cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
            else:
                # 在Unix系统上，使用preexec_fn设置进程组
                self.process = subprocess.Popen(
                    self.cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    preexec_fn=os.setsid,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
            
            # 读取输出并发送信号
            while self.running:
                line = self.process.stdout.readline()
                if not line:
                    break
                
                line = line.rstrip('\r\n')
                if line:  # 只处理非空行
                    self.output_received.emit(line)
                    
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
                                
                                # 提取当前库名
                                lib_name = line.split(':')[-1].strip()
                                self.progress_updated.emit(current, total, lib_name)
                        except (ValueError, IndexError) as e:
                            self.output_received.emit(f"解析进度信息出错: {str(e)}")
                    
                    # 检测测试完成信息
                    if "所有测试报告已生成完成" in line:
                        self.test_completed.emit(True, "测试和报告生成已完成，可以查看测试报告。")
            
            # 等待进程结束
            self.process.wait()
            
            # 发送测试完成信号
            if self.running:  # 只有在没有被手动停止的情况下才发送
                self.test_completed.emit(True, "测试进程已结束，可以开始新的测试。")
        
        except Exception as e:
            # 捕获所有异常并发送信号
            error_msg = f"测试执行出错: {str(e)}"
            self.output_received.emit(error_msg)
            import traceback
            self.output_received.emit(traceback.format_exc())
            self.test_completed.emit(False, error_msg)
    
    def stop(self):
        """停止测试进程"""
        self.mutex.lock()
        self.running = False
        if self.process and self.process.poll() is None:
            try:
                # 在Windows上，使用taskkill命令强制终止进程树
                if hasattr(self.process, 'pid'):
                    # 先尝试发送SIGTERM信号
                    import signal
                    try:
                        os.kill(self.process.pid, signal.SIGTERM)
                        # 等待一小段时间让信号处理程序执行
                        time.sleep(0.5)
                    except:
                        pass
                    # 然后使用taskkill强制终止进程树
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception as e:
                print(f"停止进程时出错: {str(e)}")
        self.mutex.unlock()


class MainGUI(QMainWindow):
    """XTS测试工具主界面"""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings('XTSTester', 'XTSMain')
        self.test_thread = None
        self.process_id = None
        self.init_ui()
        self.load_settings()
        
        # 检查配置
        self.check_config()
    
    def init_ui(self):
        """初始化UI界面"""
        # 设置窗口标题和大小
        self.setWindowTitle('XTS测试工具')
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建顶部工具栏
        toolbar_layout = QHBoxLayout()
        
        # 添加配置按钮
        self.config_button = QPushButton('配置设置')
        self.config_button.setMinimumWidth(120)
        self.config_button.clicked.connect(self.show_config)
        toolbar_layout.addWidget(self.config_button)
        
        # 添加查看结果按钮
        self.view_results_button = QPushButton('查看测试结果')
        self.view_results_button.setMinimumWidth(120)
        self.view_results_button.clicked.connect(self.show_test_results)
        toolbar_layout.addWidget(self.view_results_button)
        
        # 添加间隔
        toolbar_layout.addStretch(1)
        
        main_layout.addLayout(toolbar_layout)
        
        # 创建选项卡部件
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 创建测试选项卡
        self.test_tab = QWidget()
        self.tab_widget.addTab(self.test_tab, '测试执行')
        
        # 创建测试选项卡布局
        test_layout = QVBoxLayout(self.test_tab)
        
        # 创建测试选项组
        test_options_group = QGroupBox('测试选项')
        test_options_layout = QVBoxLayout(test_options_group)
        
        # 创建库类型选择
        repo_type_layout = QHBoxLayout()
        repo_type_label = QLabel('库类型:')
        repo_type_layout.addWidget(repo_type_label)
        
        self.repo_type_combo = QComboBox()
        self.repo_type_combo.addItems(['sig', 'tpc', 'samples', 'auto'])
        repo_type_layout.addWidget(self.repo_type_combo)
        
        # 添加SDK版本显示
        sdk_version_label = QLabel('SDK版本:')
        repo_type_layout.addWidget(sdk_version_label)
        
        self.sdk_version_label = QLabel('未设置')
        self.sdk_version_label.setStyleSheet('font-weight: bold;')
        repo_type_layout.addWidget(self.sdk_version_label)
        
        # 添加Release模式显示
        release_mode_label = QLabel('Release模式:')
        repo_type_layout.addWidget(release_mode_label)
        
        self.release_mode_label = QLabel('未启用')
        self.release_mode_label.setStyleSheet('font-weight: bold;')
        repo_type_layout.addWidget(self.release_mode_label)
        
        repo_type_layout.addStretch(1)
        test_options_layout.addLayout(repo_type_layout)
        
        # 创建特定库搜索和选择
        specific_lib_layout = QHBoxLayout()
        specific_lib_label = QLabel('特定库测试:')
        specific_lib_layout.addWidget(specific_lib_label)
        
        self.specific_lib_edit = QLineEdit()
        self.specific_lib_edit.setPlaceholderText('输入库名进行搜索，多个库用逗号分隔')
        specific_lib_layout.addWidget(self.specific_lib_edit)
        
        self.search_lib_button = QPushButton('搜索')
        self.search_lib_button.clicked.connect(self.search_libraries)
        specific_lib_layout.addWidget(self.search_lib_button)
        
        test_options_layout.addLayout(specific_lib_layout)
        
        # 创建库搜索结果显示
        self.lib_results_tree = QTreeWidget()
        self.lib_results_tree.setHeaderLabels(['库名称', '版本', '类型'])
        self.lib_results_tree.setColumnWidth(0, 400)
        self.lib_results_tree.setColumnWidth(1, 100)
        self.lib_results_tree.setColumnWidth(2, 100)
        self.lib_results_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        test_options_layout.addWidget(self.lib_results_tree)
        
        # 添加选中库按钮
        select_lib_layout = QHBoxLayout()
        select_lib_layout.addStretch(1)
        
        self.select_lib_button = QPushButton('添加选中的库')
        self.select_lib_button.clicked.connect(self.add_selected_libraries)
        select_lib_layout.addWidget(self.select_lib_button)
        
        self.clear_lib_button = QPushButton('清空选择')
        self.clear_lib_button.clicked.connect(self.clear_selected_libraries)
        select_lib_layout.addWidget(self.clear_lib_button)
        
        test_options_layout.addLayout(select_lib_layout)
        
        # 创建已选库显示
        selected_lib_layout = QHBoxLayout()
        selected_lib_label = QLabel('已选库:')
        selected_lib_layout.addWidget(selected_lib_label)
        
        self.selected_lib_edit = QLineEdit()
        self.selected_lib_edit.setReadOnly(True)
        selected_lib_layout.addWidget(self.selected_lib_edit)
        
        test_options_layout.addLayout(selected_lib_layout)
        
        test_layout.addWidget(test_options_group)
        
        # 创建测试控制组
        test_control_group = QGroupBox('测试控制')
        test_control_layout = QHBoxLayout(test_control_group)
        
        # 添加开始测试按钮
        self.start_test_button = QPushButton('开始测试')
        self.start_test_button.setMinimumWidth(120)
        self.start_test_button.clicked.connect(self.start_test)
        test_control_layout.addWidget(self.start_test_button)
        
        # 添加停止测试按钮
        self.stop_test_button = QPushButton('停止测试')
        self.stop_test_button.setMinimumWidth(120)
        self.stop_test_button.setEnabled(False)
        self.stop_test_button.clicked.connect(self.stop_test)
        test_control_layout.addWidget(self.stop_test_button)
        
        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat('%v/%m - %p% - %s')
        self.progress_bar.setValue(0)
        test_control_layout.addWidget(self.progress_bar)
        
        test_layout.addWidget(test_control_group)
        
        # 创建测试输出组
        test_output_group = QGroupBox('测试输出')
        test_output_layout = QVBoxLayout(test_output_group)
        
        # 添加测试输出文本框
        self.test_output_text = QTextEdit()
        self.test_output_text.setReadOnly(True)
        self.test_output_text.setLineWrapMode(QTextEdit.NoWrap)
        self.test_output_text.setFont(QFont('Courier New', 9))
        test_output_layout.addWidget(self.test_output_text)
        
        test_layout.addWidget(test_output_group)
        
        # 创建状态栏
        self.statusBar().showMessage('就绪')
    
    def load_settings(self):
        """加载设置"""
        # 更新SDK版本和Release模式显示
        if config.selected_sdk_version:
            self.sdk_version_label.setText(config.selected_sdk_version)
        
        if config.get_release_mode():
            self.release_mode_label.setText('已启用')
            self.release_mode_label.setStyleSheet('font-weight: bold; color: green;')
        else:
            self.release_mode_label.setText('未启用')
            self.release_mode_label.setStyleSheet('font-weight: bold; color: red;')
        
        # 加载上次选择的库类型
        repo_type = self.settings.value('repo_type', 'sig')
        index = self.repo_type_combo.findText(repo_type)
        if index >= 0:
            self.repo_type_combo.setCurrentIndex(index)
        
        # 加载上次选择的特定库
        specific_libs = self.settings.value('specific_libs', '')
        self.selected_lib_edit.setText(specific_libs)
    
    def save_settings(self):
        """保存设置"""
        self.settings.setValue('repo_type', self.repo_type_combo.currentText())
        self.settings.setValue('specific_libs', self.selected_lib_edit.text())
    
    def check_config(self):
        """检查配置是否完整"""
        if not os.path.exists(config.DEVECO_DIR) or not os.path.exists(config.EXCEL_FILE_PATH):
            QMessageBox.warning(self, '配置不完整', '请先完成基本配置设置!')
            self.show_config()
    
    def show_config(self):
        """显示配置对话框"""
        if show_config_dialog(self):
            # 配置已更新，刷新显示
            self.load_settings()
    
    def show_test_results(self):
        """打开测试报告目录"""
        report_dir = config.REPORT_DIR
        if os.path.exists(report_dir):
            # 使用系统默认程序打开目录
            import subprocess
            if os.name == 'nt':  # Windows
                os.startfile(report_dir)
            elif os.name == 'posix':  # Linux, Mac
                subprocess.call(['xdg-open', report_dir])
            self.statusBar().showMessage(f'已打开报告目录: {report_dir}')
        else:
            QMessageBox.warning(self, '警告', f'报告目录不存在: {report_dir}')
            self.statusBar().showMessage('报告目录不存在')
    
    def search_libraries(self):
        """搜索库"""
        search_term = self.specific_lib_edit.text().strip()
        if not search_term:
            QMessageBox.warning(self, '警告', '请输入搜索关键词!')
            return
        
        try:
            # 执行模糊匹配
            matched_libraries = fuzzy_match_libraries(search_term)
            
            # 清空树
            self.lib_results_tree.clear()
            
            # 添加匹配的库到树
            for lib in matched_libraries:
                item = QTreeWidgetItem(self.lib_results_tree)
                if isinstance(lib, dict):
                    item.setText(0, lib.get('name', lib))
                    item.setText(1, lib.get('version', ''))
                    item.setText(2, lib.get('type', ''))
                else:
                    item.setText(0, str(lib))
                    item.setText(1, '')
                    item.setText(2, '')
            
            # 展开树
            self.lib_results_tree.expandAll()
            
            # 更新状态栏
            self.statusBar().showMessage(f'找到 {len(matched_libraries)} 个匹配的库')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'搜索库时出错: {str(e)}')
            self.statusBar().showMessage('搜索库失败')
    
    def add_selected_libraries(self):
        """添加选中的库到已选列表"""
        selected_items = self.lib_results_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, '警告', '请先选择要添加的库!')
            return
        
        # 获取当前已选库
        current_libs = self.selected_lib_edit.text().strip()
        selected_libs = [current_libs] if current_libs else []
        
        # 添加新选中的库
        for item in selected_items:
            lib_name = item.text(0)
            if lib_name not in selected_libs:
                selected_libs.append(lib_name)
        
        # 更新已选库显示
        self.selected_lib_edit.setText(', '.join(selected_libs))
    
    def clear_selected_libraries(self):
        """清空已选库"""
        self.selected_lib_edit.clear()
    
    def start_test(self):
        """开始测试"""
        # 检查配置
        if not os.path.exists(config.DEVECO_DIR) or not os.path.exists(config.EXCEL_FILE_PATH):
            QMessageBox.warning(self, '配置不完整', '请先完成基本配置设置!')
            self.show_config()
            return
        
        # 获取测试参数
        repo_type = self.repo_type_combo.currentText()
        specific_libraries = self.selected_lib_edit.text().strip()
        
        # 构建命令
        cmd = [
            "python", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run.py"),
            "--sdk-version", config.selected_sdk_version or list(config.SDK_API_MAPPING.keys())[-1],
            "--release-mode", "y" if config.get_release_mode() else "n"
        ]
        
        # 如果指定了特定库，则使用auto模式并传递特定库参数
        if specific_libraries:
            cmd.extend(["--group", "auto"])
            # 将多个库作为命令行参数传递
            for lib in specific_libraries.split(','):
                lib = lib.strip()
                if lib:  # 只添加非空库名
                    cmd.extend(["--specific-libraries", lib])
        else:
            cmd.extend(["--group", repo_type])
        
        # 创建进程ID
        self.process_id = str(uuid.uuid4())
        
        # 清空输出
        self.test_output_text.clear()
        self.append_output(f"开始测试 {specific_libraries if specific_libraries else repo_type}...")
        self.append_output(f"进程ID: {self.process_id}")
        self.append_output(f"命令: {' '.join(cmd)}")
        
        # 更新UI状态
        self.start_test_button.setEnabled(False)
        self.stop_test_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('%v/%m - %p% - 准备中...')
        self.statusBar().showMessage('测试运行中...')
        
        # 启动测试线程
        self.test_thread = TestOutputThread(cmd)
        self.test_thread.output_received.connect(self.append_output)
        self.test_thread.test_completed.connect(self.on_test_completed)
        self.test_thread.progress_updated.connect(self.update_progress)
        self.test_thread.start()
        
        # 保存设置
        self.save_settings()
    
    def stop_test(self):
        """停止测试"""
        if self.test_thread and self.test_thread.isRunning():
            reply = QMessageBox.question(self, '确认', '确定要停止当前测试吗？',
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.append_output("正在停止测试...")
                self.test_thread.stop()
                self.on_test_completed(False, "测试已被用户中断")
    
    def on_test_completed(self, success, message):
        """测试完成回调"""
        # 更新UI状态
        self.start_test_button.setEnabled(True)
        self.stop_test_button.setEnabled(False)
        
        # 添加完成消息
        self.append_output(message)
        
        # 更新状态栏
        if success:
            self.statusBar().showMessage('测试完成')
        else:
            self.statusBar().showMessage('测试中断')
    
    def update_progress(self, current, total, lib_name):
        """更新进度条"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f'%v/%m - %p% - {lib_name}')
    
    def append_output(self, text):
        """添加输出文本"""
        self.test_output_text.append(text)
        # 滚动到底部
        cursor = self.test_output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.test_output_text.setTextCursor(cursor)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 如果测试正在运行，询问是否确定关闭
        if self.test_thread and self.test_thread.isRunning():
            reply = QMessageBox.question(self, '确认', '测试正在运行，确定要关闭吗？',
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
            else:
                # 停止测试线程
                self.test_thread.stop()
        
        # 保存设置
        self.save_settings()
        
        # 接受关闭事件
        event.accept()


def main():
    """启动主界面"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName('XTS测试工具')
    app.setOrganizationName('XTSTester')
    
    # 创建并显示主窗口
    window = MainGUI()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()