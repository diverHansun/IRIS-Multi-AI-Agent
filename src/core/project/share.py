from pathlib import Path


class IrisShareDir:
    """Manage the shared ~/.iris directory."""

    _SHARE_DIR_NAME = ".iris"

    @classmethod
    def get_share_dir(cls) -> Path:
        """
        Return the shared directory, creating it if missing.
        """
        share_dir = Path.home() / cls._SHARE_DIR_NAME
        share_dir.mkdir(parents=True, exist_ok=True)
        return share_dir

    @classmethod
    def get_metadata_file(cls) -> Path:
        """Return path to metadata.json in the shared directory."""
        return cls.get_share_dir() / "metadata.json"

    @classmethod
    def get_global_config_file(cls) -> Path:
        """Return path to global config.json."""
        return cls.get_share_dir() / "config.json"

    @classmethod
    def get_global_agent_md_file(cls) -> Path:
        """Return path to global agent instruction file."""
        return cls.get_share_dir() / "agent.md"
