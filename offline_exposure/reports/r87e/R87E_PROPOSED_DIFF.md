# R.87E proposed workflow diff

Prepared locally after clean Ubuntu/Python 3.12 validation. Not staged, committed, pushed, or run in GitHub. Existing test job remains unchanged.

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 56f72ba..94a579f 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -21,3 +21,18 @@ jobs:
           EXECUTION_MODE: paper
           TRADING_MODE: practice
           PAPER_TRADING: "true"
+
+  offline-exposure-contract:
+    runs-on: ubuntu-latest
+    timeout-minutes: 5
+    permissions:
+      contents: read
+    steps:
+      - uses: actions/checkout@v4
+        with:
+          persist-credentials: false
+      - uses: actions/setup-python@v5
+        with:
+          python-version: "3.12"
+      - name: Run isolated offline exposure contract
+        run: python -I -S -B offline_exposure/run_checks.py
```
