"""HTML page routes."""

from __future__ import annotations

from flask import Flask, render_template, session


def register_page_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        """Primary multi-session workspace (no forced connect form)."""
        return render_template("workspace.html")

    @app.route("/workspace")
    def workspace():
        return render_template("workspace.html")

    @app.route("/leaderboard")
    def leaderboard():
        """Collaborative privilege-escalation benchmark leaderboard."""
        return render_template("leaderboard.html")

    @app.route("/terminal")
    def terminal_legacy():
        """Legacy full-page terminal kept for compatibility."""
        hostname = session.get("hostname", "host")
        username = session.get("username", "user")
        return render_template("index.html", hostname=hostname, username=username)

    @app.route("/login")
    def login():
        return render_template("login.html")
