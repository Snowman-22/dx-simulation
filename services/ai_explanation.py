"""
AI Explanation Service
Uses OpenAI GPT-4o-mini to explain why products were placed in certain positions.
"""
from openai import OpenAI

import os
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)

# 배치 규칙 요약 (프롬프트에 포함)
PLACEMENT_RULES_SUMMARY = """
[주요 배치 규칙]
1. 벽 밀착: 대부분의 가전/가구는 벽에 밀착 배치 (후면 여유 0mm)
2. 문 회피: 문 열림 공간 + 문 앞 800mm 통행 구역에 배치 금지. 인접 방의 문도 고려
3. 창문 회피: 창문 앞 300mm 영역에 배치 금지. TV는 빛반사, 전기레인지는 화재 위험
4. 설비 근접: 냉장고/세탁기/식기세척기→수전 근처, 전기레인지→가스 근처
5. TV↔소파: 반대편 벽 마주보기, 중앙점 정렬
6. 세탁기↔건조기: 나란히 밀착 배치
7. 의자: 책상/식탁/화장대가 있는 방으로 따라가서 밀착 배치
8. 대형 가전/가구(냉장고,침대,소파,옷장): 코너 배치 우선 (+500점)
9. 에어컨/TV: 벽 중앙 배치 선호, 코너 배치 회피
10. 열원 분리: 냉장고와 전기레인지는 최소 500mm 이격
11. 에어컨↔침대: 직접 바람 방지를 위해 1500mm 이상 이격
12. 자연스러운 방향: 넓은 면이 벽을 따라가도록 배치
13. 제품 전면 금지 구역: TV 앞 2500mm, 냉장고 앞 900mm, 에어컨 앞 1500mm 등 다른 제품 배치 금지
"""


def _build_prompt(floor_plan: dict, rooms_data: list[dict]) -> str:
    """배치 설명을 위한 프롬프트 생성."""
    lines = []

    # 도면 정보
    lines.append(f"[도면 정보]")
    lines.append(f"도면: {floor_plan['name']}, 면적: {floor_plan.get('total_area_m2', '?')}㎡")
    lines.append(f"전체 크기: {floor_plan['total_width_mm']/1000:.1f}m x {floor_plan['total_height_mm']/1000:.1f}m")
    lines.append("")

    # 방별 정보 + 배치 결과
    lines.append("[방 구성 및 배치 결과]")
    for room_info in rooms_data:
        room = room_info["room"]
        features = room_info.get("features", [])
        placements = room_info.get("placements", [])

        w_m = room["width_mm"] / 1000
        h_m = room["height_mm"] / 1000
        room_type_names = {
            "living": "거실", "kitchen": "주방", "bedroom": "침실",
            "bathroom": "화장실", "utility": "세탁실/발코니",
        }
        type_name = room_type_names.get(room["room_type"], room["room_type"])

        lines.append(f"\n■ {room['name']} ({type_name}, {w_m:.1f}m x {h_m:.1f}m)")

        # 설비 정보
        feat_names = {"door": "문", "window": "창문", "water_hookup": "수전", "gas_line": "가스"}
        wall_names = {"north": "북", "south": "남", "east": "동", "west": "서"}
        if features:
            feat_strs = []
            for f in features:
                if f.get("_virtual"):
                    continue  # 가상 문은 제외
                fname = feat_names.get(f.get("type"), f.get("type", "?"))
                fwall = wall_names.get(f.get("wall"), f.get("wall", "?"))
                feat_strs.append(f"{fname}({fwall}벽)")
            if feat_strs:
                lines.append(f"  설비: {', '.join(feat_strs)}")

        # 배치 결과
        if not room["is_placeable"]:
            lines.append(f"  → 배치 불가 (화장실 등)")
        elif placements:
            for pl in placements:
                name = pl.get("product_name", pl.get("model", "?"))
                cat = pl.get("category", "?")
                x_cm = pl["x_mm"] / 10
                y_cm = pl["y_mm"] / 10
                rot = pl.get("rotation", 0)
                lines.append(f"  → {name} ({cat}): 위치({x_cm:.0f}cm, {y_cm:.0f}cm), 회전 {rot}°")
        else:
            lines.append(f"  → 배치된 제품 없음")

    # 배치 규칙
    lines.append(PLACEMENT_RULES_SUMMARY)

    # 요청
    lines.append("[요청]")
    lines.append("위 도면과 배치 결과를 바탕으로, 배치 근거를 방별로 설명해주세요.")
    lines.append("")
    lines.append("출력 형식:")
    lines.append("## 전체 배치 요약")
    lines.append("(1~2문장 전체 요약)")
    lines.append("")
    lines.append("## 거실")
    lines.append("- 각 제품 배치 이유 (1줄씩)")
    lines.append("")
    lines.append("## 주방")
    lines.append("- 각 제품 배치 이유")
    lines.append("(방이 없으면 생략)")
    lines.append("")
    lines.append("규칙: 마크다운 ## 제목과 - 리스트를 사용하세요.")
    lines.append("각 방의 제품 배치 이유, 제품 간 관계, 문/창문/설비와의 관계를 간결하게 작성하세요.")

    return "\n".join(lines)


def generate_explanation_stream(floor_plan: dict, rooms_data: list[dict]):
    """OpenAI GPT-4o-mini 스트리밍으로 배치 근거 설명을 생성. yields 텍스트 청크."""
    prompt = _build_prompt(floor_plan, rooms_data)

    try:
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 경험 많은 인테리어 전문가입니다. "
                        "가전 및 가구 배치 결과를 분석하고, "
                        "왜 이렇게 배치되었는지 근거 있는 설명을 제공합니다. "
                        "반드시 한국어 존댓말(~합니다, ~됩니다, ~있습니다)로 답변하세요."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1000,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"AI 설명 생성 실패: {str(e)}"
