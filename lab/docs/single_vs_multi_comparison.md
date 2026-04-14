# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** XYZ  
**Ngày:** 14/04/2026

> Số liệu Day 09 lấy từ `artifacts/eval_report.json` (15 test questions).  
> Số liệu Day 08 lấy từ baseline được tính sẵn trong `eval_trace.py` (10 câu).

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | 0.92 | 0.863 | −0.057 | Day 09 thấp hơn do LLM-Judge chấm nghiêm hơn |
| Avg latency (ms) | 2,244 | 12,722 | +10,478 | Multi-agent chậm hơn ~5.7× do nhiều LLM calls |
| Abstain rate (%) | 20% (2/10) | 6.7% (1/15) | −13.3% | Day 09 ít abstain hơn nhờ routing chuyên biệt |
| Multi-hop accuracy | ~83% (5/6) | ~100% | +17% | Day 09 tốt hơn nhờ supervisor điều phối |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | Mỗi trace có route_reason rõ ràng |
| Debug time (estimate) | ~20 phút | ~5 phút | −15 phút | Trace giúp khoanh vùng lỗi nhanh hơn |
| HITL rate | 0% | 6.7% (1/15) | +6.7% | Day 09 có human_review node |
| MCP usage rate | 0% | 46.7% (7/15) | +46.7% | Day 09 gọi external tools qua MCP |

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | ~80% | ~95% |
| Latency | ~2.2s | ~6–8s |
| Observation | Retrieval đơn giản, đôi khi thiếu context | Routing đúng worker, synthesis có citation rõ ràng |

**Kết luận:**  
Multi-agent cải thiện accuracy nhờ phân loại intent tốt hơn. Tuy nhiên latency tăng đáng kể (~3–4×) do thêm bước supervisor và LLM-Judge. Với câu hỏi đơn giản, overhead này không cần thiết — single agent đủ dùng.

---

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | ~83% (5/6) | ~100% |
| Routing visible? | ✗ | ✓ |
| Observation | Không tách task → dễ thiếu thông tin từ tài liệu thứ 2 | Supervisor điều phối, policy_tool_worker gọi MCP để lấy thêm context |

**Kết luận:**  
Multi-agent vượt trội rõ rệt với câu hỏi multi-hop. Ví dụ câu q15 (P1 + Level 2 access): Day 09 gọi cả `search_kb` và `get_ticket_info` qua MCP, trả lời đủ cả 2 phần. Day 08 chỉ có 1 retrieval pass, dễ bỏ sót thông tin từ tài liệu thứ 2.

---

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | 20% (2/10) | 6.7% (1/15) |
| Hallucination cases | Có khả năng xảy ra | Được kiểm soát qua LLM-Judge |
| Observation | Không có cơ chế phát hiện "không đủ thông tin" | Synthesis abstain khi chunks rỗng; confidence thấp khi thiếu evidence |

**Kết luận:**  
Day 09 ít abstain hơn vì routing chuyên biệt giúp tìm đúng tài liệu hơn. Tuy nhiên LLM-Judge giúp kiểm soát hallucination tốt hơn — câu gq07 (mức phạt tài chính SLA) được trả lời đúng là "không có thông tin trong tài liệu" thay vì bịa số liệu.

---

## 3. Debuggability Analysis

> Khi pipeline trả lời sai, mất bao lâu để tìm ra nguyên nhân?

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: ~20 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: ~5 phút
```

**Câu cụ thể nhóm đã debug:**  
Câu "Ai phải phê duyệt để cấp quyền Level 3?" — trace cho thấy `route_reason: "default route"` thay vì match keyword "cấp quyền". Nhờ trace, nhóm xác định ngay vấn đề nằm ở supervisor routing rules (thiếu keyword "Level 3"), không phải ở retrieval hay synthesis. Sửa trong 2 phút bằng cách thêm "level 3" vào `policy_tool_keywords` trong `graph.py`.

---

## 4. Extensibility Analysis

> Dễ extend thêm capability không?

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker |

**Nhận xét:**  
Day 09 dễ extend hơn đáng kể. Ví dụ thực tế: thêm `create_ticket` MCP tool chỉ cần thêm 1 entry vào `TOOL_REGISTRY` trong `mcp_server.py` và 1 routing rule trong `supervisor_node()` — không cần sửa workers hay synthesis.

---

## 5. Cost & Latency Trade-off

> Multi-agent thường tốn nhiều LLM calls hơn. Nhóm đo được gì?

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query (retrieval) | 1 LLM call | 2 LLM calls (synthesis + LLM-Judge) |
| Complex query (policy) | 1 LLM call | 3–4 LLM calls (policy analysis + synthesis + LLM-Judge + MCP) |
| MCP tool call | N/A | 1 MCP dispatch (in-process, không tốn LLM call) |

**Nhận xét về cost-benefit:**  
Multi-agent tốn ~2–4× LLM calls so với single agent. Với câu đơn giản, overhead này không đáng. Với câu phức tạp (multi-hop, policy exception), chất lượng câu trả lời tốt hơn rõ rệt và justify được chi phí thêm. LLM-Judge là bước tốn kém nhất nhưng cung cấp confidence score có giá trị cho production system.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. **Accuracy với câu phức tạp:** Multi-hop accuracy tăng từ ~83% lên ~100% nhờ supervisor điều phối và MCP tools lấy thêm context từ nhiều nguồn.
2. **Debuggability:** Trace với `route_reason`, `workers_called`, `worker_io_logs` giúp khoanh vùng lỗi trong ~5 phút thay vì ~20 phút.
3. **Extensibility:** Thêm capability mới (MCP tool, worker mới) không cần sửa core pipeline.
4. **Safety:** LLM-Judge kiểm soát hallucination; HITL node cho phép human review khi risk cao.

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. **Latency:** Chậm hơn ~5.7× (12,722ms vs 2,244ms). Với câu đơn giản, single agent đủ dùng và nhanh hơn nhiều.
2. **Cost:** Tốn ~2–4× LLM calls. Với volume lớn, chi phí tăng đáng kể.
3. **Avg confidence thấp hơn:** 0.863 vs 0.92 — do LLM-Judge chấm nghiêm hơn, không phải do chất lượng answer kém hơn.

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi câu hỏi đơn giản, single-document, không cần policy check hay cross-document reasoning. Ví dụ: FAQ lookup, simple fact retrieval. Overhead của supervisor + LLM-Judge không justify được với những câu này.

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Thêm LLM-based intent classifier cho supervisor (thay keyword matching) để routing chính xác hơn với các câu không có keyword rõ ràng. Đồng thời fix bug `retrieved_sources` rỗng khi đi qua `policy_tool_worker` để grading trace đầy đủ hơn.
