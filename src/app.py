"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
"""

import json
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mcp_server import MCPFinanceServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_AGENT_SYSTEM_PROMPT,
    MAX_ITERATIONS
)
from providers import get_llm_provider

load_dotenv()

def load_test_cases():
    """Tải danh sách 5 test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy file 'config/test_cases.json'. Đang dùng mẫu 'config/test_cases.example.json'.")
            print("👉 Hãy chạy: copy config/test_cases.example.json config/test_cases.json và viết test cases theo đề tài của bạn!\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list, filename: str = "trace_waterfall.json"):
    """Ghi vết log Waterfall Trace Log ra file docs/<filename> (mặc định docs/trace_waterfall.json)"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, os.path.basename(filename))
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện Waterfall Trace tại '{trace_path}'!")


def get_cli_option(name: str, default: str | None = None) -> str | None:
    """Đọc giá trị của tùy chọn dòng lệnh dạng '--name value'"""
    if name in sys.argv:
        index = sys.argv.index(name)
        if index + 1 < len(sys.argv):
            return sys.argv[index + 1]
    return default


def run_baseline_chatbot(user_query: str, provider) -> dict:
    """Chạy Chatbot gốc (Cấp 2) không có công cụ gọi Tool"""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    start_time = time.time()
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    latency_ms = round((time.time() - start_time) * 1000, 2)
    print(f"🤖 Chatbot phản hồi:\n{response}")
    return {"model": getattr(provider, "model_name", "unknown"), "output": response, "latency_ms": latency_ms}


def summarize_agent_logs(logs: list) -> dict:
    """Tóm tắt 1 phiên ReAct Agent: các Tool đã gọi, Final Answer, model, số bước và tổng độ trễ"""
    return {
        "model": next((log["model"] for log in logs if log.get("model")), "unknown"),
        "tool_calls": [
            {"tool_name": log["tool_name"], "arguments": log["arguments"], "status": log["observation"].get("status")}
            for log in logs if log["action_type"] == "TOOL_EXECUTION"
        ],
        "final_answer": next((log["output"] for log in logs if log["action_type"] == "FINAL_ANSWER"), None),
        "steps": max((log["step"] for log in logs), default=0),
        "latency_ms": round(sum(log.get("latency_ms", 0) for log in logs), 2)
    }


def load_saved_agent_results() -> dict:
    """Đọc kết quả ReAct Agent theo test_case_id từ docs/trace_waterfall.json (bỏ qua phiên bị fallback Mock)"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    trace_path = os.path.join(base_dir, "docs", "trace_waterfall.json")
    if not os.path.exists(trace_path):
        return {}
    with open(trace_path, "r", encoding="utf-8") as f:
        logs = json.load(f)

    grouped = {}
    for log in logs:
        if log.get("test_case_id"):
            grouped.setdefault(log["test_case_id"], []).append(log)

    results = {}
    for tc_id, tc_logs in grouped.items():
        summary = summarize_agent_logs(tc_logs)
        if summary["final_answer"] is not None and "Mock" not in str(summary["model"]):
            results[tc_id] = summary
    return results


def run_react_agent(user_query: str, provider, mcp_server: MCPFinanceServer) -> list:
    """
    [REACT AGENT LOOP] Thực thi vòng lặp Thought -> Action -> Observation với MCP Server
    Mỗi Observation được nạp lại vào lịch sử hội thoại để LLM suy luận bước kế tiếp,
    cho tới khi LLM tự đưa ra Final Answer hoặc chạm giới hạn MAX_ITERATIONS.
    Trả về danh sách trace log của phiên thực thi.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    trace_logs = []
    tools_list = mcp_server.list_tools()
    # Bộ nhớ ngắn hạn của Agent: câu hỏi gốc + toàn bộ Action/Observation đã diễn ra
    messages = [{"role": "user", "content": user_query}]

    for step in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")

        # THOUGHT: LLM đọc toàn bộ lịch sử và quyết định bước tiếp theo
        llm_start_time = time.time()
        llm_response = provider.generate_with_tools(messages, tools_list, system_prompt=REACT_AGENT_SYSTEM_PROMPT)
        # Không tính thời gian chờ do rate limit vào độ trễ suy luận thực tế của LLM
        rate_limit_wait_ms = llm_response.get("rate_limit_wait_ms", 0.0)
        llm_latency_ms = round((time.time() - llm_start_time) * 1000 - rate_limit_wait_ms, 2)

        thought = llm_response.get("thought", "Đang suy luận...")
        model = llm_response.get("model", getattr(provider, "model_name", "unknown"))
        print(f"🧠 [Thought]: {thought}")

        # Trường hợp 1: LLM đã đủ thông tin và trả lời bằng văn bản -> Final Answer
        if llm_response.get("type") == "text":
            final_content = llm_response.get("content", "")
            print(f"🏁 [Final Answer]: {final_content}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "model": model,
                "thought": thought,
                "output": final_content,
                "latency_ms": llm_latency_ms
            })
            break

        # Trường hợp 2: LLM đề xuất gọi Tool (Action)
        tool_calls = llm_response.get("tool_calls", [])
        if llm_response.get("type") != "tool_call" or not tool_calls:
            print(f"⚠️ [LLM Response không hợp lệ]: {llm_response}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "ERROR",
                "model": model,
                "thought": thought,
                "output": f"Phản hồi LLM không hợp lệ: {llm_response.get('type')}",
                "latency_ms": llm_latency_ms
            })
            break

        tool_results = []
        for index, call in enumerate(tool_calls):
            print(f"🛠️ [Action]: {call['name']}({json.dumps(call['arguments'], ensure_ascii=False)})")

            # ACTION: Thực thi Tool qua MCP Server
            tool_start_time = time.time()
            mcp_result = mcp_server.call_tool(call["name"], call["arguments"])
            tool_latency_ms = round((time.time() - tool_start_time) * 1000, 2)

            # OBSERVATION: Kết quả thực tế từ MCP Server
            observation = mcp_result.get("result", {})
            print(f"👁️ [Observation từ MCP Server]: {json.dumps(observation, ensure_ascii=False)}")
            tool_results.append({"id": call["id"], "name": call["name"], "result": observation})

            # Thời gian gọi LLM chỉ tính 1 lần cho tool đầu tiên nếu LLM gọi nhiều tool cùng lúc
            step_llm_latency_ms = llm_latency_ms if index == 0 else 0.0
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "TOOL_EXECUTION",
                "model": model,
                "thought": thought,
                "tool_name": call["name"],
                "arguments": call["arguments"],
                "observation": observation,
                "llm_latency_ms": step_llm_latency_ms,
                "tool_latency_ms": tool_latency_ms,
                "latency_ms": round(step_llm_latency_ms + tool_latency_ms, 2)
            })

        # Nạp Action + Observation vào lịch sử để LLM suy luận ở vòng lặp kế tiếp
        messages.append({"role": "assistant_tool_calls", "tool_calls": tool_calls, "raw": llm_response.get("raw")})
        messages.append({"role": "tool_results", "results": tool_results})
    else:
        # for-else: chỉ chạy khi hết MAX_ITERATIONS mà vòng lặp không gặp break (chưa có Final Answer)
        print(f"⛔ [MAX_ITERATIONS]: Agent đã chạy {MAX_ITERATIONS} bước nhưng chưa đưa ra câu trả lời cuối cùng.")
        trace_logs.append({
            "step": MAX_ITERATIONS,
            "query": user_query,
            "action_type": "MAX_ITERATIONS_REACHED",
            "output": f"Agent dừng sau {MAX_ITERATIONS} bước mà chưa đưa ra Final Answer.",
            "latency_ms": 0.0
        })

    return trace_logs


if __name__ == "__main__":
    print("==========================================================")
    print("🏫 VINUNI AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("==========================================================")

    provider = get_llm_provider()
    mcp_server = MCPFinanceServer()

    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")

    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")

    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với ReAct Agent:")
        print("💡 Gợi ý câu hỏi thử nghiệm:")
        print("   - Câu hỏi chung: 'Quy tắc 50/30/20 trong quản lý chi tiêu là gì?'")
        print("   - Tra cứu chi tiêu: 'Tháng 09/2026 tài khoản U001 đã chi tiêu bao nhiêu?'")
        print("   - Ghi khoản chi: 'Ghi giúp U001 khoản chi 45.000đ tiền grab ngày 13/09/2026'")
        print("   - Quyết định có điều kiện: 'U001 kiểm tra ngân sách Giải trí tháng 09/2026, nếu còn đủ thì ghi khoản chi 500.000đ xem ca nhạc ngày 14/09/2026'")
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc phiên trò chuyện.\n")
        while True:
            try:
                user_input = input("👤 Sinh viên hỏi: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break
                logs = run_react_agent(user_input, provider, mcp_server)
                save_waterfall_trace(logs)
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break
    elif "--query" in sys.argv:
        user_query = get_cli_option("--query")
        if not user_query:
            print('❌ Thiếu câu hỏi. Ví dụ: python src/app.py --query "Tháng 09/2026 U001 đã chi bao nhiêu?" --trace-name trace_single_query.json')
            sys.exit(1)
        trace_name = get_cli_option("--trace-name") or "trace_single_query.json"
        print(f"🎯 [SINGLE QUERY MODE] Trace sẽ lưu tại docs/{os.path.basename(trace_name)} (không ghi đè trace của test suite)")
        logs = run_react_agent(user_query, provider, mcp_server)
        save_waterfall_trace(logs, trace_name)
    elif "--compare" in sys.argv:
        print("⚖️ [COMPARE MODE] Chatbot Baseline (Cấp 2) vs ReAct Agent (Cấp 3) trên cùng bộ Test Cases")
        print("ℹ️ Chatbot gọi LLM trực tiếp; kết quả ReAct Agent lấy từ docs/trace_waterfall.json (lần chạy --all), test case nào chưa có sẽ chạy Agent trực tiếp.")
        saved_agent_results = load_saved_agent_results()
        comparisons = []

        for tc in tests:
            if tc["question"].strip().startswith("TODO"):
                continue
            print(f"\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']}")

            chatbot_result = run_baseline_chatbot(tc["question"], provider)

            agent_result = saved_agent_results.get(tc["id"])
            if agent_result:
                agent_result["source"] = "docs/trace_waterfall.json"
                print(f"\n🤖 [REACT AGENT] (từ trace --all, model {agent_result['model']}):")
                for call in agent_result["tool_calls"]:
                    print(f"   🛠️ {call['tool_name']}({json.dumps(call['arguments'], ensure_ascii=False)}) -> {call['status']}")
                print(f"🏁 Final Answer:\n{agent_result['final_answer']}")
            else:
                agent_result = summarize_agent_logs(run_react_agent(tc["question"], provider, mcp_server))
                agent_result["source"] = "live"

            comparisons.append({
                "test_case_id": tc["id"],
                "type": tc["type"],
                "question": tc["question"],
                "chatbot_baseline": chatbot_result,
                "react_agent": agent_result
            })

        save_waterfall_trace(comparisons, "compare_chatbot_vs_agent.json")
        failed_cases = [c["test_case_id"] for c in comparisons if c["chatbot_baseline"]["output"].startswith(("[Gemini", "[OpenAI"))]
        if failed_cases:
            print(f"⚠️ [CẢNH BÁO]: Chatbot Baseline của {failed_cases} bị lỗi API, kết quả so sánh CHƯA hợp lệ. Hãy chạy lại --compare khi còn quota!")
    elif "--all" in sys.argv:
        print("🚀 [TEST SUITE MODE] Kiểm tra 5 Test Cases:")
        completed_count = 0
        todo_count = 0
        all_traces = []

        for tc in tests:
            print(f"\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']} (Độ phức tạp: {tc['complexity']})")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")

            if tc["question"].strip().startswith("TODO"):
                print(f"⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]:")
                print(f"   {tc['question']}")
                print(f"   👉 Hãy mở file 'config/test_cases.json' để viết câu hỏi thực tế cho Test Case này!")
                todo_count += 1
            else:
                logs = run_react_agent(tc["question"], provider, mcp_server)
                for log in logs:
                    log["test_case_id"] = tc["id"]
                all_traces.extend(logs)
                completed_count += 1

        print(f"\n==================================================")
        print(f"📊 [KẾT QUẢ TEST SUITE]: Đã thực thi {completed_count}/{len(tests)} Test Cases | {todo_count} Test Cases đang chờ điền câu hỏi (TODO)")
        if all_traces:
            save_waterfall_trace(all_traces)
            fallback_cases = sorted({log["test_case_id"] for log in all_traces if "Mock" in str(log.get("model"))})
            if fallback_cases and provider.__class__.__name__ != "MockOfflineProvider":
                print(f"⚠️ [CẢNH BÁO NỘP BÀI]: {fallback_cases} có bước bị fallback về Mock do lỗi API. Trace này KHÔNG phản ánh LLM thật, hãy chạy lại!")
        print(f"💡 Để trò chuyện trực tiếp từng câu: Chạy 'python src/app.py --interactive'")
    else:
        # Chế độ mặc định khi chỉ gõ 'python src/app.py'
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG CHƯƠNG TRÌNH:")
        print("  1. Chat trực tiếp liên tục:   python src/app.py --interactive")
        print("  2. Chạy toàn bộ Test Cases:    python src/app.py --all")
        print("  3. Chạy 1 câu hỏi, lưu trace riêng: python src/app.py --query \"<câu hỏi>\" --trace-name <ten_file>.json")
        print("  4. So sánh Chatbot vs Agent:   python src/app.py --compare\n")

        sample_query = tests[1]["question"]
        print(f"--- 🏁 DEMO CHẠY THỬ 1 TEST CASE MẪU (TC02: Tra cứu chi tiêu) ---")
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)
        print("\n💡 Hãy thử ngay lệnh: python src/app.py --interactive để chat trực tiếp!")
