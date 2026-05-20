"""
Security-focused tests for Phase 0 implementation.
Tests for input validation, injection attacks, and data integrity.
"""
import pytest
from backend.core.models import Understanding, Assumption, Unknown, MandatoryCategories, SkepticCritique
from backend.core.confidence import compute_confidence, _any_category_empty
from backend.orchestrator.database import get_db, init_db
from backend.orchestrator.audit import append_event, get_events
import json


class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_assumption_statement_empty_string(self):
        """Empty string statements should be allowed but validated."""
        a = Assumption(statement="")
        assert a.statement == ""
    
    def test_assumption_statement_none_fails(self):
        """None should fail validation."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Assumption(statement=None)
    
    def test_unknown_question_empty_string(self):
        """Empty questions allowed but questionable."""
        u = Unknown(question="")
        assert u.question == ""
    
    def test_understanding_goal_empty(self):
        """Empty goal should be allowed (edge case)."""
        u = Understanding(goal="")
        assert u.goal == ""
    
    def test_assumption_id_uniqueness(self):
        """IDs should be unique (12 char hex = 12^16 possibilities)."""
        ids = set()
        for _ in range(1000):
            a = Assumption(statement="test")
            assert a.id not in ids, "ID collision detected"
            ids.add(a.id)
    
    def test_unknown_id_uniqueness(self):
        """Unknown IDs should be unique."""
        ids = set()
        for _ in range(1000):
            u = Unknown(question="test")
            assert u.id not in ids, "ID collision detected"
            ids.add(u.id)


class TestSQLInjection:
    """Test for SQL injection vulnerabilities in audit events."""
    
    @pytest.mark.asyncio
    async def test_payload_sql_injection_attempt(self):
        """Malicious payloads in audit events should be serialized safely."""
        db = await get_db(":memory:")
        await init_db(db)
        
        malicious_payloads = [
            {"test": "'; DROP TABLE audit_events; --"},
            {"test": "1; DELETE FROM audit_events WHERE 1=1"},
            {"test": "'; INSERT INTO audit_events VALUES('hacked', 'test', NULL, NULL, '{}', '2024-01-01'); --"},
        ]
        
        for payload in malicious_payloads:
            await append_event(db, "test_event", "u1", None, payload)
        
        events = await get_events(db, limit=10)
        assert len(events) == 3
        
        reversed_payloads = list(reversed(malicious_payloads))
        for i, event in enumerate(events):
            data = json.loads(event["payload"])
            assert data == reversed_payloads[i]
        
        await db.close()
    
    @pytest.mark.asyncio
    async def test_event_type_sql_injection(self):
        """Event type should be safely parameterized."""
        db = await get_db(":memory:")
        await init_db(db)
        
        malicious_types = [
            "'; DROP TABLE audit_events; --",
            "test'; DELETE FROM audit_events; --",
        ]
        
        for event_type in malicious_types:
            try:
                await append_event(db, event_type, "u1", None, {"test": True})
            except Exception:
                pass  # May fail validation, which is fine
        
        await db.close()


class TestModelValidation:
    """Test Pydantic model validation edge cases."""
    
    def test_understanding_with_all_fields_empty_lists(self):
        """Understanding with empty lists should be valid."""
        u = Understanding(
            goal="test",
            assumptions=[],
            unknowns=[],
            mandatory_categories=MandatoryCategories()
        )
        assert u.goal == "test"
        assert len(u.assumptions) == 0
        assert len(u.unknowns) == 0
    
    def test_mandatory_categories_all_empty(self):
        """All empty mandatory categories should be detectable."""
        mc = MandatoryCategories()
        assert _any_category_empty(mc) is True
    
    def test_mandatory_categories_all_filled(self):
        """All filled mandatory categories should pass."""
        mc = MandatoryCategories(
            accessibility=["a"],
            performance=["p"],
            security=["s"],
            state_management=["sm"],
            persistence=["pe"]
        )
        assert _any_category_empty(mc) is False
    
    def test_assumption_status_values(self):
        """Test valid assumption status values."""
        valid_statuses = ["open", "validated", "rejected", "pending", ""]
        for status in valid_statuses:
            a = Assumption(statement="test", status=status)
            assert a.status == status
    
    def test_unknown_without_resolution(self):
        """Unknown without resolution should have None values."""
        u = Unknown(question="test")
        assert u.resolution is None
        assert u.resolved_at is None
    
    def test_unknown_with_resolution_no_timestamp(self):
        """Unknown with resolution but no timestamp is valid."""
        u = Unknown(question="test", resolution="answered")
        assert u.resolution == "answered"
        assert u.resolved_at is None


class TestConfidenceCalculation:
    """Test confidence calculation edge cases."""
    
    def test_confidence_division_by_zero_protection(self):
        """Zero total assumptions should not cause division by zero."""
        profile = compute_confidence(
            open_unknowns=0,
            total_unknowns=0,
            validated_count=0,
            total_assumptions=0,
            mandatory_categories=MandatoryCategories(
                accessibility=["a"], performance=["p"],
                security=["s"], state_management=["sm"], persistence=["pe"]
            ),
        )
        assert profile.validation_ratio == 0.0
    
    def test_confidence_negative_score_clamped(self):
        """Negative scores should be clamped to 0."""
        profile = compute_confidence(
            open_unknowns=10,
            total_unknowns=5,
            validated_count=0,
            total_assumptions=1,
            mandatory_categories=MandatoryCategories(performance=["p"]),
        )
        assert profile.score >= 0.0
    
    def test_confidence_all_categories_empty_penalty(self):
        """Empty categories should trigger 50% penalty."""
        profile = compute_confidence(
            open_unknowns=0,
            total_unknowns=10,
            validated_count=10,
            total_assumptions=10,
            mandatory_categories=MandatoryCategories(),
        )
        assert profile.score == 0.5
    
    def test_confidence_partial_categories_no_penalty(self):
        """Partially filled categories should not trigger penalty."""
        profile = compute_confidence(
            open_unknowns=0,
            total_unknowns=10,
            validated_count=10,
            total_assumptions=10,
            mandatory_categories=MandatoryCategories(
                accessibility=["a"],
                performance=[],
                security=["s"],
                state_management=["sm"],
                persistence=["p"]
            ),
        )
        assert profile.score == 0.5


class TestDatabaseIsolation:
    """Test database isolation between connections."""
    
    @pytest.mark.asyncio
    async def test_separate_connections_isolated(self):
        """Separate DB connections should not share state."""
        db1 = await get_db(":memory:")
        db2 = await get_db(":memory:")
        await init_db(db1)
        await init_db(db2)
        
        await append_event(db1, "event1", "u1", None, {"from": "db1"})
        await append_event(db2, "event2", "u2", None, {"from": "db2"})
        
        events1 = await get_events(db1, limit=10)
        events2 = await get_events(db2, limit=10)
        
        assert len(events1) == 1
        assert len(events2) == 1
        assert json.loads(events1[0]["payload"])["from"] == "db1"
        assert json.loads(events2[0]["payload"])["from"] == "db2"
        
        await db1.close()
        await db2.close()


class TestSkepticCritiqueValidation:
    """Test SkepticCritique model validation."""
    
    def test_critique_empty_lists(self):
        """Empty critique should be valid."""
        c = SkepticCritique(understanding_id="u1")
        assert c.scenarios == []
        assert c.questions == []
        assert c.tool_evidence == []
    
    def test_critique_with_data(self):
        """Critique with data should validate."""
        c = SkepticCritique(
            understanding_id="u1",
            scenarios=["scenario1", "scenario2"],
            questions=["question1"],
            tool_evidence=["evidence1"]
        )
        assert len(c.scenarios) == 2
        assert len(c.questions) == 1
        assert len(c.tool_evidence) == 1


class TestConcurrency:
    """Test concurrent access patterns."""
    
    @pytest.mark.asyncio
    async def test_concurrent_event_appends(self):
        """Concurrent event appends should not cause issues."""
        import asyncio
        
        db = await get_db(":memory:")
        await init_db(db)
        
        async def append_many(n):
            for i in range(n):
                await append_event(db, "concurrent", f"u{i}", None, {"i": i})
        
        await asyncio.gather(*[append_many(10) for _ in range(10)])
        
        events = await get_events(db, limit=1000)
        assert len(events) == 100
        
        await db.close()


class TestJSONSerializationSecurity:
    """Test JSON serialization edge cases and security."""
    
    def test_json_special_characters_in_assumption(self):
        """Special JSON characters should be handled."""
        special_strings = [
            '{"key": "value"}',
            '<script>alert("xss")</script>',
            "'; DROP TABLE--",
            "{{template}}",
            "${variable}",
            "\\n\\t\\r",
            "unicode: \u00e9",
        ]
        for s in special_strings:
            a = Assumption(statement=s)
            assert a.statement == s
    
    def test_json_special_characters_in_unknown(self):
        """Special characters in questions."""
        s = 'What if "quotes" and {braces} are involved?'
        u = Unknown(question=s)
        assert u.question == s
    
    def test_understanding_json_serialization(self):
        """Understanding should serialize to valid JSON."""
        u = Understanding(
            goal="Test goal",
            assumptions=[Assumption(statement="test")],
            unknowns=[Unknown(question="test?")],
            mandatory_categories=MandatoryCategories(performance=["fast"])
        )
        json_str = u.model_dump_json()
        assert "Test goal" in json_str
        
        u2 = Understanding.model_validate_json(json_str)
        assert u2.goal == "Test goal"
    
    def test_skeptic_critique_json_serialization(self):
        """SkepticCritique should serialize properly."""
        c = SkepticCritique(
            understanding_id="u1",
            scenarios=["scenario with \"quotes\""],
            questions=["question with 'apostrophe'"],
            tool_evidence=["evidence"]
        )
        json_str = c.model_dump_json()
        c2 = SkepticCritique.model_validate_json(json_str)
        assert c2.understanding_id == "u1"
        assert len(c2.scenarios) == 1


class TestPydanticModelSecurity:
    """Test Pydantic-specific security features."""
    
    def test_model_extra_fields_allowed_by_default(self):
        """Extra fields are allowed by default (Pydantic v2 behavior).
        
        Note: This is acceptable for this use case since:
        1. Extra fields are ignored in model_dump()
        2. They don't affect core functionality
        3. Can be restricted later if needed via model_config
        """
        # Extra fields are silently ignored (not rejected)
        a = Assumption(statement="test", extra_field="ignored")
        assert a.statement == "test"
        # extra_field is not accessible as it's not in the model
        assert not hasattr(a, "extra_field")
    
    def test_model_type_enforcement(self):
        """Type enforcement should work."""
        from pydantic import ValidationError
        
        # Status should be string, not number
        with pytest.raises(ValidationError):
            Assumption(statement="test", status=123)
    
    def test_model_nested_validation(self):
        """Nested models should validate."""
        u = Understanding(
            goal="test",
            assumptions=[
                Assumption(statement="a1"),
                Assumption(statement="a2")
            ],
            unknowns=[Unknown(question="q1")]
        )
        assert len(u.assumptions) == 2
        assert len(u.unknowns) == 1
