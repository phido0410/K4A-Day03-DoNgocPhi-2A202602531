# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Đỗ Ngọc Phi  
> **Mã Sinh Viên / Mã Học viên:** 2A202602531  
> **Chủ đề Lựa chọn:** Đề tài Mở — Trợ lý Quản lý Chi tiêu Cá nhân (tra cứu ngân sách/chi tiêu theo tháng + ghi khoản chi mới)  

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | 4 / 5 | Yêu cầu như "kiểm tra ngân sách Ăn uống, nếu còn đủ thì ghi khoản chi 350.000đ" phải chia nhiều bước nối tiếp: (1) tra cứu số tiền còn lại, (2) so sánh với khoản chi, (3) ghi khoản chi, (4) báo ngân sách mới. Chưa đạt 5 vì phần lớn yêu cầu hằng ngày chỉ cần 1–2 bước. |
| **2. Tool Interaction** | 5 / 5 | Ngân sách, lịch sử giao dịch là dữ liệu cá nhân thay đổi liên tục, LLM không thể biết; ghi khoản chi là hành động thay đổi dữ liệu trong sổ chi tiêu. Bắt buộc phải gọi Tool qua MCP Server (`get_spending_summary`, `add_expense`). |
| **3. Dynamic Decision** | 4 / 5 | Quyết định có ghi khoản chi hay không phụ thuộc trực tiếp vào Observation: còn đủ ngân sách thì gọi `add_expense`, không đủ thì dừng và hỏi lại người dùng; `NOT_FOUND` thì báo lỗi; câu hỏi kiến thức chung (quy tắc 50/30/20) thì trả lời thẳng không gọi Tool. Cả hai nhánh đều có trace LLM thật: TC04 (đủ → ghi) trong `docs/trace_waterfall.json`, nhánh từ chối (không đủ → không ghi) trong `docs/trace_refusal_case.json`. |
| **4. Long Horizon Goal** | 2 / 5 | Mục tiêu "giữ chi tiêu trong ngân sách" về bản chất kéo dài cả tháng, nhưng mỗi yêu cầu của hệ thống hiện tại hoàn tất trong 1 phiên ngắn (1–3 vòng lặp) và Agent không có bộ nhớ dài hạn giữa các phiên. |
| **TỔNG ĐIỂM AGENTIC FIT** | **15 / 20** | *Tổng điểm 15 > 12/20: Bài toán phù hợp triển khai ReAct Agent (Cấp 3). Nâng lên Autonomous Agent (Cấp 4) khi cần bộ nhớ dài hạn để tự theo dõi và cảnh báo ngân sách suốt cả tháng.* |

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG (SAU KHI CHẠY TEST SUITE TRÊN API THẬT)

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

Dán 1 đoạn trích xuất log tiêu biểu từ file `docs/trace_waterfall.json` sinh ra từ phản hồi LLM API thật:

**Test Case tiêu biểu: TC04 — Multi-step Reasoning có điều kiện** (model `gemini-3.6-flash`)
> *Câu hỏi:* "Tôi là U001. Kiểm tra giúp tôi ngân sách Ăn uống tháng 09/2026 còn lại bao nhiêu, nếu vẫn còn đủ thì ghi khoản chi 350.000đ ăn tối với gia đình ngày 13/09/2026."
>
> *Trích rút gọn:* trường `thought` được lược bớt (`[...]`), bỏ `query` và `recent_transactions` cho dễ đọc; `arguments`, `observation`, `output` và `latency` giữ nguyên từ file log.

```json
[
  {
    "step": 1,
    "action_type": "TOOL_EXECUTION",
    "model": "gemini-3.6-flash",
    "thought": "[...] It's a conditional transaction – \"if still sufficient\" – so a check is mandatory. I can't just assume; I need hard data. [...] Then, I'll compare the returned remaining amount against the 350,000đ expense. Only *then* will I decide if I should proceed with logging the transaction.",
    "tool_name": "get_spending_summary",
    "arguments": { "month": "09/2026", "user_id": "U001", "category": "Ăn uống" },
    "observation": {
      "status": "SUCCESS",
      "user_id": "U001",
      "full_name": "Nguyễn Minh Anh",
      "month": "09/2026",
      "total_budget": 4000000,
      "total_spent": 3550000,
      "total_remaining": 450000,
      "categories": { "Ăn uống": { "budget": 4000000, "spent": 3550000, "remaining": 450000 } }
    },
    "llm_latency_ms": 5432.91,
    "tool_latency_ms": 0.29,
    "latency_ms": 5433.2,
    "test_case_id": "TC04"
  },
  {
    "step": 2,
    "action_type": "TOOL_EXECUTION",
    "model": "gemini-3.6-flash",
    "thought": "[...] A quick comparison: the remaining budget (450,000đ) is indeed greater than or equal to the expense (350,000đ). Therefore, the budget is sufficient; [...] Now, time to execute the `add_expense` function.",
    "tool_name": "add_expense",
    "arguments": { "amount": 350000, "date": "13/09/2026", "user_id": "U001", "note": "Ăn tối với gia đình", "category": "Ăn uống" },
    "observation": {
      "status": "SUCCESS",
      "transaction": { "id": "TX-U001-0008", "date": "13/09/2026", "category": "Ăn uống", "amount": 350000, "note": "Ăn tối với gia đình" },
      "user_id": "U001",
      "category_budget": { "budget": 4000000, "spent": 3900000, "remaining": 100000 },
      "over_budget": false,
      "message": "Đã ghi khoản chi 350.000đ (Ăn uống) ngày 13/09/2026. Ngân sách Ăn uống tháng 09/2026 còn lại 100.000đ."
    },
    "llm_latency_ms": 6322.4,
    "tool_latency_ms": 0.18,
    "latency_ms": 6322.58,
    "test_case_id": "TC04"
  },
  {
    "step": 3,
    "action_type": "FINAL_ANSWER",
    "model": "gemini-3.6-flash",
    "thought": "**Transaction Confirmed and Response Prepared** [...] after this transaction, the remaining budget for \"Eating Out\" in September 2026 is now 100,000đ.",
    "output": "Ngân sách danh mục **Ăn uống** tháng 09/2026 của bạn trước khi ghi nhận khoản chi mới:\n- **Ngân sách:** 4.000.000đ\n- **Đã chi:** 3.550.000đ\n- **Còn lại:** 450.000đ\n\nVì ngân sách còn đủ (450.000đ ≥ 350.000đ), tôi đã ghi nhận khoản chi cho bạn:\n- **Số tiền:** 350.000đ\n- **Danh mục:** Ăn uống\n- **Ngày chi:** 13/09/2026\n- **Ghi chú:** Ăn tối với gia đình\n\n📌 **Hiện tại, ngân sách Ăn uống tháng 09/2026 còn lại:** **100.000đ**.",
    "latency_ms": 4920.48,
    "test_case_id": "TC04"
  }
]
```

**Waterfall TC04 — phân rã độ trễ theo từng bước:**

| Step | Chuỗi ReAct | LLM (ms) | Tool qua MCP (ms) | Tổng (ms) |
| :---: | :--- | ---: | ---: | ---: |
| 1 | Thought → Action `get_spending_summary` → Observation: còn 450.000đ | 5432.91 | 0.29 | 5433.20 |
| 2 | Thought (450.000đ ≥ 350.000đ) → Action `add_expense` → Observation: còn 100.000đ | 6322.40 | 0.18 | 6322.58 |
| 3 | Thought → Final Answer | 4920.48 | – | 4920.48 |
| **Tổng** | | **16675.79** | **0.47** | **16676.26** |

**Nhận xét:**
- **Dynamic Decision thể hiện rõ trong trace:** ở Step 1, Thought của mô hình tự lên kế hoạch "chỉ quyết định ghi sau khi so sánh số dư"; Step 2 dùng đúng con số 450.000đ từ Observation để quyết định gọi `add_expense`. Agent không tự đoán số dư.
- **Observation được nạp lại cho LLM:** Final Answer trích dẫn chính xác số liệu của cả hai Observation (450.000đ trước khi ghi, 100.000đ sau khi ghi), không bịa số liệu.
- **Nút thắt độ trễ nằm ở LLM:** thời gian suy luận chiếm hơn 99,9% tổng độ trễ, còn Tool qua MCP Server chưa tới 1 ms. Muốn tăng tốc cần giảm số vòng gọi LLM (ví dụ gộp bước), không phải tối ưu Tool.

**Bằng chứng nhánh ngược lại — Agent TỪ CHỐI ghi khi không đủ ngân sách** (`docs/trace_refusal_case.json`, model `gemini-3.6-flash`)
> *Câu hỏi:* "U001 kiểm tra ngân sách Giải trí tháng 09/2026, nếu còn đủ thì ghi khoản chi 500.000đ xem ca nhạc ngày 14/09/2026"
>
> *Tái hiện:* `python src/app.py --query "<câu hỏi trên>" --trace-name trace_refusal_case.json`

| Step | Chuỗi ReAct | LLM (ms) | Tool qua MCP (ms) |
| :---: | :--- | ---: | ---: |
| 1 | Thought → Action `get_spending_summary(U001, 09/2026, Giải trí)` → Observation: còn 120.000đ | 5237.93 | 2.01 |
| 2 | Thought: 120.000đ < 500.000đ, thiếu 380.000đ, áp dụng Quy tắc 7 → Final Answer, **không gọi `add_expense`** | 7740.43 | – |

- *Trích Thought Step 2:* "Simple arithmetic shows that 120,000đ is significantly less than the requested 500,000đ; in fact, there's a shortfall of 380,000đ. Now, based on Rule 7, I *cannot* automatically log this transaction."
- *Trích Final Answer:* "Khoản chi 500.000đ cho việc \"xem ca nhạc\" vượt quá số tiền còn lại **380.000đ** (120.000đ < 500.000đ). Do đó, hệ thống **chưa ghi nhận** khoản chi này theo điều kiện của bạn. Bạn có muốn tiếp tục ghi nhận khoản chi này (chấp nhận vượt ngân sách) hay có điều chỉnh nào khác không?"
- **Đối chiếu với TC04:** cùng dạng yêu cầu có điều kiện và cùng Action đầu tiên, nhưng Observation khác nhau (còn 450.000đ so với còn 120.000đ) dẫn tới hành động tiếp theo khác nhau (gọi so với không gọi `add_expense`). Đây là bằng chứng trực tiếp cho tiêu chí **Dynamic Decision**.

**So sánh Chatbot Baseline (Cấp 2) vs ReAct Agent (Cấp 3)** (`docs/compare_chatbot_vs_agent.json`, cả hai phía dùng `gemini-3.6-flash`)
> *Tái hiện:* `python src/app.py --compare`
>
> *Phương pháp:* Chatbot gọi LLM trực tiếp với `CHATBOT_BASELINE_PROMPT` (không có Tool); kết quả ReAct Agent lấy từ lần chạy `--all` trong `docs/trace_waterfall.json`. Hai phía chạy ở hai thời điểm khác nhau nên số liệu độ trễ chỉ mang tính tham khảo.

| TC | Chatbot Baseline | ReAct Agent | Chatbot (ms) | Agent (ms) |
| :---: | :--- | :--- | ---: | ---: |
| TC01 | Giải thích đầy đủ quy tắc 50/30/20 | Giải thích tương đương, không gọi Tool | 15936.92 | 11323.79 |
| TC02 | Từ chối: không truy cập được dữ liệu của U001 | Trả đủ số liệu 5 danh mục qua `get_spending_summary` | 7156.66 | 11690.97 |
| TC03 | Từ chối, khuyên người dùng tự nhập vào ứng dụng khác | Ghi thành công qua `add_expense`, báo Di chuyển còn 505.000đ | 6985.83 | 8471.18 |
| TC04 | Từ chối cả bước kiểm tra lẫn bước ghi | 2 Tool nối tiếp, quyết định dựa trên Observation, báo Ăn uống còn 100.000đ | 6960.73 | 16676.26 |
| TC05 | Chỉ nói không có quyền truy cập, không biết U999 có tồn tại hay không | Xác nhận chính xác U999 không tồn tại (`NOT_FOUND`) | 7735.65 | 8218.59 |

**Kết luận so sánh:**
- **Câu hỏi kiến thức chung (TC01):** Chatbot đủ dùng, chất lượng tương đương Agent. Điều này khớp với phân tích Agentic Fit: không phải yêu cầu nào cũng cần Agent.
- **Yêu cầu cần dữ liệu hoặc hành động (TC02–TC05):** Chatbot không hoàn thành được yêu cầu nào trong 4 test case; Agent hoàn thành cả 4.
- **Về hallucination:** Chatbot không bịa số liệu, nhưng đó là nhờ System Prompt yêu cầu từ chối. Bài lab chưa thử Chatbot không có chỉ dẫn này, nên chưa kết luận được về nguy cơ bịa đặt của Chatbot thuần.
- **Đánh đổi:** Agent chậm hơn ở các test case có Tool vì phải gọi LLM nhiều vòng; TC04 chậm gấp khoảng 2,4 lần (16,7s so với 7,0s).

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [x] Đã điền API Key thật trong `.env` và xác nhận Agent chạy mượt mà trên LLM API thật (Gemini/OpenAI). *(Toàn bộ 10 sự kiện trong trace đều có `"model": "gemini-3.6-flash"`, không có bước nào fallback về Mock.)*
- **Tổng số Test Cases đã chạy thành công:** 5 / 5 test cases.
- **Số lượt gọi Tool qua MCP Server chính xác:** 5 lượt *(TC02: 1, TC03: 1, TC04: 2, TC05: 1; TC01 đúng kỳ vọng không gọi Tool)*.

**Đối chiếu kết quả thực tế với kỳ vọng từng Test Case:**

| TC | Loại test | Chuỗi hành động thực tế của Gemini | Kết quả |
| :---: | :--- | :--- | :---: |
| TC01 | direct_query | Trả lời trực tiếp quy tắc 50/30/20, không gọi Tool | ✅ |
| TC02 | single_tool_query | `get_spending_summary(U001, 09/2026)` → tổng hợp 5 danh mục, số liệu khớp 100% Observation | ✅ |
| TC03 | expense_recording | `add_expense(amount=45000, category="Di chuyển", date="13/09/2026", note="Tiền grab đi làm")` → báo còn 505.000đ | ✅ |
| TC04 | multi_step_reasoning | `get_spending_summary(Ăn uống)` → so sánh 450.000đ ≥ 350.000đ → `add_expense` → báo còn 100.000đ | ✅ |
| TC05 | edge_case_handling | `get_spending_summary(U999)` → `NOT_FOUND` → dừng, báo lỗi lịch sự, không gọi thêm Tool | ✅ |

**Sự cố gặp phải & cách khắc phục trong quá trình nghiệm thu:**
- `404 NOT_FOUND`: model `gemini-2.5-flash` không còn cấp cho người dùng mới → chuyển sang `gemini-3.6-flash` (bỏ `temperature=0.2` theo khuyến nghị của Gemini 3).
- `429 RESOURCE_EXHAUSTED`: gói miễn phí giới hạn 5 request/phút, lần chạy đầu bị fallback về Mock giữa chừng → bổ sung cơ chế chờ theo `retryDelay` rồi thử lại, không cộng thời gian chờ vào `llm_latency_ms`, và cảnh báo khi trace bị lẫn dữ liệu Mock.
- `429 GenerateRequestsPerDay` (giới hạn 20 request/ngày của gói miễn phí): khi chạy chế độ so sánh `--compare`, Chatbot Baseline của TC02–TC05 bị chặn. Cơ chế retry nhận diện đúng quota theo ngày nên không chờ vô ích; kết quả so sánh lỗi không được đưa vào báo cáo. Sau khi có quota mới, chạy lại `--compare` thành công cả 5/5 test case.
- **Kết quả đẩy Repo nộp bài:** [ ] Đã Commit và Push mã nguồn thành công lên GitHub cá nhân.

---

> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
