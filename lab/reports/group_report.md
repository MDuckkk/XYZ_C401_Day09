# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** XYZ  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Bùi Minh Đức | Supervisor Owner, MCP Owner, Trace & Docs Owner | bmd040510@gmail.com |
| Trần Thanh Nguyên | Worker Owner, Trace & Docs Owner | ttnguyen1410@gmail.com |

**Ngày nộp:** 14/04/2026  
**Repo:** https://github.com/MDuckkk/XYZ_C401_Day09.git

---

## 1. Kiến trúc nhóm đã xây dựng

Hệ thống nhóm triển khai pattern **Supervisor-Worker** với 3 workers chuyên biệt và 1 MCP server mock. Luồng xử lý: mọi câu hỏi đều đi qua `supervisor_node()` trong `graph.py` trước, supervisor phân tích task và ghi `supervisor_route` + `route_reason` vào `AgentState`, sau đó `route_decision()` điều hướng sang worker phù hợp. Tất cả workers đều kết thúc bằng `synthesis_worker` để tổng hợp câu trả lời có citation và confidence score.

**Routing logic cốt lõi:** Keyword matching rule-based trong `supervisor_node()`. Ba nhóm rule:
- Keywords `hoàn tiền`, `refund`, `flash sale`, `license`, `cấp quyền`, `access level`, `emergency` → `policy_tool_worker`
- Keywords `P1`, `SLA`, `ticket`, `escalation` → `retrieval_worker`
- Pattern `ERR-xxx` hoặc ngữ cảnh không rõ → `human_review`
- Mặc định → `retrieval_worker`

**MCP tools đã tích hợp** (4 tools trong `mcp_server.py`):
- `search_kb`: Tìm kiếm Knowledge Base qua ChromaDB — được gọi trong 5/10 câu grading (gq02, gq03, gq04, gq09, gq10). Ví dụ trace gq02: `{"tool": "search_kb", "input": {"query": "...", "top_k": 3}, "output": {"chunks": [...], "sources": ["policy/refund-v4.pdf"]}}`
- `get_ticket_info`: Tra cứu thông tin ticket mock — được gọi trong gq03 và gq09 để lấy context P1 ticket đang active
- `check_access_permission`: Kiểm tra điều kiện cấp quyền theo Access Control SOP
- `create_ticket`: Tạo ticket mới (mock, không gọi trong grading run)

---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Dùng keyword matching rule-based cho supervisor routing thay vì LLM classifier.

**Bối cảnh vấn đề:** Supervisor cần phân loại câu hỏi đầu vào để route sang đúng worker. Nhóm phải chọn giữa hai hướng: (1) dùng LLM để classify intent, hoặc (2) dùng keyword matching cứng. Đây là quyết định ảnh hưởng trực tiếp đến routing accuracy, latency và chi phí của toàn pipeline.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| LLM classifier (gọi OpenAI để classify intent) | Hiểu ngữ nghĩa, xử lý được câu không có keyword rõ ràng | Thêm 1 LLM call (~1–2s) cho mỗi câu hỏi; tăng cost; có thể fail nếu API timeout |
| Keyword matching rule-based | Nhanh (< 1ms), không tốn API call, dễ debug và kiểm soát | Miss câu không có keyword đặc trưng; cần maintain danh sách keyword thủ công |

**Phương án đã chọn:** Keyword matching rule-based — vì trong phạm vi lab với 5 tài liệu và domain rõ ràng, keyword matching đủ chính xác và giúp giữ latency thấp. Thêm LLM call ở supervisor sẽ tăng latency thêm ~1–2s cho mọi câu, không justify được với bộ câu hỏi hiện tại.

**Bằng chứng từ trace:** 14/15 câu test questions được route đúng. Câu duy nhất route sai là "Ai phải phê duyệt để cấp quyền Level 3?" — trace ghi `route_reason: "default route"` thay vì match keyword "cấp quyền", vì câu hỏi dùng từ "phê duyệt" thay vì "cấp quyền". Đây là điểm yếu đã biết của keyword matching.

```json
{
  "task": "Ai phải phê duyệt để cấp quyền Level 3?",
  "supervisor_route": "retrieval_worker",
  "route_reason": "default route",
  "workers_called": ["retrieval_worker", "synthesis_worker"]
}
```

Câu trả lời vẫn đúng nhờ retrieval tìm được chunk từ `it/access-control-sop.md`, nhưng không gọi MCP `check_access_permission` như thiết kế — đây là trade-off chấp nhận được trong lab.

---

## 3. Kết quả grading questions

**Tổng điểm raw ước tính: 83 / 96**

| ID | Điểm tối đa | Ước tính đạt | Nhận xét |
|----|------------|-------------|---------|
| gq01 | 10 | 8 | Nêu đúng Slack + email + 22:57, nhưng thiếu PagerDuty → Partial |
| gq02 | 10 | 1 | Trả lời sai — không nhận ra temporal scoping (v3 vs v4) |
| gq03 | 10 | 10 | Đúng 3 người phê duyệt, đúng IT Security là người cuối |
| gq04 | 6 | 6 | Đúng 110% store credit |
| gq05 | 8 | 8 | Đúng escalate lên Senior Engineer sau 10 phút |
| gq06 | 8 | 8 | Đúng không được remote trong probation, đúng điều kiện |
| gq07 | 10 | 10 | Abstain đúng — không bịa số liệu phạt |
| gq08 | 8 | 8 | Đúng 90 ngày + cảnh báo 7 ngày trước |
| gq09 | 16 | 14 | Nêu đủ SLA steps + Level 2 emergency bypass, nhưng thiếu chi tiết "không cần IT Security cho Level 2" |
| gq10 | 10 | 10 | Đúng Flash Sale exception override lỗi nhà sản xuất |

**Câu pipeline xử lý tốt nhất:**
- **gq07** (abstain) — Pipeline trả lời "Không đủ thông tin trong tài liệu nội bộ về mức phạt tài chính cụ thể" mà không bịa số liệu. Đây là kết quả của grounding strategy trong synthesis_worker: khi LLM-Judge phát hiện context không có thông tin, confidence giảm và synthesis abstain thay vì hallucinate.
- **gq10** (Flash Sale exception) — Policy_tool_worker phát hiện đúng exception Flash Sale và override điều kiện "lỗi nhà sản xuất", trả lời đúng "không được hoàn tiền".

**Câu pipeline fail:**
- **gq02** (temporal scoping) — Pipeline trả lời "không được hoàn tiền vì gửi muộn hơn 7 ngày" thay vì nhận ra đơn đặt ngày 31/01/2026 phải áp dụng chính sách v3 (không có trong tài liệu). Root cause: `analyze_policy()` trong `policy_tool.py` chỉ check exception cases (Flash Sale, digital product, activated) mà không có logic kiểm tra `effective_date` của policy so với ngày đặt hàng. Đây là gap trong thiết kế policy worker.

**Câu gq07 (abstain):** Synthesis_worker abstain đúng cách — LLM-Judge đánh giá context không có thông tin về mức phạt tài chính, confidence giảm, answer trả về "Không đủ thông tin trong tài liệu nội bộ". Không có penalty hallucination.

**Câu gq09 (multi-hop khó nhất):** Trace ghi `workers_called: ["policy_tool_worker", "synthesis_worker"]` — chỉ 1 worker chính thay vì 2 workers riêng biệt cho SLA và access control. Pipeline gọi MCP `search_kb` và `get_ticket_info` để lấy context từ cả 2 tài liệu, nhưng synthesis thiếu chi tiết "Level 2 không cần IT Security" → Partial.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được

**Metric thay đổi rõ nhất:**

Latency tăng mạnh nhất: từ **2,244ms** (Day 08) lên **12,722ms** (Day 09) — tăng ~5.7×. Nguyên nhân chính là LLM-Judge trong synthesis_worker gọi thêm 1 OpenAI API call để đánh giá faithfulness/relevance/completeness. Với câu đơn giản (gq05, gq06), latency chỉ ~6–7s; với câu phức tạp có MCP calls (gq09), latency lên đến ~20s.

Avg confidence giảm nhẹ: từ **0.92** (Day 08) xuống **0.863** (Day 09) — không phải do chất lượng kém hơn mà do LLM-Judge chấm nghiêm hơn so với rule-based scoring của Day 08.

**Điều nhóm bất ngờ nhất:** MCP `search_kb` trong `policy_tool_worker` trả về chunks nhưng không ghi vào `retrieved_sources` trong AgentState — dẫn đến field `sources` rỗng trong grading_run.jsonl cho 5/10 câu policy. Đây là bug không phát hiện được khi test từng worker độc lập, chỉ lộ ra khi chạy end-to-end grading. Nguyên nhân: `policy_tool_worker` lưu chunks vào `retrieved_chunks` nhưng không cập nhật `retrieved_sources`.

**Trường hợp multi-agent không giúp ích:** Câu hỏi đơn giản single-document như gq05 ("P1 không phản hồi sau 10 phút — hệ thống làm gì?") — pipeline mất 6.8s trong khi Day 08 chỉ cần ~2s. Supervisor overhead + LLM-Judge không cần thiết cho câu fact lookup đơn giản này.

---

## 5. Phân công và đánh giá nhóm

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Bùi Minh Đức | `graph.py` (supervisor, routing logic, AgentState), `mcp_server.py` (4 tools), `eval_trace.py`, `docs/`, `reports/` | 1, 3, 4 |
| Trần Thanh Nguyên | `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`, `docs/` | 2, 4 |

**Điều nhóm làm tốt:** Phân chia rõ ràng giữa orchestration layer (Đức) và worker layer (Nguyên) giúp 2 người làm song song từ Sprint 1.

**Điều nhóm làm chưa tốt:** Không test end-to-end sớm — bug `retrieved_sources` rỗng khi đi qua `policy_tool_worker` chỉ phát hiện khi chạy grading. Nếu test integration sớm hơn (sau Sprint 2), có thể sửa trước deadline.

**Nếu làm lại:** Thêm integration test sau mỗi sprint — chạy 2–3 câu end-to-end và kiểm tra tất cả fields trong trace thay vì chỉ test từng worker độc lập.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?

**Ưu tiên 1 — Fix bug `retrieved_sources`:** Khi `policy_tool_worker` gọi MCP `search_kb`, cần đồng bộ chunks trả về vào `state["retrieved_sources"]`. Sửa 3 dòng trong `workers/policy_tool.py`. Bằng chứng: 5/10 câu grading có `sources: []` — ảnh hưởng trực tiếp đến điểm trace theo rubric SCORING.md.

**Ưu tiên 2 — Thêm temporal policy scoping vào `analyze_policy()`:** Câu gq02 mất 10 điểm vì không nhận ra đơn đặt trước `effective_date` của policy v4 (01/02/2026). Cần thêm logic so sánh ngày đặt hàng với `effective_date` trong metadata chunk, và abstain khi cần áp dụng version policy không có trong tài liệu.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
