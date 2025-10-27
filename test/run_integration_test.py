"""独立运行集成测试的脚本."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from test.test_integration import test_mcp_router_server_integration


if __name__ == "__main__":
    print("正在运行MCP Router集成测试...")
    print("确保config.json中server.enabled=true")
    print()
    
    try:
        asyncio.run(test_mcp_router_server_integration())
        print("\n" + "="*60)
        print("[SUCCESS] 所有测试通过！MCP Router工作正常")
        print("="*60)
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

