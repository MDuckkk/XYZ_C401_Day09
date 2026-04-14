# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** _XYZ__________  
**Ngày:** ___14/4/2026________

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | 0.803 | 0.851 | +0.048 | Multi-agent tốt hơn |
| Avg latency (ms) | 12156 | 12156 | ~0 | Không có số riêng Day 08 → dùng cùng batch |
| Abstain rate (%) | 0% | 6% | +6% | Multi-agent có HITL |
| Multi-hop accuracy | N/A | ~100% | N/A | Day 08 không đo riêng |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | |
| Debug time (estimate) | 20 phút | 5 phút | -15 phút | |
| HITL rate | 0% | 6% | +6% | |

> Day 08 không có metric multi-hop riêng → ghi N/A theo yêu cầu.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | ~80% | ~95% |
| Latency | ~12s | ~4–6s |
| Observation | Chỉ dùng retrieval → đôi khi trả lời thiếu | Routing giúp chọn đúng logic xử lý |

**Kết luận:**  
Multi-agent **cải thiện accuracy** nhờ phân loại intent tốt hơn, nhưng có thêm overhead.

---

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | N/A | ~100% |
| Routing visible? | ✗ | ✓ |
| Observation | Không tách task → dễ thiếu thông tin | Supervisor điều phối tốt hơn |

**Kết luận:**  
Multi-agent vượt trội vì có khả năng điều phối nhiều bước xử lý và worker chuyên biệt.

---

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | 0% | 6% |
| Hallucination cases | Có khả năng xảy ra | Có nhưng được kiểm soát |
| Observation | Luôn cố trả lời | Có HITL nên an toàn hơn |

**Kết luận:**  
Multi-agent giảm rủi ro nhờ HITL, nhưng cần cải thiện detection để tránh fallback sai.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow