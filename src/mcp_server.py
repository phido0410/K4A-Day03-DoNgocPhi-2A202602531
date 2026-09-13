"""
🔌 MODEL CONTEXT PROTOCOL (MCP) SERVER MODULE
Mô phỏng kiến trúc MCP Server (Client-Server Architecture) cung cấp công cụ chuẩn hóa.
"""

import json
import sys
from typing import Dict, Any, List
from tools import TOOLS_SCHEMA, dispatch_tool_call

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

class MCPFinanceServer:
    """
    Giả lập MCP Server tuân thủ chuẩn giao thức Model Context Protocol
    """
    def __init__(self, server_name: str = "personal-finance-mcp-server"):
        self.server_name = server_name
        self.version = "2026.1.0"

    def list_tools(self) -> List[Dict[str, Any]]:
        """Trả về danh sách các Tools chuẩn giao thức MCP"""
        return TOOLS_SCHEMA

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        [TASK 2.1] HÀM THỰC THI TOOL TRÊN MCP SERVER
        Thực thi request gọi Tool theo chuẩn MCP JSON-RPC
        """
        # Bước 1: Chuyển request tới Tool Router để thực thi tool thực tế
        raw_result = dispatch_tool_call(tool_name, arguments or {})

        # Bước 2: Parse chuỗi JSON thành Dict để Client đọc được từng trường
        try:
            content = json.loads(raw_result)
        except (json.JSONDecodeError, TypeError):
            content = {"status": "INVALID_RESPONSE", "error": f"Tool '{tool_name}' trả về dữ liệu không phải JSON: {raw_result!r}"}

        # Bước 3: Đóng gói phản hồi theo chuẩn MCP JSON-RPC 2.0
        return {
            "jsonrpc": "2.0",
            "server": self.server_name,
            "tool": tool_name,
            "result": content
        }


if __name__ == "__main__":
    print("==========================================================")
    print("🔌 KIỂM THỬ ĐỘC LẬP MCP SERVER (personal-finance-mcp-server)")
    print("==========================================================")

    server = MCPFinanceServer()
    tools = server.list_tools()
    print(f"✅ Khởi tạo thành công MCP Server: {server.server_name} (Version: {server.version})")
    print(f"📦 Số lượng Tools công bố: {len(tools)}")

    # Kiểm tra Tool Schema (Task 1.2)
    incomplete = [t.get("name") for t in tools if not t.get("parameters", {}).get("properties")]
    if incomplete:
        print(f"⏳ [TASK 1.2]: Tool {incomplete} chưa được định nghĩa properties trong 'src/tools.py'.")
    else:
        print(f"✅ [TASK 1.2]: Tất cả Tools đã có schema đầy đủ: {[t['name'] for t in tools]}")

    # Kiểm tra call_tool (Task 2.1)
    test_result = server.call_tool("get_spending_summary", {"user_id": "U001", "month": "09/2026", "category": "Ăn uống"})
    if not test_result:
        print("⏳ [TASK 2.1]: Hàm call_tool() đang trả về rỗng. Hãy hoàn thiện Task 2.1 trong 'src/mcp_server.py'!")
    else:
        print(f"✅ [TASK 2.1]: Test dispatch tool 'get_spending_summary' thành công:")
        print(f"   Phản hồi JSON-RPC: {json.dumps(test_result, ensure_ascii=False)}")
