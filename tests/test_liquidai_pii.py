from redact.liquidai_pii import LiquidAIPIIExtractor, _alphabetical_entities


def test_alphabetical_entities_deduplicates():
    entities = _alphabetical_entities(["human_name", "email_address", "human_name", " address "])
    assert entities == ("address", "email_address", "human_name")


def test_mask_text_replaces_longer_values_first():
    extractor = LiquidAIPIIExtractor(backend="offline", hf_token="dummy")
    mapping = {
        "human_name": ["Taro Yamada", "Taro"],
        "email_address": ["taro@example.com"],
    }
    masked, replacements = extractor._mask_text(
        "Taro Yamada can be reached at taro@example.com.", mapping
    )
    assert "Taro Yamada" not in masked
    assert "taro@example.com" not in masked

    human_entries = [item for item in replacements if item["category"] == "human_name"]
    assert human_entries[0]["value"] == "Taro Yamada"
    assert human_entries[1]["value"] == "Taro"
