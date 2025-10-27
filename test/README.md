# MCP Router 测试说明

## 测试文件

### 单元测试
- `test_router.py` - 路由器功能测试
- `test_api.py` - REST API端点测试
- `test_security.py` - 安全功能测试

### 集成测试
- `test_integration.py` - MCP服务器完整集成测试
- `run_integration_test.py` - 独立运行集成测试的脚本

## 运行测试

### 运行所有单元测试
```bash
uv run pytest test/test_router.py test/test_api.py test/test_security.py -v
```

### 运行集成测试
```bash
# 方法1: 使用pytest
uv run pytest test/test_integration.py -v -s

# 方法2: 直接运行脚本
uv run python test/run_integration_test.py
```

### 运行所有测试
```bash
uv run pytest test/ -v
```

## 集成测试说明

集成测试会：
1. 启动MCP Router服务器（使用stdio传输）
2. 作为MCP客户端连接到服务器
3. 测试所有8个MCP工具的功能
4. 验证工具的输入输出
5. 测试实例的完整生命周期（添加、禁用、启用、删除）

### 测试的工具
- ✅ mcp.router.list - 列出实例
- ✅ mcp.router.help - 获取帮助
- ✅ mcp.router.use - 使用实例
- ✅ mcp.router.add - 添加实例
- ✅ mcp.router.disable - 禁用实例
- ✅ mcp.router.enable - 启用实例
- ✅ mcp.router.remove - 删除实例

### 注意事项
- 集成测试需要 `config.json` 中 `server.enabled = true`
- 测试遇到任何错误会立即退出（exit()）
- 测试会在 `data/test_integration/` 创建临时配置，测试后会自动删除
- 超时时间已设置为合理值，如果超时说明服务器响应异常

## 配置要求

确保 `config.json` 配置正确：

```json
{
  "server": {
    "enabled": true,
    "transport_type": "stdio"
  },
  "mcp_client": {
    "enabled": true,
    "timeout": 30
  }
}
```

## MCP客户端配置示例

在LLM客户端中使用此配置测试MCP Router：

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
        "C:/Users/churan/Documents/Project/ChuranNeko/mcp_router",
        "run",
        "python",
        "main.py"
      ]
    }
  }
}
```

## 故障排除

### 测试失败：会话初始化超时
- 检查 `config.json` 中 `server.enabled` 是否为 `true`
- 检查日志文件 `logs/mcp_router.log`
- 确认没有其他进程占用stdio

### 测试失败：获取工具列表失败
- 检查 `data/` 目录下是否有有效的MCP配置
- 查看日志确认实例是否正确加载

### 测试失败：调用工具超时
- 增加 `config.json` 中的 `timeout` 值
- 检查被调用的MCP实例是否正常工作
- 查看日志了解具体超时原因

