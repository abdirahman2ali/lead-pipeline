import pytest

from src.ingestor import Lead, normalize


def test_normalize_minimal_valid():
    lead = normalize({"email": "Test@Example.COM", "name": "Test User", "source": "ad"})
    assert lead.email == "test@example.com"
    assert lead.name == "Test User"
    assert lead.source == "ad"


def test_normalize_phone_10digit():
    lead = normalize({"email": "a@b.com", "name": "A", "source": "x", "phone": "416-555-0101"})
    assert lead.phone == "+14165550101"


def test_normalize_phone_11digit():
    lead = normalize({"email": "a@b.com", "name": "A", "source": "x", "phone": "14165550101"})
    assert lead.phone == "+14165550101"


def test_normalize_no_phone():
    lead = normalize({"email": "a@b.com", "name": "A", "source": "x"})
    assert lead.phone is None


def test_normalize_missing_email():
    with pytest.raises(ValueError, match="email"):
        normalize({"name": "A", "source": "x"})


def test_normalize_invalid_email():
    with pytest.raises(ValueError, match="Invalid email"):
        normalize({"email": "not-an-email", "name": "A", "source": "x"})


def test_normalize_missing_name():
    with pytest.raises(ValueError, match="name"):
        normalize({"email": "a@b.com", "source": "x"})


def test_normalize_missing_source():
    with pytest.raises(ValueError, match="source"):
        normalize({"email": "a@b.com", "name": "A"})


def test_normalize_returns_lead():
    result = normalize({"email": "a@b.com", "name": "A", "source": "fb", "company": "ACME"})
    assert isinstance(result, Lead)
    assert result.company == "ACME"
