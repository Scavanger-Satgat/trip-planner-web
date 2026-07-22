"""Fill templates/page_template.html with a validated itinerary + geocoded map data.

No jinja2 — plain string building with html.escape discipline, spliced into
the template via stdlib string.Template.
"""
import html
import json
import string
import urllib.parse
from pathlib import Path

import theme

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "page_template.html"


def _esc(value):
    return html.escape(str(value)) if value is not None else ""


def _naver_search_url(name):
    return "https://map.naver.com/p/search/" + urllib.parse.quote(name)


def _render_meta_chips(chips):
    return "\n".join(f'      <span class="meta-chip">{_esc(c)}</span>' for c in chips)


def _render_day_tabs(days):
    parts = []
    for i, day in enumerate(days):
        selected = "true" if i == 0 else "false"
        parts.append(
            f'    <button class="day-tab" role="tab" data-day="{day["day_number"]}" '
            f'aria-selected="{selected}">\n'
            f'      <span class="tab-date">{_esc(day.get("date_label", ""))}</span>\n'
            f'      <span class="tab-theme">{_esc(day.get("theme_label", ""))}</span>\n'
            f"    </button>"
        )
    return "\n".join(parts)


def _render_card(place, extra_class=""):
    category = place.get("category", "activity")
    tag_labels = {"food": "맛집", "cafe": "카페", "activity": "액티비티", "special": "특별한 곳"}
    tag_label = tag_labels.get(category, category)

    price_html = f'\n        <div class="price">{_esc(place["price"])}</div>' if place.get("price") else ""
    caution_html = (
        f'\n        <div class="caution">{_esc(place["caution"])}</div>' if place.get("caution") else ""
    )

    return (
        f'      <div class="card{" " + extra_class if extra_class else ""}"'
        f' data-category="{_esc(category)}">\n'
        f'        <div class="card-top"><h3>{_esc(place.get("name", ""))}</h3>'
        f'<span class="tag {_esc(category)}">{_esc(tag_label)}</span></div>\n'
        f'        <div class="loc">{_esc(place.get("location_note", ""))}</div>\n'
        f'        <div class="desc">{_esc(place.get("description", ""))}</div>'
        f"{price_html}{caution_html}\n"
        f'        <a class="card-map" href="{_naver_search_url(place.get("name", ""))}" '
        f'target="_blank" rel="noopener noreferrer">네이버 지도에서 보기</a>\n'
        f"      </div>"
    )


def _render_route(stops, transit_notes, unresolved_names):
    parts = ['    <div class="route">']
    for i, stop in enumerate(stops):
        name = stop.get("name", "")
        note = stop.get("location_note", "") or stop.get("stop_note", "")
        unresolved_marker = " (위치 미확인)" if name in unresolved_names else ""
        parts.append(
            '      <div class="stop">\n'
            '        <div class="stop-head">\n'
            f'          <span class="stop-name">{_esc(name)}{_esc(unresolved_marker)}</span>\n'
            f'          <a class="map-link" href="{_naver_search_url(name)}" '
            f'target="_blank" rel="noopener noreferrer">지도</a>\n'
            "        </div>\n"
            f'        <div class="stop-note">{_esc(note)}</div>\n'
            "      </div>"
        )
        if i < len(transit_notes):
            parts.append(f'      <div class="transit">{_esc(transit_notes[i])}</div>')
    parts.append("    </div>")
    return "\n".join(parts)


def _render_callouts(callouts):
    parts = []
    for c in callouts:
        cls = "callout good" if c.get("type") == "good" else "callout"
        parts.append(f'    <div class="{cls}">{_esc(c.get("text", ""))}</div>')
    return "\n".join(parts)


def _render_day_panel(day, unresolved_names, is_first):
    day_number = day["day_number"]
    active_class = " active" if is_first else ""
    hidden_attr = "" if is_first else " hidden"

    stats_html = " · ".join(f"<b>{_esc(s)}</b>" for s in day.get("stats", []))
    cards_html = "\n".join(_render_card(c) for c in day.get("cards", []))
    callouts_html = _render_callouts(day.get("callouts", []))
    alt_line_html = (
        f'    <div class="alt-line">{_esc(day["alt_line"])}</div>' if day.get("alt_line") else ""
    )

    return f"""  <section class="day-panel{active_class}" data-panel="{day_number}" role="tabpanel"{hidden_attr}>
    <div class="day-head">
      <h2>{_esc(day.get("title", ""))}</h2>
      <span class="day-sub">{_esc(day.get("subtitle", ""))}</span>
    </div>
    <div class="day-stats">{stats_html}</div>
    <div id="map-{day_number}" class="day-map">지도를 불러오는 중...</div>
{_render_route(day.get("stops", []), day.get("transit_notes", []), unresolved_names)}
    <div class="cards">
{cards_html}
    </div>
{callouts_html}
{alt_line_html}
  </section>"""


def render_page(itinerary, map_data, day_routes, ncp_key_id, accent_hex=theme.DEFAULT_ACCENT):
    days = itinerary.get("days", [])
    unresolved_names = set()  # populated by caller via itinerary["_unresolved_names"] if present
    if "_unresolved_names" in itinerary:
        unresolved_names = set(itinerary["_unresolved_names"])

    themes = theme.derive_theme(accent_hex)
    accent_css_light = theme.css_vars_block(themes["light"])
    accent_css_dark = theme.css_vars_block(themes["dark"])

    day_panels_html = "\n\n".join(
        _render_day_panel(day, unresolved_names, i == 0) for i, day in enumerate(days)
    )
    pool_cards_html = "\n".join(_render_card(p) for p in itinerary.get("pool", []))
    footer_notes_html = "\n".join(
        f'      <li><b>{_esc(n.get("label", ""))}</b> — {_esc(n.get("text", ""))}</li>'
        for n in itinerary.get("footer_notes", [])
    )

    # DAY_ROUTES keys must be strings matching data-day attributes for JS object lookup consistency.
    day_routes_for_json = {str(k): v for k, v in day_routes.items()}

    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    filled = string.Template(template_text).substitute(
        accent_css_light=accent_css_light,
        accent_css_dark=accent_css_dark,
        title=_esc(itinerary.get("trip_title", "여행 계획")),
        dates_text=_esc(f'{itinerary.get("start_date", "")} – {itinerary.get("end_date", "")}'),
        meta_chips_html=_render_meta_chips(itinerary.get("meta_chips", [])),
        day_count=max(len(days), 1),
        day_tabs_html=_render_day_tabs(days),
        day_panels_html=day_panels_html,
        pool_grid_html=pool_cards_html,
        footer_notes_html=footer_notes_html,
        ncp_key_id=ncp_key_id,
        map_data_json=json.dumps(map_data, ensure_ascii=False),
        day_routes_json=json.dumps(day_routes_for_json, ensure_ascii=False),
        first_day_number=str(days[0]["day_number"]) if days else "1",
    )
    return filled
