import unittest
from pathlib import Path


class PistonRuntimeScriptsTest(unittest.TestCase):
    def test_shell_entrypoints_use_unix_line_endings(self):
        repository_root = Path(__file__).resolve().parents[1]
        scripts = (
            repository_root / "tools/piston-runtimes/python/run",
            repository_root / "tools/piston-runtimes/gcc/run",
            repository_root / "tools/piston-runtimes/gcc/compile",
        )
        for script in scripts:
            with self.subTest(script=script):
                content = script.read_bytes()
                self.assertTrue(content.startswith(b"#!/bin/bash\n"))
                self.assertNotIn(b"\r", content)
