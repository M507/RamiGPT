"""Static vertical leaderboard export (self-contained HTML + tall PNG).

Used for README / docs snapshots. Data comes from ``build_leaderboard_payload``
so numbers match the live ``/leaderboard`` UI.
"""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ramigpt.paths import BENCHMARK_RESULTS_DIR, DOCS_DIR, ensure_runtime_dirs
from ramigpt.utils import debug_logger

_LOG_PREFIX = "[benchmark-leaderboard-export]"

LEADERBOARD_HTML_NAME = "leaderboard.html"
LEADERBOARD_PNG_REL = Path("docs/screenshots/benchmark_leaderboard.png")
README_LEADERBOARD_IMAGE_MD = (
    "![Collaborative benchmark leaderboard](docs/screenshots/benchmark_leaderboard.png)"
)

SHORT_COLORS = (
    "#00ff00",
    "#33ff99",
    "#66ff33",
    "#99ff00",
    "#00cc66",
    "#22aa22",
)

# Pillow RGB equivalents
_BG = (10, 14, 10)
_CARD_BG = (14, 20, 14)
_BORDER = (0, 120, 0)
_ACCENT = (0, 255, 0)
_MUTED = (120, 160, 120)
_TEXT = (180, 255, 180)
_TRACK = (0, 40, 0)
_UNRESOLVED = (51, 85, 51)

PNG_WIDTH = 980
PNG_PAD = 24
CARD_PAD = 16
CARD_GAP = 18


def _log_info(message: str) -> None:
    debug_logger.info(f"{_LOG_PREFIX} {message}")


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _fmt_int(value: Any) -> str:
    try:
        if value is None:
            return "—"
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def _fmt_num(value: Any, digits: int = 1) -> str:
    try:
        if value is None:
            return "—"
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(rate: Any, digits: int = 1) -> str:
    try:
        if rate is None:
            return "—"
        return f"{float(rate) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_tokens(value: Any) -> str:
    try:
        if value is None:
            return "—"
        n = float(value)
        if n <= 0 or math.isnan(n):
            return "—"
        return f"{int(round(n)):,}"
    except (TypeError, ValueError):
        return "—"


def _color(i: int) -> str:
    return SHORT_COLORS[i % len(SHORT_COLORS)]


def _rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _label_lines(label: str, max_chars: int = 42) -> List[str]:
    text = str(label or "unknown")
    limit = max(12, max_chars)
    if len(text) <= limit:
        return [text]
    parts = text.replace(" · ", " ·\n").split("\n")
    lines: List[str] = []
    for part in parts:
        while len(part) > limit:
            cut = part.rfind(" ", 0, limit)
            if cut < limit // 2:
                cut = limit
            lines.append(part[:cut].rstrip())
            part = part[cut:].lstrip()
        if part:
            lines.append(part)
    return lines[:3] or [text[:limit]]


# ---------------------------------------------------------------------------
# SVG chart helpers (for HTML)
# ---------------------------------------------------------------------------


def _svg_multiline(label: str, x: float, y: float, *, max_chars: int = 45) -> str:
    lines = _label_lines(label, max_chars)
    parts = []
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else 11
        if i == 0:
            parts.append(
                f'<text x="{x:.1f}" y="{y:.1f}" class="lb-axis-label">{_esc(line)}</text>'
            )
        else:
            parts.append(
                f'<text x="{x:.1f}" y="{y:.1f}" dy="{dy * i}" class="lb-axis-label">{_esc(line)}</text>'
            )
    return "".join(parts)


def _svg_bar_chart(
    rows: Sequence[Dict[str, Any]],
    *,
    get_value: Callable[[Dict[str, Any]], Any],
    get_label: Optional[Callable[[Dict[str, Any]], str]] = None,
    format_value: Optional[Callable[[Any], str]] = None,
    max_hint: Optional[float] = None,
    empty: str = "No data",
) -> str:
    get_label = get_label or (lambda r: str(r.get("profile_label") or "—"))
    format_value = format_value or (lambda v: _fmt_num(v, 1))
    values: List[Optional[float]] = []
    for r in rows:
        raw = get_value(r)
        try:
            values.append(None if raw is None else float(raw))
        except (TypeError, ValueError):
            values.append(None)
    if not rows or all(v is None for v in values):
        return f'<div class="lb-empty">{_esc(empty)}</div>'
    present = [v for v in values if v is not None]
    max_v = max(max_hint or 0.0, max(present), 0.0001)
    width, row_h, left, right, top = 760, 42, 310, 72, 8
    height = top + len(rows) * row_h + 8
    bar_w = width - left - right
    parts = [f'<svg viewBox="0 0 {width} {height}" role="presentation">']
    for i, row in enumerate(rows):
        y = top + i * row_h
        val = values[i]
        w = 0.0 if val is None else max(2.0, (val / max_v) * bar_w)
        parts.append(_svg_multiline(get_label(row), 0, y + 13))
        parts.append(
            f'<rect x="{left}" y="{y + 8}" width="{bar_w}" height="16" fill="rgba(0,255,0,0.06)" />'
        )
        if val is not None:
            parts.append(
                f'<rect x="{left}" y="{y + 8}" width="{w:.1f}" height="16" fill="{_color(i)}" />'
            )
            parts.append(
                f'<text x="{left + w + 6:.1f}" y="{y + 20}">{_esc(format_value(val))}</text>'
            )
        else:
            parts.append(f'<text x="{left + 6}" y="{y + 20}">—</text>')
    parts.append("</svg>")
    return "".join(parts)


def _svg_grouped_bars(rows: Sequence[Dict[str, Any]], series: List[Dict[str, Any]]) -> str:
    if not rows:
        return '<div class="lb-empty">No token telemetry</div>'
    width, row_h, left, right, top = 760, 46, 310, 20, 28
    height = top + len(rows) * row_h + 8
    bar_area = width - left - right
    bar_h = 10
    max_v = 0.0
    for row in rows:
        for s in series:
            try:
                v = s["get_value"](row)
                if v is not None and float(v) > max_v:
                    max_v = float(v)
            except (TypeError, ValueError):
                pass
    if max_v <= 0:
        return '<div class="lb-empty">Token telemetry unavailable (zeros excluded)</div>'
    parts = [f'<svg viewBox="0 0 {width} {height}" role="presentation">']
    for si, s in enumerate(series):
        parts.append(
            f'<rect x="{left + si * 110}" y="6" width="10" height="10" fill="{s["color"]}" />'
            f'<text x="{left + si * 110 + 16}" y="15">{_esc(s["label"])}</text>'
        )
    for i, row in enumerate(rows):
        y = top + i * row_h
        parts.append(_svg_multiline(str(row.get("profile_label") or "—"), 0, y + 13))
        for si, s in enumerate(series):
            raw = s["get_value"](row)
            try:
                val = None if raw is None else float(raw)
            except (TypeError, ValueError):
                val = None
            w = 0.0 if val is None or val <= 0 else max(2.0, (val / max_v) * bar_area)
            yy = y + si * (bar_h + 2)
            parts.append(
                f'<rect x="{left}" y="{yy}" width="{bar_area}" height="{bar_h}" fill="rgba(0,255,0,0.05)" />'
            )
            if w > 0:
                parts.append(
                    f'<rect x="{left}" y="{yy}" width="{w:.1f}" height="{bar_h}" fill="{s["color"]}" />'
                )
    parts.append("</svg>")
    return "".join(parts)


def _svg_stacked_outcomes(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return '<div class="lb-empty">No outcomes</div>'
    width, row_h, left, right, top = 760, 42, 310, 64, 24
    height = top + len(rows) * row_h + 8
    bar_w = width - left - right
    max_v = max(
        ((r.get("got_root_count") or 0) + (r.get("unresolved_count") or 0) for r in rows),
        default=1,
    )
    max_v = max(int(max_v), 1)
    parts = [f'<svg viewBox="0 0 {width} {height}" role="presentation">']
    parts.append(
        f'<rect x="{left}" y="6" width="10" height="10" fill="#00ff00" />'
        f'<text x="{left + 16}" y="15">Resolved</text>'
        f'<rect x="{left + 110}" y="6" width="10" height="10" fill="#335533" />'
        f'<text x="{left + 126}" y="15">Unresolved</text>'
    )
    for i, row in enumerate(rows):
        y = top + i * row_h
        resolved = int(row.get("got_root_count") or 0)
        unresolved = int(row.get("unresolved_count") or 0)
        total = resolved + unresolved
        rw = (resolved / max_v) * bar_w if total else 0
        uw = (unresolved / max_v) * bar_w if total else 0
        parts.append(_svg_multiline(str(row.get("profile_label") or "—"), 0, y + 13))
        parts.append(
            f'<rect x="{left}" y="{y + 8}" width="{rw:.1f}" height="16" fill="#00ff00" />'
            f'<rect x="{left + rw:.1f}" y="{y + 8}" width="{uw:.1f}" height="16" fill="#335533" />'
            f'<text x="{left + rw + uw + 6:.1f}" y="{y + 20}">{resolved}/{total}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _svg_scatter(rows: Sequence[Dict[str, Any]]) -> str:
    points = []
    for i, r in enumerate(rows):
        x = r.get("score_percent")
        y = r.get("usable_mean_tokens_to_root")
        try:
            if x is None or y is None or float(y) <= 0:
                continue
            points.append({"i": i, "x": float(x), "y": float(y), "n": int(r.get("attempted") or 1), "row": r})
        except (TypeError, ValueError):
            continue
    if not points:
        return '<div class="lb-empty">Need success rate + usable tokens-to-root</div>'
    width, plot_h, legend_h = 760, 250, 30
    height = plot_h + len(points) * legend_h + 28
    pad = {"t": 20, "r": 20, "b": 36, "l": 48}
    max_y = max(p["y"] for p in points) * 1.15
    max_n = max(p["n"] for p in points)
    x_scale = lambda v: pad["l"] + (v / 100.0) * (width - pad["l"] - pad["r"])
    y_scale = lambda v: plot_h - pad["b"] - (v / max_y) * (plot_h - pad["t"] - pad["b"])
    parts = [f'<svg viewBox="0 0 {width} {height}" role="presentation">']
    parts.append(
        f'<line x1="{pad["l"]}" y1="{plot_h - pad["b"]}" x2="{width - pad["r"]}" y2="{plot_h - pad["b"]}" stroke="rgba(0,255,0,0.35)" />'
        f'<line x1="{pad["l"]}" y1="{pad["t"]}" x2="{pad["l"]}" y2="{plot_h - pad["b"]}" stroke="rgba(0,255,0,0.35)" />'
        f'<text x="{width / 2}" y="{plot_h - 8}">Success rate (%)</text>'
    )
    for p in points:
        r = 6 + (p["n"] / max_n) * 10
        c = _color(p["i"])
        parts.append(
            f'<circle cx="{x_scale(p["x"]):.1f}" cy="{y_scale(p["y"]):.1f}" r="{r:.1f}" '
            f'fill="{c}" fill-opacity="0.75" stroke="#0f0" />'
            f'<text x="{x_scale(p["x"]) + r + 4:.1f}" y="{y_scale(p["y"]) + 3:.1f}">#{p["i"] + 1}</text>'
        )
    for idx, p in enumerate(points):
        y = plot_h + 12 + idx * legend_h
        parts.append(
            f'<rect x="12" y="{y - 8}" width="9" height="9" fill="{_color(p["i"])}" />'
        )
        parts.append(
            _svg_multiline(
                f'#{p["i"] + 1} {p["row"].get("profile_label") or ""}',
                28,
                y,
                max_chars=92,
            )
        )
    parts.append("</svg>")
    return "".join(parts)


def _svg_radar(radar_rows: Sequence[Dict[str, Any]], limit: int = 6) -> str:
    if not radar_rows:
        return '<div class="lb-empty">No radar scores</div>'
    axes = ["success", "speed", "token_efficiency", "request_efficiency"]
    labels = ["Success", "Speed", "Tokens", "Requests"]
    width, plot_h, legend_h = 760, 270, 30
    rows = list(radar_rows)[:limit]
    height = plot_h + len(rows) * legend_h + 12
    cx, cy, radius = width / 2, 140, 90

    def angle(i: int) -> float:
        return (-math.pi / 2) + (i * 2 * math.pi) / len(axes)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="presentation">']
    for ring in range(1, 5):
        rr = (radius * ring) / 4
        pts = " ".join(
            f"{cx + math.cos(angle(i)) * rr},{cy + math.sin(angle(i)) * rr}"
            for i in range(len(axes))
        )
        parts.append(f'<polygon points="{pts}" fill="none" stroke="rgba(0,255,0,0.2)" />')
    for i, lab in enumerate(labels):
        a = angle(i)
        parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{cx + math.cos(a) * radius}" y2="{cy + math.sin(a) * radius}" stroke="rgba(0,255,0,0.25)" />'
            f'<text x="{cx + math.cos(a) * (radius + 18)}" y="{cy + math.sin(a) * (radius + 18)}" text-anchor="middle">{_esc(lab)}</text>'
        )
    for idx, row in enumerate(rows):
        color = _color(idx)
        pts = []
        for i, key in enumerate(axes):
            axes_map = row.get("axes") or {}
            try:
                score = float(axes_map.get(key) or 0)
            except (TypeError, ValueError):
                score = 0.0
            score = max(0.0, min(100.0, score))
            a = angle(i)
            rr = (score / 100.0) * radius
            pts.append(f"{cx + math.cos(a) * rr},{cy + math.sin(a) * rr}")
        parts.append(
            f'<polygon points="{" ".join(pts)}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="1.5" />'
        )
    for idx, row in enumerate(rows):
        y = plot_h + 8 + idx * legend_h
        parts.append(f'<rect x="12" y="{y - 8}" width="9" height="9" fill="{_color(idx)}" />')
        parts.append(
            _svg_multiline(
                f'#{idx + 1} {row.get("profile_label") or ""}',
                28,
                y,
                max_chars=92,
            )
        )
    parts.append("</svg>")
    return "".join(parts)


def _svg_heatmap(heat: Dict[str, Any]) -> str:
    families = list((heat or {}).get("families") or [])
    profiles = list((heat or {}).get("profiles") or [])
    cells = list((heat or {}).get("cells") or [])
    if not families or not profiles:
        return '<div class="lb-empty">No family coverage yet</div>'
    cell_map = {f"{c.get('family')}|{c.get('profile_key')}": c for c in cells}
    left, top, cell_w, cell_h = 110, 38, 76, 28
    grid_bottom = top + len(families) * cell_h
    legend_h = 30
    width = max(760, left + len(profiles) * cell_w + 20)
    height = grid_bottom + len(profiles) * legend_h + 28
    parts = [f'<svg viewBox="0 0 {width} {height}" role="presentation">']
    for i, _p in enumerate(profiles):
        x = left + i * cell_w + cell_w / 2
        parts.append(f'<text x="{x}" y="24" text-anchor="middle" class="lb-axis-label">#{i + 1}</text>')
    for fi, family in enumerate(families):
        y = top + fi * cell_h
        parts.append(f'<text x="0" y="{y + 18}" class="lb-axis-label">{_esc(family)}</text>')
        for pi, p in enumerate(profiles):
            cell = cell_map.get(f"{family}|{p.get('profile_key')}")
            rate = None if not cell else cell.get("got_root_rate")
            x = left + pi * cell_w
            if rate is None:
                fill = "rgba(0,255,0,0.05)"
                label = "—"
            else:
                try:
                    a = 0.12 + float(rate) * 0.75
                    fill = f"rgba(0,255,0,{a:.2f})"
                    label = _fmt_pct(rate)
                except (TypeError, ValueError):
                    fill = "rgba(0,255,0,0.05)"
                    label = "—"
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - 2}" height="{cell_h - 2}" fill="{fill}" stroke="rgba(0,255,0,0.25)" />'
                f'<text x="{x + cell_w / 2 - 1}" y="{y + 17}" text-anchor="middle">{_esc(label)}</text>'
            )
    for idx, p in enumerate(profiles):
        y = grid_bottom + 22 + idx * legend_h
        parts.append(f'<rect x="12" y="{y - 8}" width="9" height="9" fill="{_color(idx)}" />')
        parts.append(
            _svg_multiline(
                f'#{idx + 1} {p.get("profile_label") or ""}',
                28,
                y,
                max_chars=92,
            )
        )
    parts.append("</svg>")
    return "".join(parts)


def _svg_trend(points: Sequence[Dict[str, Any]]) -> str:
    if not points or len(points) < 2:
        return '<div class="lb-empty">Need at least two dated runs for a trend</div>'
    width, height = 680, 260
    pad = {"t": 20, "r": 24, "b": 40, "l": 48}
    max_passed = max(int(p.get("cumulative_passed") or 0) for p in points) or 1

    def x_scale(i: int) -> float:
        return pad["l"] + (i / (len(points) - 1)) * (width - pad["l"] - pad["r"])

    def y_rate(v: float) -> float:
        return height - pad["b"] - (float(v or 0) * (height - pad["t"] - pad["b"]))

    def y_count(v: float) -> float:
        return height - pad["b"] - (float(v or 0) / max_passed) * (height - pad["t"] - pad["b"])

    rate_pts = " ".join(
        f'{x_scale(i):.1f},{y_rate(float(p.get("cumulative_pass_rate") or 0)):.1f}'
        for i, p in enumerate(points)
    )
    count_pts = " ".join(
        f'{x_scale(i):.1f},{y_count(float(p.get("cumulative_passed") or 0)):.1f}'
        for i, p in enumerate(points)
    )
    first = points[0]
    last = points[-1]
    return (
        f'<svg viewBox="0 0 {width} {height}" role="presentation">'
        f'<polyline fill="none" stroke="#00ff00" stroke-width="2" points="{rate_pts}" />'
        f'<polyline fill="none" stroke="#66ff33" stroke-width="1.5" stroke-dasharray="4 3" points="{count_pts}" />'
        f'<text x="{pad["l"]}" y="14">Cum. pass rate</text>'
        f'<text x="{pad["l"] + 120}" y="14">Cum. passed (dashed)</text>'
        f'<text x="{pad["l"]}" y="{height - 12}">{_esc(first.get("date"))}</text>'
        f'<text x="{width - pad["r"]}" y="{height - 12}" text-anchor="end">{_esc(last.get("date"))}</text>'
        f"</svg>"
    )


def _card_html(title: str, body: str, *, wide: bool = True) -> str:
    cls = "lb-card lb-card-wide" if wide else "lb-card"
    return f'<article class="{cls}"><h3>{_esc(title)}</h3>{body}</article>'


def _table_html(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return '<p class="muted">No collaborative results yet.</p>'
    head = (
        "<table class='lb-table'><thead><tr>"
        "<th>#</th><th>Configuration</th><th>Resolved</th><th>Score</th>"
        "<th>Attempted</th><th>Runs</th><th>Avg input tok</th>"
        "<th>Tok → root</th><th>Time → root</th>"
        "</tr></thead><tbody>"
    )
    body_parts = []
    for row in rows:
        score = row.get("score_percent")
        score_s = "—" if score is None else f"{float(score):.1f}%"
        elapsed = row.get("mean_elapsed_to_root")
        time_s = "—" if elapsed is None else f"{_fmt_num(elapsed, 1)}s"
        body_parts.append(
            "<tr>"
            f"<td class='lb-rank'>{_esc(row.get('rank'))}</td>"
            f"<td class='lb-name'>{_esc(row.get('profile_label') or row.get('model_key_name') or '—')}</td>"
            f"<td>{_esc(_fmt_int(row.get('got_root_count')))}</td>"
            f"<td>{_esc(score_s)}</td>"
            f"<td>{_esc(_fmt_int(row.get('attempted')))}</td>"
            f"<td>{_esc(_fmt_int(row.get('runs')))}</td>"
            f"<td>{_esc(_fmt_tokens(row.get('usable_mean_prompt_tokens') or row.get('mean_prompt_tokens')))}</td>"
            f"<td>{_esc(_fmt_tokens(row.get('usable_mean_tokens_to_root') or row.get('mean_tokens_to_root')))}</td>"
            f"<td>{_esc(time_s)}</td>"
            "</tr>"
        )
    return head + "".join(body_parts) + "</tbody></table>"


def format_leaderboard_export_html(master: Optional[Dict[str, Any]]) -> str:
    """Self-contained vertical leaderboard HTML (no /static dependencies)."""
    from ramigpt.benchmark.master_results import build_leaderboard_payload

    payload = build_leaderboard_payload(master, limit=6, metric="got_root_count")
    top = list(payload.get("top") or [])
    charts = payload.get("charts") or {}
    summary = payload.get("summary") or {}
    methodology = payload.get("methodology") or {}
    updated = payload.get("updated_at") or "—"

    stats = "".join(
        f'<div class="lb-stat"><span class="label">{_esc(label)}</span>'
        f'<span class="value">{_esc(value)}</span></div>'
        for label, value in (
            ("Profiles", _fmt_int(summary.get("profiles"))),
            ("Runs", _fmt_int(summary.get("runs"))),
            ("Attempted", _fmt_int(summary.get("attempted"))),
            ("Resolved", _fmt_int(summary.get("got_root_count"))),
        )
    )

    cards: List[str] = [
        _card_html("Top 6 table", f'<div class="lb-table-wrap">{_table_html(top)}</div>'),
        _card_html(
            "Resolved (got root)",
            _svg_bar_chart(
                top,
                get_value=lambda r: r.get("got_root_count"),
                format_value=_fmt_int,
                empty="No resolved counts",
            ),
        ),
        _card_html(
            "Success rate",
            _svg_bar_chart(
                top,
                get_value=lambda r: None
                if r.get("got_root_rate") is None
                else float(r["got_root_rate"]) * 100,
                format_value=lambda v: f"{_fmt_num(v, 1)}%",
                max_hint=100,
                empty="No success rates",
            ),
        ),
        _card_html(
            "Input vs tokens to root",
            _svg_grouped_bars(
                top,
                [
                    {
                        "label": "Avg input",
                        "color": "#66ff33",
                        "get_value": lambda r: r.get("usable_mean_prompt_tokens"),
                    },
                    {
                        "label": "Tok → root",
                        "color": "#00ff00",
                        "get_value": lambda r: r.get("usable_mean_tokens_to_root"),
                    },
                ],
            ),
        ),
        _card_html(
            "Time to root",
            _svg_bar_chart(
                top,
                get_value=lambda r: r.get("mean_elapsed_to_root"),
                format_value=lambda v: f"{_fmt_num(v, 1)}s",
                empty="No time-to-root data",
            ),
        ),
        _card_html(
            "AI requests to root",
            _svg_bar_chart(
                top,
                get_value=lambda r: r.get("mean_ai_requests_to_root"),
                format_value=lambda v: _fmt_num(v, 2),
                empty="No AI request data",
            ),
        ),
        _card_html(
            "Commands to root",
            _svg_bar_chart(
                top,
                get_value=lambda r: r.get("mean_commands_to_root"),
                format_value=lambda v: _fmt_num(v, 2),
                empty="No command data",
            ),
        ),
        _card_html(
            "Tokens / sec to root",
            _svg_bar_chart(
                top,
                get_value=lambda r: r.get("usable_tokens_per_second_to_root")
                or r.get("tokens_per_second_to_root"),
                format_value=lambda v: _fmt_num(v, 2),
                empty="No usable tokens/sec (zeros excluded)",
            ),
        ),
        _card_html("Multi-axis score", _svg_radar(charts.get("radar") or [])),
        _card_html("Success vs token efficiency", _svg_scatter(top)),
        _card_html("Resolved vs unresolved", _svg_stacked_outcomes(top)),
        _card_html(
            "Catalog attempt coverage",
            _svg_bar_chart(
                charts.get("coverage") or [],
                get_label=lambda r: str(r.get("profile_label") or "—"),
                get_value=lambda r: None
                if r.get("coverage_rate") is None
                else float(r["coverage_rate"]) * 100,
                format_value=lambda v: f"{_fmt_num(v, 1)}%",
                max_hint=100,
                empty="No coverage data",
            ),
        ),
        _card_html("Success by lab family", _svg_heatmap(charts.get("family_heatmap") or {})),
        _card_html("Benchmark trend", _svg_trend(charts.get("trend") or [])),
        _card_html(
            "Hardware comparison",
            _svg_bar_chart(
                charts.get("hardware_comparison") or [],
                get_label=lambda r: f"{r.get('model_key_name')} · {r.get('hardware_label') or r.get('hardware_key')}",
                get_value=lambda r: None
                if r.get("got_root_rate") is None
                else float(r["got_root_rate"]) * 100,
                format_value=lambda v: f"{_fmt_num(v, 1)}%",
                max_hint=100,
                empty="No multi-hardware comparisons yet",
            ),
        ),
        _card_html(
            "Tools impact",
            _svg_bar_chart(
                charts.get("tools_impact") or [],
                get_label=lambda r: str(r.get("tools_label") or "none"),
                get_value=lambda r: None
                if r.get("got_root_rate") is None
                else float(r["got_root_rate"]) * 100,
                format_value=lambda v: f"{_fmt_num(v, 1)}%",
                max_hint=100,
                empty="No tools impact data",
            ),
        ),
    ]

    method_items = [
        methodology.get("score"),
        methodology.get("resolved"),
        methodology.get("tokens"),
        methodology.get("trend"),
    ]
    method_html = "".join(f"<li>{_esc(t)}</li>" for t in method_items if t)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>RamiGPT · Benchmark Leaderboard (export)</title>
  <style>
    :root {{
      --bg: #0a0e0a;
      --card: #0e140e;
      --accent: #00ff00;
      --muted: #78a078;
      --text: #b4ffb4;
      --border: #007800;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }}
    .lb-main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 20px 18px 48px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}
    .lb-hero {{
      border: 1px solid var(--border);
      background: var(--card);
      padding: 18px 16px;
    }}
    .lb-eyebrow {{
      margin: 0 0 6px;
      font-size: 11px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--accent);
    }}
    .lb-hero h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--accent);
      text-shadow: 0 0 8px rgba(0, 255, 0, 0.45);
    }}
    .muted {{ color: var(--muted); }}
    .small {{ font-size: 12px; }}
    .lb-summary {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }}
    .lb-stat {{
      border: 1px solid var(--border);
      background: var(--card);
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .lb-stat .label {{
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .lb-stat .value {{
      color: var(--accent);
      font-size: 22px;
      font-weight: 700;
    }}
    .lb-section-head h2 {{
      margin: 8px 0 4px;
      color: var(--accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .lb-card {{
      border: 1px solid var(--border);
      background: var(--card);
      padding: 14px;
      width: 100%;
    }}
    .lb-card h3 {{
      margin: 0 0 12px;
      color: var(--accent);
      font-size: 14px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .lb-table-wrap {{ overflow-x: auto; }}
    .lb-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    .lb-table th, .lb-table td {{
      border-bottom: 1px solid rgba(0, 255, 0, 0.15);
      padding: 8px 6px;
      text-align: left;
      vertical-align: top;
    }}
    .lb-table th {{
      color: var(--muted);
      font-size: 10px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .lb-rank {{ color: var(--accent); font-weight: 700; }}
    .lb-name {{ max-width: 280px; word-break: break-word; }}
    svg {{ width: 100%; height: auto; display: block; }}
    svg text {{ fill: var(--text); font-size: 11px; font-family: inherit; }}
    .lb-axis-label {{ fill: var(--muted); }}
    .lb-empty {{ color: var(--muted); padding: 18px 4px; }}
    .lb-method-list {{ margin: 0; padding-left: 18px; }}
    .lb-method-list li {{ margin-bottom: 6px; }}
    .lb-stack {{ display: flex; flex-direction: column; gap: 18px; }}
  </style>
</head>
<body>
  <main class="lb-main">
    <section class="lb-hero">
      <p class="lb-eyebrow">Privilege Escalation Benchmark</p>
      <h1>Model Leaderboard</h1>
      <p class="muted small">
        Static export of collaborative rankings · updated {_esc(updated)} ·
        top {len(top)} by resolved labs (got-root count).
      </p>
    </section>
    <section class="lb-summary">{stats}</section>
    <section>
      <div class="lb-section-head">
        <h2>Rankings</h2>
        <p class="muted small">Top 6 model · hardware profiles. Score = got-root rate on scoreable attempts.</p>
      </div>
      <div class="lb-stack">
        {"".join(cards[:3])}
      </div>
    </section>
    <section>
      <div class="lb-section-head">
        <h2>Efficiency</h2>
        <p class="muted small">Tokens, speed, and request cost on successful root escalations.</p>
      </div>
      <div class="lb-stack">
        {"".join(cards[3:10])}
      </div>
    </section>
    <section>
      <div class="lb-section-head">
        <h2>Coverage</h2>
        <p class="muted small">Sample size, lab families, and how much of the catalog each Top 6 has tried.</p>
      </div>
      <div class="lb-stack">
        {"".join(cards[10:13])}
      </div>
    </section>
    <section>
      <div class="lb-section-head">
        <h2>Context</h2>
        <p class="muted small">Trends, hardware, and tool-profile impact across collaborative runs.</p>
      </div>
      <div class="lb-stack">
        {"".join(cards[13:])}
      </div>
    </section>
    <section class="lb-card">
      <h3>Methodology</h3>
      <ul class="lb-method-list muted small">{method_html}</ul>
    </section>
  </main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# PNG (Pillow)
# ---------------------------------------------------------------------------


def _load_font(size: int):
    from PIL import ImageFont

    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


class _PngCanvas:
    def __init__(self, width: int = PNG_WIDTH) -> None:
        from PIL import Image, ImageDraw

        self.width = width
        self.parts: List[Any] = []
        self._Image = Image
        self._ImageDraw = ImageDraw
        self.font = _load_font(13)
        self.font_sm = _load_font(11)
        self.font_lg = _load_font(22)
        self.font_xl = _load_font(28)
        self.font_title = _load_font(14)

    def _new(self, height: int):
        img = self._Image.new("RGB", (self.width, height), _BG)
        draw = self._ImageDraw.Draw(img)
        return img, draw

    def add(self, img) -> None:
        self.parts.append(img)

    def text_size(self, text: str, font) -> Tuple[int, int]:
        # Pillow >=10 uses textbbox
        tmp = self._Image.new("RGB", (10, 10))
        d = self._ImageDraw.Draw(tmp)
        bbox = d.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def wrap(self, text: str, font, max_width: int) -> List[str]:
        words = str(text).split()
        if not words:
            return [""]
        lines: List[str] = []
        cur = words[0]
        for w in words[1:]:
            trial = f"{cur} {w}"
            if self.text_size(trial, font)[0] <= max_width:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        return lines

    def hero(self, updated: str, top_n: int) -> None:
        h = 110
        img, draw = self._new(h)
        draw.rectangle([PNG_PAD, 8, self.width - PNG_PAD, h - 8], outline=_BORDER, fill=_CARD_BG)
        draw.text((PNG_PAD + 16, 18), "PRIVILEGE ESCALATION BENCHMARK", fill=_ACCENT, font=self.font_sm)
        draw.text((PNG_PAD + 16, 36), "MODEL LEADERBOARD", fill=_ACCENT, font=self.font_xl)
        draw.text(
            (PNG_PAD + 16, 74),
            f"Static export · updated {updated} · top {top_n} by resolved labs",
            fill=_MUTED,
            font=self.font_sm,
        )
        self.add(img)

    def summary_row(self, summary: Dict[str, Any]) -> None:
        items = [
            ("PROFILES", _fmt_int(summary.get("profiles"))),
            ("RUNS", _fmt_int(summary.get("runs"))),
            ("ATTEMPTED", _fmt_int(summary.get("attempted"))),
            ("RESOLVED", _fmt_int(summary.get("got_root_count"))),
        ]
        h = 78
        img, draw = self._new(h)
        gap = 10
        usable = self.width - 2 * PNG_PAD - 3 * gap
        card_w = usable // 4
        x = PNG_PAD
        for label, value in items:
            draw.rectangle([x, 4, x + card_w, h - 4], outline=_BORDER, fill=_CARD_BG)
            draw.text((x + 12, 14), label, fill=_MUTED, font=self.font_sm)
            draw.text((x + 12, 34), value, fill=_ACCENT, font=self.font_lg)
            x += card_w + gap
        self.add(img)

    def section_head(self, title: str, subtitle: str) -> None:
        lines = self.wrap(subtitle, self.font_sm, self.width - 2 * PNG_PAD)
        h = 48 + len(lines) * 14
        img, draw = self._new(h)
        draw.text((PNG_PAD, 10), title.upper(), fill=_ACCENT, font=self.font_lg)
        y = 40
        for line in lines:
            draw.text((PNG_PAD, y), line, fill=_MUTED, font=self.font_sm)
            y += 14
        self.add(img)

    def card_start_height(self, title: str, body_h: int) -> int:
        return CARD_PAD * 2 + 28 + body_h

    def draw_card_chrome(self, draw, height: int, title: str) -> int:
        draw.rectangle(
            [PNG_PAD, 4, self.width - PNG_PAD, height - 4],
            outline=_BORDER,
            fill=_CARD_BG,
        )
        draw.text((PNG_PAD + CARD_PAD, 14), title.upper(), fill=_ACCENT, font=self.font_title)
        return 40

    def table_card(self, rows: Sequence[Dict[str, Any]]) -> None:
        row_h = 36
        body_h = 28 + max(len(rows), 1) * row_h
        h = self.card_start_height("Top 6 table", body_h)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, "Top 6 table")
        headers = ["#", "Configuration", "Resolved", "Score", "Att", "Runs", "Time"]
        cols = [36, 360, 80, 70, 60, 50, 70]
        x = PNG_PAD + CARD_PAD
        for header, w in zip(headers, cols):
            draw.text((x, y0), header.upper(), fill=_MUTED, font=self.font_sm)
            x += w
        y = y0 + 20
        if not rows:
            draw.text((PNG_PAD + CARD_PAD, y), "No collaborative results yet.", fill=_MUTED, font=self.font)
            self.add(img)
            return
        for row in rows:
            x = PNG_PAD + CARD_PAD
            score = row.get("score_percent")
            score_s = "—" if score is None else f"{float(score):.1f}%"
            elapsed = row.get("mean_elapsed_to_root")
            time_s = "—" if elapsed is None else f"{_fmt_num(elapsed, 1)}s"
            vals = [
                str(row.get("rank") or ""),
                str(row.get("profile_label") or row.get("model_key_name") or "—"),
                _fmt_int(row.get("got_root_count")),
                score_s,
                _fmt_int(row.get("attempted")),
                _fmt_int(row.get("runs")),
                time_s,
            ]
            for i, (val, w) in enumerate(zip(vals, cols)):
                color = _ACCENT if i == 0 else _TEXT
                if i == 1:
                    lines = self.wrap(val, self.font_sm, w - 4)[:2]
                    yy = y
                    for line in lines:
                        draw.text((x, yy), line, fill=color, font=self.font_sm)
                        yy += 12
                else:
                    draw.text((x, y), val, fill=color, font=self.font_sm)
                x += w
            draw.line(
                [PNG_PAD + CARD_PAD, y + row_h - 4, self.width - PNG_PAD - CARD_PAD, y + row_h - 4],
                fill=_TRACK,
            )
            y += row_h
        self.add(img)

    def bar_card(
        self,
        title: str,
        rows: Sequence[Dict[str, Any]],
        *,
        get_value: Callable[[Dict[str, Any]], Any],
        get_label: Optional[Callable[[Dict[str, Any]], str]] = None,
        format_value: Optional[Callable[[Any], str]] = None,
        max_hint: Optional[float] = None,
        empty: str = "No data",
    ) -> None:
        get_label = get_label or (lambda r: str(r.get("profile_label") or "—"))
        format_value = format_value or (lambda v: _fmt_num(v, 1))
        row_h = 40
        body_h = 16 + max(len(rows), 1) * row_h
        h = self.card_start_height(title, body_h)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, title)
        if not rows:
            draw.text((PNG_PAD + CARD_PAD, y0), empty, fill=_MUTED, font=self.font)
            self.add(img)
            return
        values: List[Optional[float]] = []
        for r in rows:
            raw = get_value(r)
            try:
                values.append(None if raw is None else float(raw))
            except (TypeError, ValueError):
                values.append(None)
        present = [v for v in values if v is not None]
        if not present:
            draw.text((PNG_PAD + CARD_PAD, y0), empty, fill=_MUTED, font=self.font)
            self.add(img)
            return
        max_v = max(max_hint or 0.0, max(present), 0.0001)
        label_w = 300
        bar_left = PNG_PAD + CARD_PAD + label_w
        bar_right = self.width - PNG_PAD - CARD_PAD - 70
        bar_w = max(40, bar_right - bar_left)
        y = y0
        for i, row in enumerate(rows):
            label = get_label(row)
            for li, line in enumerate(self.wrap(label, self.font_sm, label_w - 8)[:2]):
                draw.text((PNG_PAD + CARD_PAD, y + li * 12), line, fill=_MUTED, font=self.font_sm)
            draw.rectangle([bar_left, y + 6, bar_left + bar_w, y + 20], fill=_TRACK)
            val = values[i]
            if val is not None:
                w = max(2, int((val / max_v) * bar_w))
                draw.rectangle([bar_left, y + 6, bar_left + w, y + 20], fill=_rgb(_color(i)))
                draw.text((bar_left + w + 6, y + 4), format_value(val), fill=_TEXT, font=self.font_sm)
            else:
                draw.text((bar_left + 6, y + 4), "—", fill=_MUTED, font=self.font_sm)
            y += row_h
        self.add(img)

    def stacked_card(self, title: str, rows: Sequence[Dict[str, Any]]) -> None:
        row_h = 40
        body_h = 28 + max(len(rows), 1) * row_h
        h = self.card_start_height(title, body_h)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, title)
        draw.rectangle([PNG_PAD + CARD_PAD, y0, PNG_PAD + CARD_PAD + 10, y0 + 10], fill=_ACCENT)
        draw.text((PNG_PAD + CARD_PAD + 16, y0), "Resolved", fill=_TEXT, font=self.font_sm)
        draw.rectangle([PNG_PAD + CARD_PAD + 110, y0, PNG_PAD + CARD_PAD + 120, y0 + 10], fill=_UNRESOLVED)
        draw.text((PNG_PAD + CARD_PAD + 126, y0), "Unresolved", fill=_TEXT, font=self.font_sm)
        if not rows:
            draw.text((PNG_PAD + CARD_PAD, y0 + 24), "No outcomes", fill=_MUTED, font=self.font)
            self.add(img)
            return
        max_v = max(
            ((r.get("got_root_count") or 0) + (r.get("unresolved_count") or 0) for r in rows),
            default=1,
        )
        max_v = max(int(max_v), 1)
        label_w = 300
        bar_left = PNG_PAD + CARD_PAD + label_w
        bar_w = max(40, self.width - PNG_PAD - CARD_PAD - 70 - bar_left)
        y = y0 + 20
        for row in rows:
            for li, line in enumerate(
                self.wrap(str(row.get("profile_label") or "—"), self.font_sm, label_w - 8)[:2]
            ):
                draw.text((PNG_PAD + CARD_PAD, y + li * 12), line, fill=_MUTED, font=self.font_sm)
            resolved = int(row.get("got_root_count") or 0)
            unresolved = int(row.get("unresolved_count") or 0)
            total = resolved + unresolved
            rw = int((resolved / max_v) * bar_w) if total else 0
            uw = int((unresolved / max_v) * bar_w) if total else 0
            draw.rectangle([bar_left, y + 6, bar_left + rw, y + 20], fill=_ACCENT)
            draw.rectangle([bar_left + rw, y + 6, bar_left + rw + uw, y + 20], fill=_UNRESOLVED)
            draw.text(
                (bar_left + rw + uw + 6, y + 4),
                f"{resolved}/{total}",
                fill=_TEXT,
                font=self.font_sm,
            )
            y += row_h
        self.add(img)

    def grouped_card(self, title: str, rows: Sequence[Dict[str, Any]]) -> None:
        row_h = 44
        body_h = 28 + max(len(rows), 1) * row_h
        h = self.card_start_height(title, body_h)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, title)
        draw.rectangle([PNG_PAD + CARD_PAD, y0, PNG_PAD + CARD_PAD + 10, y0 + 10], fill=_rgb("#66ff33"))
        draw.text((PNG_PAD + CARD_PAD + 16, y0), "Avg input", fill=_TEXT, font=self.font_sm)
        draw.rectangle(
            [PNG_PAD + CARD_PAD + 110, y0, PNG_PAD + CARD_PAD + 120, y0 + 10], fill=_ACCENT
        )
        draw.text((PNG_PAD + CARD_PAD + 126, y0), "Tok → root", fill=_TEXT, font=self.font_sm)
        max_v = 0.0
        for r in rows:
            for key in ("usable_mean_prompt_tokens", "usable_mean_tokens_to_root"):
                try:
                    v = r.get(key)
                    if v is not None and float(v) > max_v:
                        max_v = float(v)
                except (TypeError, ValueError):
                    pass
        if max_v <= 0:
            draw.text(
                (PNG_PAD + CARD_PAD, y0 + 24),
                "Token telemetry unavailable (zeros excluded)",
                fill=_MUTED,
                font=self.font,
            )
            self.add(img)
            return
        label_w = 300
        bar_left = PNG_PAD + CARD_PAD + label_w
        bar_w = max(40, self.width - PNG_PAD - CARD_PAD - bar_left)
        y = y0 + 20
        for i, row in enumerate(rows):
            for li, line in enumerate(
                self.wrap(str(row.get("profile_label") or "—"), self.font_sm, label_w - 8)[:2]
            ):
                draw.text((PNG_PAD + CARD_PAD, y + li * 12), line, fill=_MUTED, font=self.font_sm)
            for si, (key, color) in enumerate(
                (("usable_mean_prompt_tokens", "#66ff33"), ("usable_mean_tokens_to_root", "#00ff00"))
            ):
                yy = y + si * 12
                draw.rectangle([bar_left, yy, bar_left + bar_w, yy + 8], fill=_TRACK)
                try:
                    val = row.get(key)
                    fval = None if val is None else float(val)
                except (TypeError, ValueError):
                    fval = None
                if fval and fval > 0:
                    w = max(2, int((fval / max_v) * bar_w))
                    draw.rectangle([bar_left, yy, bar_left + w, yy + 8], fill=_rgb(color))
            y += row_h
        self.add(img)

    def text_card(self, title: str, lines: Sequence[str]) -> None:
        wrapped: List[str] = []
        for line in lines:
            wrapped.extend(self.wrap(f"• {line}", self.font_sm, self.width - 2 * PNG_PAD - 2 * CARD_PAD))
        body_h = 12 + max(len(wrapped), 1) * 16
        h = self.card_start_height(title, body_h)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, title)
        y = y0
        for line in wrapped:
            draw.text((PNG_PAD + CARD_PAD, y), line, fill=_MUTED, font=self.font_sm)
            y += 16
        self.add(img)

    def simple_note_card(self, title: str, message: str) -> None:
        h = self.card_start_height(title, 36)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, title)
        for i, line in enumerate(self.wrap(message, self.font, self.width - 2 * PNG_PAD - 2 * CARD_PAD)[:3]):
            draw.text((PNG_PAD + CARD_PAD, y0 + i * 16), line, fill=_MUTED, font=self.font)
        self.add(img)

    def heatmap_card(self, title: str, heat: Dict[str, Any]) -> None:
        families = list((heat or {}).get("families") or [])
        profiles = list((heat or {}).get("profiles") or [])
        cells = list((heat or {}).get("cells") or [])
        if not families or not profiles:
            self.simple_note_card(title, "No family coverage yet")
            return
        cell_map = {f"{c.get('family')}|{c.get('profile_key')}": c for c in cells}
        cell_w, cell_h = 70, 26
        left = 120
        top_extra = 30
        grid_h = len(families) * cell_h
        legend_h = len(profiles) * 18
        body_h = top_extra + grid_h + legend_h + 12
        h = self.card_start_height(title, body_h)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, title)
        for i, _p in enumerate(profiles):
            x = PNG_PAD + CARD_PAD + left + i * cell_w + 18
            draw.text((x, y0), f"#{i + 1}", fill=_MUTED, font=self.font_sm)
        for fi, family in enumerate(families):
            y = y0 + top_extra + fi * cell_h
            draw.text((PNG_PAD + CARD_PAD, y + 4), str(family)[:14], fill=_MUTED, font=self.font_sm)
            for pi, p in enumerate(profiles):
                cell = cell_map.get(f"{family}|{p.get('profile_key')}")
                rate = None if not cell else cell.get("got_root_rate")
                x = PNG_PAD + CARD_PAD + left + pi * cell_w
                if rate is None:
                    fill = _TRACK
                    label = "—"
                else:
                    try:
                        a = 0.12 + float(rate) * 0.75
                        fill = (0, int(255 * a), 0)
                        label = _fmt_pct(rate, 0)
                    except (TypeError, ValueError):
                        fill = _TRACK
                        label = "—"
                draw.rectangle([x, y, x + cell_w - 3, y + cell_h - 3], outline=_BORDER, fill=fill)
                draw.text((x + 8, y + 5), label, fill=_TEXT, font=self.font_sm)
        y = y0 + top_extra + grid_h + 8
        for idx, p in enumerate(profiles):
            draw.rectangle(
                [PNG_PAD + CARD_PAD, y + 2, PNG_PAD + CARD_PAD + 8, y + 10],
                fill=_rgb(_color(idx)),
            )
            label = f"#{idx + 1} {p.get('profile_label') or ''}"
            draw.text(
                (PNG_PAD + CARD_PAD + 14, y),
                self.wrap(label, self.font_sm, self.width - 2 * PNG_PAD - 40)[0],
                fill=_MUTED,
                font=self.font_sm,
            )
            y += 18
        self.add(img)

    def trend_card(self, title: str, points: Sequence[Dict[str, Any]]) -> None:
        if not points or len(points) < 2:
            self.simple_note_card(title, "Need at least two dated runs for a trend")
            return
        plot_h = 180
        body_h = plot_h + 36
        h = self.card_start_height(title, body_h)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, title)
        left = PNG_PAD + CARD_PAD + 20
        right = self.width - PNG_PAD - CARD_PAD
        top = y0 + 20
        bottom = top + plot_h - 30
        max_passed = max(int(p.get("cumulative_passed") or 0) for p in points) or 1
        draw.line([left, bottom, right, bottom], fill=_BORDER)
        draw.line([left, top, left, bottom], fill=_BORDER)
        rate_pts = []
        count_pts = []
        for i, p in enumerate(points):
            x = left + int(i / (len(points) - 1) * (right - left))
            rate = float(p.get("cumulative_pass_rate") or 0)
            count = float(p.get("cumulative_passed") or 0)
            yr = bottom - int(rate * (bottom - top))
            yc = bottom - int((count / max_passed) * (bottom - top))
            rate_pts.append((x, yr))
            count_pts.append((x, yc))
        if len(rate_pts) >= 2:
            draw.line(rate_pts, fill=_ACCENT, width=2)
        if len(count_pts) >= 2:
            draw.line(count_pts, fill=_rgb("#66ff33"), width=1)
        draw.text((left, top - 16), "Cum. pass rate / passed", fill=_MUTED, font=self.font_sm)
        draw.text((left, bottom + 8), str(points[0].get("date") or ""), fill=_MUTED, font=self.font_sm)
        last = str(points[-1].get("date") or "")
        tw = self.text_size(last, self.font_sm)[0]
        draw.text((right - tw, bottom + 8), last, fill=_MUTED, font=self.font_sm)
        self.add(img)

    def radar_card(self, title: str, radar_rows: Sequence[Dict[str, Any]]) -> None:
        rows = list(radar_rows)[:6]
        if not rows:
            self.simple_note_card(title, "No radar scores")
            return
        axes = ["success", "speed", "token_efficiency", "request_efficiency"]
        labels = ["Success", "Speed", "Tokens", "Requests"]
        plot = 220
        body_h = plot + len(rows) * 18 + 8
        h = self.card_start_height(title, body_h)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, title)
        cx = self.width // 2
        cy = y0 + 100
        radius = 80

        def ang(i: int) -> float:
            return (-math.pi / 2) + (i * 2 * math.pi) / len(axes)

        for ring in range(1, 5):
            rr = radius * ring / 4
            pts = [
                (cx + math.cos(ang(i)) * rr, cy + math.sin(ang(i)) * rr)
                for i in range(len(axes))
            ]
            draw.polygon(pts, outline=_TRACK)
        for i, lab in enumerate(labels):
            a = ang(i)
            x2 = cx + math.cos(a) * radius
            y2 = cy + math.sin(a) * radius
            draw.line([(cx, cy), (x2, y2)], fill=_TRACK)
            draw.text(
                (cx + math.cos(a) * (radius + 14) - 18, cy + math.sin(a) * (radius + 14) - 6),
                lab,
                fill=_MUTED,
                font=self.font_sm,
            )
        for idx, row in enumerate(rows):
            pts = []
            for i, key in enumerate(axes):
                axes_map = row.get("axes") or {}
                try:
                    score = float(axes_map.get(key) or 0)
                except (TypeError, ValueError):
                    score = 0.0
                score = max(0.0, min(100.0, score))
                a = ang(i)
                rr = (score / 100.0) * radius
                pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
            color = _rgb(_color(idx))
            draw.polygon(pts, outline=color)
        y = y0 + plot
        for idx, row in enumerate(rows):
            draw.rectangle(
                [PNG_PAD + CARD_PAD, y + 2, PNG_PAD + CARD_PAD + 8, y + 10],
                fill=_rgb(_color(idx)),
            )
            label = f"#{idx + 1} {row.get('profile_label') or ''}"
            draw.text(
                (PNG_PAD + CARD_PAD + 14, y),
                self.wrap(label, self.font_sm, self.width - 2 * PNG_PAD - 40)[0],
                fill=_MUTED,
                font=self.font_sm,
            )
            y += 18
        self.add(img)

    def scatter_card(self, title: str, rows: Sequence[Dict[str, Any]]) -> None:
        points = []
        for i, r in enumerate(rows):
            try:
                x = r.get("score_percent")
                y = r.get("usable_mean_tokens_to_root")
                if x is None or y is None or float(y) <= 0:
                    continue
                points.append((i, float(x), float(y), int(r.get("attempted") or 1), r))
            except (TypeError, ValueError):
                continue
        if not points:
            self.simple_note_card(title, "Need success rate + usable tokens-to-root")
            return
        plot_h = 200
        body_h = plot_h + len(points) * 18 + 24
        h = self.card_start_height(title, body_h)
        img, draw = self._new(h)
        y0 = self.draw_card_chrome(draw, h, title)
        left = PNG_PAD + CARD_PAD + 30
        right = self.width - PNG_PAD - CARD_PAD - 10
        top = y0 + 10
        bottom = top + plot_h - 40
        max_y = max(p[2] for p in points) * 1.15
        max_n = max(p[3] for p in points)
        draw.line([left, bottom, right, bottom], fill=_BORDER)
        draw.line([left, top, left, bottom], fill=_BORDER)
        draw.text((left + 80, bottom + 8), "Success rate (%)", fill=_MUTED, font=self.font_sm)
        for i, x, yv, n, _row in points:
            px = left + int((x / 100.0) * (right - left))
            py = bottom - int((yv / max_y) * (bottom - top))
            r = 4 + int((n / max_n) * 6)
            draw.ellipse([px - r, py - r, px + r, py + r], fill=_rgb(_color(i)), outline=_ACCENT)
            draw.text((px + r + 2, py - 6), f"#{i + 1}", fill=_TEXT, font=self.font_sm)
        y = top + plot_h
        for i, _x, _yv, _n, row in points:
            draw.rectangle(
                [PNG_PAD + CARD_PAD, y + 2, PNG_PAD + CARD_PAD + 8, y + 10],
                fill=_rgb(_color(i)),
            )
            label = f"#{i + 1} {row.get('profile_label') or ''}"
            draw.text(
                (PNG_PAD + CARD_PAD + 14, y),
                self.wrap(label, self.font_sm, self.width - 2 * PNG_PAD - 40)[0],
                fill=_MUTED,
                font=self.font_sm,
            )
            y += 18
        self.add(img)

    def compose(self, path: Path) -> Path:
        from PIL import Image

        if not self.parts:
            img = Image.new("RGB", (self.width, 200), _BG)
            img.save(path, format="PNG", optimize=True)
            return path
        total_h = sum(p.height for p in self.parts) + PNG_PAD
        out = Image.new("RGB", (self.width, total_h), _BG)
        y = PNG_PAD // 2
        for part in self.parts:
            out.paste(part, (0, y))
            y += part.height
        path.parent.mkdir(parents=True, exist_ok=True)
        out.save(path, format="PNG", optimize=True)
        return path


def render_leaderboard_export_png(
    master: Optional[Dict[str, Any]],
    path: Path,
) -> Path:
    """Draw a tall vertical PNG matching the export HTML card stack."""
    from ramigpt.benchmark.master_results import build_leaderboard_payload

    payload = build_leaderboard_payload(master, limit=6, metric="got_root_count")
    top = list(payload.get("top") or [])
    charts = payload.get("charts") or {}
    summary = payload.get("summary") or {}
    methodology = payload.get("methodology") or {}
    updated = str(payload.get("updated_at") or "—")

    canvas = _PngCanvas()
    canvas.hero(updated, len(top))
    canvas.summary_row(summary)
    canvas.section_head(
        "Rankings",
        "Top 6 model · hardware profiles. Score = got-root rate on scoreable attempts.",
    )
    canvas.table_card(top)
    canvas.bar_card(
        "Resolved (got root)",
        top,
        get_value=lambda r: r.get("got_root_count"),
        format_value=_fmt_int,
        empty="No resolved counts",
    )
    canvas.bar_card(
        "Success rate",
        top,
        get_value=lambda r: None
        if r.get("got_root_rate") is None
        else float(r["got_root_rate"]) * 100,
        format_value=lambda v: f"{_fmt_num(v, 1)}%",
        max_hint=100,
        empty="No success rates",
    )
    canvas.section_head(
        "Efficiency",
        "Tokens, speed, and request cost on successful root escalations.",
    )
    canvas.grouped_card("Input vs tokens to root", top)
    canvas.bar_card(
        "Time to root",
        top,
        get_value=lambda r: r.get("mean_elapsed_to_root"),
        format_value=lambda v: f"{_fmt_num(v, 1)}s",
        empty="No time-to-root data",
    )
    canvas.bar_card(
        "AI requests to root",
        top,
        get_value=lambda r: r.get("mean_ai_requests_to_root"),
        format_value=lambda v: _fmt_num(v, 2),
        empty="No AI request data",
    )
    canvas.bar_card(
        "Commands to root",
        top,
        get_value=lambda r: r.get("mean_commands_to_root"),
        format_value=lambda v: _fmt_num(v, 2),
        empty="No command data",
    )
    canvas.bar_card(
        "Tokens / sec to root",
        top,
        get_value=lambda r: r.get("usable_tokens_per_second_to_root")
        or r.get("tokens_per_second_to_root"),
        format_value=lambda v: _fmt_num(v, 2),
        empty="No usable tokens/sec (zeros excluded)",
    )
    canvas.radar_card("Multi-axis score", charts.get("radar") or [])
    canvas.scatter_card("Success vs token efficiency", top)
    canvas.section_head(
        "Coverage",
        "Sample size, lab families, and how much of the catalog each Top 6 has tried.",
    )
    canvas.stacked_card("Resolved vs unresolved", top)
    canvas.bar_card(
        "Catalog attempt coverage",
        charts.get("coverage") or [],
        get_label=lambda r: str(r.get("profile_label") or "—"),
        get_value=lambda r: None
        if r.get("coverage_rate") is None
        else float(r["coverage_rate"]) * 100,
        format_value=lambda v: f"{_fmt_num(v, 1)}%",
        max_hint=100,
        empty="No coverage data",
    )
    canvas.heatmap_card("Success by lab family", charts.get("family_heatmap") or {})
    canvas.section_head(
        "Context",
        "Trends, hardware, and tool-profile impact across collaborative runs.",
    )
    canvas.trend_card("Benchmark trend", charts.get("trend") or [])
    canvas.bar_card(
        "Hardware comparison",
        charts.get("hardware_comparison") or [],
        get_label=lambda r: f"{r.get('model_key_name')} · {r.get('hardware_label') or r.get('hardware_key')}",
        get_value=lambda r: None
        if r.get("got_root_rate") is None
        else float(r["got_root_rate"]) * 100,
        format_value=lambda v: f"{_fmt_num(v, 1)}%",
        max_hint=100,
        empty="No multi-hardware comparisons yet",
    )
    canvas.bar_card(
        "Tools impact",
        charts.get("tools_impact") or [],
        get_label=lambda r: str(r.get("tools_label") or "none"),
        get_value=lambda r: None
        if r.get("got_root_rate") is None
        else float(r["got_root_rate"]) * 100,
        format_value=lambda v: f"{_fmt_num(v, 1)}%",
        max_hint=100,
        empty="No tools impact data",
    )
    method_lines = [
        methodology.get("score"),
        methodology.get("resolved"),
        methodology.get("tokens"),
        methodology.get("trend"),
    ]
    canvas.text_card("Methodology", [m for m in method_lines if m])
    return canvas.compose(path)


def write_leaderboard_exports(
    master: Optional[Dict[str, Any]],
    *,
    results_dir: Optional[Path] = None,
    image_path: Optional[Path] = None,
) -> Dict[str, Path]:
    """Write leaderboard.html + benchmark_leaderboard.png from master data."""
    ensure_runtime_dirs()
    root = results_dir or BENCHMARK_RESULTS_DIR
    root.mkdir(parents=True, exist_ok=True)
    html_path = root / LEADERBOARD_HTML_NAME
    png_path = image_path or (DOCS_DIR / "screenshots" / "benchmark_leaderboard.png")
    png_path.parent.mkdir(parents=True, exist_ok=True)

    html_path.write_text(format_leaderboard_export_html(master), encoding="utf-8")
    render_leaderboard_export_png(master, png_path)
    _log_info(f"leaderboard export → {html_path} + {png_path}")
    return {"html": html_path, "png": png_path}


def ensure_readme_leaderboard_image(readme: str) -> Tuple[str, bool]:
    """Ensure the leaderboard PNG markdown sits above ``## Project layout``."""
    from ramigpt.benchmark.master_results import README_PROJECT_LAYOUT_HEADING

    image_line = README_LEADERBOARD_IMAGE_MD
    # Drop any existing occurrences of this image markdown.
    lines = readme.splitlines(keepends=True)
    filtered: List[str] = []
    skip_blank_after_image = False
    for line in lines:
        stripped = line.strip()
        if "docs/screenshots/benchmark_leaderboard.png" in stripped and stripped.startswith("!["):
            skip_blank_after_image = True
            continue
        if skip_blank_after_image and stripped == "":
            skip_blank_after_image = False
            continue
        skip_blank_after_image = False
        filtered.append(line)
    text = "".join(filtered)

    heading = README_PROJECT_LAYOUT_HEADING
    pattern_idx = text.find(f"\n{heading}\n")
    if pattern_idx < 0:
        if text.startswith(f"{heading}\n"):
            insert_at = 0
            prefix = ""
            suffix = text
        else:
            # No Project layout heading — leave image omitted rather than guess.
            return text, text != readme
    else:
        insert_at = pattern_idx + 1  # point at heading start
        prefix = text[:insert_at]
        suffix = text[insert_at:]

    # Normalize: end prefix with a blank line, then image, blank line, heading…
    prefix = prefix.rstrip("\n")
    block = f"{prefix}\n\n{image_line}\n\n{suffix.lstrip()}"
    if not block.endswith("\n"):
        block += "\n"
    return block, block != readme
