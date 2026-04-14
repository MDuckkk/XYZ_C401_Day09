# Routing Decisions Log — Lab Day 09

**Nhóm:** ___XYZ________  
**Ngày:** _____14/4/2026______

> **Hướng dẫn:** Ghi lại ít nhất **3 quyết định routing** thực tế từ trace của nhóm.  
> Không ghi giả định — phải từ trace thật (`artifacts/traces/`).

---

## Routing Decision #1

**Task đầu vào:**
> SLA xử lý ticket P1 là bao lâu?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `question about SLA → retrieve from knowledge base`  
**MCP tools được gọi:** vector_search  
**Workers called sequence:** supervisor → retrieval_worker

**Kết quả thực tế:**
- final_answer (ngắn): SLA xử lý ticket P1 được trả lời chính xác theo tài liệu
- confidence: 0.95  
- Correct routing? Yes

**Nhận xét:**  
Routing đúng vì đây là câu hỏi fact-based, có thể trả lời trực tiếp từ knowledge base.

---

## Routing Decision #2

**Task đầu vào:**
> Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `refund policy question → use policy tool`  
**MCP tools được gọi:** policy_lookup_tool  
**Workers called sequence:** supervisor → policy_tool_worker

**Kết quả thực tế:**
- final_answer (ngắn): Thời gian hoàn tiền và điều kiện được trả lời đầy đủ
- confidence: 0.95  
- Correct routing? Yes

**Nhận xét:**  
Routing chính xác vì liên quan đến policy có logic và điều kiện → cần tool chuyên biệt.

---

## Routing Decision #3

**Task đầu vào:**
> Ai phải phê duyệt để cấp quyền Level 3?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `access control / approval process → policy tool`  
**MCP tools được gọi:** policy_lookup_tool  
**Workers called sequence:** supervisor → policy_tool_worker

**Kết quả thực tế:**
- final_answer (ngắn): Line Manager + IT Admin (thiếu IT Security)
- confidence: 0.65  
- Correct routing? Yes

**Nhận xét:**  
Routing đúng nhưng execution chưa tốt → thiếu thông tin về IT Security.  
Vấn đề nằm ở worker, không phải routing.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> ERR-403-AUTH là lỗi gì và cách xử lý?

**Worker được chọn:** `retrieval_worker`  
**Route reason:** `unknown error code → fallback retrieval`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**

- Đây là error code không có trong knowledge base  
- Supervisor không nhận diện được → fallback sai  
- HITL được trigger nhưng vẫn auto-approve trong lab  
→ Cần rule riêng cho "unknown error" để route sang human_review

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 7 | 46.7% |
| policy_tool_worker | 8 | 53.3% |
| human_review | 1 (HITL) | ~6.7% |

### Routing Accuracy

> Trong số 15 câu nhóm đã chạy, bao nhiêu câu supervisor route đúng?

- Câu route đúng: 14 / 15  
- Câu route sai (đã sửa bằng cách nào?): 1 (q09 → nên route human_review thay vì retrieval)  
- Câu trigger HITL: 1

### Lesson Learned về Routing

1. Phân loại task bằng keyword + intent (SLA → retrieval, refund → policy) là hiệu quả  
2. Cần thêm rule/threshold để detect unknown queries → trigger HITL thay vì fallback

### Route Reason Quality

> Nhìn lại các `route_reason` trong trace — chúng có đủ thông tin để debug không?

Chưa đủ chi tiết. Nhiều route_reason chỉ mang tính mô tả chung, chưa giải thích rõ vì sao chọn worker.

**Cải tiến đề xuất:**
- Thêm intent classification (e.g. "policy_question", "factual_lookup")  
- Thêm confidence routing score  
- Log keyword / signal dẫn đến decision  
- Format chuẩn: