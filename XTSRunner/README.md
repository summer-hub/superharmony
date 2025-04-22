# XTSRunner - OpenHarmony三方库测试工具

## 项目介绍
XTSRunner是一个专为OpenHarmony三方库设计的自动化测试工具，支持命令行和交互式两种运行模式，能够自动执行测试用例并生成详细的测试报告。

## 技术架构
- **核心模块**: 
  - 测试执行引擎(main.py)
  - 并行测试框架(parallel/)
  - 报告生成系统(reports/)
- **依赖技术**:
  - Python 3.8+
  - Colorama (终端彩色输出)
  - Allure (测试报告生成)

## 目录结构
```
XTSTester/
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
└── run_parallel.bat # 并行测试批处理
```

## 前置配置
config.py 文件中需要配置以下参数：
- `DEVECO_DIR`: DEVECO_DIR路径
- `node_path`: node.js路径
- `hvigor_path`: hvigor路径
- `npm_path`: npm路径
- `ohpm_path`: ohpm路径
- `EXCEL_FILE_PATH`: 测试用例Excel文件路径
- `SIGNING_CONFIG_XXX`: 所有签名配置的路径要把"D:\\code\\PycharmProjects\\0419"替换为你本地的路径

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

### 可选参数
| 参数 | 说明 |
|------|------|
| --group | 指定仓库组 (openharmony-sig, openharmony-tpc, openharmony_tpc_samples) |
| --libs-file | 包含库列表的文件路径 |
| --output-dir | 输出目录 |
| --sdk-version | SDK版本 |
| --release-mode | 是否开启release模式编译 (y/n) |
| --parallel | 并行运行三个仓库组 |

## 报告查看
测试完成后，报告将生成在`results/`目录下，支持Allure和HTML两种格式。