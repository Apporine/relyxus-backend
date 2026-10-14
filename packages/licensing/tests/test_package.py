import importlib


def test_package_imports_without_side_effects() -> None:
    module = importlib.import_module("apporine_licensing")

    assert module.__doc__ is not None
