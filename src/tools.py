"""
🛠️ TOOL DEFINITIONS & EXECUTION BACKEND
Mã nguồn chứa danh sách Tool Schemas (JSON Schema) và Execution Layer phục vụ cho MCP Server.
Đề tài: Trợ lý Quản lý Chi tiêu Cá nhân (Đề tài Mở).
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional

CATEGORIES = ["Ăn uống", "Di chuyển", "Mua sắm", "Giải trí", "Hóa đơn"]

# ==============================================================================
# 1. KHAI BÁO TOOL SCHEMAS CHUẨN NATIVE JSON SCHEMA (TASK 1.2)
# ==============================================================================

TOOLS_SCHEMA = [
    # Tool 1: Tra cứu thông tin (đọc dữ liệu)
    {
        "name": "get_spending_summary",
        "description": (
            "Tra cứu tình hình chi tiêu của người dùng trong một tháng: ngân sách, số tiền đã chi và số tiền còn lại "
            "theo từng danh mục, kèm các giao dịch gần nhất. "
            "Hãy gọi tool này trước khi ghi khoản chi nếu cần biết ngân sách còn đủ hay không."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Mã người dùng cần tra cứu (ví dụ: 'U001')"
                },
                "month": {
                    "type": "string",
                    "description": "Tháng cần tra cứu theo định dạng 'MM/YYYY' (ví dụ: '09/2026')"
                },
                "category": {
                    "type": "string",
                    "enum": CATEGORIES,
                    "description": "(Tùy chọn) Chỉ xem một danh mục chi tiêu. Bỏ trống để xem tất cả danh mục."
                }
            },
            "required": ["user_id", "month"]
        }
    },

    # Tool 2: Hành động (ghi dữ liệu)
    {
        "name": "add_expense",
        "description": (
            "Ghi một khoản chi tiêu mới vào sổ chi tiêu của người dùng và trả về ngân sách còn lại của danh mục đó. "
            "Chỉ gọi khi đã có đủ mã người dùng, số tiền, danh mục và ngày chi."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Mã người dùng (ví dụ: 'U001')"
                },
                "amount": {
                    "type": "integer",
                    "description": "Số tiền đã chi, đơn vị VND, số nguyên dương (ví dụ: '350.000đ' -> 350000, '45k' -> 45000)"
                },
                "category": {
                    "type": "string",
                    "enum": CATEGORIES,
                    "description": "Danh mục chi tiêu phù hợp nhất với khoản chi (ví dụ: tiền grab -> 'Di chuyển')"
                },
                "date": {
                    "type": "string",
                    "description": "Ngày chi tiêu theo định dạng 'DD/MM/YYYY' (ví dụ: '13/09/2026')"
                },
                "note": {
                    "type": "string",
                    "description": "Mô tả ngắn cho khoản chi (ví dụ: 'Ăn tối cùng gia đình')"
                }
            },
            "required": ["user_id", "amount", "category", "date"]
        }
    }
]

# ==============================================================================
# 2. MÔ PHỎNG DỮ LIỆU & HÀM THỰC THI TOOL (EXECUTION LAYER)
# ==============================================================================

# Sổ chi tiêu giả lập lưu trong bộ nhớ: add_expense ghi thêm giao dịch nên các lần tra cứu sau thấy số liệu mới
MOCK_DATABASE = {
    "U001": {
        "full_name": "Nguyễn Minh Anh",
        "budgets": {
            "09/2026": {"Ăn uống": 4000000, "Di chuyển": 1000000, "Mua sắm": 2000000, "Giải trí": 1000000, "Hóa đơn": 2500000}
        },
        "transactions": [
            {"id": "TX-U001-0001", "date": "02/09/2026", "category": "Hóa đơn", "amount": 2150000, "note": "Tiền điện, nước và internet"},
            {"id": "TX-U001-0002", "date": "05/09/2026", "category": "Ăn uống", "amount": 1250000, "note": "Đi chợ tuần 1"},
            {"id": "TX-U001-0003", "date": "07/09/2026", "category": "Mua sắm", "amount": 1200000, "note": "Mua giày chạy bộ"},
            {"id": "TX-U001-0004", "date": "08/09/2026", "category": "Di chuyển", "amount": 450000, "note": "Xăng xe và gửi xe"},
            {"id": "TX-U001-0005", "date": "10/09/2026", "category": "Giải trí", "amount": 880000, "note": "Xem phim và cà phê cuối tuần"},
            {"id": "TX-U001-0006", "date": "12/09/2026", "category": "Ăn uống", "amount": 2300000, "note": "Đi chợ tuần 2 và ăn ngoài"}
        ]
    },
    "U002": {
        "full_name": "Trần Quốc Bảo",
        "budgets": {
            "09/2026": {"Ăn uống": 3000000, "Di chuyển": 800000, "Mua sắm": 1000000, "Giải trí": 500000, "Hóa đơn": 1500000}
        },
        "transactions": [
            {"id": "TX-U002-0001", "date": "03/09/2026", "category": "Hóa đơn", "amount": 1320000, "note": "Tiền nhà trọ phần điện nước"},
            {"id": "TX-U002-0002", "date": "09/09/2026", "category": "Ăn uống", "amount": 950000, "note": "Ăn trưa văn phòng"}
        ]
    }
}


def _format_vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + "đ"


def _error(status: str, message: str) -> str:
    return json.dumps({"status": status, "message": message}, ensure_ascii=False)


def _normalize_month(month: str) -> Optional[str]:
    """Chuẩn hóa '9/2026' hoặc '09/2026' thành '09/2026'"""
    try:
        return datetime.strptime(str(month).strip(), "%m/%Y").strftime("%m/%Y")
    except ValueError:
        return None


def _category_report(user: Dict[str, Any], month: str, category: str) -> Dict[str, int]:
    budget = user["budgets"][month][category]
    spent = sum(t["amount"] for t in user["transactions"] if t["category"] == category and t["date"][3:] == month)
    return {"budget": budget, "spent": spent, "remaining": budget - spent}


def execute_get_spending_summary(user_id: str, month: str, category: Optional[str] = None) -> str:
    """Thực thi tra cứu tình hình chi tiêu theo tháng"""
    user_key = str(user_id).strip().upper()
    user = MOCK_DATABASE.get(user_key)
    if not user:
        return _error("NOT_FOUND", f"Không tìm thấy người dùng có mã '{user_id}'")

    month_key = _normalize_month(month)
    if not month_key or month_key not in user["budgets"]:
        return _error("NOT_FOUND", f"Người dùng {user_key} chưa thiết lập ngân sách cho tháng '{month}'")
    if category and category not in CATEGORIES:
        return _error("INVALID_ARGUMENT", f"Danh mục '{category}' không hợp lệ. Chọn một trong: {', '.join(CATEGORIES)}")

    selected = [category] if category else CATEGORIES
    report = {c: _category_report(user, month_key, c) for c in selected}
    transactions = [
        t for t in user["transactions"]
        if t["date"][3:] == month_key and (not category or t["category"] == category)
    ]
    return json.dumps({
        "status": "SUCCESS",
        "user_id": user_key,
        "full_name": user["full_name"],
        "month": month_key,
        "total_budget": sum(r["budget"] for r in report.values()),
        "total_spent": sum(r["spent"] for r in report.values()),
        "total_remaining": sum(r["remaining"] for r in report.values()),
        "categories": report,
        "recent_transactions": transactions[-3:]
    }, ensure_ascii=False)


def execute_add_expense(user_id: str, amount: int, category: str, date: str, note: str = "") -> str:
    """Thực thi ghi khoản chi tiêu mới vào sổ chi tiêu"""
    user_key = str(user_id).strip().upper()
    user = MOCK_DATABASE.get(user_key)
    if not user:
        return _error("NOT_FOUND", f"Không tìm thấy người dùng có mã '{user_id}'")

    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return _error("INVALID_ARGUMENT", f"Số tiền '{amount}' không hợp lệ, cần là số nguyên VND")
    if amount <= 0:
        return _error("INVALID_ARGUMENT", "Số tiền phải là số nguyên dương")
    if category not in CATEGORIES:
        return _error("INVALID_ARGUMENT", f"Danh mục '{category}' không hợp lệ. Chọn một trong: {', '.join(CATEGORIES)}")
    try:
        date_key = datetime.strptime(str(date).strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
    except ValueError:
        return _error("INVALID_ARGUMENT", f"Ngày '{date}' không đúng định dạng DD/MM/YYYY")

    month_key = date_key[3:]
    if month_key not in user["budgets"]:
        return _error("NOT_FOUND", f"Người dùng {user_key} chưa thiết lập ngân sách cho tháng '{month_key}'")

    transaction = {
        "id": f"TX-{user_key}-{len(user['transactions']) + 1:04d}",
        "date": date_key,
        "category": category,
        "amount": amount,
        "note": note
    }
    user["transactions"].append(transaction)

    report = _category_report(user, month_key, category)
    over_budget = report["remaining"] < 0
    message = (
        f"Đã ghi khoản chi {_format_vnd(amount)} ({category}) ngày {date_key}. "
        f"Ngân sách {category} tháng {month_key} còn lại {_format_vnd(report['remaining'])}."
    )
    if over_budget:
        message += " Cảnh báo: danh mục này đã vượt ngân sách!"

    return json.dumps({
        "status": "SUCCESS",
        "transaction": transaction,
        "user_id": user_key,
        "category_budget": report,
        "over_budget": over_budget,
        "message": message
    }, ensure_ascii=False)


# Router gọi tool thực tế
TOOL_ROUTER = {
    "get_spending_summary": execute_get_spending_summary,
    "add_expense": execute_add_expense
}

def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Hàm trung chuyển thực thi tool"""
    if tool_name in TOOL_ROUTER:
        try:
            return TOOL_ROUTER[tool_name](**arguments)
        except Exception as e:
            return json.dumps({"status": "EXECUTION_ERROR", "error": str(e)}, ensure_ascii=False)
    return json.dumps({"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại!"}, ensure_ascii=False)
