import unittest

from app.runtime_errors import (
    ERROR_JUDGE_TIMEOUT,
    ERROR_MODEL_OVERLOAD,
    ERROR_RAG_UNAVAILABLE,
    JudgeRuntimeError,
    classify_openai_failure,
    classify_rag_failure,
    extract_runtime_error_code,
    normalize_runtime_error_code,
)


class RuntimeErrorsTests(unittest.TestCase):
    def test_normalize_runtime_error_code_should_fallback_to_model_overload(self) -> None:
        self.assertEqual(normalize_runtime_error_code(""), ERROR_MODEL_OVERLOAD)
        self.assertEqual(normalize_runtime_error_code("unknown"), ERROR_MODEL_OVERLOAD)
        self.assertEqual(normalize_runtime_error_code(ERROR_RAG_UNAVAILABLE), ERROR_RAG_UNAVAILABLE)

    def test_classify_openai_failure_should_map_timeout_and_overload(self) -> None:
        self.assertEqual(classify_openai_failure("timeout while waiting"), ERROR_JUDGE_TIMEOUT)
        self.assertEqual(classify_openai_failure("openai status=504"), ERROR_JUDGE_TIMEOUT)
        self.assertEqual(classify_openai_failure("openai status=429"), ERROR_MODEL_OVERLOAD)
        self.assertEqual(classify_openai_failure("openai status=503"), ERROR_MODEL_OVERLOAD)

    def test_classify_rag_failure_should_map_timeout_and_unavailable(self) -> None:
        self.assertEqual(classify_rag_failure("milvus timeout"), ERROR_JUDGE_TIMEOUT)
        self.assertEqual(classify_rag_failure("redis connection refused"), ERROR_RAG_UNAVAILABLE)

    def test_extract_runtime_error_code_should_read_custom_error(self) -> None:
        err = JudgeRuntimeError(code=ERROR_RAG_UNAVAILABLE, message="rag fallback")
        self.assertEqual(extract_runtime_error_code(err), ERROR_RAG_UNAVAILABLE)
        self.assertEqual(
            extract_runtime_error_code(RuntimeError("openai status=429")),
            ERROR_MODEL_OVERLOAD,
        )


if __name__ == "__main__":
    unittest.main()
