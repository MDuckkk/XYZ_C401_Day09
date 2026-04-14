# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** _____Trần Thanh Nguyên______  
**Vai trò trong nhóm:** Worker Owner
**Ngày nộp:** 15/04/2026

---

## 1. Tôi phụ trách phần nào?

Trong lab Day 09, tôi chịu trách nhiệm chính cho  worker xử lý logic liên quan.
**Module/file tôi chịu trách nhiệm:**
- File chính: `workers

**Functions tôi implement:**

| Function | Mô tả |
|---|---|
| `_call_mcp_tool(tool_name, tool_input)` | Gọi MCP tool qua HTTP (nếu có `MCP_SERVER_URL`) hoặc local dispatch qua `mcp_server.dispatch_tool()` |
| `analyze_policy(task, chunks)` | Phân tích policy dựa trên context chunks — rule-based + optional LLM (OpenAI hoặc Gemini) |
| `run(state)` | Entry point của worker, xử lý state và orchestration nội bộ, gọi từ `graph.py` |

**Cách công việc của tôi kết nối với phần của thành viên khác:**

```
retrieval_worker  ──→  retrieved_chunks   ──→  policy_tool_worker
supervisor        ──→  needs_tool         ──→  policy_tool_worker
policy_tool_worker ──→  policy_result     ──→  synthesis_worker  ──→  final_answer
```

- **Nhận từ `retrieval_worker`** (`workers/retrieval.py`): `state["retrieved_chunks"]` — list of `{"text", "source", "score", "metadata"}`
- **Nhận từ supervisor**: `state["needs_tool"]` — nếu `True`, worker gọi thêm MCP tools (`search_kb`, `get_ticket_info`)
- **Trả về cho `synthesis_worker`** (`workers/synthesis.py`): `state["policy_result"]` — dict với `policy_applies`, `exceptions_found`, `policy_version_note`, `explanation`

**Bằng chứng — identifier trong code:**
```python
# workers/policy_tool.py, line 25
WORKER_NAME = "policy_tool_worker"
```

**Bằng chứng — trace log được ghi vào state:**
```python
# workers/policy_tool.py, line 261-264
state["history"].append(
    f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
    f"exceptions={len(policy_result.get('exceptions_found', []))}"
)
```

**File có thể chạy standalone:**
```bash
python workers/policy_tool.py
```

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:**  
Chọn **Hybrid — rule-based exception detection + LLM fallback (optional)** thay vì dùng thuần LLM hoặc thuần rule-based trong hàm `analyze_policy()`.

**Các lựa chọn thay thế:**

| # | Phương án | Nhược điểm |
|---|---|---|
| 1 | Thuần LLM | Tốn API call mỗi request, không deterministic, latency cao |
| 2 | Thuần rule-based | Không xử lý được edge case phức tạp |
| **3** | **Hybrid (rule-based → LLM fallback)** ✅ | Rule cứng nhắc, phải maintain keyword list |

**Lý do chọn Hybrid:**
- Rule-based chạy **trước**, nhanh, deterministic — phù hợp các pattern rõ ràng (Flash Sale, license key, đã kích hoạt)
- LLM chỉ chạy **sau** nếu có API key, dùng cho reasoning phức tạp hơn
- Giảm latency và chi phí so với LLM-only

**Bằng chứng từ code (`workers/policy_tool.py`, lines 124–146):**
```python
# Exception 1: Flash Sale
if "flash sale" in task_lower or "flash sale" in context_text:
    exceptions_found.append({
        "type": "flash_sale_exception",
        "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
        "source": "policy_refund_v4.txt",
    })

# Exception 2: Digital product
if any(kw in task_lower for kw in ["license key", "license", "subscription", "kỹ thuật số"]):
    exceptions_found.append({
        "type": "digital_product_exception",
        "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3).",
        "source": "policy_refund_v4.txt",
    })

# Exception 3: Activated product
if any(kw in task_lower for kw in ["đã kích hoạt", "đã đăng ký", "đã sử dụng"]):
    exceptions_found.append({
        "type": "activated_exception",
        "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3).",
        "source": "policy_refund_v4.txt",
    })
```

**Bằng chứng LLM fallback chỉ chạy khi có API key (lines 160–186):**
```python
if os.getenv("OPENAI_API_KEY"):
    # gọi gpt-4o-mini
    ...
elif os.getenv("GOOGLE_API_KEY"):
    # gọi gemini-1.5-flash
    ...
else:
    analysis += " (Bỏ qua LLM vì không cấu hình API key)"
```

**Trade-off đã chấp nhận:**
- Rule-based có thể miss edge cases không có trong keyword list
- Phải maintain `exceptions_found` keyword list thủ công khi policy thay đổi

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:**  
Sai policy version cho đơn hàng đặt trước ngày 01/02/2026

**Symptom:**
- Câu hỏi liên quan ngày 31/01/2026 vẫn áp dụng policy v4
- Output thiếu thông tin rằng đơn hàng cũ phải áp dụng policy v3
- `synthesis_worker` tổng hợp câu trả lời thiếu context temporal → sai

**Root cause:**
- `analyze_policy()` ban đầu chỉ detect exception theo keyword (Flash Sale, license key...)
- Chưa có **temporal logic** — không parse/compare date trong task
- `policy_version_note` trả về chuỗi rỗng với mọi câu hỏi

**Cách sửa — thêm temporal rule (lines 155–156):**
```python
policy_version_note = ""
if "31/01" in task_lower or "30/01" in task_lower or "trước 01/02" in task_lower:
    policy_version_note = "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách v3 (không có trong tài liệu hiện tại)."
```

**Bằng chứng — output trước khi sửa:**
```
policy_name: refund_policy_v4
policy_version_note: ""
```

**Bằng chứng — output sau khi sửa:**
```
policy_name: refund_policy_v4
policy_version_note: "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách v3 (không có trong tài liệu hiện tại)."
```

**Kết quả:**  
`synthesis_worker` nhận được `policy_version_note` trong `policy_result` và có thêm context để tổng hợp câu trả lời chính xác hơn, phân biệt rõ đơn hàng trước/sau 01/02/2026.

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**
- Thiết kế `analyze_policy()` rõ ràng, từng exception tách biệt → dễ debug và extend
- Tách biệt hoàn toàn giữa rule-based và LLM — LLM chỉ là optional enhancement
- Worker log đầy đủ: `worker_io_logs`, `history`, `mcp_tools_used` → traceable
- File chạy standalone (`__main__`) với 3 test cases cover cả happy path và exception

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
- Temporal logic còn đơn giản: chỉ match chuỗi ngày cứng, không parse date thực sự
- Keyword list hard-code trong code (Flash Sale, license key...) — không scalable khi policy thay đổi
- Chưa xử lý case "unknown" (ví dụ: `ERR-403-AUTH`) — worker vẫn cố trả lời dù confidence rất thấp

**Nhóm phụ thuộc vào tôi ở đâu?**

`synthesis_worker` phụ thuộc trực tiếp vào output của `policy_tool_worker`:
```python
# workers/synthesis.py, line 264
policy_result = state.get("policy_result", {})
```
- Nếu `policy_result["exceptions_found"]` sai → `_build_context()` build context sai → câu trả lời sai
- Nếu `policy_applies` sai → synthesis không nêu ngoại lệ → user bị mislead

**Phần tôi phụ thuộc vào thành viên khác:**

```python
# workers/policy_tool.py, line 215
chunks = state.get("retrieved_chunks", [])   # phụ thuộc retrieval_worker
needs_tool = state.get("needs_tool", False)  # phụ thuộc supervisor
```
- `retrieval_worker` phải trả `retrieved_chunks` đúng format `{"text", "source", "score"}`
- Supervisor phải route `needs_tool=True` đúng lúc để worker gọi MCP

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

**Tôi sẽ implement: Unknown Query Detection + HITL (Human-in-the-Loop) Routing**

**Lý do — vấn đề hiện tại:**

Hiện tại khi không match bất kỳ rule nào và không có context, worker vẫn set `policy_applies=True` và synthesis vẫn cố generate câu trả lời:
```python
# workers/synthesis.py, line 128-148 — rule-based confidence
if not chunks:
    return 0.1  # Chỉ trả về confidence thấp, nhưng KHÔNG dừng lại
```

Trace cho thấy case nguy hiểm:
```
task: "ERR-403-AUTH là lỗi gì?"
retrieved_chunks: []   # không tìm được context
confidence: 0.1        # thấp nhưng vẫn trả lời
→ synthesis hallucinate câu trả lời sai
```

**Cải tiến tôi sẽ thêm vào `analyze_policy()`:**
```python
# Thêm unknown detection
if not chunks and not exceptions_found:
    return {
        "policy_applies": False,
        "policy_name": None,
        "exceptions_found": [],
        "status": "unknown",           # <-- flag mới
        "explanation": "Không đủ context để phân tích policy.",
    }
```

**Và thêm vào `run()` để route về supervisor:**
```python
if policy_result.get("status") == "unknown":
    state["needs_human_review"] = True
    state["human_review_reason"] = "Không match rule và không có context"
    # → supervisor nhận tín hiệu, route sang human_review node
```

**Kết quả kỳ vọng:**

| Trước | Sau |
|---|---|
| Unknown query → synthesis hallucinate | Unknown query → dừng pipeline, flag HITL |
| confidence=0.1, trả lời sai | `needs_human_review=True`, không generate |
| Tăng hallucination risk | An toàn hơn cho production use-case |
