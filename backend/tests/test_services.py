"""
Unit tests for services — no live DB, no real API calls.

RAGService.chunk_document   — pure sync logic, no I/O
MLService.predict           — joblib.load patched with mock_ml_model fixture
send_webhook                — httpx.AsyncClient patched; asyncio.sleep patched for speed
"""
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.ml_service import MLService
from app.services.rag_service import RAGService
from app.services.webhook_service import send_webhook


# ── Shared helpers ────────────────────────────────────────────────────────────

@pytest.fixture
def rag(mock_embedding_service):
    """RAGService backed by mock_embedding_service (no real API calls)."""
    yield RAGService(
        db=MagicMock(),
        embedding_service=mock_embedding_service,
    )


def _ok_response() -> MagicMock:
    """httpx Response mock that raise_for_status() silently."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    return resp


def _http_error_response(status_code: int) -> MagicMock:
    """httpx Response mock that raise_for_status() raises HTTPStatusError."""
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"{status_code} Error",
        request=MagicMock(),
        response=MagicMock(status_code=status_code),
    )
    return resp


@contextmanager
def _http_client_mock(*post_responses):
    """
    Patch httpx.AsyncClient so that successive client.post() calls return
    or raise the given responses in order.

    Usage:
        with _http_client_mock(ok, ConnectError(...), ok) as mock_client:
            await send_webhook(...)
            mock_client.post.assert_called()
    """
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=list(post_responses))

    with patch("httpx.AsyncClient") as MockClass:
        MockClass.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClass.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock_client


# ═══════════════════════════════════════════════════════════════════════════════
# RAGService.chunk_document
# ═══════════════════════════════════════════════════════════════════════════════

class TestChunkDocument:

    def test_short_text_returns_single_chunk(self, rag):
        chunks = rag.chunk_document("hello world", size=100, overlap=10)
        assert chunks == ["hello world"]

    def test_empty_text_returns_empty_list(self, rag):
        assert rag.chunk_document("", size=512, overlap=64) == []

    def test_whitespace_only_returns_empty_list(self, rag):
        assert rag.chunk_document("   \n\t  ", size=512, overlap=64) == []

    def test_chunk_count_matches_expected(self, rag):
        # char-level: 100 chars, size=30, overlap=5 → stride=25
        # starts: 0, 25, 50, 75 → 4 chunks
        text = "A" * 100
        chunks = rag.chunk_document(text, size=30, overlap=5)
        assert len(chunks) == 4

    def test_overlap_chars_shared_between_consecutive_chunks(self, rag):
        # char-level: last `overlap` chars of chunk[0] == first `overlap` chars of chunk[1]
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # 26 chars
        overlap = 4
        chunks = rag.chunk_document(text, size=10, overlap=overlap)
        assert len(chunks) >= 2
        assert chunks[0][-overlap:] == chunks[1][:overlap]

    def test_text_exactly_chunk_size_produces_one_chunk(self, rag):
        # char-level: text length == size → exactly one chunk, no stride needed
        text = "A" * 20
        chunks = rag.chunk_document(text, size=20, overlap=5)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_each_chunk_is_non_empty_string(self, rag):
        text = " ".join(f"word{i}" for i in range(60))
        chunks = rag.chunk_document(text, size=15, overlap=3)
        assert all(isinstance(c, str) and c.strip() for c in chunks)


# ═══════════════════════════════════════════════════════════════════════════════
# MLService.predict
# ═══════════════════════════════════════════════════════════════════════════════

class TestMLServicePredict:

    def test_predict_returns_label(self, mock_ml_model):
        with patch("joblib.load", return_value=mock_ml_model):
            svc = MLService("/models/test.joblib")
        assert svc.predict({"climate": "tropical", "budget_tier": "mid"}) == "adventure"

    def test_predict_passes_single_row_dataframe(self, mock_ml_model):
        with patch("joblib.load", return_value=mock_ml_model):
            svc = MLService("/models/test.joblib")
        features = {"climate": "tropical", "budget_tier": "mid", "best_season": "summer"}
        svc.predict(features)
        call_df = mock_ml_model.predict.call_args[0][0]
        assert list(call_df.columns) == list(features.keys())
        assert len(call_df) == 1

    def test_predict_respects_label_from_model(self, mock_ml_model):
        mock_ml_model.predict.return_value = ["culture"]
        with patch("joblib.load", return_value=mock_ml_model):
            svc = MLService("/models/test.joblib")
        assert svc.predict({"climate": "temperate"}) == "culture"

    def test_predict_raises_runtime_error_when_model_not_loaded(self):
        svc = MLService("/nonexistent/path.joblib")
        with pytest.raises(RuntimeError, match="not loaded"):
            svc.predict({"climate": "tropical"})

    def test_is_ready_false_when_model_file_missing(self):
        svc = MLService("/nonexistent/path.joblib")
        assert svc.is_ready is False

    def test_is_ready_true_after_successful_load(self, mock_ml_model):
        with patch("joblib.load", return_value=mock_ml_model):
            svc = MLService("/models/test.joblib")
        assert svc.is_ready is True


# ═══════════════════════════════════════════════════════════════════════════════
# send_webhook — retry logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestSendWebhook:

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        with _http_client_mock(_ok_response()) as mock_client:
            result = await send_webhook("http://example.com/hook", {"event": "test"})

        assert result is True
        mock_client.post.assert_called_once_with(
            "http://example.com/hook", json={"event": "test"}
        )

    @pytest.mark.asyncio
    async def test_retries_on_connect_error_then_succeeds(self):
        with (
            _http_client_mock(
                httpx.ConnectError("refused"),
                httpx.ConnectError("refused"),
                _ok_response(),
            ) as mock_client,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_webhook(
                "http://example.com/hook", {"x": 1}, max_retries=3
            )

        assert result is True
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_false_after_all_retries_exhausted(self):
        with (
            _http_client_mock(
                httpx.ConnectError("refused"),
                httpx.ConnectError("refused"),
                httpx.ConnectError("refused"),
            ) as mock_client,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_webhook(
                "http://example.com/hook", {"x": 1}, max_retries=3
            )

        assert result is False
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_http_status_error_triggers_retry_and_recovers(self):
        with (
            _http_client_mock(
                _http_error_response(500),
                _ok_response(),
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_webhook(
                "http://example.com/hook", {}, max_retries=2
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_all_http_errors_exhaust_retries(self):
        with (
            _http_client_mock(
                _http_error_response(503),
                _http_error_response(503),
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_webhook(
                "http://example.com/hook", {}, max_retries=2
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_never_raises_on_unexpected_error(self):
        """send_webhook must always return bool, never propagate exceptions."""
        with (
            _http_client_mock(RuntimeError("totally unexpected")),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await send_webhook(
                "http://example.com/hook", {}, max_retries=1
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_payload_forwarded_to_post(self):
        payload = {"destination": "Kyoto", "nights": 5}
        with _http_client_mock(_ok_response()) as mock_client:
            await send_webhook("http://example.com/hook", payload)

        _, kwargs = mock_client.post.call_args
        assert kwargs["json"] == payload
