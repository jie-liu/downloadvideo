import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import PORT, DEFAULT_OUTPUT_DIR

def test_port_is_integer():
    assert isinstance(PORT, int)
    assert PORT == 8765

def test_default_output_dir_expands_home():
    assert DEFAULT_OUTPUT_DIR.startswith("/")
    assert "Downloads" in DEFAULT_OUTPUT_DIR
