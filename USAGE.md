# MCP Router 使用指南
## 目录

1. [快速开始](#快速开始)
2. [配置说明](#配置说明)
3. [使用模式](#使用模式)
4. [MCP工具说明](#mcp工具说明)
5. [REST API使用](#rest-api使用)
6. [示例场景](#示例场景)
7. [故障排除](#故障排除)

---

## 快速开始

### 1. 安装依赖

```bash
# 使用 uv (推荐)
uv pip install -r requirements.txt

# 或使用 pip
pip install -r requirements.txt
```

### 2. 配置MCP实例

在 `data/` 目录下为每个MCP服务创建一个子目录，并添加 `mcp_settings.json`：

```
data/
├── my_provider/
│   └── mcp_settings.json
```

配置文件示例：

```json
{
  "provider": "my_provider",
  "isActive": true,
  "name": "my_instance",
  "type": "stdio",
  "command": "python",
  "args": ["-m", "my_mcp_server"],
  "env": {
    "API_KEY": "your_api_key"
  },
  "metadata": {
    "description": "My MCP Server",
    "version": "1.0.0"
  }
}
```

### 3. 运行

```bash
uv run python main.py
```

---

## 配置说明

### config.json 配置项

#### API配置
```json
{
  "api": {
    "enabled": false,               // 是否启用REST API
    "port": 8000,                   // API端口
    "host": "127.0.0.1",            // API监听地址
    "cors_origin": "*",             // CORS配置
    "auto_find_port": true,         // 端口占用时自动+1查找可用端口
    "enable_realtime_logs": false   // 启用WebSocket实时日志
  }
}
```

#### MCP服务端配置
```json
{
  "server": {
    "enabled": true,                    // 是否启用MCP服务端
    "transport_type": "stdio",          // 传输类型: stdio, sse, http
    "allow_instance_management": false  // 允许LLM管理实例 (add/remove/enable/disable)
  }
}
```

#### MCP客户端配置
```json
{
  "mcp_client": {
    "enabled": true,  // 是否启用MCP客户端
    "timeout": 30     // 操作超时时间（秒）
  }
}
```

#### 安全配置
```json
{
  "security": {
    "bearer_token": "",           // Bearer Token (空字符串=禁用认证)
    "enable_validation": true     // 是否启用输入验证
  }
}
```

#### 日志配置
```json
{
  "logging": {
    "level": "INFO",    // 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF
    "format": "...",    // 日志格式
    "directory": "logs" // 日志目录 (Minecraft风格: latest.txt + YY.MM.DD-HH-MM.txt)
  }
}
```

**日志文件**:
- `logs/latest.txt` - 当前运行的日志
- `logs/25.10.28-23-45.txt` - 历史日志（启动时间戳）

#### 文件监视器配置
```json
{
  "watcher": {
    "enabled": true,          // 是否启用热加载
    "watch_path": "data",     // 监视的目录
    "debounce_delay": 1.0     // 防抖延迟（秒）
  }
}
```

---

## 使用模式

### 模式1: MCP Server (与LLM集成)

**适用场景**: 作为MCP服务器，供LLM通过stdio调用

**配置**:
```json
{
  "api": {"enabled": false},
  "server": {"enabled": true, "transport_type": "stdio"}
}
```

**LLM配置示例** (Claude Desktop):
```json
{
  "mcpServers": {
    "mcp_router": {
      "command": "uv",
      "args": ["--directory", "C:/path/to/mcp_router", "run", "python", "main.py"]
    }
  }
}
```

### 模式2: API Server (配置管理)

**适用场景**: 仅提供REST API进行配置管理

**配置**:
```json
{
  "api": {"enabled": true},
  "server": {"enabled": false}
}
```

**运行后可访问**:
- http://127.0.0.1:8000/docs - API文档
- http://127.0.0.1:8000/api/instances - 列出所有实例

### 模式3: 组合模式

**适用场景**: 同时提供MCP服务和REST API

**配置**:
```json
{
  "api": {"enabled": true},
  "server": {"enabled": true}
}
```

---

## MCP工具说明

当MCP Router作为MCP服务器运行时，LLM可以使用以下工具：

### 1. mcp.router.list()
列出所有已注册的MCP客户端实例

**参数**: 无

**返回示例**:
```json
[
  {
    "name": "openai_docs",
    "provider": "Openai",
    "active": true,
    "connected": true,
    "transport_type": "stdio",
    "tools_count": 5
  }
]
```

### 2. mcp.router.use(instance_name)
切换到指定的MCP实例

**参数**:
- `instance_name` (string): 实例名称

**返回示例**:
```json
{
  "instance": "openai_docs",
  "tools": ["search_api", "get_endpoint", "list_models"],
  "active": true
}
```

### 3. mcp.router.help()
获取所有实例的工具列表和说明

**参数**: 无

**返回示例**:
```json
{
  "openai_docs": [
    {
      "name": "search_api",
      "description": "Search OpenAI API documentation",
      "inputSchema": {...}
    }
  ]
}
```

### 4. mcp.router.call(instance_name, tool_name, arguments)
调用指定实例的工具

**参数**:
- `instance_name` (string): 实例名称
- `tool_name` (string): 工具名称
- `arguments` (object): 工具参数

**示例**:
```json
{
  "instance_name": "openai_docs",
  "tool_name": "search_api",
  "arguments": {
    "query": "chat completions"
  }
}
```

### 5. mcp.router.add(provider_name, config)
动态添加新的MCP配置

**参数**:
- `provider_name` (string): 提供者名称
- `config` (object): MCP配置对象

**示例**:
```json
{
  "provider_name": "new_provider",
  "config": {
    "name": "new_instance",
    "type": "stdio",
    "command": "python",
    "args": ["-m", "new_mcp"],
    "env": {},
    "isActive": true
  }
}
```

### 6. mcp.router.remove(instance_name)
移除MCP实例

**参数**:
- `instance_name` (string): 实例名称

### 7. mcp.router.enable(instance_name) / mcp.router.disable(instance_name)
启用/禁用MCP实例

**参数**:
- `instance_name` (string): 实例名称

---

## REST API使用

### 认证

如果配置了 `bearer_token`，所有API请求需要包含认证头：

```bash
curl -H "Authorization: Bearer your_token_here" http://127.0.0.1:8000/api/instances
```

### API端点

#### 列出所有实例
```bash
GET /api/instances
```

#### 获取实例详情
```bash
GET /api/instances/{name}
```

#### 添加新实例
```bash
POST /api/instances
Content-Type: application/json

{
  "provider": "test",
  "name": "test_instance",
  "type": "stdio",
  "command": "echo",
  "args": ["hello"],
  "env": {},
  "isActive": true
}
```

#### 更新实例
```bash
PATCH /api/instances/{name}
Content-Type: application/json

{配置同上}
```

#### 删除实例
```bash
DELETE /api/instances/{name}
```

#### 启用/禁用实例
```bash
POST /api/instances/{name}/enable
POST /api/instances/{name}/disable
```

#### 列出所有工具
```bash
GET /api/tools
```

#### 获取特定实例的工具
```bash
GET /api/tools/{instance_name}
```

#### 调用工具
```bash
POST /api/call
Content-Type: application/json

{
  "instance": "openai_docs",
  "tool": "search_api",
  "params": {
    "query": "embeddings"
  }
}
```

#### WebSocket实时日志

启用 `enable_realtime_logs` 后：

```bash
# 使用wscat
wscat -c ws://127.0.0.1:8000/ws

# 使用浏览器
const ws = new WebSocket('ws://127.0.0.1:8000/ws');
ws.onmessage = (e) => console.log(e.data);
```

---

## 示例场景

### 场景1: 添加Apifox MCP Server

1. 创建目录和配置:
```bash
mkdir -p data/apifox
```

2. 创建 `data/apifox/mcp_settings.json`:
```json
{
  "provider": "apifox",
  "isActive": true,
  "name": "apifox_docs",
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "apifox-mcp-server@latest", "--project=YOUR_PROJECT_ID"],
  "env": {
    "APIFOX_ACCESS_TOKEN": "your_token"
  }
}
```

3. 如果启用了文件监视器，配置会自动加载。否则重启MCP Router。

### 场景2: 使用API动态添加实例

```bash
curl -X POST http://127.0.0.1:8000/api/instances \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "dynamic",
    "name": "dynamic_instance",
    "type": "stdio",
    "command": "python",
    "args": ["-m", "my_mcp"],
    "env": {},
    "isActive": true
  }'
```

### 场景3: LLM调用工作流

1. LLM调用 `mcp.router.list()` 查看可用实例
2. LLM调用 `mcp.router.use("openai_docs")` 选择实例
3. LLM调用 `mcp.router.help()` 查看该实例的工具
4. LLM调用 `mcp.router.call("openai_docs", "search_api", {"query": "..."})` 执行搜索

---

## 故障排除

### 问题1: 实例连接失败

**症状**: 日志显示 "Failed to connect to instance"

**解决方法**:
1. 检查 `command` 和 `args` 是否正确
2. 确认命令在命令行中可以独立运行
3. 检查 `env` 环境变量是否正确
4. 增加 `timeout` 值

### 问题2: 热加载不工作

**症状**: 修改配置文件后没有自动重载

**解决方法**:
1. 确认 `config.json` 中 `watcher.enabled` 为 `true`
2. 检查文件路径是否在 `watch_path` 下
3. 查看日志是否有watchdog相关错误

### 问题3: API认证失败

**症状**: API返回401 Unauthorized

**解决方法**:
1. 检查 `Authorization` 头格式: `Bearer <token>`
2. 确认token与 `config.json` 中 `security.bearer_token` 一致
3. 如不需要认证，将 `bearer_token` 设为空字符串

### 问题4: 工具调用超时

**症状**: 工具调用返回超时错误

**解决方法**:
1. 增加 `config.json` 中 `mcp_client.timeout` 值
2. 检查被调用的MCP服务器是否响应缓慢
3. 查看日志确认具体超时位置

### 问题5: 日志级别调整

**调试时**:
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

**生产环境**:
```json
{
  "logging": {
    "level": "INFO"  // 或 WARNING
  }
}
```

**完全关闭日志**:
```json
{
  "logging": {
    "level": "OFF"
  }
}
```

---

## 更多帮助

**日志查看**:
- 当前日志: `logs/latest.txt`
- 历史日志: `logs/25.10.28-23-45.txt`
- 实时日志: `ws://127.0.0.1:8000/ws` (需启用API和realtime_logs)

**文档和支持**:
- API文档: http://127.0.0.1:8000/docs
- 健康检查: http://127.0.0.1:8000/health
- 提交Issue: GitHub仓库

