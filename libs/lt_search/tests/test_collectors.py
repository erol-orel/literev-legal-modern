from __future__ import annotations

from lt_contracts import ElasticsearchConnectionConfig
from lt_search import ElasticSearchCollector


class FakeClient:
    def search(self, **_kwargs):
        return {
            "_scroll_id": "scroll-1",
            "hits": {
                "hits": [
                    {
                        "_id": "doc-1",
                        "_score": 1.5,
                        "_source": {
                            "document_text": "Texte de decision",
                            "collector_name": "civil",
                        },
                    }
                ]
            },
        }

    def scroll(self, **_kwargs):
        return {"_scroll_id": "scroll-1", "hits": {"hits": []}}

    def clear_scroll(self, **_kwargs):
        return None

    def count(self, **_kwargs):
        return {"count": 7}


def test_collect_all_documents_uses_plain_contracts() -> None:
    collector = ElasticSearchCollector(
        index_name="legal",
        connection_config=ElasticsearchConnectionConfig(
            host_url="http://example.test"
        ),
        client=FakeClient(),
    )
    documents = collector.collect_all_documents()
    assert documents[0].doc_id == "doc-1"
    assert documents[0].chamber == "civil"
    assert documents[0].es_score == 1.5
