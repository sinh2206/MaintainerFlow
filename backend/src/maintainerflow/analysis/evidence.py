from maintainerflow.core.schemas import Evidence


def deduplicate_evidence(items: list[Evidence] | tuple[Evidence, ...]) -> tuple[Evidence, ...]:
    merged: dict[tuple[str, str | None, int | None, str], Evidence] = {}
    for item in items:
        key = (item.kind, item.path, item.line, item.message)
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            continue
        sources = {
            existing.source,
            item.source,
            *existing.metadata.get("sources", []),
            *item.metadata.get("sources", []),
        }
        metadata = {**existing.metadata, **item.metadata, "sources": sorted(sources)}
        merged[key] = existing.model_copy(
            update={"confidence": max(existing.confidence, item.confidence), "metadata": metadata}
        )
    return tuple(merged.values())
