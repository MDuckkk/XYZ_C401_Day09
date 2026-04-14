# Routing Decisions Log — Lab Day 09

**Nhóm:** XYZ  
**Ngày:** 14/04/2026

> **Hướng dẫn:** Ghi lại ít nhất **3 quyết định routing** thực tế từ trace của nhóm.  
> Không ghi giả định — phải từ trace thật (`artifacts/traces/`).

---

## Routing Decision #1

**Task đầu vào:**
> SLA xử lý ticket P1 là bao lâu?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains SLA or ticket keyword`  
**MCP tools được gọi:** Không có  
**Workers called sequence:** supervisor → retrieval_worker → synthesis_worker

**Kết quả thực tế:**
- final_answer (ngắn): SLA P1 — phản hồi ban đầu 15 phút, resolution 4 giờ, escalate lên Senior Engineer sau 10 phút không phản hồi
- confidence: 0.95  
- Correct routing? Yes

**Nhận xét:**  
Routing đúng vì đây là câu hỏi fact-based về SLA, có thể trả lời trực tiếp từ knowledge base. Keyword "SLA" và "P1" kích hoạt đúng rule `retrieval_worker`. Trace file: `run_20260414_173843.json`.

---

## Routing Decision #2

**Task đầu vào:**
> Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy or access control keyword`  
**MCP tools được gọi:** `search_kb` (query: "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?", top_k: 3)  
**Workers called sequence:** supervisor → policy_tool_worker → synthesis_worker

**Kết quả thực tế:**
- final_answer (ngắn): Được hoàn tiền trong 7 ngày làm việc kể từ xác nhận đơn hàng; nêu đủ ngoại lệ (Flash Sale, kỹ thuật số, đã kích hoạt)
- confidence: 0.95  
- Correct routing? Yes

**Nhận xét:**  
Routing chính xác vì câu hỏi liên quan đến policy có logic và điều kiện → cần tool chuyên biệt. Keyword "hoàn tiền" kích hoạt `policy_tool_worker`. MCP `search_kb` được gọi và trả về 3 chunks từ `policy/refund-v4.pdf`. Trace file: `run_20260414_173859.json`.

---

## Routing Decision #3

**Task đầu vào:**
> Nhân viên vừa vào thử việc (trong probation period) muốn làm remote vì lý do cá nhân. Điều kiện là gì?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `default route`  
**MCP tools được gọi:** Không có  
**Workers called sequence:** supervisor → retrieval_worker → synthesis_worker

**Kết quả thực tế:**
- final_answer (ngắn): Nhân viên trong probation period không được làm remote; chỉ sau probation mới được tối đa 2 ngày/tuần với Team Lead phê duyệt
- confidence: 0.95  
- Correct routing? Yes (kết quả đúng, nhưng route reason là "default" — không phải keyword match)

**Nhận xét:**  
Routing ra kết quả đúng nhưng vì lý do sai — supervisor không nhận diện được keyword HR policy, nên fallback về `default route`. Câu trả lời vẫn đúng vì retrieval_worker tìm được chunk từ `hr/leave-policy-2026.pdf`. Đây là điểm yếu của keyword matching: câu hỏi HR không có keyword rõ ràng trong routing rules. Trace file: `run_20260414_174103.json`.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> ERR-403-AUTH là lỗi gì và cách xử lý?

**Worker được chọn:** `human_review` → sau đó `retrieval_worker`  
**Route reason:** `task contains unknown error code or unclear context`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**

- Đây là error code không có trong knowledge base  
- Supervisor nhận diện pattern `ERR-` → route sang `human_review` (đúng theo thiết kế)  
- Tuy nhiên HITL chỉ là placeholder: auto-approve và tiếp tục với `retrieval_worker`  
- Retrieval không tìm được chunk liên quan → synthesis abstain với confidence thấp  
→ Đây là trường hợp duy nhất trong 15 câu test có `hitl_triggered: true`. Hệ thống hoạt động đúng theo thiết kế nhưng HITL chưa thực sự dừng để chờ human input.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 8 | 53.3% |
| policy_tool_worker | 7 | 46.7% |
| human_review | 1 (HITL) | ~6.7% |

> Lưu ý: câu HITL sau đó tiếp tục qua retrieval_worker, nên tổng workers_called > 15.

### Routing Accuracy

> Trong số 15 câu nhóm đã chạy, bao nhiêu câu supervisor route đúng?

- Câu route đúng: 14 / 15  
- Câu route sai: 1 — câu "Ai phải phê duyệt để cấp quyền Level 3?" bị route sang `retrieval_worker` (route_reason: "default route") thay vì `policy_tool_worker`. Câu trả lời vẫn đúng nhờ retrieval tìm được chunk, nhưng không gọi MCP `check_access_permission` như thiết kế.  
- Câu trigger HITL: 1 (ERR-403-AUTH)

### Lesson Learned về Routing

1. **Keyword matching hoạt động tốt cho các domain rõ ràng** (SLA, refund, access level) nhưng miss các câu HR policy vì không có keyword đặc trưng trong routing rules. Cải tiến: thêm keyword "remote", "probation", "leave", "nghỉ phép" vào routing rules.

2. **Route reason "default route" là dấu hiệu cần cải thiện** — khi supervisor không match được keyword nào, fallback về retrieval_worker là an toàn nhưng không tối ưu. Nên thêm intent classification để phân biệt HR/IT/Policy queries.

### Route Reason Quality

> Nhìn lại các `route_reason` trong trace — chúng có đủ thông tin để debug không?

Chưa đủ chi tiết. Nhiều route_reason chỉ mang tính mô tả chung ("task contains policy or access control keyword"), chưa giải thích rõ keyword nào đã trigger và tại sao chọn worker đó thay vì worker khác.

**Cải tiến đề xuất:**
- Thêm intent classification (e.g. "policy_question", "factual_lookup", "hr_policy")  
- Thêm confidence routing score  
- Log keyword cụ thể đã trigger decision (e.g. "keyword='hoàn tiền' → policy_tool_worker")  
- Format chuẩn: `"route=policy_tool_worker | trigger=keyword:hoàn tiền | confidence=high"`
