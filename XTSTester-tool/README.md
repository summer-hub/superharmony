# XTSTester-tool - OpenHarmony三方库测试工具（Windows版）

## 项目介绍
XTSTester-tool是一个专为OpenHarmony三方库设计的自动化测试工具的Windows兼容版本，支持命令行和交互式两种运行模式，能够自动执行测试用例并生成详细的测试报告。

## 技术架构
- **核心模块**: 
  - 测试执行引擎(main.py)
  - 并行测试框架(parallel/)
  - 报告生成系统(reports/)
- **依赖技术**:
  - Python 3.8+
  - Colorama (终端彩色输出)
  - Flask (Web界面)

## 目录结构
```
XTSTester-tool/
├── core/            # 核心测试逻辑
├── data/            # 测试数据
├── Libraries/       # 测试库资源
├── parallel/        # 并行测试模块
├── reports/         # 报告生成模块
├── results/         # 测试结果输出
├── ui/              # Web界面
├── utils/           # 工具函数
├── main.py          # 主测试程序
├── run.py           # 入口脚本
└── requirements.txt # 依赖包列表
```

## 安装依赖
```bash
pip install -r requirements.txt
```

## 使用说明
### 1. 命令行模式
```bash
python run.py --group openharmony-sig --sdk-version 5.0.4 --release-mode y
```

### 2. 交互模式
```bash
python run.py
```

### 3. 并行模式
```bash
python run.py --parallel
```

### 4. Web界面模式
```bash
python run.py --web-ui
```
然后在浏览器中访问 http://localhost:5000

## 配置说明
在首次运行前，请确保在utils/config.py中正确配置以下参数：
- 开发工具路径
- SDK版本
- 签名配置

## Windows兼容性说明
本工具已针对Windows环境进行了优化，主要改进包括：
1. 路径处理兼容Windows格式
2. 系统命令执行使用Windows兼容方式
3. 进程管理适配Windows环境
4. 文件操作使用跨平台API

## 注意事项
- 确保Python 3.8+已正确安装
- 确保Git已安装并添加到系统PATH
- 首次运行时会自动检查并提示缺少的依赖