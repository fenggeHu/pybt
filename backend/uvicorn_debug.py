"""
用于本地启动Fastapi和调试
"""
import argparse

import uvicorn

import backend

if __name__ == '__main__':
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="启动 redback forecast API服务")
    parser.add_argument(
        "--host",  # 参数名
        type=str,  # 参数类型
        default="127.0.0.1",  # 默认值
        help="服务绑定的主机地址（默认：127.0.0.1）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="服务监听的端口（默认：8000）"
    )
    parser.add_argument(
        "--reload",
        action="store_true",  # 无需传值，只要出现该参数就为 True
        help="是否启用自动重载（开发环境用）"
    )

    # 解析参数
    args = parser.parse_args()

    uvicorn.run(backend.app,
                host=args.host, port=args.port,
                reload=args.reload,  # 自动重载
                )
