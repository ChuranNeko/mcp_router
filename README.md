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

<details>
<summary><b>📁 项目结构</b></summary>

```
mcp_router/
├── main.py                 # 项目入口
├── config.json            # 全局配置文件
├── requirements.txt       # 依赖文件
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
│   └── ...
│
└── test/                  # 测试文件
    ├── test_router.py
    ├── test_api.py
    └── test_security.py
```

</details>

## 快速开始

### 安装

**从 PyPI 安装（推荐）：**

```bash
pip install mcp-router
```

<details>
<summary><b>从源码安装</b></summary>

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

</details>

### 配置

编辑 `config.json` 文件：

```json
{
  "api": {
    "enabled": false,
    "port": 8001,
    "host": "0.0.0.0"
  },
  "server": {
    "host": "0.0.0.0",
    "http": { "enabled": true, "port": 3000 },
    "sse": { "enabled": true, "port": 3001 }
  },
  "security": {
    "bearer_token": "",
    "enable_validation": true
  },
  "logging": {
    "level": "INFO",
    "directory": "logs"
  }
}
```

<details>
<summary><b>⚙️ 配置项说明</b></summary>

- `server.host`: HTTP/SSE模式的监听地址（默认：0.0.0.0）
- `server.http.port`: HTTP模式的监听端口（默认：3000）
- `server.sse.port`: SSE模式的监听端口（默认：3001）
- `server.allow_instance_management`: 允许LLM管理实例（默认：false）
- `api.enabled`: 是否启动REST API服务器（默认：false）
- `api.port`: REST API端口（默认：8001）
- `api.auto_find_port`: 端口占用时自动递增查找可用端口
- `api.enable_realtime_logs`: 启用WebSocket实时日志 (ws://host:port/ws)
- `logging.directory`: 日志目录，使用Minecraft风格 (latest-{mode}.txt + 时间戳备份)
- `logging.level`: 日志级别（DEBUG/INFO/WARNING/ERROR/OFF）

**注意**：传输模式（stdio/http/sse）通过命令行参数指定，不在配置文件中设置。

</details>

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
  "env": {}
}
```

### 运行

```bash
# 直接指定传输模式
python main.py              # Stdio模式（默认）
python main.py stdio        # Stdio模式
python main.py http         # HTTP模式
python main.py sse          # SSE模式
python main.py api          # API服务器模式

# 查看帮助
python main.py help
python main.py -h
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

<details>
<summary><b>📡 REST API 端点</b></summary>

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

</details>

## 与 LLM 集成

### Stdio 模式（推荐）

适用于单个LLM客户端（如Claude Desktop、Cursor）。

**客户端配置示例** (mcp.json):
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
      ],
      "transport": "stdio"
    }
  }
}
```

### HTTP 模式

适用于多客户端并发连接（端口 3000）。

**客户端配置示例** (mcp.json):
```json
{
  "mcpServers": {
    "mcp_router_http": {
      "url": "http://localhost:3000/mcp",
      "transport": "streamableHttp"
    }
  }
}
```

<details>
<summary><b>HTTP 使用示例（curl / Python）</b></summary>

**curl 示例**:
```bash
# 初始化会话
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'

# 列出工具
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

**Python 客户端示例**:
```python
import httpx

class MCPHTTPClient:
    def __init__(self, base_url="http://localhost:3000"):
        self.client = httpx.Client()
        self.base_url = base_url
        self.request_id = 0
        self.initialized = False
    
    def call_method(self, method, params=None):
        self.request_id += 1
        response = self.client.post(f"{self.base_url}/mcp", json={
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        })
        return response.json()
    
    def initialize(self):
        result = self.call_method("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "python-client", "version": "1.0.0"}
        })
        self.initialized = True
        return result
    
    def list_tools(self):
        if not self.initialized:
            self.initialize()
        return self.call_method("tools/list")

# 使用示例
client = MCPHTTPClient()
tools = client.list_tools()
print(tools)
```

</details>

### SSE 模式

适用于实时推送场景（端口 3001）。

**客户端配置示例** (mcp.json):
```json
{
  "mcpServers": {
    "mcp_router_sse": {
      "url": "http://localhost:3001/sse",
      "transport": "sse"
    }
  }
}
```

<details>
<summary><b>SSE JavaScript 客户端示例</b></summary>

```javascript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";

const transport = new SSEClientTransport(
  new URL("http://localhost:3001/sse")
);
const client = new Client(
  { name: "my-client", version: "1.0.0" }, 
  { capabilities: {} }
);

await client.connect(transport);
const tools = await client.listTools();
console.log(tools);
```

</details>

### REST API 模式

独立的配置管理接口（端口 8001）。

```bash
# 单独启动API模式
python main.py api

# 或在任意MCP模式下同时启用API（需config.json中配置api.enabled: true）
python main.py http
```

<details>
<summary><b>REST API 使用示例</b></summary>

**curl 示例**:
```bash
# 列出所有实例
curl http://localhost:8001/api/instances \
  -H "Authorization: Bearer your-token"

# 调用工具
curl -X POST http://localhost:8001/api/call \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"instance": "openai_doc", "tool": "read_project_oas", "params": {}}'
```

**Python 客户端示例**:
```python
import httpx

client = httpx.Client(
    base_url="http://localhost:8001",
    headers={"Authorization": "Bearer your-token"}
)

# 列出实例
instances = client.get("/api/instances").json()

# 调用工具
result = client.post("/api/call", json={
    "instance": "openai_doc",
    "tool": "read_project_oas",
    "params": {}
}).json()
```

</details>

### 混合模式（MCP + API）

同时运行MCP服务器和REST API，使用独立端口互不干扰。

**配置**:
```json
{
  "api": {"enabled": true, "port": 8001},
  "server": {
    "host": "0.0.0.0",
    "http": {"enabled": true, "port": 3000}
  }
}
```

**启动**:
```bash
python main.py http  # MCP@3000 + API@8001
```

## 开发

### 代码风格

本项目使用 [Ruff](https://github.com/astral-sh/ruff) 进行代码格式化和 linting：

```bash
# 格式化代码
ruff format .

# 检查代码
ruff check .

# 自动修复
ruff check --fix .
```

<details>
<summary><b>🧪 运行测试</b></summary>

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest test/test_router.py

# 带覆盖率
pytest --cov=src --cov-report=html
```

</details>

## 安全性

- **输入验证**: 防止SQL注入、XSS攻击、路径遍历
- **Bearer Token**: 可选的API认证
- **CORS配置**: 灵活的跨域请求控制
- **文件大小限制**: 防止DOS攻击
- **HTTP安全头**: X-Frame-Options, CSP, HSTS等

## 许可证

[MIT License](LICENSE)

## 贡献

欢迎提交 Issue 和 Pull Request！

请确保：
- 代码通过 `ruff` 检查
- 添加或更新相关测试
- 更新文档（如果需要）

