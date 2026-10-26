from repomind.domain.models import Event, MemoryQuery
from repomind.memory.resolver import MemoryResolver


def e(event_id, value, when, kind="declare", **kwargs):
    return Event(event_id=event_id, project_id="A", subject="project", predicate="database", value=value,
                 event_type=kind, observed_at=when, source_id=f"session-{event_id}", **kwargs)


def query(events, as_of="2026-04-10", **kwargs):
    return MemoryResolver().resolve(MemoryQuery(project_id="A", predicate="database", as_of=as_of, **kwargs), events)


def test_plan_completion_and_trace():
    events = [e("old", "MySQL", "2026-01-01T00:00:00Z"),
              e("plan", "PostgreSQL", "2026-03-01T00:00:00Z", "plan", effective_at="2026-04-01T00:00:00Z"),
              e("done", "PostgreSQL", "2026-04-02T00:00:00Z", "complete", effective_at="2026-04-01T00:00:00Z")]
    assert query(events, "2026-02-01").value == "MySQL"
    march = query(events, "2026-03-15")
    assert march.value == "MySQL" and march.plan_event_ids == ["plan"]
    april = query(events)
    assert april.value == "PostgreSQL"
    assert [(item.event_id, item.source_id) for item in april.evidence] == [("done", "session-done")]
    assert query(events, "2026-04-01", known_at="2026-04-01").value == "MySQL"


def test_correction_changes_old_fact_without_hiding_later_state():
    events = [e("old", "MySQL", "2026-01-01T00:00:00Z"),
              e("done", "PostgreSQL", "2026-04-01T00:00:00Z", "complete"),
              e("fix", "MariaDB", "2026-05-01T00:00:00Z", "correct",
                effective_at="2026-01-01T00:00:00Z", supersedes_event_id="old")]
    assert query(events, "2026-02-01").value == "MariaDB"
    assert query(events, "2026-02-01", known_at="2026-02-01").value == "MySQL"
    assert query(events).value == "PostgreSQL"


def test_conflict_refuses_and_equivalent_values_merge_evidence():
    events = [e("a", "MySQL", "2026-01-01T00:00:00Z"), e("b", "MariaDB", "2026-01-02T00:00:00Z",
              effective_at="2026-01-01T00:00:00Z")]
    result = query(events)
    assert result.status == "insufficient_evidence" and result.value is None
    assert {item.event_id for item in result.evidence} == {"a", "b"}
    same = [events[0], e("c", "MySQL", "2026-01-02T00:00:00Z", effective_at="2026-01-01T00:00:00Z")]
    assert query(same).value == "MySQL"
    assert len(query(same).evidence) == 2


def test_unknown_and_plan_only_have_no_supporting_fact():
    assert query([]).status == "unknown"
    result = query([e("plan", "PostgreSQL", "2026-02-01T00:00:00Z", "plan")])
    assert result.status == "unknown" and result.value is None and result.evidence == []
    assert result.reason == "only_plans"


def test_effective_and_observation_are_distinct():
    late = e("late", "PostgreSQL", "2026-05-01T00:00:00Z", "complete", effective_at="2026-03-01T00:00:00Z")
    assert query([late], "2026-04-01").value == "PostgreSQL"
    assert query([late], "2026-04-01", known_at="2026-04-01").status == "unknown"
    assert query([late], "2026-02-28").status == "unknown"
