"""启动脚本:在命令行运行 python run.py 即可启动网站"""
import uvicorn

if __name__ == "__main__":
    # reload=True 表示修改代码后自动重启,方便开发调试
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
