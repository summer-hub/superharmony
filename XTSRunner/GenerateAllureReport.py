import os
import json
import time
import uuid

from config import ALLURE_RESULTS_DIR


def generate_allure_report(test_results, library_name):
    """生成Allure格式的测试报告"""
    try:
        # 确保allure-results目录存在
        os.makedirs(ALLURE_RESULTS_DIR, exist_ok=True)
        
        # 确保test_results是字典类型
        if not isinstance(test_results, dict):
            print(f"警告：库 {library_name} 的测试结果不是有效的字典格式")
            # 创建一个空字典作为默认值
            test_results = {}

        # 为每个测试生成唯一的UUID
        lib_uuid = str(uuid.uuid4())

        # 创建库级别的测试套件结果
        lib_total = sum(len(tests) for tests in test_results.values())
        lib_passed = sum(1 for cls in test_results.values() for test in cls if test.get('status') == 'passed')
        lib_failed = lib_total - lib_passed
        lib_status = "passed" if lib_failed == 0 and lib_total > 0 else "failed"

        # 创建库级别的测试套件JSON，但不写入文件
        suite_result = {
            "uuid": lib_uuid,
            "historyId": f"{library_name}_suite",
            "name": f"{library_name} 测试套件",
            "fullName": f"{library_name}",
            "status": lib_status,
            "stage": "finished",
            "start": int(time.time() * 1000),
            "stop": int(time.time() * 1000) + 1000,  # 假设套件执行时间为1秒
            "labels": [
                {"name": "suite", "value": library_name},
                {"name": "package", "value": library_name}
            ],
            "statusDetails": {
                "message": f"总计: {lib_passed}/{lib_total} 测试通过, {lib_failed} 失败"
            }
        }

        # 创建Allure结果文件
        for test_class, tests in test_results.items():
            for test in tests:
                test_status = test.get('status', 'unknown')
                test_name = test.get('name', 'unknown')

                # 确保test_time是字符串并处理时间格式
                test_time_str = test.get('time', '0ms')
                if isinstance(test_time_str, int):
                    test_time = str(test_time_str)
                else:
                    test_time = test_time_str.replace('ms', '')

                # 确保test_time是数字字符串
                try:
                    test_time_int = int(test_time)
                except ValueError:
                    test_time_int = 0

                # 创建Allure测试结果JSON
                allure_result = {
                    "uuid": str(uuid.uuid4()),
                    "historyId": f"{library_name}_{test_class}_{test_name}",
                    "name": test_name,
                    "fullName": f"{library_name}.{test_class}.{test_name}",
                    "status": "passed" if test_status == "passed" else "failed",
                    "stage": "finished",
                    "start": int(time.time() * 1000),
                    "stop": int(time.time() * 1000) + test_time_int,
                    "labels": [
                        {"name": "suite", "value": test_class},
                        {"name": "package", "value": library_name},
                        {"name": "testClass", "value": test_class},
                        {"name": "testMethod", "value": test_name},
                        {"name": "parentSuite", "value": library_name}
                    ]
                }

                # 如果是失败的测试，添加错误信息
                if test_status != "passed":
                    allure_result["statusDetails"] = {
                        "message": test.get('error_message', 'Test failed'),
                        "trace": test.get('error_stack', 'No stack trace available')
                    }

                # 写入Allure结果文件
                result_file = os.path.join(ALLURE_RESULTS_DIR, f"{library_name}_{test_class}_{test_name}-result.json")
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(allure_result, f, ensure_ascii=False, indent=2)  # type: ignore

        print(f"已为库 {library_name} 生成Allure测试结果")

    except Exception as e:
        print(f"生成Allure报告时出错: {str(e)}")
        # 打印详细的错误堆栈
        import traceback
        traceback.print_exc()
