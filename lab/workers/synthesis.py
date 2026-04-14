"""
workers/synthesis.py — Synthesis Worker
Sprint 2: Tổng hợp câu trả lời từ retrieved_chunks và policy_result.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: evidence từ retrieval_worker
    - policy_result: kết quả từ policy_tool_worker

Output (vào AgentState):
    - final_answer: câu trả lời cuối với citation
    - sources: danh sách nguồn tài liệu được cite
    - confidence: mức độ tin cậy (0.0 - 1.0)

Gọi độc lập để test:
    python workers/synthesis.py
"""

import os

WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk nội bộ.

Quy tắc nghiêm ngặt:
1. CHỈ trả lời dựa vào context được cung cấp. KHÔNG dùng kiến thức ngoài.
2. Nếu context không đủ để trả lời → nói rõ "Không đủ thông tin trong tài liệu nội bộ".
3. Trích dẫn nguồn cuối mỗi câu quan trọng: [tên_file].
4. Trả lời súc tích, có cấu trúc. Không dài dòng.
5. Nếu có exceptions/ngoại lệ → nêu rõ ràng trước khi kết luận.
"""
from dotenv import load_dotenv
load_dotenv()

def _call_llm(messages: list) -> str:
    """
    Gọi LLM để tổng hợp câu trả lời.
    TODO Sprint 2: Implement với OpenAI hoặc Gemini.
    """
    # Option A: OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=10)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,  # Low temperature để grounded
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI error: {e}")
            pass

    # Option B: Gemini
    if os.getenv("GOOGLE_API_KEY"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            model = genai.GenerativeModel("gemini-1.5-flash")
            combined = "\n".join([m["content"] for m in messages])
            response = model.generate_content(combined)
            return response.text
        except Exception as e:
            print(f"Gemini error: {e}")
            pass

    # Fallback: trả về message báo lỗi (không hallucinate)
    return "[SYNTHESIS ERROR] Không thể gọi LLM. Kiểm tra API key trong .env."


def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result."""
    parts = []

    if chunks:
        parts.append("=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            parts.append(f"[{i}] Nguồn: {source} (relevance: {score:.2f})\n{text}")

    if policy_result and policy_result.get("exceptions_found"):
        parts.append("\n=== POLICY EXCEPTIONS ===")
        for ex in policy_result["exceptions_found"]:
            parts.append(f"- {ex.get('rule', '')}")

    if not parts:
        return "(Không có context)"

    return "\n\n".join(parts)


JUDGE_PROMPT = """Bạn là một AI Judge đánh giá chất lượng câu trả lời của hệ thống RAG.

Cho:
- Câu hỏi gốc (question)
- Tài liệu tham khảo (context)
- Câu trả lời cần đánh giá (answer)

Hãy chấm điểm câu trả lời theo 3 tiêu chí, mỗi tiêu chí từ 0.0 đến 1.0:

1. **faithfulness** (trung thực): Câu trả lời có hoàn toàn dựa vào context không? Có hallucinate thông tin ngoài context không?
   - 1.0 = hoàn toàn dựa vào context, không hallucinate
   - 0.5 = pha trộn context + kiến thức ngoài
   - 0.0 = hoàn toàn bịa đặt, không liên quan context

2. **relevance** (liên quan): Câu trả lời có trả lời đúng câu hỏi không?
   - 1.0 = trả lời trực tiếp và đầy đủ
   - 0.5 = trả lời một phần
   - 0.0 = lạc đề hoàn toàn

3. **completeness** (đầy đủ): Tất cả thông tin quan trọng từ context có được đề cập không?
   - 1.0 = đầy đủ, không bỏ sót thông tin trọng yếu
   - 0.5 = thiếu một số thông tin
   - 0.0 = bỏ sót hầu hết thông tin quan trọng

Trả lời CHÍNH XÁC theo định dạng JSON (không thêm markdown, không giải thích):
{"faithfulness": <float>, "relevance": <float>, "completeness": <float>, "reasoning": "<1 câu giải thích ngắn>"}"""


def _estimate_confidence(chunks: list, answer: str, policy_result: dict) -> float:
    """
    Ước tính confidence bằng LLM-as-Judge.

    LLM đánh giá 3 chiều:
      - faithfulness  (trọng số 0.5): câu trả lời có grounded vào context không?
      - relevance     (trọng số 0.3): có trả lời đúng câu hỏi không?
      - completeness  (trọng số 0.2): có đầy đủ thông tin không?

    Fallback về rule-based scoring nếu LLM không khả dụng.

    Returns:
        float: confidence score [0.1, 0.95]
    """
    import json as _json

    # ── rule-based fallback (dùng khi LLM không trả lời được) ──
    def _rule_based() -> float:
        if not chunks:
            return 0.1
        if "Không đủ thông tin" in answer or "không có trong tài liệu" in answer.lower():
            return 0.3
        avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks) if chunks else 0
        penalty = 0.05 * len(policy_result.get("exceptions_found", []))
        return round(max(0.1, min(0.95, avg_score - penalty)), 2)

    if not chunks:
        return 0.1

    # ── Build judge prompt ──
    context_snippet = "\n".join(
        f"[{i+1}] ({c.get('source','?')}) {c.get('text','')[:300]}"
        for i, c in enumerate(chunks[:5])
    )
    judge_messages = [
        {"role": "system", "content": JUDGE_PROMPT},
        {
            "role": "user",
            "content": (
                f"CONTEXT:\n{context_snippet}\n\n"
                f"ANSWER:\n{answer}"
            ),
        },
    ]

    # ── Call LLM ──
    raw_response = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=10)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=judge_messages,
                temperature=0.0,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            raw_response = resp.choices[0].message.content
        except Exception as e:
            print(f"  [LLM-Judge] OpenAI error: {e}")

    if raw_response is None and os.getenv("GOOGLE_API_KEY"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            model = genai.GenerativeModel("gemini-1.5-flash")
            combined = "\n".join(m["content"] for m in judge_messages)
            resp = model.generate_content(combined)
            raw_response = resp.text
        except Exception as e:
            print(f"  [LLM-Judge] Gemini error: {e}")

    # ── Parse & compute weighted score ──
    if raw_response:
        try:
            # Strip possible markdown fences
            clean = raw_response.strip().strip("```json").strip("```").strip()
            scores = _json.loads(clean)
            faithfulness  = float(scores.get("faithfulness",  0.5))
            relevance     = float(scores.get("relevance",     0.5))
            completeness  = float(scores.get("completeness",  0.5))
            reasoning     = scores.get("reasoning", "")

            weighted = (
                0.5 * faithfulness
                + 0.3 * relevance
                + 0.2 * completeness
            )
            confidence = round(max(0.1, min(0.95, weighted)), 2)
            print(
                f"  [LLM-Judge] faith={faithfulness:.2f} rel={relevance:.2f} "
                f"comp={completeness:.2f} → confidence={confidence} | {reasoning}"
            )
            return confidence
        except Exception as e:
            print(f"  [LLM-Judge] parse error: {e} — falling back to rule-based")

    return _rule_based()


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Tổng hợp câu trả lời từ chunks và policy context.

    Returns:
        {"answer": str, "sources": list, "confidence": float}
    """
    context = _build_context(chunks, policy_result)

    # Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Câu hỏi: {task}

{context}

Hãy trả lời câu hỏi dựa vào tài liệu trên."""
        }
    ]

    answer = _call_llm(messages)
    sources = list({c.get("source", "unknown") for c in chunks})
    confidence = _estimate_confidence(chunks, answer, policy_result)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"]
        state["confidence"] = result["confidence"]

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources": result["sources"],
            "confidence": result["confidence"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated, confidence={result['confidence']}, "
            f"sources={result['sources']}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
        state["confidence"] = 0.0
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker — Standalone Test")
    print("=" * 50)

    test_state = {
        "task": "SLA ticket P1 là bao lâu?",
        "retrieved_chunks": [
            {
                "text": "Ticket P1: Phản hồi ban đầu 15 phút kể từ khi ticket được tạo. Xử lý và khắc phục 4 giờ. Escalation: tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút.",
                "source": "sla_p1_2026.txt",
                "score": 0.92,
            }
        ],
        "policy_result": {},
    }

    result = run(test_state.copy())
    print(f"\nAnswer:\n{result['final_answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Confidence: {result['confidence']}")

    print("\n--- Test 2: Exception case ---")
    test_state2 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
        "retrieved_chunks": [
            {
                "text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4.",
                "source": "policy_refund_v4.txt",
                "score": 0.88,
            }
        ],
        "policy_result": {
            "policy_applies": False,
            "exceptions_found": [{"type": "flash_sale_exception", "rule": "Flash Sale không được hoàn tiền."}],
        },
    }
    result2 = run(test_state2.copy())
    print(f"\nAnswer:\n{result2['final_answer']}")
    print(f"Confidence: {result2['confidence']}")

    print("\n✅ synthesis_worker test done.")
