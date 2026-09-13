"""
🔌 MULTI-PROVIDER LLM ADAPTER (Google Gemini, OpenAI & Offline Mock)
Hỗ trợ Native Tool Calling, hội thoại nhiều lượt (ReAct history) và chuyển đổi linh hoạt qua biến môi trường LLM_PROVIDER.

📨 ĐỊNH DẠNG LỊCH SỬ HỘI THOẠI CHUNG (provider-neutral) mà app.py truyền vào generate_with_tools():
  {"role": "user", "content": "câu hỏi của người dùng"}
  {"role": "assistant_tool_calls", "tool_calls": [{"id", "name", "arguments"}], "raw": <nội dung gốc từ provider>}
  {"role": "tool_results", "results": [{"id", "name", "result": dict}]}
Mỗi provider tự chuyển định dạng chung này sang định dạng riêng của SDK (Gemini Content / OpenAI messages).
"""

import os
import re
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

Messages = Union[str, List[Dict[str, Any]]]


def _normalize_messages(messages: Messages) -> List[Dict[str, Any]]:
    """Cho phép truyền 1 câu hỏi dạng chuỗi (tương thích cách gọi cũ) hoặc cả lịch sử hội thoại"""
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    return messages


class BaseLLMProvider:
    """Interface cơ sở cho các LLM Provider hỗ trợ Native Tool Calling"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(self, messages: Messages, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        """
        Trả về 1 trong 2 dạng:
          {"type": "text", "content": str, "thought": str, "model": str}
          {"type": "tool_call", "tool_calls": [{"id", "name", "arguments"}], "thought": str, "model": str, "raw": Any}
        """
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Offline Mock Provider mô phỏng LLM bằng luật từ khóa + đọc Observation trong lịch sử (không tốn API Key)"""
    CATEGORY_KEYWORDS = {
        "Ăn uống": ["ăn", "uống", "cà phê", "đi chợ", "nhà hàng"],
        "Di chuyển": ["grab", "taxi", "xăng", "gửi xe", "xe buýt"],
        "Mua sắm": ["mua", "quần áo", "shopee", "siêu thị"],
        "Giải trí": ["phim", "ca nhạc", "game", "du lịch"],
        "Hóa đơn": ["tiền điện", "tiền nước", "internet", "hóa đơn"],
    }

    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return f"[Mock Chatbot Response]: Xin chào! Tôi đã nhận được câu hỏi '{prompt}'. (Chế độ Chatbot không có Tool tra cứu dữ liệu thời gian thực)."

    @staticmethod
    def _vnd(amount: int) -> str:
        return f"{amount:,}".replace(",", ".") + "đ"

    @staticmethod
    def _extract_amount(text: str) -> Optional[int]:
        match = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(k|nghìn|ngàn|đ|vnđ|vnd)\b", text, re.IGNORECASE)
        if not match:
            return None
        amount = int(re.sub(r"[.,]", "", match.group(1)))
        return amount * 1000 if match.group(2).lower() in ("k", "nghìn", "ngàn") else amount

    @staticmethod
    def _extract_date(text: str) -> Optional[str]:
        match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if match:
            return f"{int(match.group(1)):02d}/{int(match.group(2)):02d}/{match.group(3)}"
        if "hôm nay" in text.lower():
            return datetime.now().strftime("%d/%m/%Y")
        return None

    def _extract_month(self, text: str) -> Optional[str]:
        match = re.search(r"tháng\s+(\d{1,2})/(\d{4})", text, re.IGNORECASE)
        if match:
            return f"{int(match.group(1)):02d}/{match.group(2)}"
        date = self._extract_date(text)
        return date[3:] if date else None

    def _extract_category(self, text: str, allow_keywords: bool) -> Optional[str]:
        text_lower = text.lower()
        for category in self.CATEGORY_KEYWORDS:
            if category.lower() in text_lower:
                return category
        if allow_keywords:
            for category, keywords in self.CATEGORY_KEYWORDS.items():
                if any(k in text_lower for k in keywords):
                    return category
        return None

    @staticmethod
    def _extract_note(text: str) -> str:
        match = re.search(r"\d\s*(?:k|nghìn|ngàn|đ|vnđ|vnd)\s+(.+?)\s+(?:hôm nay|ngày|vào)\b", text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _text(self, content: str, thought: str) -> Dict[str, Any]:
        return {"type": "text", "content": content, "thought": thought, "model": self.model_name}

    def _tool_call(self, name: str, arguments: Dict[str, Any], thought: str, call_index: int) -> Dict[str, Any]:
        return {
            "type": "tool_call",
            "tool_calls": [{"id": f"mock-call-{call_index}", "name": name, "arguments": arguments}],
            "thought": thought,
            "model": self.model_name,
            "raw": None
        }

    def generate_with_tools(self, messages: Messages, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        messages = _normalize_messages(messages)
        query = [m["content"] for m in messages if m["role"] == "user"][-1]
        query_lower = query.lower()
        observations = [r for m in messages if m["role"] == "tool_results" for r in m["results"]]
        call_index = len(observations) + 1

        user_match = re.search(r"\bU\d+\b", query, re.IGNORECASE)
        user_id = user_match.group(0).upper() if user_match else None
        wants_add = any(k in query_lower for k in ["ghi ", "thêm khoản", "thêm chi", "nhập khoản"])
        wants_check = any(k in query_lower for k in ["kiểm tra", "xem", "bao nhiêu", "còn lại", "còn đủ", "tình hình"])
        month = self._extract_month(query)
        amount = self._extract_amount(query)
        date = self._extract_date(query)
        category = self._extract_category(query, allow_keywords=wants_add)

        expense_args = {"user_id": user_id, "amount": amount, "category": category, "date": date, "note": self._extract_note(query)}
        missing = [name for name in ("amount", "category", "date") if not expense_args[name]]

        # Lượt đầu tiên: chưa có Observation nào trong lịch sử
        if not observations:
            if not user_id:
                if wants_add or wants_check:
                    return self._text(
                        "[Mock Agent Response]: Bạn vui lòng cung cấp mã người dùng (ví dụ: U001) để tôi tra cứu hoặc ghi chi tiêu.",
                        "Yêu cầu cần dữ liệu sổ chi tiêu nhưng thiếu mã người dùng, cần hỏi lại."
                    )
                return self._text(
                    "[Mock Agent Response]: Quy tắc 50/30/20 chia thu nhập sau thuế thành 50% cho nhu cầu thiết yếu, "
                    "30% cho mong muốn cá nhân và 20% cho tiết kiệm hoặc trả nợ.",
                    "Câu hỏi kiến thức chung về quản lý tài chính, trả lời trực tiếp không cần gọi Tool."
                )
            if wants_add and wants_check:
                if not month:
                    return self._text("Bạn muốn kiểm tra ngân sách của tháng nào (MM/YYYY)?", "Thiếu tháng để tra cứu ngân sách, cần hỏi lại.")
                arguments = {"user_id": user_id, "month": month}
                if category:
                    arguments["category"] = category
                return self._tool_call(
                    "get_spending_summary", arguments,
                    f"Người dùng muốn ghi khoản chi có điều kiện ngân sách. Tôi phải tra cứu ngân sách {category or ''} tháng {month} trước rồi mới quyết định.",
                    call_index
                )
            if wants_add:
                if missing:
                    return self._text(f"Để ghi khoản chi, bạn vui lòng cung cấp thêm: {', '.join(missing)}.", f"Thiếu thông tin bắt buộc {missing}, không tự đoán.")
                return self._tool_call(
                    "add_expense", expense_args,
                    f"Người dùng cung cấp đủ thông tin khoản chi {self._vnd(amount)} ({category}). Tôi gọi add_expense.",
                    call_index
                )
            if month:
                arguments = {"user_id": user_id, "month": month}
                if category:
                    arguments["category"] = category
                return self._tool_call(
                    "get_spending_summary", arguments,
                    f"Người dùng muốn xem tình hình chi tiêu tháng {month} của {user_id}. Tôi gọi get_spending_summary.",
                    call_index
                )
            return self._text("Bạn muốn xem chi tiêu của tháng nào (MM/YYYY)?", "Thiếu tháng để tra cứu, cần hỏi lại.")

        # Các lượt sau: suy luận dựa trên Observation gần nhất
        last = observations[-1]
        obs = last["result"]
        if obs.get("status") != "SUCCESS":
            return self._text(
                f"Rất tiếc, {obs.get('message') or obs.get('error', 'đã có lỗi xảy ra')}. Bạn vui lòng kiểm tra lại thông tin.",
                f"Tool trả về trạng thái {obs.get('status')}, không có dữ liệu. Tôi dừng lại và báo lỗi, không bịa số liệu."
            )

        already_added = any(r["name"] == "add_expense" for r in observations)
        if last["name"] == "get_spending_summary" and wants_add and not already_added:
            if missing:
                return self._text(f"Để ghi khoản chi, bạn vui lòng cung cấp thêm: {', '.join(missing)}.", f"Thiếu thông tin bắt buộc {missing}, không tự đoán.")
            remaining = obs["categories"].get(category, {}).get("remaining", 0)
            if amount > remaining:
                return self._text(
                    f"Ngân sách {category} tháng {obs['month']} chỉ còn {self._vnd(remaining)}, khoản chi {self._vnd(amount)} sẽ vượt "
                    f"{self._vnd(amount - remaining)}. Tôi chưa ghi khoản chi này, bạn có muốn vẫn ghi không?",
                    f"Observation: {category} còn {self._vnd(remaining)} < {self._vnd(amount)}. Không đủ điều kiện nên KHÔNG gọi add_expense."
                )
            return self._tool_call(
                "add_expense", expense_args,
                f"Observation: {category} còn {self._vnd(remaining)} >= {self._vnd(amount)}. Đủ ngân sách, tôi gọi add_expense.",
                call_index
            )

        if last["name"] == "get_spending_summary":
            details = "; ".join(
                f"{c}: đã chi {self._vnd(r['spent'])}/{self._vnd(r['budget'])}, còn {self._vnd(r['remaining'])}"
                for c, r in obs["categories"].items()
            )
            return self._text(
                f"Tháng {obs['month']}, {obs['full_name']} ({obs['user_id']}) đã chi {self._vnd(obs['total_spent'])} trên tổng ngân sách "
                f"{self._vnd(obs['total_budget'])}, còn lại {self._vnd(obs['total_remaining'])}. Chi tiết: {details}.",
                "Đã có đủ số liệu từ get_spending_summary, tổng hợp câu trả lời cho người dùng."
            )
        return self._text(obs.get("message", "Đã xử lý thành công."), "Tool đã thực thi thành công, xác nhận kết quả với người dùng.")


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider (Native Tool Calling với Google GenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-3.6-flash"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.api_key)
            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
            response, _ = self._generate_with_retry(client, prompt, config)
            return response.text or ""
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"

    MAX_RATE_LIMIT_RETRIES = 3

    def _generate_with_retry(self, client, contents, config):
        """
        Gọi Gemini API. Khi vượt giới hạn request/phút (429) thì chờ đúng thời gian server yêu cầu (retryDelay) rồi thử lại,
        thay vì fallback về Mock làm trace bị lẫn dữ liệu giả. Trả về (response, tổng thời gian đã chờ tính bằng ms).
        """
        from google.genai import errors

        waited_ms = 0.0
        for attempt in range(1, self.MAX_RATE_LIMIT_RETRIES + 2):
            try:
                response = client.models.generate_content(model=self.model_name, contents=contents, config=config)
                return response, round(waited_ms, 2)
            except errors.ClientError as e:
                details = json.dumps(e.details, ensure_ascii=False)
                # Hết quota theo ngày thì chờ vài chục giây cũng vô ích -> ném lỗi ra ngoài
                if e.code != 429 or "PerDay" in details or attempt > self.MAX_RATE_LIMIT_RETRIES:
                    raise
                match = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', details)
                wait_seconds = float(match.group(1)) + 1 if match else 30.0
                print(f"⏳ [Gemini Rate Limit]: Vượt giới hạn request/phút của gói miễn phí. Chờ {wait_seconds:.0f}s rồi thử lại (lần {attempt}/{self.MAX_RATE_LIMIT_RETRIES})...")
                time.sleep(wait_seconds)
                waited_ms += wait_seconds * 1000

    @staticmethod
    def _to_gemini_contents(messages: List[Dict[str, Any]], types) -> list:
        """Chuyển lịch sử hội thoại chung sang danh sách Content của Gemini"""
        contents = []
        for m in messages:
            if m["role"] == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=m["content"])]))
            elif m["role"] == "assistant_tool_calls":
                # Ưu tiên gửi lại nội dung gốc của Gemini để giữ nguyên thought_signature
                if isinstance(m.get("raw"), types.Content):
                    contents.append(m["raw"])
                else:
                    contents.append(types.Content(role="model", parts=[
                        types.Part.from_function_call(name=c["name"], args=c["arguments"]) for c in m["tool_calls"]
                    ]))
            elif m["role"] == "tool_results":
                contents.append(types.Content(role="user", parts=[
                    types.Part.from_function_response(name=r["name"], response=r["result"]) for r in m["results"]
                ]))
        return contents

    def generate_with_tools(self, messages: Messages, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        messages = _normalize_messages(messages)
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("ℹ️ [Gemini Provider]: Chưa tìm thấy GEMINI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(messages, tools_schema, system_prompt)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            # Chuẩn hóa function declarations cho Gemini SDK
            function_declarations = []
            for tool in tools_schema:
                # Bỏ qua các tool schema chưa được định nghĩa hoàn chỉnh
                if not tool.get("name") or not tool.get("parameters"):
                    continue
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })

            is_gemini_3 = "gemini-3" in self.model_name
            # Chỉ dòng Gemini 2.5+ hỗ trợ trả về tóm tắt suy luận (Thought) thật của mô hình
            supports_thinking = "gemini-2.5" in self.model_name or is_gemini_3

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                thinking_config=types.ThinkingConfig(include_thoughts=True) if supports_thinking else None,
                # Gemini 3 khuyến nghị giữ temperature mặc định; giảm temperature có thể khiến mô hình lặp hoặc suy luận kém
                temperature=None if is_gemini_3 else 0.2,
                # Tắt Automatic Function Calling của SDK: vòng lặp ReAct trong app.py tự thực thi Tool qua MCP Server
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )

            response, rate_limit_wait_ms = self._generate_with_retry(client, self._to_gemini_contents(messages, types), config)

            candidate = response.candidates[0] if response.candidates else None
            parts = candidate.content.parts if candidate and candidate.content and candidate.content.parts else []
            thought_text = " ".join(p.text.strip() for p in parts if p.thought and p.text)
            answer_text = "".join(p.text for p in parts if p.text and not p.thought)

            # Kiểm tra xem Gemini có trả về Tool Call không
            if response.function_calls:
                tool_calls = [
                    {"id": call.id or f"gemini-call-{i}", "name": call.name, "arguments": dict(call.args) if call.args else {}}
                    for i, call in enumerate(response.function_calls)
                ]
                summary = ", ".join(f"{c['name']}({json.dumps(c['arguments'], ensure_ascii=False)})" for c in tool_calls)
                return {
                    "type": "tool_call",
                    "tool_calls": tool_calls,
                    "thought": thought_text or answer_text or f"Gemini quyết định gọi công cụ: {summary}",
                    "model": self.model_name,
                    "raw": types.Content(role="model", parts=[p for p in parts if not p.thought]),
                    "rate_limit_wait_ms": rate_limit_wait_ms
                }
            return {
                "type": "text",
                "content": answer_text,
                "thought": thought_text or "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi thêm công cụ).",
                "model": self.model_name,
                "rate_limit_wait_ms": rate_limit_wait_ms
            }

        except Exception as e:
            print(f"⚠️ [Gemini API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(messages, tools_schema, system_prompt)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (Native Tool Calling với OpenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"

    @staticmethod
    def _to_openai_messages(messages: List[Dict[str, Any]], system_prompt: str) -> List[Dict[str, Any]]:
        """Chuyển lịch sử hội thoại chung sang định dạng messages của OpenAI Chat Completions"""
        out = [{"role": "system", "content": system_prompt}] if system_prompt else []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant_tool_calls":
                out.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                        for c in m["tool_calls"]
                    ]
                })
            elif m["role"] == "tool_results":
                # OpenAI yêu cầu mỗi tool_call_id phải có đúng 1 message role="tool" tương ứng
                for r in m["results"]:
                    out.append({"role": "tool", "tool_call_id": r["id"], "content": json.dumps(r["result"], ensure_ascii=False)})
        return out

    def generate_with_tools(self, messages: Messages, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        messages = _normalize_messages(messages)
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            print("ℹ️ [OpenAI Provider]: Chưa tìm thấy OPENAI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(messages, tools_schema, system_prompt)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            tools = []
            for tool in tools_schema:
                if not tool.get("name"):
                    continue
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                })

            request = {"model": self.model_name, "messages": self._to_openai_messages(messages, system_prompt)}
            if tools:
                request["tools"] = tools
                request["tool_choice"] = "auto"
            response = client.chat.completions.create(**request)

            msg = response.choices[0].message
            if msg.tool_calls:
                tool_calls = [
                    {"id": call.id, "name": call.function.name,
                     "arguments": json.loads(call.function.arguments) if call.function.arguments else {}}
                    for call in msg.tool_calls
                ]
                summary = ", ".join(f"{c['name']}({json.dumps(c['arguments'], ensure_ascii=False)})" for c in tool_calls)
                return {
                    "type": "tool_call",
                    "tool_calls": tool_calls,
                    "thought": msg.content or f"OpenAI quyết định gọi công cụ: {summary}",
                    "model": self.model_name,
                    "raw": None
                }
            return {
                "type": "text",
                "content": msg.content or "",
                "thought": "OpenAI phản hồi trực tiếp bằng văn bản (không cần gọi thêm công cụ).",
                "model": self.model_name
            }
        except Exception as e:
            print(f"⚠️ [OpenAI API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(messages, tools_schema, system_prompt)


def get_llm_provider() -> BaseLLMProvider:
    """Factory function khởi tạo Provider theo LLM_PROVIDER env variable"""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider_type == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if key and key != "your_gemini_api_key_here":
            return GeminiProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key and key != "your_openai_api_key_here":
            return OpenAIProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "mock":
        return MockOfflineProvider()
    else:
        return MockOfflineProvider()
