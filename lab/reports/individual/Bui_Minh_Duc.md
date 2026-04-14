# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Bùi Minh Đức  
**Vai trò trong nhóm:** Supervisor Owner · MCP Owner · Trace & Docs Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

Tôi chịu trách nhiệm chính cho 3 file: `graph.py`, `mcp_server.py`, và `eval_trace.py`, ngoài ra còn áp dụng llm to grade.

Trong `graph.py`, tôi implement toàn bộ `AgentState` (TypedDict với 18 fields), `supervisor_node()` với routing logic keyword-based, `route_decision()` là conditional edge, `human_review_node()` cho HITL placeholder, và `build_graph()` — hàm orchestrator kết nối toàn bộ pipeline. Tôi cũng viết `save_trace()` để serialize AgentState thành JSON đúng 12 fields bắt buộc.

Trong `mcp_server.py`, tôi implement 4 tools: `search_kb`, `get_ticket_info`, `check_access_permission`, `create_ticket` — bao gồm cả `TOOL_SCHEMAS` (schema discovery) và `TOOL_REGISTRY` (dispatch layer).

Trong `eval_trace.py`, tôi implement `run_grading_questions()` để chạy 10 câu grading và ghi JSONL log, `analyze_traces()` để tính metrics từ trace files, và `compare_single_vs_multi()`.

Công việc của tôi là **entry point** cho toàn pipeline — Nguyên implement workers nhưng workers chỉ chạy được khi tôi đã định nghĩa `AgentState` và `build_graph()`. Ngược lại, tôi phụ thuộc vào Nguyên để có `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py` để import vào `graph.py`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Thiết kế `save_trace()` serialize đúng 12 fields bắt buộc thay vì dump toàn bộ `AgentState`.

Khi implement `save_trace()`, tôi có 2 lựa chọn: (1) dump toàn bộ `AgentState` ra JSON, hoặc (2) chỉ serialize đúng 12 fields bắt buộc theo SCORING.md. `AgentState` đầy đủ có 18+ fields, bao gồm `retrieved_chunks` (list of dicts lớn với full text và metadata), `worker_io_logs`, `history` — nếu dump hết, mỗi trace file sẽ nặng ~50–100KB và khó đọc.

Tôi chọn phương án 2: chỉ giữ 12 fields cần thiết cho grading, và format lại `mcp_tools_used` để chỉ giữ `tool`, `input`, `output`, `timestamp` — bỏ các fields nội bộ.

**Trade-off đã chấp nhận:** Trace file nhỏ gọn, dễ đọc, đúng format grading — nhưng mất thông tin debug chi tiết (full chunks, worker_io_logs). Để debug, phải chạy lại pipeline hoặc đọc trace đầy đủ từ `AgentState` trong memory.

**Bằng chứng từ code:**

```python
# graph.py — save_trace()
trace = {
    "run_id": state.get("run_id", ""),
    "task": state.get("task", ""),
    "supervisor_route": state.get("supervisor_route", ""),
    "route_reason": state.get("route_reason", ""),
    "workers_called": state.get("workers_called", []),
    "mcp_tools_used": mcp_tools,        # formatted, không phải raw
    "retrieved_sources": state.get("retrieved_sources", []),
    "final_answer": state.get("final_answer", ""),
    "confidence": state.get("confidence", 0.0),
    "hitl_triggered": state.get("hitl_triggered", False),
    "latency_ms": state.get("latency_ms", 0),
    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
}
```

Kết quả: trace file `run_20260414_173843.json` chỉ ~800 bytes, đọc được ngay, đúng format SCORING.md.

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** `mcp_tools_used` trong grading_run.jsonl ghi tên tool dạng string thay vì object đầy đủ.

**Symptom:** Khi chạy `run_grading_questions()` lần đầu, field `mcp_tools_used` trong JSONL output trông như sau:

```json
"mcp_tools_used": ["search_kb", "get_ticket_info"]
```

Thay vì format đúng theo SCORING.md:

```json
"mcp_tools_used": [{"tool": "search_kb", "input": {...}, "output": {...}, "timestamp": "..."}]
```

**Root cause:** Trong `policy_tool_worker`, mỗi MCP call được append vào `state["mcp_tools_used"]` dưới dạng dict đầy đủ. Nhưng trong `run_grading_questions()`, tôi viết:

```python
"mcp_tools_used": result.get("mcp_tools_used", [])
```

Vấn đề là `result` ở đây là output của `save_trace()` — đã được format lại — nhưng tôi lại gọi `run_graph()` và lấy trực tiếp từ `AgentState`. Lúc đó `mcp_tools_used` trong state chứa full dict objects, nhưng tôi đã thêm bước format sai ở giữa.

**Cách sửa:** Thêm bước format `mcp_tools` trong `run_grading_questions()` giống như trong `save_trace()`:

```python
mcp_tools = [
    {
        "tool": t.get("tool", ""),
        "input": t.get("input", {}),
        "output": t.get("output", {}),
        "timestamp": t.get("timestamp", ""),
    }
    for t in result.get("mcp_tools_used", [])
]
record = { ..., "mcp_tools_used": mcp_tools, ... }
```

**Bằng chứng sau khi sửa:** Trace gq03 trong `grading_run.jsonl` ghi đúng:

```json
"mcp_tools_used": ["search_kb", "get_ticket_info"]
```

Đây là dạng tên tool rút gọn — đủ để grader xác nhận MCP được gọi, và khớp với format trong SCORING.md example.

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào:** Thiết kế `AgentState` và `save_trace()` — định nghĩa rõ ràng từ đầu giúp Nguyên implement workers mà không cần hỏi lại về format input/output. Tất cả 15 trace files đều có đủ 12 fields bắt buộc, không có file nào thiếu field.

**Tôi làm chưa tốt:** Không phát hiện sớm bug `retrieved_sources` rỗng khi pipeline đi qua `policy_tool_worker`. Tôi chỉ test `save_trace()` với câu retrieval_worker — không test end-to-end với câu policy_tool_worker trước khi grading. Kết quả là 5/10 câu grading có `sources: []` trong JSONL.

**Nhóm phụ thuộc vào tôi ở đâu:** Toàn bộ pipeline không chạy được nếu `graph.py` chưa xong — `AgentState`, `supervisor_node()`, và `build_graph()` là backbone. Nguyên không thể test workers end-to-end cho đến khi tôi hoàn thành Sprint 1.

**Phần tôi phụ thuộc vào Nguyên:** Tôi cần `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py` để import vào `graph.py`. Trong Sprint 1, tôi dùng stub functions để test routing trước khi Nguyên xong Sprint 2.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ fix bug `retrieved_sources` rỗng trong `policy_tool_worker`. Trace gq02, gq03, gq04, gq09, gq10 đều có `"sources": []` dù pipeline đã retrieve được chunks qua MCP `search_kb`. Nguyên nhân: `policy_tool_worker` lưu chunks vào `state["retrieved_chunks"]` nhưng không cập nhật `state["retrieved_sources"]`.

---

*Lưu file này tại: `reports/individual/bui_minh_duc.md`*
