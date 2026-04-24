"""Import-sanity tests: every public module must load cleanly."""


def test_import_package():
    import holographic_reservoir as hr
    assert hr.__version__ == "1.0.0"


def test_import_backends():
    from holographic_reservoir import backends
    assert hasattr(backends, "SimulatedASICBackend")
    assert hasattr(backends, "AxeOSBackend")


def test_import_model():
    from holographic_reservoir import model
    assert hasattr(model, "HolographicReservoirModel")
    assert hasattr(model, "mackey_glass")


def test_import_cli():
    from holographic_reservoir import cli
    assert callable(cli.main)


def test_import_topology_alias():
    from holographic_reservoir.core.topology import VeselovLayer, VeselovExpander
    assert issubclass(VeselovExpander, VeselovLayer)


def test_public_api():
    import holographic_reservoir as hr
    for name in [
        "HardwareBackend", "SimulatedASICBackend", "AxeOSBackend",
        "get_backend", "HolographicReservoirModel", "mackey_glass",
    ]:
        assert hasattr(hr, name), name
