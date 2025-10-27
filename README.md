# MCP Router

[![PyPI Publish](https://github.com/ChuranNeko/mcp_router/actions/workflows/python-publish.yml/badge.svg)](https://github.com/ChuranNeko/mcp_router/actions/workflows/python-publish.yml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP Router 是一个模型上下文协议（MCP）路由/代理系统，作为MCP服务端和客户端，支持动态管理MCP工具配置，解决LLM无法区分同名工具的问题。

## 特性

- **动态路由**: 类似Next.js的文件路由系统，使用 `mcp_settings.json` 作为配置文件
- **热加载**: 自动检测配置文件变化并重新加载
- **多传输支持**: 支持 Stdio、SSE、HTTP 三种传输方式
- **安全认证**: 可选的 Bearer Token 认证
- **REST API**: 可选的 HTTP API 用于配置管理
- **完整日志**: 支持文件和控制台日志，带日志轮转
- **输入验证**: 防止路径遍历、注入攻击等安全问题

## 项目结构

```
mcp_router/
├── main.py                 # 项目入口
├── config.json            # 全局配置文件
├── requirements.txt       # 依赖文件
├── .python-version        # Python版本管理
├── pyproject.toml         # uv项目配置
│
├── src/
│   ├── core/              # 核心模块
│   │   ├── logger.py      # 日志系统
│   │   ├── config.py      # 配置管理器
│   │   └── exceptions.py  # 自定义异常
│   │
│   ├── mcp/               # MCP模块
│   │   ├── client.py      # MCP客户端管理
│   │   ├── server.py      # MCP服务端
│   │   ├── router.py      # 路由核心逻辑
│   │   └── transport.py   # 传输层
│   │
│   ├── api/               # API模块
│   │   ├── app.py         # FastAPI应用
│   │   └── routes.py      # API路由处理
│   │
│   └── utils/             # 工具模块
│       ├── validator.py   # 输入验证
│       ├── watcher.py     # 文件监视器
│       └── security.py    # 安全工具
│
├── data/                  # MCP配置目录
│   ├── example/
│   │   └── mcp_settings.json
│   ├── Openai/
│   │   └── mcp_settings.json
│   └── Wxcom/
│       └── mcp_settings.json
│
└── test/                  # 测试文件
    ├── test_router.py
    ├── test_api.py
    └── test_security.py
```

## 快速开始

### 环境要求

- Python 3.10+
- uv (推荐) 或 pip 或 conda

### 安装

**从 PyPI 安装（推荐）：**

```bash
pip install mcp-router
```

**从源码安装：**

```bash
# 使用 uv (推荐)
uv venv .venv
uv pip install -e ".[dev]"

# 或使用 pip
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
pip install -e ".[dev]"

# 或使用 conda
conda env create -f environment.yml
conda activate mcp_router
```

### 配置

编辑 `config.json` 文件：

```json
{
  "api": {
    "enabled": true,
    "port": 8000,
    "host": "127.0.0.1",
    "cors_origin": "*"
  },
  "server": {
    "enabled": true,
    "transport_type": "stdio"
  },
  "mcp_client": {
    "enabled": true,
    "timeout": 30
  },
  "security": {
    "bearer_token": "",
    "enable_validation": true
  },
  "logging": {
    "level": "INFO",
    "file": "logs/mcp_router.log"
  },
  "watcher": {
    "enabled": true,
    "watch_path": "data",
    "debounce_delay": 1.0
  }
}
```

### 添加MCP配置

在 `data/{provider}/mcp_settings.json` 中添加MCP服务器配置：

```json
{
  "provider": "example",
  "isActive": true,
  "name": "example_instance",
  "type": "stdio",
  "command": "python",
  "args": ["-m", "example_mcp"],
  "env": {},
  "metadata": {
    "description": "Example MCP server",
    "version": "1.0.0"
  }
}
```

### 运行

```bash
# 使用 uv
uv run python main.py

# 或直接运行
python main.py
```

## 使用模式

### 1. MCP Server 模式 (Stdio)

适用于与 LLM 集成，通过 stdio 协议通信。

配置:
```json
{
  "api": {"enabled": false},
  "server": {"enabled": true, "transport_type": "stdio"}
}
```

### 2. API 模式

仅启动 REST API 服务器，用于配置管理。

配置:
```json
{
  "api": {"enabled": true},
  "server": {"enabled": false}
}
```

### 3. 组合模式

同时运行 MCP Server 和 REST API。

配置:
```json
{
  "api": {"enabled": true},
  "server": {"enabled": true}
}
```

## MCP 工具

MCP Router 提供以下工具给 LLM 使用：

- `mcp.router.use(instance_name)` - 使用指定的MCP实例
- `mcp.router.list()` - 列出所有已注册的MCP客户端实例
- `mcp.router.help()` - 返回所有实例的工具列表和使用说明
- `mcp.router.add(provider_name, config)` - 动态添加新的MCP配置
- `mcp.router.call(instance_name, tool_name, **kwargs)` - 调用指定实例的指定工具
- `mcp.router.remove(instance_name)` - 移除MCP配置
- `mcp.router.disable(instance_name)` - 禁用MCP实例
- `mcp.router.enable(instance_name)` - 启用MCP实例

## REST API

当 API 模式启用时，可通过以下端点管理 MCP Router：

- `GET /api/instances` - 列出所有实例
- `GET /api/instances/{name}` - 获取实例详情
- `GET /api/tools` - 列出所有工具
- `GET /api/tools/{instance_name}` - 获取实例的工具列表
- `POST /api/instances` - 添加新实例
- `PATCH /api/instances/{name}` - 更新实例配置
- `DELETE /api/instances/{name}` - 删除实例
- `POST /api/instances/{name}/enable` - 启用实例
- `POST /api/instances/{name}/disable` - 禁用实例
- `POST /api/call` - 调用工具
- `GET /api/config` - 获取配置 (调试用)

## 与 LLM 集成

在您的 LLM 客户端配置中添加：

```json
{
  "mcpServers": {
    "mcp_router": {
      "isActive": true,
      "name": "mcp_router",
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "path/to/mcp_router",
        "run",
        "python",
        "main.py"
      ]
    }
  }
}
```

## 开发

### 代码风格

本项目使用 [Ruff](https://github.com/astral-sh/ruff) 进行代码格式化和 linting：

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 格式化代码
ruff format .

# 检查代码
ruff check .

# 自动修复问题
ruff check --fix .
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest test/test_router.py

# 带覆盖率
pytest --cov=src --cov-report=html
```

本项目配置了 GitHub Actions CI，每次推送到 main 分支时会自动运行代码检查和测试。

## 安全性

- **输入验证**: 防止SQL注入、XSS攻击、路径遍历
- **Bearer Token**: 可选的API认证
- **CORS配置**: 灵活的跨域请求控制
- **日志记录**: 不记录敏感信息如完整token

## 许可证

[MIT License](LICENSE)

## 贡献

欢迎提交 Issue 和 Pull Request！

贡献指南：
1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

请确保：
- 代码通过 `ruff` 检查
- 添加或更新相关测试
- 更新文档（如果需要）

## 联系方式

如有问题，请提交 Issue。

