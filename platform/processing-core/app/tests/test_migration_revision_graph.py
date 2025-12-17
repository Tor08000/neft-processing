from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_revision_graph_builds() -> None:
    config_path = Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(config_path.parent / "alembic"))
    script = ScriptDirectory.from_config(cfg)

    heads = list(script.get_revisions("heads"))

    assert heads, "Alembic should expose at least one head revision"
