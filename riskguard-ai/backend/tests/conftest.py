import os
import tempfile

# MUST be set before any `app.*` import: point the app at an isolated throwaway
# database so the test suite can never clobber the demo/seed database.
_tmpdir = tempfile.mkdtemp(prefix="riskguard_tests_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmpdir, "test_riskguard.db")