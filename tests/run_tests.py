"""pytest が無くても動くテストの走らせ方 (標準ライブラリだけ)。python -X utf8 tests/run_tests.py"""
import importlib.util
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def main():
    passed, failed = 0, []
    for fn in sorted(os.listdir(HERE)):
        if not (fn.startswith("test_") and fn.endswith(".py")):
            continue
        spec = importlib.util.spec_from_file_location(fn[:-3], os.path.join(HERE, fn))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in sorted(dir(mod)):
            if name.startswith("test_") and callable(getattr(mod, name)):
                try:
                    getattr(mod, name)()
                    passed += 1
                except Exception:  # noqa: BLE001
                    failed.append((f"{fn}::{name}", traceback.format_exc(limit=3)))
    for n, tb in failed:
        print("FAILED", n, "\n", tb)
    print(f"{passed} passed, {len(failed)} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
