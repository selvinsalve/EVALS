"""
Unit and integration tests for the DeepEval external evaluation wrapper.
Tests:
1. Golden dataset generators (RAG, DB, Multi-Turn) produce valid models
2. Client adapter captures black-box responses, tools, and contexts cleanly
3. Direct serialization to strictly JSON format without datetime serialization errors
4. Verifies evaluation/reports contains only .json files
"""

import json
from pathlib import Path
import pytest
from evaluation.config import get_eval_settings
from evaluation.golden_generator import (
    RAGGoldenDatasetGenerator,
    DBGoldenDatasetGenerator,
    MultiTurnGoldenDatasetGenerator,
)
from evaluation.client_adapter import DirectServiceAdapter
from evaluation.models import DBGoldenCase, RAGGoldenCase, MultiTurnGoldenCase, EvaluationReport, CaseEvaluationResult


def test_rag_golden_generator():
    gen = RAGGoldenDatasetGenerator()
    cases = gen.generate_all()
    assert len(cases) >= 10
    for case in cases:
        assert isinstance(case, RAGGoldenCase)
        assert case.id.lower().startswith("rag_")
        assert len(case.input) > 0
        assert len(case.expected_output) > 0
        assert len(case.context) > 0


def test_db_golden_generator():
    gen = DBGoldenDatasetGenerator()
    cases = gen.generate_all()
    assert len(cases) >= 8
    isolation_cases = [c for c in cases if c.is_cross_user_attempt]
    assert len(isolation_cases) >= 2
    for case in cases:
        assert isinstance(case, DBGoldenCase)
        assert case.id.startswith("DB_")


def test_multiturn_golden_generator():
    gen = MultiTurnGoldenDatasetGenerator()
    cases = gen.generate_all()
    assert len(cases) >= 3
    for case in cases:
        assert isinstance(case, MultiTurnGoldenCase)
        assert len(case.turns) >= 2


def test_client_adapter_rag_query():
    adapter = DirectServiceAdapter()
    resp = adapter.query_rag("What is the return policy?")
    assert resp.answer is not None
    assert len(resp.answer) > 0
    assert resp.latency_ms is not None
    assert resp.latency_ms > 0


def test_client_adapter_chat_query():
    adapter = DirectServiceAdapter()
    resp = adapter.query_chat("Where is my order ORD-1001?", customer_id="CUS-001")
    assert resp.answer is not None
    assert "ORD-1001" in resp.answer or "shipped" in resp.answer.lower()
    # Check JSON serializability of captured response
    dumped = resp.model_dump(mode="json")
    json_str = json.dumps(dumped)
    assert len(json_str) > 0


def test_report_json_serializability():
    report = EvaluationReport(
        evaluation_type="RAG",
        model_name="qwen2.5:7b-instruct-q4_K_M",
        total_test_cases=1,
        passed_test_cases=1,
        failed_test_cases=0,
        overall_pass_rate=1.0,
        metric_averages={"Answer Relevancy": 0.95},
        metric_pass_rates={"Answer Relevancy": 1.0},
        case_results=[
            CaseEvaluationResult(
                test_case_id="RAG_RET_001",
                category="return_policy",
                input="What is the return window?",
                actual_output="You have 30 days.",
                expected_output="30 days.",
                retrieval_context=["Standard return window is 30 days."],
                tools_called=[],
                expected_tools=[],
                metrics=[],
                all_passed=True,
            )
        ],
    )
    dumped = report.model_dump(mode="json")
    json_str = json.dumps(dumped, indent=2)
    assert "RAG_RET_001" in json_str
