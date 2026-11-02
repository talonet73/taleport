"""Plain text to copy for each platform, built from the structured draft."""

from __future__ import annotations

from taleport.core.i18n import tr
from taleport.generator.schemas import GeneratedPost


def hashtag_line(tags: list[str]) -> str:
    return " ".join(f"#{tag}" for tag in tags)


def render_copy_text(post: GeneratedPost, ui_language: str) -> str:
    parts: list[str] = []
    if post.platform == "youtube":
        if post.title:
            parts.append(post.title)
        if post.text:
            parts.append(post.text)
        if post.outline:
            parts.append(
                tr(ui_language, "render.outline") + "\n" + "\n".join(f"- {o}" for o in post.outline)
            )
    elif post.platform == "tiktok":
        if post.hook:
            parts.append(f"{tr(ui_language, 'render.hook')}: {post.hook}")
        if post.script:
            lines = [
                f"[{line.time}] {line.voiceover}" + (f" ({line.scene})" if line.scene else "")
                for line in post.script
            ]
            parts.append(tr(ui_language, "render.script") + "\n" + "\n".join(lines))
        if post.text:
            parts.append(post.text)
    else:
        body = post.text
        if post.hook and not body.startswith(post.hook):
            body = f"{post.hook}\n\n{body}" if body else post.hook
        if body:
            parts.append(body)
    tags = [t for t in post.hashtags if f"#{t}".lower() not in "\n".join(parts).lower()]
    if tags:
        parts.append(hashtag_line(tags))
    return "\n\n".join(p.strip() for p in parts if p.strip())
