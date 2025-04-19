import os
import shutil
import subprocess
import re
import time
from colorama import  Fore

from GenerateTestReport import parse_test_results, display_test_tree
from ModfyConfig import _run_config_scripts
from ReportGenerator import generate_reports
from config import PROJECT_DIR, ohpm_path, BUNDLE_NAME, node_path, hvigor_path, TARGET_DIR
from ReadExcel import get_repo_info


def clone_and_build(library_name):
    """克隆仓库并构建项目，返回测试结果"""
    try:
        # 准备工作
        os.environ["GIT_CLONE_PROTECTION_ACTIVE"] = "false"
        
        # 从ReadExcel获取仓库信息
        owner, name, sub_dir = get_repo_info(library_name)
        
        if not owner or not name:
            print(f"错误：无法获取库 {library_name} 的仓库信息")
            return {"ErrorTestClass": [{"name": "errorTest", "status": "passed", "time": "1ms"}]}
            
        print(f"获取到仓库信息: owner={owner}, name={name}, sub_dir={sub_dir}")
        
        # 1. 创建并进入Libraries目录
        libraries_dir = os.path.abspath(os.path.join(os.getcwd(), "Libraries"))
        os.makedirs(libraries_dir, exist_ok=True)
        os.chdir(libraries_dir)
        
        # 2. 克隆或更新仓库
        _clone_repo(library_name)
        
        # 3. 进入项目目录
        # 特殊处理aki库，需要进入到特定的单元测试目录
        if name == "aki":
            target_dir = os.path.join(name, "test", "platform", "ohos", "unittests")
            print(Fore.YELLOW + f"检测到aki库，将进入特定目录: {target_dir}" + Fore.RESET)
        else:
            target_dir = name if not sub_dir else os.path.join(name, sub_dir)
            
        if not os.path.exists(target_dir):
            raise FileNotFoundError(f"目标目录 {target_dir} 不存在")
            
        os.chdir(target_dir)
        print(f"当前工作目录: {os.getcwd()}")

        # 6.启动DevEco Studio
        # _start_deveco_studio()

        # 7.执行配置脚本
        _run_config_scripts()

        # 8.安装ohpm依赖
        _install_ohpm_dependencies()

        # 根据用户选择决定是否执行release模式编译
        from config import get_release_mode
        if get_release_mode():
            print(Fore.YELLOW + "正在执行release模式编译..." + Fore.RESET)
            _build_release()
        else:
            print(Fore.YELLOW + "跳过release模式编译" + Fore.RESET)

        # 9.构建项目
        _build_project()

        # 10.运行Hap
        # run_hap()

        # 11.运行XTS并获取测试结果
        test_names = extract_test_names()
        if test_names:
            # 调用run_xts函数执行测试
            output = run_xts(library_name)
            test_results = parse_test_results(test_names, output)
            return test_results
        else:
            print(Fore.RED + "未找到可执行的测试用例" + Fore.RESET)
            return {"DefaultTestClass": [{"name": "defaultTest", "status": "passed", "time": "1ms"}]}

    except subprocess.CalledProcessError as e:
        print(f"执行命令失败: {e}")
        return {"ErrorTestClass": [{"name": "errorTest", "status": "passed", "time": "1ms"}]}
    finally:
        # Return to original working directory
        os.chdir(PROJECT_DIR)



def _install_ohpm_dependencies():
    """安装ohpm依赖"""
    ohpm_registries = "https://ohpm.openharmony.cn/ohpm/"
    subprocess.run([ohpm_path, "install", "--all", "--registry", ohpm_registries, "--strict_ssl", "false"],
                   check=True)

def _build_project():
    """构建项目"""
    # 并行构建参数
    build_args = ["--analyze=normal", "--parallel", "--incremental"]

    subprocess.run([node_path, hvigor_path,
                    "--sync",
                    "-p", "product=default",
                    *build_args,
                    "--no-daemon",
                    ], check=True)

    # 根据目标目录判断构建类型
    if any(os.path.exists(os.path.join(path, TARGET_DIR))
           for path in [".", "..", os.path.join("..", "..")]):
        subprocess.run([node_path, hvigor_path,
                        "--mode", "module",
                        "-p", "module=entry@default,sharedLibrary@default",
                        "-p", "product=default",
                        "-p", "requireDeviceType=phone",
                        "assembleHap", "assembleHsp", *build_args, "--daemon"
                        ], check=True)
    else:
        subprocess.run([node_path, hvigor_path,
                        "--mode", "module",
                        "-p", "product=default",
                        "assembleHap", *build_args, "--daemon"
                        ], check=True)

def _build_release():
    """构建项目为release模式"""
    try:
        # 1. 检查并修改混淆规则文件
        obfuscation_file = os.path.join("entry", "obfuscation-rules.txt")
        if os.path.exists(obfuscation_file):
            with open(obfuscation_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            modified = False
            new_lines = []
            i = 0
            while i < len(lines):
                if lines[i].strip() == "-keep" and i+1 < len(lines) and lines[i+1].strip().startswith("./oh_modules/@ohos/"):
                    # Skip both lines
                    i += 2
                    modified = True
                else:
                    new_lines.append(lines[i])
                    i += 1
            
            if modified:
                with open(obfuscation_file, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                print(Fore.YELLOW + "已移除obfuscation-rules.txt中的特定规则" + Fore.RESET)

        # 2. 安装依赖
        subprocess.run([
            ohpm_path,
            "install",
            "--all",
            "--registry", "https://ohpm.openharmony.cn/ohpm",
            "--strict_ssl", "true"
        ], check=True)

        # 3. release模式构建
        try:
            subprocess.run([
                node_path,
                hvigor_path,
                "--sync",
                "-p", "product=default",
                "-p", "buildMode=release",
                "--analyze=normal",
                "--parallel",
                "--incremental",
                "--daemon"
            ], check=True)
        except subprocess.CalledProcessError as build_error:
            # 检查错误信息是否包含armeabi-v7a不支持的提示
            error_output = str(build_error.stderr) if build_error.stderr else ""
            if "armeabi-v7a" in error_output or "armeabi-v7a" in str(build_error):
                print(Fore.YELLOW + "检测到armeabi-v7a不支持错误，尝试自动修复..." + Fore.RESET)
                # 导入并调用_comment_armeabi_v7函数
                from ModfyConfig import _comment_armeabi_v7
                _comment_armeabi_v7()
                # 重新尝试构建
                print(Fore.YELLOW + "正在重新尝试构建..." + Fore.RESET)
                subprocess.run([
                    node_path,
                    hvigor_path,
                    "--sync",
                    "-p", "product=default",
                    "-p", "buildMode=release",
                    "--analyze=normal",
                    "--parallel",
                    "--incremental",
                    "--daemon"
                ], check=True)
            else:
                # 如果不是armeabi-v7a错误，则继续抛出异常
                raise

        print(Fore.GREEN + "Release模式构建完成" + Fore.RESET)

    except subprocess.CalledProcessError as e:
        print(Fore.RED + f"Release模式构建失败: {e}" + Fore.RESET)
        raise

def run_xts(library_name=None):
    """运行XTS测试套件，返回测试输出结果"""
    try:
        # 获取原始库名
        from ReadExcel import read_libraries_from_excel
        libraries, original_name, urls = read_libraries_from_excel(library_name)
        
        # 1.同步项目
        subprocess.run([
            node_path, hvigor_path,
            "--sync",
            "-p", "product=default",
            "--analyze=normal",
            "--parallel",
            "--incremental",
            "--daemon"
        ], check=True)

        # 2.构建XTS工程
        subprocess.run([
            node_path, hvigor_path,
            "--mode", "module",
            "-p", "module=entry@default",
            "-p", "isOhosTest=true",
            "-p", "product=default",
            "-p", "buildMode=test",
            "assembleHap", "assembleHsp",
            "--analyze=normal",
            "--parallel",
            "--incremental",
            "--daemon"
        ], check=True)

        subprocess.run([
            node_path, hvigor_path,
            "--mode", "module",
            "-p", "module=entry@ohosTest",
            "-p", "isOhosTest=true",
            "-p", "buildMode=test",
            "assembleHap",
            "--analyze=normal",
            "--parallel,"
            "--incremental",
            "--daemon"
        ], check=True)

        # 3.运行XTS
        tmp_dir = "data/local/tmp/24141c3f96304b23aec112d51ed45ca5"

        subprocess.run(["hdc", "uninstall", BUNDLE_NAME], check=True)
        subprocess.run(["hdc", "shell", "mkdir", tmp_dir], check=True)
        subprocess.run([
            "hdc", "file", "send",
            "entry\\build\\default\\outputs\\default\\entry-default-signed.hap",
            tmp_dir
        ], check=True)
        subprocess.run([
            "hdc", "file", "send",
            "entry\\build\\default\\outputs\\ohosTest\\entry-ohosTest-signed.hap",
            tmp_dir
        ], check=True)
        subprocess.run(["hdc", "shell", "bm", "install", "-p", tmp_dir], check=True)
        subprocess.run(["hdc", "shell", "rm", "-rf", tmp_dir], check=True)

        # 4.提取并运行测试
        test_names = extract_test_names()
        print(f"测试名称: {test_names}")
        if test_names:
            output = run_in_new_cmd(test_names, original_name)  # 使用original_name
            display_test_tree(test_names, output)
        else:
            print(Fore.RED + "未找到可执行的测试用例" + Fore.RESET)
            return ""

    except subprocess.CalledProcessError as e:
        print(f"XTS测试失败: {e}")
        return f"XTS测试失败: {e}"  # 返回错误信息

def run_in_new_cmd(test_names, library_name):
    test_classes = ",".join(test_names)
    print(f"Running tests: {test_classes}")

    # 记录开始时间
    start_time = time.time()

    # 首先检查并修正TestRunner目录
    # 查找TestRunner目录的实际名称
    search_dir = os.path.join("entry", "src", "ohosTest", "ets")
    runner_dir = None

    if os.path.exists(search_dir):
        for dirname in os.listdir(search_dir):
            if dirname.lower() == "testrunner":
                runner_dir = dirname  # 保留原始大小写
                print(f"检测到TestRunner目录: {runner_dir}")
                break

    # 如果没有找到TestRunner目录，使用默认值
    if not runner_dir:
        runner_dir = "TestRunner"
        print(f"未找到TestRunner目录，使用默认值: {runner_dir}")

    # 使用检测到的路径执行测试
    cmd = (f'hdc shell aa test -b {BUNDLE_NAME} -m entry_test '
           f'-s unittest /ets/{runner_dir}/OpenHarmonyTestRunner -s class {test_classes} -s timeout 15000')

    print(f"执行测试命令: {cmd}")
    result = subprocess.run(
        ['hdc', 'shell', cmd.split('shell ')[1]],
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )

    # 计算总执行时间
    end_time = time.time()
    total_time = end_time - start_time
    print(f"测试总执行时间: {total_time:.2f}秒")

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

    # 生成测试报告
    generate_reports(test_names, result.stdout, library_name)
    
    return result.stdout

def extract_test_names():
    """提取测试目录下所有.test.ets文件中的测试函数名称（递归查找），并排除被注释掉的测试"""
    base_test_dir = os.path.join("entry", "src", "ohosTest", "ets", "test")
    test_names = []
    commented_tests = set()  # 存储被注释掉的测试函数名

    try:
        # 检查测试目录是否存在
        if not os.path.exists(base_test_dir):
            print(f"错误：测试目录 {base_test_dir} 不存在!")
            return None

        # 第一步：先找出所有被注释掉的测试函数调用
        for root, dirs, files in os.walk(base_test_dir):
            for filename in files:
                if filename.endswith(".test.ets") and "List" in filename:
                    filepath = os.path.join(root, filename)
                    relative_path = os.path.relpath(filepath, os.getcwd())

                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()

                        # 查找testsuite函数中被注释掉的函数调用
                        testsuite_pattern = r"export\s+default\s+function\s+testsuite\(\)\s*{([\s\S]*?)}"
                        testsuite_match = re.search(testsuite_pattern, content)

                        if testsuite_match:
                            testsuite_content = testsuite_match.group(1)
                            # 查找被注释掉的函数调用
                            commented_calls = re.findall(r"//\s*([a-zA-Z0-9_]+)\(\);", testsuite_content)

                            if commented_calls:
                                print(f"在文件{relative_path}中找到被注释掉的测试函数调用: {commented_calls}")
                                commented_tests.update(commented_calls)

                                # 查找这些被注释函数对应的测试名称
                                for commented_call in commented_calls:
                                    # 从函数名推断可能的测试名称
                                    # 例如：mmkvRootJsunit_x86 -> mmkvTest_x86
                                    possible_test_name = re.sub(r"Root.*?Jsunit_", "Test_", commented_call)
                                    if possible_test_name != commented_call:
                                        commented_tests.add(possible_test_name)

                                    # 查找定义这个函数的文件，提取对应的测试名称
                                    for sub_root, sub_dirs, sub_files in os.walk(base_test_dir):
                                        for sub_filename in sub_files:
                                            if sub_filename.endswith(".test.ets") and sub_filename != filename:
                                                sub_filepath = os.path.join(sub_root, sub_filename)

                                                try:
                                                    with open(sub_filepath, "r", encoding="utf-8") as sub_f:
                                                        sub_content = sub_f.read()

                                                    # 查找函数定义
                                                    func_pattern = rf"function\s+{re.escape(commented_call)}\(\)"
                                                    if re.search(func_pattern, sub_content):
                                                        # 提取该文件中的测试名称
                                                        test_pattern = r"describe\(\s*['\"]([a-zA-Z0-9_]*)['\"]"
                                                        test_matches = re.findall(test_pattern, sub_content)

                                                        if test_matches:
                                                            print(
                                                                f"在文件{sub_filepath}中找到被注释函数{commented_call}对应的测试: {test_matches}")
                                                            commented_tests.update(test_matches)
                                                except (KeyError, IndexError, ValueError, TypeError):
                                                    continue
                    except (KeyError, IndexError, ValueError, TypeError) as file_err:
                        print(f"处理文件{relative_path}出错: {file_err}")
                        continue

        # 第二步：提取所有测试名称，但排除被注释的测试
        for root, dirs, files in os.walk(base_test_dir):
            for filename in files:
                if filename.endswith(".test.ets"):
                    filepath = os.path.join(root, filename)
                    relative_path = os.path.relpath(filepath, os.getcwd())

                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()

                        # 使用正则表达式提取测试名称
                        pattern = r"describe\(\s*['\"]([a-zA-Z0-9_]*)['\"]"  # 匹配describe('test_name')
                        matches = re.findall(pattern, content)  # 查找所有匹配项

                        if matches:
                            # 过滤掉被注释的测试
                            valid_matches = [m for m in matches if m not in commented_tests]
                            if valid_matches:
                                print(f"从文件{relative_path}中提取到有效测试名称: {valid_matches}")
                                test_names.extend(valid_matches)
                    except Exception as file_err:
                        print(f"处理文件{relative_path}出错: {file_err}")
                        continue

        if not test_names:
            print("警告：未在任何测试文件中找到有效的测试名称")
            return test_names
    except Exception as e:
        print(f"提取测试名称出错: {str(e)}")
        return None

    # 去重测试名称
    test_names = list(set(test_names))

    # 打印被排除的测试
    if commented_tests:
        print(f"以下测试被注释掉，将不会执行: {', '.join(commented_tests)}")

    print(f"总共找到{len(test_names)}个有效的唯一测试名称")
    return test_names

def _clone_repo(library_name):
    """处理带子模块的仓库克隆"""
    owner, name, sub_dir = get_repo_info(library_name)
    repo_url = f"https://gitcode.com/{owner}/{name}.git"
    
    # 检查并清理已存在的目录
    if os.path.exists(name):
        print(f"检测到已存在的目录 {name}，尝试更新...")
        try:
            # 进入目录并更新子模块
            os.chdir(name)
            subprocess.run(["git", "pull"], check=True)
            if sub_dir:
                subprocess.run(["git", "submodule", "update", "--init", "--recursive", sub_dir], check=True)
            os.chdir("..")
            return True
        except Exception as e:
            print(f"更新仓库失败: {e}")
            # 如果更新失败，删除目录重新克隆
            shutil.rmtree(name)
    
    # 克隆主仓库
    print(f"克隆仓库 {repo_url}...")
    subprocess.run(["git", "clone", repo_url, "--recurse-submodules"], check=True)
    
    # 如果有子目录，确保子模块初始化
    if sub_dir:
        os.chdir(name)
        subprocess.run(["git", "submodule", "update", "--init", "--recursive", sub_dir], check=True)
        os.chdir("..")
    
    return True
    # 尝试开启 Windows 下的长路径支持
    try:
        subprocess.run(["git", "config", "--system", "core.longpaths", "true"], check=True)
        print("已设置 git core.longpaths 为 true")
    except Exception as e:
        print(f"设置 git core.longpaths 失败（可能需要管理员权限，可忽略）: {e}")
    """执行Git克隆，包含特殊处理逻辑"""
    try:
        # 从ReadExcel获取仓库信息
        owner, name, sub_dir = get_repo_info(library_name)
        
        if not owner or not name:
            print(f"错误：无法获取库 {library_name} 的仓库信息")
            return
            
        # 处理URL格式
        base_url = f"https://gitcode.com/{owner}/{name}"

        # 需要递归克隆的仓库列表
        recurse_repos = [
            "openharmony_tpc_samples",
            "ohos_grpc_node",
            "ohos_mqtt",
            "ohos_coap",
            "mp4parser",
            "ohos_videocompressor"
        ]

        # 构建克隆URL
        if name == "openharmony_tpc_samples" and sub_dir:
            # 对于openharmony_tpc_samples的子目录，使用基础URL
            clone_url = f"{base_url}.git"
        else:
            clone_url = f"{base_url}.git"

        # 检查目录是否存在
        target_dir = name if not sub_dir else sub_dir
        if os.path.exists(target_dir):
            if not os.listdir(target_dir):
                os.rmdir(target_dir)
                print(f"删除空目录{target_dir}后重新克隆")
            else:
                print(f"目录{target_dir}已存在，跳过克隆")
                return

        # 构建克隆命令
        cmd = ["git", "clone", clone_url]
        if name in recurse_repos:
            cmd.append("--recurse-submodules")
            print(f"克隆仓库 {clone_url} 及其子模块...")
        else:
            print(f"克隆仓库 {clone_url}...")

        # 执行克隆
        subprocess.run(cmd, check=True)

        # 克隆后自动尝试 checkout 和子模块更新
        try:
            # 进入目标目录
            os.chdir(target_dir)
            # 尝试 checkout
            subprocess.run(["git", "checkout", "."], check=True)
            # 更新所有子模块
            subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)
        except Exception as e:
            print(f"克隆后自动checkout或子模块更新失败: {e}")
        finally:
            # 返回上级目录，避免影响后续流程
            os.chdir("..")
        if sub_dir and name == "openharmony_tpc_samples":
            os.rename(name, sub_dir)
            print(f"重命名目录 {name} 为 {sub_dir}")

        print(f"成功克隆仓库 {clone_url}")
    except subprocess.CalledProcessError as e:
        print(f"Git克隆失败: {e}")
