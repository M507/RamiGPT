"""Persistent SSH sessions: one JSON file per host/session under data/sessions/hosts/."""

from __future__ import annotations

import json
import re
import threading
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ramigpt.paths import (
    SESSION_HOSTS_DIR,
    SESSION_META_PATH,
    SESSIONS_DIR,
    ensure_runtime_dirs,
)

DEFAULT_GROUPS = [
    {"id": "production", "name": "Production", "order": 0},
    {"id": "staging", "name": "Staging", "order": 1},
    {"id": "development", "name": "Development", "order": 2},
    {"id": "database", "name": "Database Servers", "order": 3},
]

LEGACY_INVENTORY = SESSIONS_DIR / "inventory.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(session_id: str) -> str:
    """Keep only safe characters so each session maps to one JSON file."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", session_id.strip())
    return cleaned or str(uuid.uuid4())


@dataclass
class SavedSession:
    id: str
    name: str
    host: str
    port: int = 22
    username: str = ""
    hostname: str = "pehost"
    group_id: str = "development"
    favorite: bool = False
    environment: str = "development"
    notes: str = ""
    remember_credentials: bool = True
    last_connected_at: Optional[str] = None
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    # Per-session AI guidance (core RamiGPT state)
    facts: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)
    avoids: List[str] = field(default_factory=list)
    # Stored only in the session's own JSON when remember_credentials is True
    password: str = ""

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "SavedSession":
        allowed = {f.name for f in fields(cls)}
        payload = {k: raw[k] for k in allowed if k in raw}
        for list_field in ("facts", "hints", "avoids"):
            if list_field not in payload or payload[list_field] is None:
                payload[list_field] = []
        return cls(**payload)

    def to_storage_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not self.remember_credentials:
            data["password"] = ""
        return data

    def to_public_dict(self, has_saved_password: bool = False) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "hostname": self.hostname,
            "group_id": self.group_id,
            "favorite": self.favorite,
            "environment": self.environment,
            "notes": self.notes,
            "remember_credentials": self.remember_credentials,
            "last_connected_at": self.last_connected_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "has_saved_password": has_saved_password or bool(self.password),
            "facts": list(self.facts or []),
            "hints": list(self.hints or []),
            "avoids": list(self.avoids or []),
        }


class SessionStore:
    """
    File-backed inventory.

    Layout:
      data/sessions/hosts/<session-id>.json   # one file per session/host
      data/sessions/meta.json                 # groups + recent_ids
    """

    def __init__(
        self,
        hosts_dir: Optional[Path] = None,
        meta_path: Optional[Path] = None,
    ) -> None:
        ensure_runtime_dirs()
        self._hosts_dir = hosts_dir or SESSION_HOSTS_DIR
        self._meta_path = meta_path or SESSION_META_PATH
        self._hosts_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._meta = self._load_meta()
        self._migrate_legacy_inventory()

    # ------------------------------------------------------------------ meta
    def _default_meta(self) -> Dict[str, Any]:
        return {
            "groups": deepcopy(DEFAULT_GROUPS),
            "recent_ids": [],
        }

    def _load_meta(self) -> Dict[str, Any]:
        if not self._meta_path.exists():
            meta = self._default_meta()
            self._write_json(self._meta_path, meta)
            return meta
        try:
            raw = json.loads(self._meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            return self._default_meta()
        meta = self._default_meta()
        if isinstance(raw.get("groups"), list) and raw["groups"]:
            meta["groups"] = raw["groups"]
        if isinstance(raw.get("recent_ids"), list):
            meta["recent_ids"] = raw["recent_ids"]
        return meta

    def _save_meta(self) -> None:
        self._write_json(self._meta_path, self._meta)

    @staticmethod
    def _write_json(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        tmp.replace(path)

    # -------------------------------------------------------------- sessions
    def _session_path(self, session_id: str) -> Path:
        return self._hosts_dir / f"{_safe_filename(session_id)}.json"

    def _read_session_file(self, path: Path) -> Optional[SavedSession]:
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(raw, dict) or not raw.get("id"):
            return None
        try:
            return SavedSession.from_dict(raw)
        except TypeError:
            return None

    def _write_session_file(self, sess: SavedSession) -> None:
        self._write_json(self._session_path(sess.id), sess.to_storage_dict())

    def _iter_sessions(self) -> List[SavedSession]:
        sessions: List[SavedSession] = []
        for path in sorted(self._hosts_dir.glob("*.json")):
            sess = self._read_session_file(path)
            if sess is not None:
                sessions.append(sess)
        return sessions

    def _migrate_legacy_inventory(self) -> None:
        """Split old inventory.json into per-session files (one-time)."""
        if not LEGACY_INVENTORY.exists():
            return
        try:
            raw = json.loads(LEGACY_INVENTORY.read_text())
        except (json.JSONDecodeError, OSError):
            return

        with self._lock:
            if isinstance(raw.get("groups"), list) and raw["groups"]:
                self._meta["groups"] = raw["groups"]
            if isinstance(raw.get("recent_ids"), list):
                self._meta["recent_ids"] = raw["recent_ids"]
            self._save_meta()

            credentials = raw.get("credentials") or {}
            for item in raw.get("sessions") or []:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                sess = SavedSession.from_dict(item)
                if not sess.password and sess.remember_credentials:
                    key = f"{sess.username}@{sess.host}:{int(sess.port)}"
                    entry = credentials.get(key) or {}
                    sess.password = entry.get("password") or ""
                # Do not overwrite a newer per-file session if it already exists
                path = self._session_path(sess.id)
                if not path.exists():
                    self._write_session_file(sess)

            migrated = LEGACY_INVENTORY.with_suffix(".json.migrated")
            try:
                LEGACY_INVENTORY.replace(migrated)
            except OSError:
                pass

    # ---------------------------------------------------------------- public
    def ensure_group(self, group_id: str, name: str, order: int = 99) -> None:
        """Add a sidebar group if it does not already exist."""
        with self._lock:
            groups = list(self._meta.get("groups") or [])
            if any(g.get("id") == group_id for g in groups):
                return
            groups.append({"id": group_id, "name": name, "order": order})
            groups.sort(key=lambda g: int(g.get("order") or 0))
            self._meta["groups"] = groups
            self._save_meta()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            sessions = [
                s.to_public_dict(has_saved_password=bool(s.password))
                for s in self._iter_sessions()
            ]
            return {
                "groups": deepcopy(self._meta.get("groups") or DEFAULT_GROUPS),
                "sessions": sessions,
                "recent_ids": list(self._meta.get("recent_ids") or []),
            }

    def get_session(self, session_id: str) -> Optional[SavedSession]:
        with self._lock:
            path = self._session_path(session_id)
            if not path.exists():
                # Filename may have been sanitized differently; scan once
                for sess in self._iter_sessions():
                    if sess.id == session_id:
                        return sess
                return None
            return self._read_session_file(path)

    def create_session(self, payload: Dict[str, Any]) -> SavedSession:
        with self._lock:
            sess = SavedSession(
                id=str(uuid.uuid4()),
                name=(payload.get("name") or payload.get("host") or "New Session").strip(),
                host=(payload.get("host") or "").strip(),
                port=int(payload.get("port") or 22),
                username=(payload.get("username") or "").strip(),
                hostname=(payload.get("hostname") or "pehost").strip(),
                group_id=payload.get("group_id") or "development",
                favorite=bool(payload.get("favorite", False)),
                environment=(payload.get("environment") or "development").strip(),
                notes=(payload.get("notes") or "").strip(),
                remember_credentials=bool(payload.get("remember_credentials", True)),
                facts=list(payload.get("facts") or []),
                hints=list(payload.get("hints") or []),
                avoids=list(payload.get("avoids") or []),
            )
            if not sess.host:
                raise ValueError("Host is required.")
            password = payload.get("password") or ""
            if sess.remember_credentials and password:
                sess.password = password
            self._write_session_file(sess)
            return sess

    def update_session(self, session_id: str, payload: Dict[str, Any]) -> SavedSession:
        with self._lock:
            sess = self.get_session(session_id)
            if sess is None:
                raise KeyError(f"Session not found: {session_id}")

            for field_name in (
                "name",
                "host",
                "username",
                "hostname",
                "group_id",
                "environment",
                "notes",
            ):
                if field_name in payload and payload[field_name] is not None:
                    setattr(sess, field_name, str(payload[field_name]).strip())
            if "port" in payload and payload["port"] is not None:
                sess.port = int(payload["port"])
            if "favorite" in payload:
                sess.favorite = bool(payload["favorite"])
            if "remember_credentials" in payload:
                sess.remember_credentials = bool(payload["remember_credentials"])

            if payload.get("password"):
                if sess.remember_credentials:
                    sess.password = str(payload["password"])
                else:
                    sess.password = ""
            elif payload.get("remember_credentials") is False:
                sess.password = ""

            sess.updated_at = _utcnow()
            self._write_session_file(sess)
            return sess

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            path = self._session_path(session_id)
            deleted = False
            if path.exists():
                path.unlink()
                deleted = True
            else:
                for sess in self._iter_sessions():
                    if sess.id == session_id:
                        self._session_path(sess.id).unlink(missing_ok=True)
                        deleted = True
                        break
            if not deleted:
                raise KeyError(f"Session not found: {session_id}")
            self._meta["recent_ids"] = [
                i for i in self._meta.get("recent_ids", []) if i != session_id
            ]
            self._save_meta()

    def touch_recent(self, session_id: str) -> None:
        with self._lock:
            sess = self.get_session(session_id)
            if sess is None:
                return
            recent = [i for i in self._meta.get("recent_ids", []) if i != session_id]
            recent.insert(0, session_id)
            self._meta["recent_ids"] = recent[:20]
            self._save_meta()
            sess.last_connected_at = _utcnow()
            sess.updated_at = _utcnow()
            self._write_session_file(sess)

    def move_session(self, session_id: str, group_id: str) -> SavedSession:
        return self.update_session(session_id, {"group_id": group_id})

    def get_password(self, username: str, host: str, port: int) -> Optional[str]:
        """Lookup remembered password for user@host:port across session files."""
        with self._lock:
            for sess in self._iter_sessions():
                if (
                    sess.username == username
                    and sess.host == host
                    and int(sess.port) == int(port)
                    and sess.password
                ):
                    return sess.password
            return None

    def resolve_password(self, sess: SavedSession, explicit: Optional[str] = None) -> str:
        if explicit:
            return explicit
        if sess.password:
            return sess.password
        saved = self.get_password(sess.username, sess.host, sess.port)
        if saved:
            return saved
        raise ValueError("Password required (or enable Remember credentials for this user@host:port).")

    def get_prompt_context(self, session_id: str) -> Dict[str, List[str]]:
        sess = self.get_session(session_id)
        if not sess:
            raise KeyError(f"Session not found: {session_id}")
        return {
            "facts": list(sess.facts or []),
            "hints": list(sess.hints or []),
            "avoids": list(sess.avoids or []),
        }

    def set_prompt_context(
        self,
        session_id: str,
        *,
        facts: Optional[List[str]] = None,
        hints: Optional[List[str]] = None,
        avoids: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
        with self._lock:
            sess = self.get_session(session_id)
            if sess is None:
                raise KeyError(f"Session not found: {session_id}")
            if facts is not None:
                sess.facts = list(facts)
            if hints is not None:
                sess.hints = list(hints)
            if avoids is not None:
                sess.avoids = list(avoids)
            sess.updated_at = _utcnow()
            self._write_session_file(sess)
            return {
                "facts": list(sess.facts or []),
                "hints": list(sess.hints or []),
                "avoids": list(sess.avoids or []),
            }

    def sync_prompt_lists_from_runtime(
        self, session_id: str, facts: List[str], hints: List[str], avoids: List[str]
    ) -> None:
        self.set_prompt_context(session_id, facts=facts, hints=hints, avoids=avoids)


_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def reset_session_store() -> SessionStore:
    """Force reload (useful after tests or path changes)."""
    global _store
    _store = SessionStore()
    return _store
