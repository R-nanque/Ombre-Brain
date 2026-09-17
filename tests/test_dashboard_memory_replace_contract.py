"""The settings UI keeps preview, explicit quote scope and undo visible."""

from pathlib import Path


DASHBOARD = Path(__file__).resolve().parents[1] / "frontend" / "dashboard.html"


def test_memory_replace_ui_is_independent_and_confirmation_gated():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="sec-memory-replace" data-sgroup="basics"' in html
    assert 'id="memory-replace-quotes"' in html
    assert '包含原话引用' in html
    assert '留空 = 删除' in html
    assert 'id="memory-replace-modal"' in html
    assert '替换前请检查一个真实例子' in html
    assert "confirmation_token: state.confirmation_token" in html
    assert "confirmBtn.disabled = !data.sample;" in html
    assert '撤销上次替换' in html

    # The old nickname repair remains a separate feature and endpoint.
    assert 'onclick="syncExistingHuman()"' in html
    assert "/api/settings/human/sync-existing" in html
    assert "/api/settings/memory-replace/preview" in html
