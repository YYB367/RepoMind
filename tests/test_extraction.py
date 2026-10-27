"""Trust binding tests; these do not claim live LLM extraction quality."""

import json

import pytest

from repomind.domain.models import Event
from repomind.intelligence.extraction import Extractor
from repomind.intelligence.models import CandidateFact, ExtractedMemory, ExtractionBatch, SourceMessage
from repomind.intelligence.providers import ReplayExtractionProvider


def source(**changes):
    data = {"project_id": "A", "source_id": "meeting-may", "observed_at": "2026-05-01T09:00:00Z", "text": "项目当前数据库是 MySQL。计划未来迁移到 PostgreSQL。"}
    data.update(changes)
    return SourceMessage.model_validate(data)


def candidate(**changes):
    data = {"subject": "project", "predicate": "database", "value": "MySQL", "event_type": "declare", "evidence_text": "当前数据库是 MySQL"}
    data.update(changes)
    return CandidateFact.model_validate(data)


def target(**changes):
    data = {"event_id": "existing-db", "project_id": "A", "source_id": "meeting-jan", "observed_at": "2026-01-01T00:00:00Z", "subject": "project", "predicate": "database", "value": "SQLite", "event_type": "declare"}
    data.update(changes)
    return Event.model_validate(data)


class StubProvider:
    name = "test-candidates-not-live"

    def __init__(self, response):
        self.response = response
        self.calls = 0

    def extract(self, message, context):
        self.calls += 1
        return self.response


def extract(facts, message=None, context=None):
    return Extractor(StubProvider(ExtractionBatch(facts=facts))).extract(message or source(), context)


def test_envelope_hash_is_canonical_and_binds_project_source_time_and_text():
    original = source()
    assert original.content_hash == source(observed_at="2026-05-01T17:00:00+08:00").content_hash
    assert len(original.content_hash) == 64
    for changes in [{"project_id": "B"}, {"source_id": "other"}, {"observed_at": "2026-05-01T09:00:01Z"}, {"text": original.text + " "}]:
        assert original.content_hash != source(**changes).content_hash


def test_source_text_and_evidence_preserve_exact_whitespace():
    message = source(text="  数据库采用 MySQL\n")
    fact = candidate(evidence_text="  数据库采用 MySQL\n")
    memory = extract([fact], message)
    assert memory.source.text == message.text
    assert memory.evidence_by_event[memory.events[0].event_id] == message.text


@pytest.mark.parametrize("extra", ["project_id", "source_id", "observed_at", "event_id", "command"])
def test_model_cannot_own_trusted_scope_or_execute_actions(extra):
    with pytest.raises(ValueError):
        candidate(**{extra: "injected"})


@pytest.mark.parametrize("timestamp", ["2026-05-01", "2026-05-01T09:00:00", 1770000000, None])
def test_source_observation_requires_explicit_timezone(timestamp):
    with pytest.raises(ValueError):
        source(observed_at=timestamp)


def test_extractor_binds_trusted_scope_time_source_and_quote():
    memory = extract([candidate()])
    event = memory.events[0]
    assert (event.project_id, event.source_id, event.observed_at) == (memory.source.project_id, memory.source.source_id, memory.source.observed_at)
    assert event.effective_at == memory.source.observed_at
    assert event.event_id.startswith("nl-")
    assert len(event.event_id) == 35
    assert memory.evidence_by_event == {event.event_id: "当前数据库是 MySQL"}


def test_event_ids_are_stable_under_reordering_exact_duplicates_and_explicit_default_time():
    first = candidate()
    second = candidate(value="PostgreSQL", event_type="plan", evidence_text="计划未来迁移到 PostgreSQL")
    left = extract([first, second, first])
    right = extract([second, candidate(effective_at=source().observed_at)])
    assert left.events == right.events
    assert left.evidence_by_event == right.evidence_by_event
    assert len(left.events) == 2


def test_scope_change_changes_generated_event_id():
    assert extract([candidate()]).events[0].event_id != extract([candidate()], source(project_id="B")).events[0].event_id


def test_plan_can_have_future_effective_time_without_claiming_completion():
    memory = extract([candidate(value="PostgreSQL", event_type="plan", effective_at="2026-07-01T00:00:00Z", evidence_text="计划未来迁移到 PostgreSQL")])
    assert memory.events[0].event_type == "plan"
    assert memory.events[0].effective_at > memory.events[0].observed_at


@pytest.mark.parametrize("event_type", ["declare", "complete"])
def test_actual_fact_cannot_be_declared_effective_in_the_future(event_type):
    with pytest.raises(ValueError, match="later than observed_at"):
        extract([candidate(event_type=event_type, effective_at="2027-01-01T00:00:00Z")])


def test_paraphrased_or_fabricated_quote_is_rejected():
    with pytest.raises(ValueError, match="exact source substring"):
        extract([candidate(evidence_text="The database is MySQL")])


def test_cross_project_context_is_rejected_before_provider_sees_it():
    provider = StubProvider(ExtractionBatch(facts=[candidate()]))
    with pytest.raises(ValueError, match="only the source project"):
        Extractor(provider).extract(source(), [target(project_id="B")])
    assert provider.calls == 0


def test_duplicate_context_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate event IDs"):
        extract([candidate()], context=[target(), target()])


def test_explicit_correction_retains_target_effective_time():
    fact = candidate(event_type="correct", supersedes_event_id="existing-db")
    memory = extract([fact], context=[target()])
    event = memory.events[0]
    assert event.effective_at == target().effective_at
    assert event.supersedes_event_id == "existing-db"
    assert target().value == "SQLite"


@pytest.mark.parametrize("context,fact_changes,needle", [
    ([], {}, "absent"),
    ([target(event_type="plan")], {}, "plan"),
    ([target(subject="worker")], {}, "different fact scope"),
    ([target()], {"effective_at": "2026-02-01T00:00:00Z"}, "retain target effective_at"),
    ([target(observed_at="2026-06-01T00:00:00Z")], {}, "before its target"),
])
def test_unsafe_corrections_are_rejected(context, fact_changes, needle):
    with pytest.raises(ValueError, match=needle):
        extract([candidate(event_type="correct", supersedes_event_id="existing-db", **fact_changes)], context=context)


def test_candidate_correction_requires_target_and_other_types_forbid_it():
    with pytest.raises(ValueError, match="explicit supersedes"):
        candidate(event_type="correct")
    with pytest.raises(ValueError, match="only a correction"):
        candidate(supersedes_event_id="existing-db")


def test_empty_batch_requires_explicit_abstention_and_preserves_it():
    with pytest.raises(ValueError, match="abstain_reason"):
        ExtractionBatch(facts=[])
    with pytest.raises(ValueError, match="mutually exclusive"):
        ExtractionBatch(facts=[candidate()], abstain_reason="none")
    provider = StubProvider(ExtractionBatch(facts=[], abstain_reason="Question only; no adopted fact."))
    memory = Extractor(provider).extract(source(text="数据库以后应该换成什么？"))
    assert memory.events == []
    assert memory.evidence_by_event == {}
    assert memory.abstain_reason == "Question only; no adopted fact."


def test_extracted_memory_revalidates_source_binding_and_evidence():
    memory = extract([candidate()])
    values = memory.model_dump()
    values["events"][0]["project_id"] = "B"
    with pytest.raises(ValueError, match="trusted source"):
        ExtractedMemory.model_validate(values)
    values = memory.model_dump()
    values["evidence_by_event"][memory.events[0].event_id] = "fabricated quote"
    with pytest.raises(ValueError, match="exact nonempty"):
        ExtractedMemory.model_validate(values)


def test_model_construct_does_not_bypass_candidate_validation():
    invalid = CandidateFact.model_construct(subject="project", predicate="database", value="MySQL", event_type="correct", effective_at=None, supersedes_event_id=None, evidence_text="MySQL")
    batch = ExtractionBatch.model_construct(facts=[invalid], abstain_reason=None)
    with pytest.raises(ValueError):
        Extractor(StubProvider(batch)).extract(source())


def replay_file(path, message, response):
    path.write_text(json.dumps({"source_sha256": message.content_hash, "response": response}, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def test_recorded_replay_is_exact_hash_bound_and_honestly_named(tmp_path):
    message = source()
    path = replay_file(tmp_path / "replay.jsonl", message, ExtractionBatch(facts=[candidate()]).model_dump(mode="json"))
    provider = ReplayExtractionProvider(path)
    assert provider.name == "replay-recorded-not-live"
    assert Extractor(provider).extract(message).events[0].value == "MySQL"
    with pytest.raises(ValueError, match="exact trusted source envelope"):
        provider.extract(source(project_id="B"), [])


def test_replay_rejects_duplicate_hash_or_duplicate_json_keys(tmp_path):
    path = replay_file(tmp_path / "replay.jsonl", source(), ExtractionBatch(facts=[candidate()]).model_dump(mode="json"))
    path.write_text(path.read_text(encoding="utf-8") * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate source_sha256"):
        ReplayExtractionProvider(path)
    path.write_text('{"source_sha256":"a","source_sha256":"b"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON"):
        ReplayExtractionProvider(path)


def test_replay_cannot_add_scope_fields_to_candidates(tmp_path):
    response = ExtractionBatch(facts=[candidate()]).model_dump(mode="json")
    response["facts"][0]["project_id"] = "B"
    with pytest.raises(ValueError, match="invalid recorded replay"):
        ReplayExtractionProvider(replay_file(tmp_path / "replay.jsonl", source(), response))
