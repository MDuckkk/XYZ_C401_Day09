# System Architecture — Lab Day 09

**Nhóm:** XYZ  
**Ngày:** 14/04/2026  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

> Mô tả ngắn hệ thống của nhóm: chọn pattern gì, gồm những thành phần nào.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**

Supervisor-Worker cho phép tách biệt logic routing (supervisor) khỏi logic xử lý (workers), giúp dễ debug, dễ mở rộng và có trace rõ ràng cho mỗi bước quyết định. So với single agent ở Day 08 — nơi toàn bộ retrieval, reasoning và generation nằm trong một prompt duy nhất — kiến trúc multi-agent cho phép test từng worker độc lập, thêm capability mới qua MCP mà không cần sửa core pipeline, và có routing visibility qua `route_reason` trong mỗi trace.

---

## 2. Sơ đồ Pipeline

```
                        User Request
                             │
                             ▼
                    ┌──────────────────┐
                    │    Supervisor    │  ← phân tích task keywords
                    │   (graph.py)     │  ← set: route, route_reason,
                    └────────┬─────────┘     risk_high, needs_tool
                             │
                      [route_decision]
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
  ┌───────────────┐  ┌──────────────────┐  ┌──────────────┐
  │   Retrieval   │  │  Policy Tool     │  │ Human Review │
  │    Worker     │  │    Worker        │  │   (HITL)     │
  │ (ChromaDB +   │  │ (MCP tools +    │  │              │
  │  OpenAI embed)│  │  retrieval)      │  └──────┬───────┘
  └───────┬───────┘  └────────┬─────────┘         │
          │                   │          auto-approve → retrieval
          │                   │                   │
          └───────────────────┴───────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Synthesis Worker │  ← LLM generate answer
                    │ (OpenAI + judge) │  ← cite sources
                    └────────┬─────────┘  ← confidence scoring
                             │
                             ▼
                    ┌──────────────────┐
                    │     Output       │
                    │  final_answer    │
                    │  sources         │
                    │  confidence      │
                    │  trace/history   │
                    └──────────────────┘
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích câu hỏi đầu vào, quyết định route sang worker phù hợp, đánh giá mức độ rủi ro |
| **Input** | `task` — câu hỏi từ user |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool` |
| **Routing logic** | Keyword matching: policy keywords → `policy_tool_worker`; SLA/ticket keywords → `retrieval_worker`; error codes/unclear → `human_review`; default → `retrieval_worker` |
| **HITL condition** | Khi task chứa mã lỗi không xác định (e.g. `ERR-xxx`) hoặc ngữ cảnh không rõ ràng; hoặc khi có từ khóa `emergency`/`khẩn cấp` kèm policy request |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Embed câu hỏi và truy vấn ChromaDB để lấy top-k chunks liên quan làm evidence |
| **Embedding model** | OpenAI `text-embedding-3-small` (1536 dimensions) |
| **Top-k** | 3 (mặc định, có thể override qua `retrieval_top_k` trong state) |
| **Stateless?** | Yes — mỗi lần gọi đều tạo embedding mới và query ChromaDB độc lập |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Xử lý câu hỏi liên quan đến chính sách, quyền truy cập — gọi MCP tools để kiểm tra policy và lấy thêm context |
| **MCP tools gọi** | `search_kb` (tìm kiếm knowledge base), `get_ticket_info`, `check_access_permission` |
| **Exception cases xử lý** | Flash sale refund, license key (sản phẩm kỹ thuật số), emergency access Level 3 cho contractor, quyền truy cập tạm thời ngoài giờ |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | OpenAI `gpt-4o-mini` |
| **Temperature** | 0.1 — thấp để đảm bảo câu trả lời grounded, ít sáng tạo |
| **Grounding strategy** | Chỉ trả lời dựa trên retrieved chunks; cite nguồn cụ thể; LLM-Judge đánh giá faithfulness, relevance, completeness |
| **Abstain condition** | Khi không có chunks liên quan hoặc confidence score thấp; LLM-Judge cho điểm thấp → confidence giảm |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| `search_kb` | `query: str`, `top_k: int` | `chunks: list`, `sources: list` |
| `get_ticket_info` | `ticket_id: str` | Ticket details (priority, status, SLA) |
| `check_access_permission` | `access_level: int`, `requester_role: str` | `can_grant: bool`, `approvers: list` |
| `create_ticket` | `priority: str`, `title: str`, `description: str` | `ticket_id: str`, `url: str` |

---

## 4. Shared State Schema

> Liệt kê các fields trong AgentState và ý nghĩa của từng field.

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| `task` | `str` | Câu hỏi đầu vào từ user | supervisor đọc |
| `supervisor_route` | `str` | Worker được chọn (`retrieval_worker` / `policy_tool_worker` / `human_review`) | supervisor ghi, graph đọc |
| `route_reason` | `str` | Lý do chọn route (e.g. "task contains policy keyword") | supervisor ghi, trace đọc |
| `risk_high` | `bool` | True nếu cần HITL hoặc human review | supervisor ghi, graph đọc |
| `needs_tool` | `bool` | True nếu cần gọi MCP tool | supervisor ghi, policy_tool đọc |
| `hitl_triggered` | `bool` | True nếu đã pause cho human review | human_review ghi, trace đọc |
| `retrieved_chunks` | `list` | Danh sách chunks evidence từ ChromaDB | retrieval ghi, synthesis đọc |
| `retrieved_sources` | `list` | Danh sách nguồn tài liệu đã dùng | retrieval ghi, synthesis đọc |
| `policy_result` | `dict` | Kết quả kiểm tra policy từ MCP tools | policy_tool ghi, synthesis đọc |
| `mcp_tools_used` | `list` | Danh sách MCP tool calls đã thực hiện | policy_tool ghi, trace đọc |
| `final_answer` | `str` | Câu trả lời tổng hợp cuối cùng | synthesis ghi |
| `sources` | `list` | Sources được cite trong answer | synthesis ghi |
| `confidence` | `float` | Mức độ tin cậy (0.0–1.0), tính từ LLM-Judge scores | synthesis ghi |
| `history` | `list` | Lịch sử các bước đã qua (dạng log messages) | mọi node ghi |
| `workers_called` | `list` | Danh sách workers đã được gọi theo thứ tự | mọi worker ghi |
| `latency_ms` | `int \| None` | Tổng thời gian xử lý pipeline (ms) | graph ghi |
| `run_id` | `str` | ID duy nhất của run (format: `run_YYYYMMDD_HHMMSS`) | graph ghi |
| `worker_io_logs` | `list` | Log chi tiết input/output của từng worker | mọi worker ghi, trace đọc |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không rõ lỗi ở retrieval hay generation | Dễ hơn — test từng worker độc lập (`python -m workers.retrieval`) |
| Thêm capability mới | Phải sửa toàn bộ prompt và logic | Thêm worker hoặc MCP tool riêng, không sửa core |
| Routing visibility | Không có — mọi câu đều đi cùng một luồng | Có `route_reason` trong trace, biết tại sao chọn worker nào |
| Xử lý policy phức tạp | Dồn hết vào 1 prompt, dễ hallucinate | Policy tool worker riêng + MCP tools chuyên biệt |
| HITL (Human-in-the-loop) | Không hỗ trợ | Có `human_review` node, trigger khi `risk_high=True` |
| Latency | Nhanh hơn (~2.2s/câu) | Chậm hơn (~12.7s/câu) do nhiều bước + LLM-Judge |
| Confidence scoring | Không có hoặc đơn giản | LLM-Judge đánh giá faithfulness, relevance, completeness |
| Trace & observability | Minimal | Full trace JSON cho mỗi run, có worker_io_logs |

**Quan sát từ thực tế lab:**

- Avg confidence Day 09: **0.863** trên 15 câu test questions, cho thấy hệ thống trả lời grounded tốt.
- Routing distribution: 53% retrieval (8/15), 47% policy_tool (7/15) — supervisor phân luồng hợp lý theo nội dung câu hỏi.
- Top sources sử dụng nhiều nhất: `support/sla-p1-2026.pdf` (4 lần), `it/access-control-sop.md` (4 lần) — phù hợp với bộ câu hỏi.
- HITL chỉ trigger 1/15 lần (6.7%) — đúng với thiết kế chỉ dùng cho trường hợp mã lỗi không xác định.

---

## 6. Giới hạn và điểm cần cải tiến

1. **Latency cao (~12.7s/câu):** Pipeline qua nhiều bước (supervisor → worker → synthesis → LLM-Judge), mỗi bước gọi OpenAI API. Cải tiến: batch embedding, cache kết quả, hoặc dùng model nhẹ hơn cho judge.

2. **Routing dựa trên keyword matching đơn giản:** Supervisor hiện tại dùng keyword matching cứng, dễ miss các câu hỏi không chứa keyword mong đợi. Ví dụ thực tế: câu "Ai phải phê duyệt để cấp quyền Level 3?" bị route sang `retrieval_worker` thay vì `policy_tool_worker` vì thiếu keyword "cấp quyền" trong câu. Cải tiến: dùng LLM classifier hoặc intent detection model cho routing.

3. **Chưa hỗ trợ multi-hop reasoning thực sự:** Khi câu hỏi cần thông tin từ nhiều tài liệu (ví dụ: SLA + access control), pipeline chỉ query một lần với top-k=3. Cải tiến: thêm re-ranking step hoặc iterative retrieval khi confidence thấp.

4. **HITL chỉ là placeholder (auto-approve):** Human review node chỉ in warning rồi tự approve, chưa có cơ chế dừng pipeline thực sự chờ human input. Cải tiến: tích hợp với messaging system hoặc UI để human review thật.

5. **`retrieved_sources` không được populate khi đi qua policy_tool_worker:** Khi pipeline route sang `policy_tool_worker`, MCP tool `search_kb` trả về chunks nhưng không ghi vào `retrieved_sources` trong state — dẫn đến field này rỗng trong grading_run.jsonl. Cải tiến: đồng bộ `retrieved_sources` từ MCP output vào state.
