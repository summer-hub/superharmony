import sys
import os
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QLineEdit, QFormLayout, QMessageBox, QComboBox,
                             QCheckBox, QGroupBox, QDialog)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont

# 确保能够导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import config

class ConfigDialog(QDialog):
    """配置对话框，用于设置关键路径和参数"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('XTSTester', 'XTSConfig')
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """初始化UI界面"""
        # 设置窗口标题和大小
        self.setWindowTitle('XTS测试工具配置')
        self.setMinimumWidth(600)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 创建表单布局
        form_layout = QFormLayout()
        
        # DevEco Studio路径
        self.deveco_dir_edit = QLineEdit()
        self.deveco_dir_button = QPushButton('浏览...')
        self.deveco_dir_button.clicked.connect(lambda: self.browse_directory(self.deveco_dir_edit, '选择DevEco Studio安装目录'))
        deveco_layout = QHBoxLayout()
        deveco_layout.addWidget(self.deveco_dir_edit)
        deveco_layout.addWidget(self.deveco_dir_button)
        form_layout.addRow('DevEco Studio目录:', deveco_layout)
        
        # Excel文件路径
        self.excel_file_edit = QLineEdit()
        self.excel_file_button = QPushButton('浏览...')
        self.excel_file_button.clicked.connect(lambda: self.browse_file(self.excel_file_edit, '选择测试表格文件', '表格文件 (*.xlsx);;所有文件 (*.*)'))
        excel_layout = QHBoxLayout()
        excel_layout.addWidget(self.excel_file_edit)
        excel_layout.addWidget(self.excel_file_button)
        form_layout.addRow('测试表格文件:', excel_layout)
        
        # SDK版本选择
        self.sdk_version_combo = QComboBox()
        for version in config.SDK_API_MAPPING.keys():
            self.sdk_version_combo.addItem(version)
        form_layout.addRow('SDK版本:', self.sdk_version_combo)
        
        # Release模式选择
        self.release_mode_check = QCheckBox('启用')
        form_layout.addRow('Release模式编译:', self.release_mode_check)
        
        main_layout.addLayout(form_layout)
        
        # 添加按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        # 保存按钮
        self.save_button = QPushButton('保存配置')
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        # 取消按钮
        self.cancel_button = QPushButton('取消')
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
    
    def browse_directory(self, line_edit, title):
        """浏览并选择目录"""
        directory = QFileDialog.getExistingDirectory(self, title, line_edit.text())
        if directory:
            line_edit.setText(directory)
    
    def browse_file(self, line_edit, title, filter_str):
        """浏览并选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, title, line_edit.text(), filter_str)
        if file_path:
            line_edit.setText(file_path)
    
    def load_settings(self):
        """从配置文件加载设置"""
        # 尝试从QSettings加载
        deveco_dir = self.settings.value('deveco_dir', config.DEVECO_DIR)
        excel_file = self.settings.value('excel_file', config.EXCEL_FILE_PATH)
        sdk_version = self.settings.value('sdk_version', list(config.SDK_API_MAPPING.keys())[-1])
        release_mode = self.settings.value('release_mode', False, type=bool)
        
        # 设置UI控件的值
        self.deveco_dir_edit.setText(deveco_dir)
        self.excel_file_edit.setText(excel_file)
        
        # 设置SDK版本
        index = self.sdk_version_combo.findText(sdk_version)
        if index >= 0:
            self.sdk_version_combo.setCurrentIndex(index)
        
        # 设置Release模式
        self.release_mode_check.setChecked(release_mode)
    
    def save_settings(self):
        """保存设置到配置文件"""
        # 获取UI控件的值
        deveco_dir = self.deveco_dir_edit.text()
        excel_file = self.excel_file_edit.text()
        sdk_version = self.sdk_version_combo.currentText()
        release_mode = self.release_mode_check.isChecked()
        
        # 验证路径
        if not os.path.exists(deveco_dir):
            QMessageBox.warning(self, '警告', 'DevEco Studio目录不存在，请检查路径!')
            return
        
        if not os.path.exists(excel_file):
            QMessageBox.warning(self, '警告', '测试表格文件不存在，请检查路径!')
            return
        
        # 保存到QSettings
        self.settings.setValue('deveco_dir', deveco_dir)
        self.settings.setValue('excel_file', excel_file)
        self.settings.setValue('sdk_version', sdk_version)
        self.settings.setValue('release_mode', release_mode)
        
        # 更新config模块中的值
        config.DEVECO_DIR = deveco_dir
        config.DEVECO_PATH = os.path.join(deveco_dir, r"bin\devecostudio64.exe")
        config.hvigor_path = os.path.join(deveco_dir, r"tools\hvigor\bin\hvigorw.js")
        config.ohpm_path = os.path.join(deveco_dir, r"tools\ohpm\bin\ohpm.bat")
        config.EXCEL_FILE_PATH = excel_file
        config.set_sdk_version(sdk_version)
        config.set_release_mode(release_mode)
        
        QMessageBox.information(self, '成功', '配置已保存!')
        self.accept()


def show_config_dialog(parent=None):
    """显示配置对话框并返回是否成功配置"""
    dialog = ConfigDialog(parent)
    result = dialog.exec_()
    return result == QDialog.Accepted


if __name__ == '__main__':
    app = QApplication(sys.argv)
    show_config_dialog()
    sys.exit(app.exec_())