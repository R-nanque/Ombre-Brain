"""Global Dashboard memory replacement is previewed, reversible and safe."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def _memory(bucket_mgr, *, content="Old body and old body"):
    return await bucket_mgr.create(
        content,
        title="Old title",
        tags=["Old-tag", "keep"],
        domain=["Old"],
        why_remembered="Old reason",
        meaning="Old meaning",
        quotes=[{"text": "Old verbatim quote", "speaker": "human"}],
        test_data=True,
    )


async def test_global_replace_previews_applies_to_archive_and_undoes(bucket_mgr):
    active_id = await _memory(bucket_mgr)
    archived_id = await _memory(bucket_mgr, content="Archived Old body")
    assert await bucket_mgr.archive(archived_id) is True

    preview = await bucket_mgr.preview_global_text_replacement(
        "old", "", ignore_case=True, include_quotes=False
    )

    assert preview["memory_count"] == 2
    assert preview["replacement_count"] >= 12
    assert preview["sample"]["bucket_id"] == active_id
    assert preview["sample"]["before"]
    assert "quotes" not in preview["field_counts"]

    applied = await bucket_mgr.apply_global_text_replacement(
        "old",
        "",
        ignore_case=True,
        include_quotes=False,
        confirmation_token=preview["confirmation_token"],
    )
    assert applied["memory_count"] == 2

    active = await bucket_mgr.get(active_id)
    archived = await bucket_mgr.get(archived_id)
    assert "old" not in active["content"].casefold()
    assert "old" not in archived["content"].casefold()
    assert active["metadata"]["domain"] == ["未分类"]
    # Verbatim evidence is opt-in and therefore untouched here.
    assert active["metadata"]["quotes"][0]["text"] == "Old verbatim quote"
    assert bucket_mgr.global_text_replace_undo_status()["available"] is True

    undone = await bucket_mgr.undo_global_text_replacement()
    assert undone == {"restored": 2, "conflicts": [], "remaining": 0}
    active = await bucket_mgr.get(active_id)
    archived = await bucket_mgr.get(archived_id)
    assert active["content"] == "Old body and old body"
    assert archived["content"] == "Archived Old body"
    assert active["metadata"]["domain"] == ["Old"]
    assert bucket_mgr.global_text_replace_undo_status()["available"] is False


async def test_global_replace_quotes_are_explicit_and_case_sensitive(bucket_mgr):
    bucket_id = await _memory(bucket_mgr)

    case_sensitive = await bucket_mgr.preview_global_text_replacement(
        "old", "new", ignore_case=False, include_quotes=True
    )
    # Lowercase body matches; capitalized title/metadata/quote do not.
    assert case_sensitive["field_counts"] == {"content": 1}

    include_quotes = await bucket_mgr.preview_global_text_replacement(
        "Old", "New", ignore_case=False, include_quotes=True
    )
    assert include_quotes["field_counts"]["quotes"] == 1
    await bucket_mgr.apply_global_text_replacement(
        "Old",
        "New",
        ignore_case=False,
        include_quotes=True,
        confirmation_token=include_quotes["confirmation_token"],
    )
    bucket = await bucket_mgr.get(bucket_id)
    assert bucket["metadata"]["quotes"][0]["text"] == "New verbatim quote"


async def test_global_replace_rejects_stale_preview(bucket_mgr):
    bucket_id = await _memory(bucket_mgr)
    preview = await bucket_mgr.preview_global_text_replacement(
        "Old", "New", ignore_case=False, include_quotes=False
    )
    assert await bucket_mgr.update(bucket_id, title="Old title edited") is True

    with pytest.raises(ValueError, match="重新检查"):
        await bucket_mgr.apply_global_text_replacement(
            "Old",
            "New",
            ignore_case=False,
            include_quotes=False,
            confirmation_token=preview["confirmation_token"],
        )


async def test_global_replace_undo_skips_later_edits(bucket_mgr):
    bucket_id = await _memory(bucket_mgr)
    preview = await bucket_mgr.preview_global_text_replacement(
        "Old", "New", ignore_case=False, include_quotes=False
    )
    await bucket_mgr.apply_global_text_replacement(
        "Old",
        "New",
        ignore_case=False,
        include_quotes=False,
        confirmation_token=preview["confirmation_token"],
    )
    assert await bucket_mgr.update(bucket_id, title="Manually edited later") is True

    result = await bucket_mgr.undo_global_text_replacement()

    assert result["restored"] == 0
    assert result["remaining"] == 1
    assert result["conflicts"][0]["bucket_id"] == bucket_id
    assert (await bucket_mgr.get(bucket_id))["metadata"]["title"] == "Manually edited later"


async def test_global_replace_rolls_back_when_a_later_commit_fails(
    bucket_mgr, monkeypatch
):
    first_id = await _memory(bucket_mgr, content="Old first")
    second_id = await _memory(bucket_mgr, content="Old second")
    preview = await bucket_mgr.preview_global_text_replacement(
        "Old", "New", ignore_case=False, include_quotes=False
    )
    original_commit = bucket_mgr._commit_global_replace_item

    async def fail_second(item, **kwargs):
        if (
            item["bucket_id"] == second_id
            and kwargs.get("event_action") == "global_text_replace"
        ):
            return False, {"bucket_id": second_id, "reason": "simulated failure"}
        return await original_commit(item, **kwargs)

    monkeypatch.setattr(bucket_mgr, "_commit_global_replace_item", fail_second)

    with pytest.raises(RuntimeError, match="已回滚"):
        await bucket_mgr.apply_global_text_replacement(
            "Old",
            "New",
            ignore_case=False,
            include_quotes=False,
            confirmation_token=preview["confirmation_token"],
        )

    assert (await bucket_mgr.get(first_id))["content"] == "Old first"
    assert (await bucket_mgr.get(second_id))["content"] == "Old second"
    assert bucket_mgr.global_text_replace_undo_status()["available"] is False
