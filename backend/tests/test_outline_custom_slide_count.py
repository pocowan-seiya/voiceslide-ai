from services.outline_generator import (
    create_fallback_outline,
    validate_and_fix_outline_timestamps,
)


def _segments(count=10, seconds=305.0):
    duration = seconds / count
    return [
        {
            "id": i,
            "start": round(i * duration, 1),
            "end": round((i + 1) * duration, 1),
            "text": f"これはスライド{i + 1}の具体的な話です。大事な言葉{i + 1}があります。",
        }
        for i in range(count)
    ]


def test_custom_slide_count_rebuilds_when_model_returns_fewer_slides():
    segments = _segments()
    outline = {
        "presentation_title": "プレゼンテーション",
        "slides": [
            {
                "number": i + 1,
                "title": f"セクション {i + 1}",
                "timestamp_start": i * 61.0,
                "timestamp_end": (i + 1) * 61.0,
            }
            for i in range(5)
        ],
        "total_slides": 5,
    }

    fixed = validate_and_fix_outline_timestamps(
        outline,
        segments,
        305.0,
        transcript=" ".join(segment["text"] for segment in segments),
        target_slide_count=10,
    )

    assert fixed["total_slides"] == 10
    assert len(fixed["slides"]) == 10
    assert fixed["slides"][0]["timestamp_start"] == 0.0
    assert fixed["slides"][-1]["timestamp_end"] == 305.0
    assert all(not slide["title"].startswith("セクション") for slide in fixed["slides"])
    assert "具体的な話" in fixed["slides"][0]["title"]


def test_fallback_outline_uses_requested_count_and_transcript_words():
    segments = _segments()
    outline = create_fallback_outline(
        " ".join(segment["text"] for segment in segments),
        segments,
        slide_count=10,
    )

    assert outline["total_slides"] == 10
    assert len(outline["slides"]) == 10
    assert outline["slides"][-1]["timestamp_end"] == segments[-1]["end"]
    assert all(not slide["title"].startswith("セクション") for slide in outline["slides"])
    assert outline["slides"][0]["slide_copy"]["headline"] == outline["slides"][0]["title"]
