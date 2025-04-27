@echo off
echo 启动三个进程分别运行三种仓库类型的库...

start "运行 openharmony-sig" cmd /c "python "D:\code\PycharmProjects\0419\XTSRunner\run.py" --group openharmony-sig --output-dir "D:\code\PycharmProjects\0419\XTSRunner" --sdk-version 5.0.3 --release-mode n > "D:\code\PycharmProjects\0419\XTSRunner\logs\openharmony-sig.log" 2>&1"
start "运行 openharmony-tpc" cmd /c "python "D:\code\PycharmProjects\0419\XTSRunner\run.py" --group openharmony-tpc --output-dir "D:\code\PycharmProjects\0419\XTSRunner" --sdk-version 5.0.3 --release-mode n > "D:\code\PycharmProjects\0419\XTSRunner\logs\openharmony-tpc.log" 2>&1"
start "运行 openharmony_tpc_samples" cmd /c "python "D:\code\PycharmProjects\0419\XTSRunner\run.py" --group openharmony_tpc_samples --output-dir "D:\code\PycharmProjects\0419\XTSRunner" --sdk-version 5.0.3 --release-mode n > "D:\code\PycharmProjects\0419\XTSRunner\logs\openharmony_tpc_samples.log" 2>&1"

echo 已启动三个进程，请查看各自的日志文件了解运行情况
echo 批处理文件执行完毕
