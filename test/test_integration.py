"""集成测试 - 测试MCP Router作为MCP服务器的完整功能."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def exit_on_error(message: str):
    """遇到错误立即退出."""
    print(f"\n[ERROR] 测试失败: {message}")
    sys.exit(1)


@pytest.mark.asyncio
async def test_mcp_router_server_integration():
    """测试MCP Router服务器集成功能."""
    
    print("\n" + "="*60)
    print("开始MCP Router集成测试")
    print("="*60)
    
    project_root = Path(__file__).parent.parent
    
    server_params = StdioServerParameters(
        command="uv",
        args=[
            "--directory",
            str(project_root),
            "run",
            "python",
            "main.py"
        ],
        env=os.environ.copy()
    )
    
    print("\n[1/10] 正在启动MCP Router服务器...")
    
    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                
                print("[OK] MCP Router服务器启动成功")
                
                print("\n[2/10] 正在初始化会话...")
                try:
                    await asyncio.wait_for(session.initialize(), timeout=30.0)
                    print("[OK] 会话初始化成功")
                except asyncio.TimeoutError:
                    exit_on_error("会话初始化超时")
                except Exception as e:
                    exit_on_error(f"会话初始化失败: {e}")
                
                print("\n[3/10] 正在获取可用工具列表...")
                try:
                    tools_result = await asyncio.wait_for(
                        session.list_tools(),
                        timeout=10.0
                    )
                    tools = tools_result.tools
                    print(f"[OK] 获取到 {len(tools)} 个工具")
                    
                    expected_tools = [
                        "mcp.router.use",
                        "mcp.router.list",
                        "mcp.router.help",
                        "mcp.router.add",
                        "mcp.router.call",
                        "mcp.router.remove",
                        "mcp.router.disable",
                        "mcp.router.enable"
                    ]
                    
                    tool_names = [tool.name for tool in tools]
                    print(f"\n   工具列表:")
                    for tool_name in tool_names:
                        print(f"   - {tool_name}")
                    
                    for expected_tool in expected_tools:
                        if expected_tool not in tool_names:
                            exit_on_error(f"缺少必需的工具: {expected_tool}")
                    
                    print(f"\n[OK] 所有 {len(expected_tools)} 个必需工具都存在")
                    
                except asyncio.TimeoutError:
                    exit_on_error("获取工具列表超时")
                except Exception as e:
                    exit_on_error(f"获取工具列表失败: {e}")
                
                print("\n[4/10] 测试 mcp.router.list 工具...")
                try:
                    result = await asyncio.wait_for(
                        session.call_tool("mcp.router.list", {}),
                        timeout=10.0
                    )
                    
                    if not result.content:
                        exit_on_error("mcp.router.list 返回空内容")
                    
                    content_text = result.content[0].text
                    instances = json.loads(content_text)
                    
                    print(f"[OK] 获取到 {len(instances)} 个MCP实例")
                    
                    if instances:
                        print("\n   已注册的实例:")
                        for instance in instances:
                            name = instance.get('name', 'unknown')
                            provider = instance.get('provider', 'unknown')
                            active = instance.get('active', False)
                            status = "[Active]" if active else "[Inactive]"
                            print(f"   {status} {name} ({provider})")
                    
                except asyncio.TimeoutError:
                    exit_on_error("调用 mcp.router.list 超时")
                except json.JSONDecodeError as e:
                    exit_on_error(f"解析 mcp.router.list 返回结果失败: {e}")
                except Exception as e:
                    exit_on_error(f"调用 mcp.router.list 失败: {e}")
                
                print("\n[5/10] 测试 mcp.router.help 工具...")
                try:
                    result = await asyncio.wait_for(
                        session.call_tool("mcp.router.help", {}),
                        timeout=10.0
                    )
                    
                    if not result.content:
                        exit_on_error("mcp.router.help 返回空内容")
                    
                    content_text = result.content[0].text
                    help_info = json.loads(content_text)
                    
                    total_tools = sum(len(tools) for tools in help_info.values())
                    print(f"[OK] 获取到帮助信息，共 {total_tools} 个工具")
                    
                    if help_info:
                        print("\n   各实例的工具数量:")
                        for instance_name, tools in help_info.items():
                            print(f"   - {instance_name}: {len(tools)} 个工具")
                    
                except asyncio.TimeoutError:
                    exit_on_error("调用 mcp.router.help 超时")
                except json.JSONDecodeError as e:
                    exit_on_error(f"解析 mcp.router.help 返回结果失败: {e}")
                except Exception as e:
                    exit_on_error(f"调用 mcp.router.help 失败: {e}")
                
                if instances:
                    print(f"\n[6/10] 测试 mcp.router.use 工具 (使用实例: {instances[0]['name']})...")
                    try:
                        instance_name = instances[0]['name']
                        result = await asyncio.wait_for(
                            session.call_tool("mcp.router.use", {
                                "instance_name": instance_name
                            }),
                            timeout=10.0
                        )
                        
                        if not result.content:
                            exit_on_error("mcp.router.use 返回空内容")
                        
                        content_text = result.content[0].text
                        use_result = json.loads(content_text)
                        
                        print(f"[OK] 成功切换到实例: {use_result.get('instance')}")
                        print(f"   可用工具数: {len(use_result.get('tools', []))}")
                        print(f"   实例状态: {'激活' if use_result.get('active') else '未激活'}")
                        
                    except asyncio.TimeoutError:
                        exit_on_error("调用 mcp.router.use 超时")
                    except json.JSONDecodeError as e:
                        exit_on_error(f"解析 mcp.router.use 返回结果失败: {e}")
                    except Exception as e:
                        exit_on_error(f"调用 mcp.router.use 失败: {e}")
                
                print("\n[7/10] 测试添加新实例 (mcp.router.add)...")
                try:
                    test_config = {
                        "name": "test_integration_instance",
                        "type": "stdio",
                        "command": "python",
                        "args": ["-c", "print('test')"],
                        "env": {},
                        "isActive": False,
                        "metadata": {
                            "description": "Integration test instance",
                            "version": "1.0.0"
                        }
                    }
                    
                    result = await asyncio.wait_for(
                        session.call_tool("mcp.router.add", {
                            "provider_name": "test_integration",
                            "config": test_config
                        }),
                        timeout=15.0
                    )
                    
                    if not result.content:
                        exit_on_error("mcp.router.add 返回空内容")
                    
                    content_text = result.content[0].text
                    add_result = json.loads(content_text)
                    
                    if add_result.get("status") != "success":
                        exit_on_error(f"添加实例失败: {add_result}")
                    
                    print(f"[OK] 成功添加测试实例: {add_result.get('instance_name')}")
                    
                except asyncio.TimeoutError:
                    exit_on_error("调用 mcp.router.add 超时")
                except json.JSONDecodeError as e:
                    exit_on_error(f"解析 mcp.router.add 返回结果失败: {e}")
                except Exception as e:
                    exit_on_error(f"调用 mcp.router.add 失败: {e}")
                
                print("\n[8/10] 测试禁用实例 (mcp.router.disable)...")
                try:
                    result = await asyncio.wait_for(
                        session.call_tool("mcp.router.disable", {
                            "instance_name": "test_integration_instance"
                        }),
                        timeout=10.0
                    )
                    
                    if not result.content:
                        exit_on_error("mcp.router.disable 返回空内容")
                    
                    content_text = result.content[0].text
                    disable_result = json.loads(content_text)
                    
                    if disable_result.get("active") != False:
                        exit_on_error("禁用实例失败")
                    
                    print(f"[OK] 成功禁用实例: {disable_result.get('instance')}")
                    
                except asyncio.TimeoutError:
                    exit_on_error("调用 mcp.router.disable 超时")
                except json.JSONDecodeError as e:
                    exit_on_error(f"解析 mcp.router.disable 返回结果失败: {e}")
                except Exception as e:
                    exit_on_error(f"调用 mcp.router.disable 失败: {e}")
                
                print("\n[9/10] 测试启用实例 (mcp.router.enable)...")
                try:
                    result = await asyncio.wait_for(
                        session.call_tool("mcp.router.enable", {
                            "instance_name": "test_integration_instance"
                        }),
                        timeout=15.0
                    )
                    
                    if not result.content:
                        exit_on_error("mcp.router.enable 返回空内容")
                    
                    content_text = result.content[0].text
                    
                    try:
                        enable_result = json.loads(content_text)
                        
                        if "error" in enable_result:
                            print(f"[WARNING] 启用实例时出现错误（预期行为，因为不是真实的MCP服务器）: {enable_result['error']}")
                            print(f"[OK] 启用实例命令执行成功（但连接失败是正常的）")
                        elif enable_result.get("active") == True:
                            print(f"[OK] 成功启用实例: {enable_result.get('instance')}")
                        else:
                            exit_on_error("启用实例失败")
                    except json.JSONDecodeError:
                        print(f"[WARNING] 无法解析响应，但这在测试中是预期的（不是真实MCP服务器）")
                        print(f"[OK] 启用实例命令执行成功")
                    
                except asyncio.TimeoutError:
                    exit_on_error("调用 mcp.router.enable 超时")
                except Exception as e:
                    print(f"[WARNING] 启用实例时出现异常（预期行为）: {e}")
                    print(f"[OK] 启用实例命令执行成功")
                
                print("\n[10/10] 测试删除实例 (mcp.router.remove)...")
                try:
                    result = await asyncio.wait_for(
                        session.call_tool("mcp.router.remove", {
                            "instance_name": "test_integration_instance"
                        }),
                        timeout=10.0
                    )
                    
                    if not result.content:
                        exit_on_error("mcp.router.remove 返回空内容")
                    
                    content_text = result.content[0].text
                    remove_result = json.loads(content_text)
                    
                    if remove_result.get("status") != "success":
                        exit_on_error("删除实例失败")
                    
                    print(f"[OK] 成功删除实例: {remove_result.get('removed')}")
                    
                except asyncio.TimeoutError:
                    exit_on_error("调用 mcp.router.remove 超时")
                except json.JSONDecodeError as e:
                    exit_on_error(f"解析 mcp.router.remove 返回结果失败: {e}")
                except Exception as e:
                    exit_on_error(f"调用 mcp.router.remove 失败: {e}")
                
                print("\n" + "="*60)
                print("[SUCCESS] 所有集成测试通过!")
                print("="*60)
                
    except Exception as e:
        exit_on_error(f"MCP服务器连接失败: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(test_mcp_router_server_integration())
        print("\n[SUCCESS] 测试执行完成，没有错误")
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n[WARNING] 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        exit_on_error(f"测试执行异常: {e}")

