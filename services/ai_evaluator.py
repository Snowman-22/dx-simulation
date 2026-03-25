"""
AI evaluator using OpenAI API to evaluate and rank multiple layout options.
"""
import os
import json
from openai import OpenAI


def _get_api_key() -> str:
    """환경변수 → ai_explanation.py 키 순서로 API 키 가져오기."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        return key
    try:
        from services.ai_explanation import OPENAI_API_KEY
        return OPENAI_API_KEY or ""
    except ImportError:
        return ""


def evaluate_layouts_with_ai(layouts: list[dict], rooms: list[dict]) -> dict:
    """Use OpenAI to evaluate multiple layouts and pick the best one."""

    api_key = _get_api_key()
    if not api_key:
        return _fallback_evaluation(layouts)

    try:
        client = OpenAI(api_key=api_key)
        prompt = _build_prompt(layouts, rooms)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "당신은 20년 경력의 인테리어 전문가입니다. "
                    "가구/가전 배치안을 평가할 때 생활 동선, 공간 활용도, "
                    "시각적 균형, 실용성(TV 시청거리, 냉장고 문 열림 등)을 종합적으로 고려합니다. "
                    "반드시 지정된 JSON 형식으로만 응답하세요."
                )},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        # Validate and normalize
        return _normalize_result(result, layouts)

    except Exception as e:
        print(f"[ai_evaluator] OpenAI API error: {e}")
        return _fallback_evaluation(layouts)


def _build_prompt(layouts: list[dict], rooms: list[dict]) -> str:
    """Build evaluation prompt with room info and layout placements."""

    # Room descriptions
    room_lines = []
    for r in rooms:
        features = r.get("features", [])
        if isinstance(features, str):
            features = json.loads(features)

        feat_descs = []
        for f in features:
            ft = f.get("type", "")
            wall = f.get("wall", "")
            if ft == "door":
                dtype = "미닫이문" if f.get("door_type") == "slide" else "여닫이문"
                feat_descs.append(f"{wall}벽 {dtype}")
            elif ft == "window":
                feat_descs.append(f"{wall}벽 창문")
            elif ft == "water_hookup":
                feat_descs.append(f"{wall}벽 수도")
            elif ft == "gas_line":
                feat_descs.append(f"{wall}벽 가스")
            elif ft == "fixture":
                feat_descs.append(f"{wall}벽 {f.get('label', '설비')}")

        feat_str = ", ".join(feat_descs) if feat_descs else "없음"
        room_lines.append(
            f"  - {r['name']} ({r['room_type']}): "
            f"{r['width_mm']}x{r['height_mm']}mm, "
            f"설비: {feat_str}"
        )

    rooms_text = "\n".join(room_lines)

    # Layout descriptions
    layout_texts = []
    for layout in layouts:
        pl_lines = []
        for p in layout["placements"]:
            # Find room name
            room_name = "?"
            for r in rooms:
                if r["id"] == p.get("room_id"):
                    room_name = r["name"]
                    break
            cat = p.get("category", "알수없음")
            x, y = round(p.get("x_mm", 0)), round(p.get("y_mm", 0))
            rot = p.get("rotation", 0)
            pw = round(p.get("pw", 0))
            pd = round(p.get("pd", 0))
            pl_lines.append(f"    {cat} ({pw}x{pd}mm) → {room_name} ({x},{y}) 회전:{rot}°")

        m = layout["metrics"]
        layout_texts.append(
            f"[배치안 {layout['id']}: {layout['name']}]\n"
            f"  설명: {layout['desc']}\n"
            f"  배치:\n" + "\n".join(pl_lines) + "\n"
            f"  참고 메트릭(내부): 공간활용 {m['space_usage']}, 동선 {m['circulation']}, "
            f"관계충족 {m['pair_satisfaction']}, 균형 {m['wall_balance']}, "
            f"중앙여백 {m['center_openness']}, 전면확보 {m['front_zone']}"
        )

    layouts_text = "\n\n".join(layout_texts)

    valid_ids = [l["id"] for l in layouts]
    id_list = ", ".join(str(i) for i in valid_ids)

    prompt = f"""아래 {len(layouts)}개의 가구/가전 배치안을 인테리어 전문가 관점에서 평가해주세요.

[방 정보]
{rooms_text}

{layouts_text}

다음 JSON 형식으로 응답하세요:
{{
  "rankings": [
    {{"layout_id": 0, "score": 85, "pros": "장점 1~2문장", "cons": "단점 1~2문장"}},
    ...
  ],
  "recommendation": 0,
  "summary": "추천 배치안에 대한 2-3문장 요약 설명"
}}

중요:
- layout_id는 반드시 {id_list} 중 하나여야 합니다 (정확히 {len(layouts)}개)
- rankings에 모든 배치안이 빠짐없이 포함되어야 합니다
- score는 0~100점입니다
- rankings는 score 높은 순서로 정렬하세요
- recommendation은 가장 추천하는 배치안의 layout_id입니다
- 내부 메트릭은 참고만 하고, 당신의 전문가적 관점으로 독립적으로 평가하세요
- 생활 동선(문/통행로 확보), 실용성(TV 시청거리, 냉장고 문 열림), 공간 활용도, 시각적 균형을 종합 평가"""

    return prompt


def _normalize_result(result: dict, layouts: list[dict]) -> dict:
    """Validate and normalize AI response."""
    rankings = result.get("rankings", [])
    recommendation = result.get("recommendation", 0)
    summary = result.get("summary", "")

    # Ensure all layouts are in rankings
    ranked_ids = {r.get("layout_id") for r in rankings}
    for layout in layouts:
        if layout["id"] not in ranked_ids:
            rankings.append({
                "layout_id": layout["id"],
                "score": layout["metrics"]["total"],
                "pros": "",
                "cons": "",
            })

    # Sort by score descending
    rankings.sort(key=lambda r: r.get("score", 0), reverse=True)

    # Validate recommendation
    valid_ids = {l["id"] for l in layouts}
    if recommendation not in valid_ids:
        recommendation = rankings[0]["layout_id"] if rankings else 0

    return {
        "rankings": rankings,
        "recommendation": recommendation,
        "summary": summary,
    }


def _fallback_evaluation(layouts: list[dict]) -> dict:
    """Fallback when AI is unavailable - use internal metrics."""
    rankings = []
    for layout in layouts:
        metrics = layout["metrics"]
        # 높은 점수 항목을 장점으로
        pros_parts = []
        if metrics.get("circulation", 0) >= 80:
            pros_parts.append("동선 효율이 좋습니다")
        if metrics.get("center_openness", 0) >= 80:
            pros_parts.append("중앙 개방감이 확보되었습니다")
        if metrics.get("space_usage", 0) >= 70:
            pros_parts.append("공간 활용도가 높습니다")
        if metrics.get("wall_balance", 0) >= 70:
            pros_parts.append("가구 배치 균형이 좋습니다")
        if not pros_parts:
            pros_parts.append("안정적인 배치입니다")

        # 낮은 점수 항목을 단점으로
        cons_parts = []
        if metrics.get("space_usage", 100) < 50:
            cons_parts.append("공간 활용도가 낮습니다")
        if metrics.get("wall_balance", 100) < 50:
            cons_parts.append("가구 배치가 한쪽에 치우쳐 있습니다")
        if metrics.get("circulation", 100) < 60:
            cons_parts.append("이동 동선이 좁을 수 있습니다")

        rankings.append({
            "layout_id": layout["id"],
            "score": round(metrics["total"], 1),
            "pros": ". ".join(pros_parts),
            "cons": ". ".join(cons_parts) if cons_parts else "특별한 단점 없음",
        })
    rankings.sort(key=lambda r: r["score"], reverse=True)

    best = rankings[0] if rankings else {"layout_id": 0}
    return {
        "rankings": rankings,
        "recommendation": best["layout_id"],
        "summary": f"내부 평가 기준으로 '{layouts[best['layout_id']]['name']}' 배치안을 추천합니다." if layouts else "",
    }
