# RTL probe of usvg/resvg text (2026-10-29)

`mk.py` writes 19 one-line SVGs (Hebrew/Arabic/Persian punctuation, brackets, numbers, math, emoji, niqqud/tashkeel,
joining across tspans, letter-spacing, LTR embeds, chunks, underline) and an HTML wrapper each (Amiri by @font-face;
Arial Hebrew, Apple Color Emoji, Arial Unicode MS from the system). Rendered with resvg main (e1a4c92), resvg #1184
(0ba954c, `--use-fonts-dir .`), Chromium 131 and Firefox 158; `sheet.py` makes the sheets.

- #1184 orders every case as both browsers do. main has no `direction`, so everything runs off the right edge.
- Emoji mixed with other text fail: usvg's fallback reshapes the whole text in the fallback font and merges by glyph
  index, stopping when the counts differ (any ZWJ/skin-tone/flag/VS16 sequence). With Apple Color Emoji primary, the
  emoji draw and the Hebrew/Arabic go missing (`emoji-fallback-isolation.png`). linebender/resvg#1087 merges by
  cluster instead; it conflicts with #1184's `shape_text`.
- The font-family list is ignored after the first family: fallback walks the font database (Arial Unicode MS instead
  of Arial Hebrew). he-punct goes from 5.8 % to 2.1 % off Firefox with Arial Hebrew named alone. #1036 / #1041.
- Joining across a colour change: resvg = Chromium (joined); Firefox breaks it. Letter-spacing on Arabic: resvg =
  Firefox (none applied); Chromium spaces the letters.
