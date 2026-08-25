import pytest

from lemmamind.objects import ContentAddressedFileStore, ObjectCorruption


def test_content_addressed_store_round_trip_is_idempotent(tmp_path) -> None:
    store = ContentAddressedFileStore(tmp_path / "objects")

    digest = store.put(b"captured bytes\n")

    assert digest.startswith("sha256:")
    assert store.exists(digest)
    assert store.get(digest) == b"captured bytes\n"
    assert store.put(b"captured bytes\n") == digest


def test_content_addressed_store_detects_corruption(tmp_path) -> None:
    store = ContentAddressedFileStore(tmp_path / "objects")
    digest = store.put(b"correct")
    path = store._path(digest)
    path.write_bytes(b"corrupt")

    with pytest.raises(ObjectCorruption):
        store.get(digest)
