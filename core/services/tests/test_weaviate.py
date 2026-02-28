"""
Unit tests for the Weaviate service (no live Weaviate required).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
import unittest

from core.services.base import ServiceDisabled, ServiceNotConfigured
from core.services.weaviate.schema import (
    SCHEMA_VERSION,
    ensure_schema,
    reset_schema_cache,
)
from core.services.weaviate.service import NAMESPACE_UUID, WeaviateService, _make_uuid


# ---------------------------------------------------------------------------
# Deterministic UUID tests
# ---------------------------------------------------------------------------

class TestDeterministicUUID(unittest.TestCase):
    def test_same_source_key_produces_same_uuid(self):
        u1 = _make_uuid("page", 42)
        u2 = _make_uuid("page", 42)
        self.assertEqual(u1, u2)

    def test_source_id_as_int_and_str_produce_same_uuid(self):
        u1 = _make_uuid("page", 42)
        u2 = _make_uuid("page", "42")
        self.assertEqual(u1, u2)

    def test_different_source_type_produces_different_uuid(self):
        u1 = _make_uuid("page", 1)
        u2 = _make_uuid("snippet", 1)
        self.assertNotEqual(u1, u2)

    def test_different_source_id_produces_different_uuid(self):
        u1 = _make_uuid("page", 1)
        u2 = _make_uuid("page", 2)
        self.assertNotEqual(u1, u2)

    def test_uuid_is_uuid5_of_namespace(self):
        expected = uuid.uuid5(NAMESPACE_UUID, "page:99")
        self.assertEqual(_make_uuid("page", 99), expected)


# ---------------------------------------------------------------------------
# ensure_schema caching tests
# ---------------------------------------------------------------------------

class TestEnsureSchemaCaching(unittest.TestCase):
    def setUp(self):
        reset_schema_cache()

    def tearDown(self):
        reset_schema_cache()

    def _make_client(self, collection_exists: bool):
        client = MagicMock()
        client.collections.exists.return_value = collection_exists
        client.collections.create.return_value = MagicMock()
        return client

    def test_creates_collection_when_not_exists(self):
        client = self._make_client(collection_exists=False)
        ensure_schema(client)
        client.collections.create.assert_called_once()

    def test_does_not_create_when_collection_exists(self):
        client = self._make_client(collection_exists=True)
        ensure_schema(client)
        client.collections.create.assert_not_called()

    def test_schema_check_runs_only_once_per_process(self):
        client = self._make_client(collection_exists=True)
        ensure_schema(client)
        ensure_schema(client)
        ensure_schema(client)
        # exists() should be called exactly once despite multiple ensure_schema() calls
        client.collections.exists.assert_called_once()

    def test_schema_check_reruns_after_cache_reset(self):
        client = self._make_client(collection_exists=True)
        ensure_schema(client)
        reset_schema_cache()
        ensure_schema(client)
        self.assertEqual(client.collections.exists.call_count, 2)


# ---------------------------------------------------------------------------
# WeaviateService tests
# ---------------------------------------------------------------------------

class TestWeaviateServiceUpsert(unittest.TestCase):
    def setUp(self):
        reset_schema_cache()

    def tearDown(self):
        reset_schema_cache()

    def _make_service_with_mock_client(self):
        mock_client = MagicMock()
        mock_client.collections.exists.return_value = True
        mock_collection = MagicMock()
        mock_client.collections.get.return_value = mock_collection
        svc = WeaviateService(client=mock_client)
        return svc, mock_client, mock_collection

    def test_upsert_returns_uuid_string(self):
        svc, _, mock_collection = self._make_service_with_mock_client()
        result = svc.upsert_document(
            source_type="page",
            source_id=1,
            title="Test",
            text="Hello world",
        )
        expected = str(_make_uuid("page", 1))
        self.assertEqual(result, expected)

    def test_upsert_calls_insert_on_first_attempt(self):
        svc, _, mock_collection = self._make_service_with_mock_client()
        mock_collection.data.insert.return_value = None  # success
        svc.upsert_document(source_type="page", source_id=2, title="T", text="body")
        mock_collection.data.insert.assert_called_once()

    def test_upsert_falls_back_to_replace_on_exception(self):
        from weaviate.exceptions import ObjectAlreadyExistsError
        svc, _, mock_collection = self._make_service_with_mock_client()
        mock_collection.data.insert.side_effect = ObjectAlreadyExistsError("42")
        mock_collection.data.replace.return_value = None
        svc.upsert_document(source_type="page", source_id=3, title="T", text="body")
        mock_collection.data.replace.assert_called_once()

    def test_upsert_is_idempotent_same_uuid(self):
        svc, _, _ = self._make_service_with_mock_client()
        id1 = svc.upsert_document(source_type="page", source_id=5, title="A", text="x")
        id2 = svc.upsert_document(source_type="page", source_id=5, title="B", text="y")
        self.assertEqual(id1, id2)


class TestWeaviateServiceDelete(unittest.TestCase):
    def setUp(self):
        reset_schema_cache()

    def tearDown(self):
        reset_schema_cache()

    def test_delete_calls_delete_by_id_with_correct_uuid(self):
        mock_client = MagicMock()
        mock_client.collections.exists.return_value = True
        mock_collection = MagicMock()
        mock_client.collections.get.return_value = mock_collection

        svc = WeaviateService(client=mock_client)
        svc.delete_document("page", 7)

        expected_uuid = _make_uuid("page", 7)
        mock_collection.data.delete_by_id.assert_called_once_with(expected_uuid)


class TestWeaviateServiceQuery(unittest.TestCase):
    def setUp(self):
        reset_schema_cache()

    def tearDown(self):
        reset_schema_cache()

    def _make_bm25_result(self, source_type, source_id, title, text, url, score):
        obj = MagicMock()
        obj.properties = {
            "source_type": source_type,
            "source_id": source_id,
            "title": title,
            "text": text,
            "url": url,
        }
        obj.metadata = MagicMock()
        obj.metadata.score = score
        return obj

    def _make_service_with_results(self, objects):
        mock_client = MagicMock()
        mock_client.collections.exists.return_value = True
        mock_collection = MagicMock()
        mock_client.collections.get.return_value = mock_collection
        mock_response = MagicMock()
        mock_response.objects = objects
        mock_collection.query.bm25.return_value = mock_response
        return WeaviateService(client=mock_client), mock_collection

    def test_query_returns_list_of_dicts(self):
        obj = self._make_bm25_result("page", "1", "Title", "Body text", "http://x", 0.9)
        svc, _ = self._make_service_with_results([obj])
        results = svc.query("test query")
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_type"], "page")
        self.assertEqual(results[0]["source_id"], "1")
        self.assertEqual(results[0]["title"], "Title")
        self.assertEqual(results[0]["score"], 0.9)
        self.assertEqual(results[0]["url"], "http://x")

    def test_query_text_preview_max_1000_chars(self):
        long_text = "x" * 2000
        obj = self._make_bm25_result("page", "2", "T", long_text, "", 0.5)
        svc, _ = self._make_service_with_results([obj])
        results = svc.query("text")
        self.assertEqual(len(results[0]["text_preview"]), 1000)

    def test_query_filters_ignored_without_exception(self):
        svc, mock_collection = self._make_service_with_results([])
        # Must not raise
        results = svc.query("q", filters={"source_type": "page"})
        self.assertIsInstance(results, list)

    def test_query_uses_bm25(self):
        svc, mock_collection = self._make_service_with_results([])
        svc.query("my query", top_k=5)
        mock_collection.query.bm25.assert_called_once()
        call_kwargs = mock_collection.query.bm25.call_args
        self.assertEqual(call_kwargs.kwargs.get("query") or call_kwargs.args[0], "my query")


# ---------------------------------------------------------------------------
# Client config tests
# ---------------------------------------------------------------------------

class TestClientConfig(unittest.TestCase):
    def test_service_disabled_when_env_false(self):
        with patch.dict("os.environ", {"WEAVIATE_ENABLED": "false"}):
            from core.services.weaviate.client import get_client
            with self.assertRaises(ServiceDisabled):
                get_client()

    def test_service_not_configured_when_url_missing(self):
        env = {
            "WEAVIATE_ENABLED": "true",
            "WEAVIATE_URL": "",
            "WEAVIATE_HTTP_PORT": "8080",
            "WEAVIATE_GRPC_PORT": "50051",
        }
        with patch.dict("os.environ", env, clear=False):
            # Remove WEAVIATE_URL entirely from env
            import os
            saved = os.environ.pop("WEAVIATE_URL", None)
            try:
                from core.services.weaviate.client import get_client
                with self.assertRaises(ServiceNotConfigured):
                    get_client()
            finally:
                if saved is not None:
                    os.environ["WEAVIATE_URL"] = saved

    def test_service_not_configured_when_ports_missing(self):
        import os
        # Remove port vars
        for key in ["WEAVIATE_HTTP_PORT", "WEAVIATE_GRPC_PORT"]:
            os.environ.pop(key, None)
        with patch.dict("os.environ", {"WEAVIATE_ENABLED": "true", "WEAVIATE_URL": "localhost"}):
            from core.services.weaviate.client import get_client
            with self.assertRaises(ServiceNotConfigured):
                get_client()
