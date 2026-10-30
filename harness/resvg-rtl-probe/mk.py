#!/usr/bin/env python3
"""RTL probe: one SVG per case, plus an HTML page per case that inlines the SVG and loads Amiri with @font-face,
for Chromium and Firefox. resvg gets Amiri from this directory (--use-fonts-dir .) and the rest from the system."""
import html, os
HE = "'Arial Hebrew'"; AR = 'Amiri'; EMO = "'Apple Color Emoji'"; MATH = "'Arial Unicode MS'"
F = f"{AR}, {HE}, {EMO}, {MATH}"
R = 'direction="rtl" x="580" y="46"'
L = 'direction="ltr" x="20" y="46"'
CASES = {
 'he-punct':    (R, F, 'שלום, עולם! מה שלומך?'),
 'he-brackets': (R, F, 'הוא אמר (בשקט) "כן" [ואז] יצא.'),
 'he-latin-num':(R, F, 'גרסה 0.28 של femtovg יצאה ב-27/10/2026.'),
 'he-percent':  (R, F, 'המחיר ירד ב-15% (מ-200₪ ל-170₪).'),
 'he-math':     (R, F, 'אם x > 3 אז f(x) = x² − 1, נכון?'),
 'ar-math':     (R, F, 'س = ٢ × (ص + ٣) − ٤٫٥'),
 'ar-latin-fn': (R, F, 'الدالة f(x) = x² + 1 متصلة.'),
 'ar-digits':   (R, F, 'من ١٢ إلى ٣٤، أي ٢٢ يومًا (٦٥٪).'),
 'fa-digits':   (R, F, 'قیمت: ۱۲۳٫۴۵ تومان؟'),
 'emoji-ar':    (R, F, 'أحبك ❤️ 👨‍👩‍👧 مرحبا 👍🏽!'),
 'emoji-he':    (R, F, 'תודה 🙏🏽! 🇮🇱 שלום 👋'),
 'he-niqqud':   (R, F, 'שָׁלוֹם עֲלֵיכֶם'),
 'ar-tashkeel': (R, F, 'مَرْحَبًا بِكُمْ'),
 'ar-join-tspan': (R, F, 'كت<tspan fill="#c00">ا</tspan>ب و<tspan fill="#c00">ل</tspan>م'),
 'ar-letterspacing': (R + ' letter-spacing="4"', F, 'مرحبا بالعالم'),
 'ltr-embed-he':(L, F, 'the word (שלום) means [peace].'),
 'ltr-embed-ar':(L, F, 'He said "مرحبا!" and left.'),
 'he-chunks':   ('direction="rtl" y="46"', F, '<tspan x="580">שורה</tspan> <tspan x="380">ב-2 חלקים!</tspan>'),
 'he-underline':(R + ' text-decoration="underline"', F, 'קו תחתון עם English בפנים.'),
}
for name, (attrs, fam, body) in CASES.items():
    text = body if '<tspan' in body else html.escape(body, quote=False)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="70" viewBox="0 0 600 70">'
           f'<rect width="600" height="70" fill="white"/>'
           f'<text {attrs} font-family="{fam}" font-size="28" fill="black">{text}</text></svg>')
    open(f'{name}.svg', 'w').write(svg)
    open(f'{name}.html', 'w').write('<!doctype html><meta charset=utf-8><style>@font-face{font-family:Amiri;src:url(Amiri-Regular.ttf)}'
        'body{margin:0}svg{display:block}</style>' + svg)
print(len(CASES))
