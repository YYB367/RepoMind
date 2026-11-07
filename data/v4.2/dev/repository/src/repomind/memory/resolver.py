"""Pure temporal projection. Neither import order nor ID resolves ambiguity."""

from collections.abc import Iterable

from repomind.domain.models import Event, MemoryQuery, QueryResult


class MemoryResolver:
    def resolve(self, query: MemoryQuery, events: Iterable[Event]) -> QueryResult:
        visible = sorted(
            (event for event in events if event.key == query.key
             and (query.known_at is None or event.observed_at <= query.known_at)),
            key=lambda event: event.event_id,
        )
        plans = [event.event_id for event in visible
                 if event.event_type == "plan" and event.observed_at <= query.as_of]
        facts = [event for event in visible
                 if event.event_type != "plan" and event.effective_at <= query.as_of]
        replaced = {event.supersedes_event_id for event in facts if event.event_type == "correct"}
        active = [event for event in facts if event.event_id not in replaced]
        audit = dict(considered_event_ids=[event.event_id for event in visible], plan_event_ids=plans)
        if not active:
            return QueryResult(status="unknown", reason="only_plans" if plans else "no_effective_fact", **audit)
        latest = max(event.effective_at for event in active)
        evidence = [event for event in active if event.effective_at == latest]
        values = {event.value for event in evidence}
        if len(values) > 1:
            return QueryResult(status="insufficient_evidence", reason="conflicting_effective_facts",
                               evidence=evidence, **audit)
        return QueryResult(status="ok", value=evidence[0].value, reason="latest_effective_fact",
                           evidence=evidence, **audit)
