import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from tests.conftest import REAL_DATA, ROOT  # noqa: E402


@pytest.mark.skipif(not REAL_DATA.exists(), reason="sample dataset not present")
def test_app_renders_sample_without_exceptions():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.tabs) >= 6
