import sys
import os
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QTreeWidget, QTreeWidgetItem, QProgressBar, 
                             QSplitter, QFrame, QTextEdit, QMessageBox, QMenu, QAction)
from PyQt5.QtCore import Qt, QSize, QSettings
from PyQt5.QtGui import QIcon, QColor, QFont

# 导入测试结果解析模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reports.ExtractTestDetails import extract_test_details, save_test_json
from utils import config

class TestResultsGUI(QMainWindow):
    """XTS测试结果可视化界面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.test_data = None
        self.settings = QSettings('XTSTester', 'XTSResults')
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """初始化UI界面"""
        # 设置窗口标题和大小
        self.setWindowTitle('XTS测试结果可视化工具')
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建顶部工具栏
        toolbar_layout = QHBoxLayout()
        
        # 添加打开文件按钮
        self.open_button = QPushButton('打开测试输出文件')
        self.open_button.setMinimumWidth(150)
        self.open_button.clicked.connect(self.open_test_output)
        toolbar_layout.addWidget(self.open_button)
        
        # 添加打开报告目录按钮
        self.open_report_dir_button = QPushButton('打开报告目录')
        self.open_report_dir_button.setMinimumWidth(150)
        self.open_report_dir_button.clicked.connect(self.open_report_directory)
        toolbar_layout.addWidget(self.open_report_dir_button)
        
        # 添加保存结果按钮
        self.save_button = QPushButton('保存为JSON')
        self.save_button.setMinimumWidth(150)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_results)
        toolbar_layout.addWidget(self.save_button)
        
        # 添加配置按钮
        self.config_button = QPushButton('配置设置')
        self.config_button.setMinimumWidth(150)
        self.config_button.clicked.connect(self.show_config)
        toolbar_layout.addWidget(self.config_button)
        
        # 添加间隔
        toolbar_layout.addStretch(1)
        
        # 添加测试摘要标签
        self.summary_label = QLabel('测试摘要: 尚未加载测试结果')
        self.summary_label.setStyleSheet('font-weight: bold;')
        toolbar_layout.addWidget(self.summary_label)
        
        main_layout.addLayout(toolbar_layout)
        
        # 创建分割器，用于分隔测试树和详情面板
        splitter = QSplitter(Qt.Horizontal)
        
        # 创建测试结果树
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(['测试项', '状态', '耗时'])
        self.results_tree.setColumnWidth(0, 500)
        self.results_tree.setColumnWidth(1, 100)
        self.results_tree.setColumnWidth(2, 100)
        self.results_tree.itemClicked.connect(self.show_test_details)
        splitter.addWidget(self.results_tree)
        
        # 创建详情面板
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        # 添加详情标题
        details_title = QLabel('测试详情')
        details_title.setStyleSheet('font-weight: bold; font-size: 14px;')
        details_layout.addWidget(details_title)
        
        # 添加详情内容
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        
        splitter.addWidget(details_widget)
        
        # 设置分割器的初始大小
        splitter.setSizes([600, 400])
        
        main_layout.addWidget(splitter)
        
        # 添加状态栏
        self.statusBar().showMessage('就绪')
        
        # 显示窗口
        self.show()
    
    def open_test_output(self):
        """打开测试输出文件并解析"""
        # 使用上次打开的目录作为起始目录
        start_dir = getattr(self, 'last_open_dir', os.path.join(config.PROJECT_DIR, 'results'))
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, '打开测试输出文件', start_dir, 
            '文本文件 (*.txt);;所有文件 (*.*)')
        
        if not file_path:
            return
        
        try:
            self.statusBar().showMessage(f'正在解析文件: {file_path}')
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                output_text = f.read()
            
            # 解析测试结果
            result_data = extract_test_details(output_text)
            self.test_data = result_data
            
            # 更新UI
            self.update_ui_with_results(result_data)
            
            self.statusBar().showMessage(f'成功解析文件: {file_path}')
            self.save_button.setEnabled(True)
            
            # 保存打开文件的目录
            self.last_open_dir = os.path.dirname(file_path)
            self.save_settings()
        except Exception as e:
            QMessageBox.critical(self, '错误', f'解析文件时出错: {str(e)}')
            self.statusBar().showMessage('解析文件失败')
    
    def update_ui_with_results(self, result_data):
        """使用测试结果更新UI"""
        if not result_data:
            return
        
        # 提取数据
        test_results = result_data['test_results']
        summary = result_data['summary']
        class_times = result_data['class_times']
        
        # 更新摘要信息
        total = summary['total']
        passed = summary['passed']
        failed = summary['failed']
        total_time = summary['total_time_ms']
        
        self.summary_label.setText(
            f'测试摘要: 总计 {total} 个测试, 通过 {passed} 个, '
            f'失败 {failed} 个, 总耗时 {total_time}ms')
        
        # 清空树
        self.results_tree.clear()
        
        # 添加测试类和测试方法到树
        for class_name, tests in test_results.items():
            # 创建测试类节点
            class_item = QTreeWidgetItem(self.results_tree)
            class_item.setText(0, class_name)
            
            # 检查测试类是否全部通过
            class_passed = all(test.get('status') == 'passed' for test in tests)
            class_time_ms = class_times.get(class_name, 0)
            
            # 设置测试类状态和耗时
            if class_passed:
                class_item.setText(1, '通过')
                class_item.setForeground(1, QColor('green'))
            else:
                class_item.setText(1, '失败')
                class_item.setForeground(1, QColor('red'))
            
            class_item.setText(2, f'{class_time_ms}ms')
            
            # 添加测试方法
            for test in tests:
                test_item = QTreeWidgetItem(class_item)
                test_item.setText(0, test.get('name', ''))
                
                # 设置测试方法状态和耗时
                status = test.get('status')
                if status == 'passed':
                    test_item.setText(1, '通过')
                    test_item.setForeground(1, QColor('green'))
                else:
                    test_item.setText(1, '失败')
                    test_item.setForeground(1, QColor('red'))
                
                test_item.setText(2, test.get('time', '0ms'))
                
                # 存储错误信息
                if 'error_stack' in test:
                    test_item.setData(0, Qt.UserRole, test['error_stack'])
        
        # 展开树
        self.results_tree.expandAll()
    
    def show_test_details(self, item, column):
        """显示选中测试项的详细信息"""
        # 清空详情
        self.details_text.clear()
        
        # 获取测试项名称
        test_name = item.text(0)
        status = item.text(1)
        time = item.text(2)
        
        # 构建详情文本
        details = f"<h3>{test_name}</h3>"
        details += f"<p><b>状态:</b> <span style='color: {'green' if status == '通过' else 'red'};'>{status}</span></p>"
        details += f"<p><b>耗时:</b> {time}</p>"
        
        # 如果有错误信息，显示错误信息
        error_stack = item.data(0, Qt.UserRole)
        if error_stack:
            details += f"<p><b>错误信息:</b></p>"
            details += f"<pre style='color: red;'>{error_stack}</pre>"
        
        # 设置详情文本
        self.details_text.setHtml(details)
    
    def save_results(self):
        """保存测试结果为JSON文件"""
        if not self.test_data:
            QMessageBox.warning(self, '警告', '没有可保存的测试结果')
            return
        
        # 使用上次打开的目录作为起始目录
        start_dir = getattr(self, 'last_open_dir', os.path.join(config.PROJECT_DIR, 'results'))
        suggested_name = os.path.join(start_dir, 'test_results.json')
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, '保存测试结果', suggested_name, 
            'JSON文件 (*.json);;所有文件 (*.*)')
        
        if not file_path:
            return
        
        try:
            # 保存测试结果
            save_test_json(
                self.test_data['test_results'],
                self.test_data['summary'],
                self.test_data['class_times'],
                file_path
            )
            
            self.statusBar().showMessage(f'测试结果已保存到: {file_path}')
            QMessageBox.information(self, '成功', f'测试结果已保存到: {file_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存文件时出错: {str(e)}')
            self.statusBar().showMessage('保存文件失败')

    def load_settings(self):
        """从配置文件加载设置"""
        # 加载上次打开的文件路径
        self.last_open_dir = self.settings.value('last_open_dir', os.path.join(config.PROJECT_DIR, 'results'))
    
    def save_settings(self):
        """保存设置到配置文件"""
        # 保存上次打开的文件路径
        self.settings.setValue('last_open_dir', self.last_open_dir)
    
    def show_config(self):
        """显示配置对话框"""
        try:
            from ui.config_gui import show_config_dialog
            if show_config_dialog(self):
                # 配置已更新，可能需要刷新某些显示
                pass
        except ImportError:
            QMessageBox.warning(self, '警告', '无法加载配置模块!')
    
    def open_report_directory(self):
        """打开报告目录"""
        report_dir = config.REPORT_DIR
        if os.path.exists(report_dir):
            # 检查目录下是否有HTML文件
            html_files = [f for f in os.listdir(report_dir) if f.lower().endswith('.html')]
            
            if html_files:
                # 如果有HTML文件，让用户选择打开哪个
                selected_file, _ = QFileDialog.getOpenFileName(
                    self, '选择要打开的HTML报告', 
                    report_dir, 'HTML文件 (*.html);;所有文件 (*.*)')
                
                if selected_file:
                    # 使用系统默认程序打开选中的HTML文件
                    import subprocess
                    if os.name == 'nt':  # Windows
                        os.startfile(selected_file)
                    elif os.name == 'posix':  # Linux, Mac
                        subprocess.call(['xdg-open', selected_file])
                    self.statusBar().showMessage(f'已打开HTML报告: {selected_file}')
                    return
            
            # 如果没有HTML文件或用户取消选择，保持原行为打开目录
            import subprocess
            if os.name == 'nt':  # Windows
                os.startfile(report_dir)
            elif os.name == 'posix':  # Linux, Mac
                subprocess.call(['xdg-open', report_dir])
            self.statusBar().showMessage(f'已打开报告目录: {report_dir}')
        else:
            QMessageBox.warning(self, '警告', f'报告目录不存在: {report_dir}')
            self.statusBar().showMessage('报告目录不存在')

def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName('XTS测试结果可视化工具')
    app.setOrganizationName('XTSTester')
    
    # 创建并显示主窗口
    window = TestResultsGUI()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()