# MCP Router

[![PyPI Publish](https://github.com/ChuranNeko/mcp_router/actions/workflows/python-publish.yml/badge.svg)](https://github.com/ChuranNeko/mcp_router/actions/workflows/python-publish.yml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP Router 是一个模型上下文协议（MCP）路由/代理系统，作为MCP服务端和客户端，支持动态管理MCP工具配置，解决LLM无法区分同名工具的问题。

## 特性

- **动态路由**: 文件系统路由，使用 `mcp_settings.json` 配置
- **快速启动**: 后台加载客户端，启动时间<0.1秒
- **热加载**: 自动检测配置变化并重新加载
- **多传输支持**: Stdio、SSE、HTTP 传输协议
- **实时日志**: WebSocket实时日志流（可选）
- **权限控制**: 可配置的LLM实例管理权限
- **智能端口**: 端口占用时自动查找可用端口
- **安全认证**: Bearer Token认证，输入验证
- **REST API**: 完整的HTTP API用于配置管理

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
    "enabled": false,
    "port": 8000,
    "host": "127.0.0.1",
    "cors_origin": "*",
    "auto_find_port": true,
    "enable_realtime_logs": false
  },
  "server": {
    "enabled": true,
    "transport_type": "stdio",
    "host": "127.0.0.1",
    "port": 3000,
    "allow_instance_management": false
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
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "directory": "logs"
  },
  "watcher": {
    "enabled": true,
    "watch_path": "data",
    "debounce_delay": 1.0
  }
}
```

**主要配置项说明**:
- `server.host`: HTTP/SSE模式的监听地址（默认：127.0.0.1）
- `server.port`: HTTP/SSE模式的监听端口（默认：8000）
- `server.allow_instance_management`: 允许LLM管理实例（默认：false）
- `api.enabled`: 是否启动REST API服务器（默认：false）
- `api.auto_find_port`: 端口占用时自动递增查找可用端口
- `api.enable_realtime_logs`: 启用WebSocket实时日志 (ws://host:port/ws)
- `logging.directory`: 日志目录，使用Minecraft风格 (latest.txt + 时间戳备份)
- `logging.level`: 日志级别（DEBUG/INFO/WARNING/ERROR）

**注意**：传输模式（stdio/http/sse/http+sse）通过命令行参数指定，不在配置文件中设置。

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
# 直接指定传输模式（最简洁）
python main.py                  # Stdio模式（默认）
python main.py stdio            # Stdio模式
python main.py http             # HTTP模式
python main.py sse              # SSE模式
python main.py http+sse         # HTTP+SSE混合模式

# 使用 uv
uv run python main.py http+sse

# 查看帮助
python main.py -h
```

**命令行参数**：
```bash
transport        MCP传输模式: stdio, http, sse, http+sse (默认: stdio)
-c, --config     配置文件路径 (默认: config.json)
-l, --log-level  日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF
-v, --version    显示版本
-h, --help       显示帮助
```

**重要说明**：
- 传输模式通过命令行参数指定，简洁直观
- API服务器是否启动由`config.json`中的`api.enabled`控制
- HTTP/SSE的host和port在`config.json`中配置
- 日志文件会自动包含传输模式标识（如：`25.10.29-09-00-stdio.txt`）

## 使用模式

### MCP传输模式

MCP Router支持三种MCP传输协议：

#### 1. Stdio模式（标准输入输出）

适用于单个客户端，通过进程的标准输入输出通信。**最常用**。

配置:
```json
{
  "server": {
    "enabled": true,
    "transport_type": "stdio"
  }
}
```

#### 2. SSE模式（Server-Sent Events）

适用于网页客户端，使用HTTP SSE协议实现服务端推送。

配置:
```json
{
  "server": {
    "enabled": true,
    "transport_type": "sse",
    "host": "127.0.0.1",
    "port": 3000
  }
}
```

#### 3. HTTP模式（HTTP POST）

适用于简单的HTTP请求-响应模式。

配置:
```json
{
  "server": {
    "enabled": true,
    "transport_type": "http",
    "host": "127.0.0.1",
    "port": 3000
  }
}
```

### API模式

独立于MCP传输的REST API服务器，用于配置管理。

配置:
```json
{
  "api": {"enabled": true},
  "server": {"enabled": false}
}
```

### 组合模式

同时运行MCP Server和REST API。

配置:
```json
{
  "api": {"enabled": true},
  "server": {
    "enabled": true,
    "transport_type": "stdio"
  }
}
```

## MCP 工具

MCP Router 提供以下工具给 LLM 使用：

**基础工具** (总是可用):
- `mcp.router.list()` - 列出所有已注册的MCP客户端实例
- `mcp.router.help()` - 返回所有实例的工具列表和使用说明
- `mcp.router.use(instance_name)` - 使用指定的MCP实例
- `mcp.router.call(instance_name, tool_name, **kwargs)` - 调用指定实例的指定工具

**管理工具** (需启用 `allow_instance_management`):
- `mcp.router.add(provider_name, config)` - 动态添加新的MCP配置
- `mcp.router.remove(instance_name)` - 移除MCP配置
- `mcp.router.enable(instance_name)` - 启用MCP实例
- `mcp.router.disable(instance_name)` - 禁用MCP实例

## REST API

当 API 模式启用时，可通过以下端点管理 MCP Router：

**实例管理**:
- `GET /api/instances` - 列出所有实例
- `GET /api/instances/{name}` - 获取实例详情
- `POST /api/instances` - 添加新实例
- `PATCH /api/instances/{name}` - 更新实例配置
- `DELETE /api/instances/{name}` - 删除实例
- `POST /api/instances/{name}/enable` - 启用实例
- `POST /api/instances/{name}/disable` - 禁用实例

**工具管理**:
- `GET /api/tools` - 列出所有工具
- `GET /api/tools/{instance_name}` - 获取实例的工具列表
- `POST /api/call` - 调用工具

**其他**:
- `GET /` - 服务状态
- `GET /health` - 健康检查
- `GET /api/config` - 获取配置
- `WS /ws` - 实时日志流 (需启用 `enable_realtime_logs`)

## 与 LLM 集成

MCP Router支持三种MCP传输协议，根据需求选择：

### 模式1: Stdio传输（推荐）

适用于单个LLM客户端（如Claude Desktop、Cursor）通过stdio协议连接。

**启动命令**:
```bash
python main.py stdio
python main.py  # 默认stdio模式
```

**LLM客户端配置**（如Claude Desktop/Cursor的mcp.json）:
```json
{
  "mcpServers": {
    "mcp_router": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/path/to/mcp_router",
        "run",
        "python",
        "main.py"
      ]
    }
  }
}
```

或使用Python直接运行：
```json
{
  "mcpServers": {
    "mcp_router": {
      "command": "python",
      "args": [
        "C:/path/to/mcp_router/main.py"
      ],
      "env": {
        "PYTHONPATH": "C:/path/to/mcp_router"
      }
    }
  }
}
```

### 模式2: HTTP传输（多客户端）

在同一端口上提供HTTP JSON-RPC端点，支持多客户端并发连接。

**启动命令**:
```bash
python main.py http
```

**配置** (`config.json`):
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

**MCP Router配置** (`config.json`):
```json
{
  "server": {
    "enabled": true,
    "transport_type": "http",
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

**端点**: `POST http://localhost:8000/mcp`

**curl示例**:
```bash
# 列出工具
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# 调用工具
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"mcp.router.call",
      "arguments":{
        "instance_name":"openai_doc",
        "tool_name":"read_project_oas_xxx",
        "arguments":{}
      }
    }
  }'
```

**Python客户端示例**:
```python
import httpx

class MCPHTTPClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.client = httpx.Client()
        self.base_url = base_url
        self.request_id = 0
    
    def call_method(self, method, params=None):
        self.request_id += 1
        response = self.client.post(f"{self.base_url}/mcp", json={
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        })
        return response.json()
    
    def list_tools(self):
        return self.call_method("tools/list")
    
    def call_tool(self, instance_name, tool_name, arguments):
        return self.call_method("tools/call", {
            "name": "mcp.router.call",
            "arguments": {
                "instance_name": instance_name,
                "tool_name": tool_name,
                "arguments": arguments
            }
        })

# 使用示例
client = MCPHTTPClient()
tools = client.list_tools()
print(tools)
```

### 模式3: SSE传输（实时推送）

使用Server-Sent Events实现双向通信，适合需要实时推送的场景。

**启动命令**:
```bash
python main.py sse
```

**配置** (`config.json`):
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

**MCP Router配置** (`config.json`):
```json
{
  "server": {
    "enabled": true,
    "transport_type": "sse",
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

**端点**:
- SSE连接: `GET http://localhost:8000/sse`
- 消息发送: `POST http://localhost:8000/messages`

**JavaScript客户端示例**:
```javascript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";

const transport = new SSEClientTransport(
  new URL("http://localhost:8000/sse")
);
const client = new Client(
  { name: "my-client", version: "1.0.0" }, 
  { capabilities: {} }
);

await client.connect(transport);
const tools = await client.listTools();
console.log(tools);
```

### 模式4: HTTP+SSE混合传输（推荐）

在同一端口上同时提供HTTP和SSE端点，最大灵活性。

**启动命令**:
```bash
python main.py http+sse
```

**配置** (`config.json`):
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

**MCP Router配置** (`config.json`):
```json
{
  "server": {
    "enabled": true,
    "transport_type": "http+sse",
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

**可用端点**:
- HTTP: `POST http://localhost:8000/mcp`
- SSE: `GET http://localhost:8000/sse` + `POST http://localhost:8000/messages`

客户端可以根据需求选择HTTP或SSE方式连接。

### 模式5: REST API（配置管理）

除了MCP标准协议，Router还提供REST API用于配置管理和简单调用。

**启动命令**:
```bash
# API模式需要在config.json中启用
python main.py  # 或任意传输模式
```

**MCP Router配置** (`config.json`):
```json
{
  "api": {
    "enabled": true,
    "port": 8000,
    "host": "0.0.0.0",
    "cors_origin": "*"
  },
  "server": {"enabled": false},
  "security": {
    "bearer_token": "your-secret-token-here",
    "enable_validation": true
  }
}
```

**步骤2：客户端通过HTTP API访问**:
```bash
# 列出所有实例
curl http://localhost:8000/api/instances \
  -H "Authorization: Bearer your-secret-token-here"

# 调用工具
curl -X POST http://localhost:8000/api/call \
  -H "Authorization: Bearer your-secret-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_name": "openai_doc",
    "tool_name": "read_project_oas_xxx",
    "arguments": {}
  }'
```

**Python客户端示例**:
```python
import httpx

client = httpx.Client(
    base_url="http://localhost:8000",
    headers={"Authorization": "Bearer your-secret-token-here"}
)

# 列出实例
instances = client.get("/api/instances").json()
print(instances)

# 调用工具
result = client.post("/api/call", json={
    "instance_name": "openai_doc",
    "tool_name": "read_project_oas_xxx",
    "arguments": {}
}).json()
print(result)
```

### 混合模式（Stdio + API）

同时支持单个stdio客户端和多个HTTP客户端。

**步骤1：MCP Router配置** (`config.json`):
```json
{
  "api": {
    "enabled": true,
    "port": 8000,
    "host": "127.0.0.1"
  },
  "server": {
    "enabled": true,
    "transport_type": "stdio"
  },
  "security": {
    "bearer_token": "your-secret-token-here",
    "enable_validation": true
  }
}
```

**步骤2：客户端配置**

**Stdio客户端**（如Claude Desktop/Cursor的mcp.json）：
```json
{
  "mcpServers": {
    "mcp_router": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/path/to/mcp_router",
        "run",
        "python",
        "main.py"
      ]
    }
  }
}
```

**HTTP客户端**：通过API访问（见上文"多客户端模式"的HTTP示例）

这样配置后：
- 一个客户端通过stdio连接（如Claude Desktop或Cursor）
- 其他客户端通过HTTP API连接（如自定义应用、脚本等）

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

