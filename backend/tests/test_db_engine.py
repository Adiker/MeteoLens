from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.core.config import Settings
from app.db.engine import get_engine, init_db
from tests.settings_helpers import apply_test_settings


def test_sqlite_connections_are_thread_affine_and_share_the_database(
    monkeypatch, tmp_path
) -> None:
    apply_test_settings(
        monkeypatch,
        Settings(
            database_url=f"sqlite:///{tmp_path / 'threaded.sqlite3'}",
            cache_dir=tmp_path / "cache",
            sync_on_startup=False,
            refresh_enabled=False,
        ),
    )
    init_db()
    main_connection = get_engine()
    main_connection.execute(
        """
        INSERT INTO warning_identity_generations (identity_hash, last_generation)
        VALUES ('shared', 3)
        """
    )
    main_connection.commit()

    barrier = Barrier(3)

    def read_generation() -> tuple[int, int]:
        connection = get_engine()
        barrier.wait()
        row = connection.execute(
            """
            SELECT last_generation
            FROM warning_identity_generations
            WHERE identity_hash = 'shared'
            """
        ).fetchone()
        return id(connection), int(row["last_generation"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(read_generation) for _ in range(2)]
        barrier.wait()
        results = [future.result() for future in futures]

    connection_ids = {connection_id for connection_id, _ in results}
    assert len(connection_ids) == 2
    assert id(main_connection) not in connection_ids
    assert [generation for _, generation in results] == [3, 3]


def test_in_memory_database_is_shared_between_worker_connections(
    monkeypatch, tmp_path
) -> None:
    apply_test_settings(
        monkeypatch,
        Settings(
            database_url="sqlite:///:memory:",
            cache_dir=tmp_path / "cache",
            sync_on_startup=False,
            refresh_enabled=False,
        ),
    )
    init_db()
    main_connection = get_engine()
    main_connection.execute(
        """
        INSERT INTO warning_identity_generations (identity_hash, last_generation)
        VALUES ('memory-shared', 4)
        """
    )
    main_connection.commit()

    def read_generation() -> tuple[int, int]:
        connection = get_engine()
        row = connection.execute(
            """
            SELECT last_generation
            FROM warning_identity_generations
            WHERE identity_hash = 'memory-shared'
            """
        ).fetchone()
        return id(connection), int(row["last_generation"])

    with ThreadPoolExecutor(max_workers=1) as executor:
        connection_id, generation = executor.submit(read_generation).result()

    assert connection_id != id(main_connection)
    assert generation == 4
