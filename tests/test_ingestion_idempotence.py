from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.intelligence.ingestion import prepare_ingestion
from repomind.intelligence.models import ExtractionBatch, SourceMessage


def test_reapplying_source_reuses_provenance_without_a_second_model_request():
    class Provider:
        name = "synthetic-not-live"
        calls = 0

        def extract(self, source, context):
            self.calls += 1
            assert self.calls == 1, "unchanged source should not be sent for extraction twice"
            return ExtractionBatch(facts=[dict(subject="project", predicate="database", value="MySQL",
                event_type="declare", evidence_text="use MySQL", effective_at=None, supersedes_event_id=None)])

    source = SourceMessage(project_id="A", source_id="s1", observed_at="2026-01-01T00:00:00Z", text="We use MySQL.")
    provider = Provider()
    with SQLiteMemoryStore(":memory:") as store:
        first = prepare_ingestion(store, [source, source], provider)
        assert provider.calls == 1 and first[0] == first[1]
        assert store.import_extractions(first).imported == 1
        again = prepare_ingestion(store, [source], provider)
        assert provider.calls == 1 and again[0].events == first[0].events
        assert again[0].evidence_by_event == first[0].evidence_by_event
        assert again[0].provider.startswith("stored-source-cache:")
        assert store.import_extractions(again).duplicates == 1
        assert store.count() == 1
