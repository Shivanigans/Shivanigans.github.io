#!/usr/bin/env python3
"""One-off migration: Claude Design bundle -> plain HTML/CSS/JS.

Reads the four exported .html bundles, unpacks their embedded manifest
(fonts, images, template) and rewrites the canvas runtime's custom markup
into standard HTML plus a small binding layer (assets/js/dc-lite.js).
"""
import base64, hashlib, json, os, re, shutil, sys, zlib

SRC = sys.argv[1]
OUT = sys.argv[2]

PAGES = {
    '1efda949-index.html': 'index',
    '59c1221b-login.html': 'login',
    '428d7242-form6-prep.html': 'form6-prep',
    '363363ec-form6-application.html': 'form6-application',
}

IMAGE_NAMES = {
    'Election Commission of India': 'eci-logo',
    'Laptop showing an application status tracker': 'status-tracker',
    'Hand holding a Form 6 application': 'form6-hand',
    'Laptop showing a voter list search': 'voter-list-search',
    'Hand holding a Form 8 correction form': 'form8-hand',
}

# One illustration carries no alt text (it is decorative), so name it by hand.
IMAGE_UUIDS = {'0cd92160-e0e9-4d47-85a0-5a93455ebdb9': 'form6-illustration'}

SC_CAMEL = {
    'view-box': 'viewBox',
    'on-click': 'on-click',
    'on-change': 'on-change',
    'on-submit': 'on-submit',
    'on-focus': 'on-focus',
    'on-blur': 'on-blur',
    'on-mouse-enter': 'on-mouseenter',
    'on-mouse-leave': 'on-mouseleave',
    'default-value': 'value',
}


def read_bundle(path):
    src = open(path, encoding='utf-8').read()
    out = {}
    for kind in ('manifest', 'template'):
        m = re.search(r'<script type="__bundler/%s">\s*(.*?)\s*</script>' % kind, src, re.S)
        out[kind] = m.group(1)
    return json.loads(out['manifest']), json.loads(out['template'])


def unpack(entry):
    raw = base64.b64decode(entry['data'])
    if entry.get('compressed'):
        raw = zlib.decompress(raw, 16 + zlib.MAX_WBITS)
    return raw


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


# ---------------------------------------------------------------- assets

written = {}          # sha1 -> published path
uuid_to_path = {}     # per-page uuid -> published path


def publish(data, path):
    """Write bytes once; identical content is shared between pages."""
    key = hashlib.sha1(data).hexdigest()
    if key in written:
        return written[key]
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, 'wb').write(data)
    written[key] = path
    return path


EXTENSIONS = [(b'wOF2', 'woff2'), (b'wOFF', 'woff'), (b'OTTO', 'otf'),
              (b'\x00\x01\x00\x00', 'ttf'), (b'true', 'ttf')]


def extension_of(data):
    for magic, ext in EXTENSIONS:
        if data.startswith(magic):
            return ext
    raise SystemExit('unrecognised font format: %r' % data[:4])


def font_labels(css):
    """Map font uuid -> a readable stem, from the @font-face blocks.

    Two shapes appear: the Google Fonts blocks, one per unicode subset with the
    subset named in a comment just above, and the UX4G layer's own blocks, which
    carry a descriptive comment instead.
    """
    labels = {}
    comment = r'/\*\s*((?:(?!\*/).)*?)\s*\*/\s*'
    for match in re.finditer(r'(?:%s)?@font-face\s*\{(.*?)\}' % comment, css, re.S):
        comment, block = match.group(1), match.group(2)
        src = re.search(r'url\("([0-9a-f-]{36})"\)', block)
        if not src:
            continue
        family = re.search(r'font-family:\s*[\'"]([^\'"]+)[\'"]', block)
        weight = re.search(r'font-weight:\s*(\d+)', block)
        style = re.search(r'font-style:\s*(\w+)', block)

        parts = [slug(family.group(1)) if family else 'font']
        if weight:
            parts.append(weight.group(1))
        if style and style.group(1) != 'normal':
            parts.append(style.group(1))
        if comment:
            parts.append(slug(comment)[:40])
        labels[src.group(1)] = '-'.join(parts)
    return labels


# ---------------------------------------------------------------- markup

def fix_known_export_bug(tpl):
    """The export left one <select> with a style attribute that was cut short by an
    unescaped quote, spilling a stray <polyline> wrapper and a run of CSS text into
    the markup. The select already has a sibling <svg> chevron, so the lost
    background-image rule is redundant; drop the debris and keep the options."""
    broken = re.search(
        r'<polyline points="6 9 12 15 18 9">"\);.*?line-height: 20px;"&gt;(.*?)</polyline>',
        tpl, re.S)
    if not broken:
        return tpl, 0
    return tpl[:broken.start()] + broken.group(1) + tpl[broken.end():], 1


def rewrite_markup(tpl, page):
    hovers = {}

    def hover_class(css):
        css = css.strip().rstrip(';')
        if css not in hovers:
            hovers[css] = 'hv-%d' % (len(hovers) + 1)
        return hovers[css]

    # style-hover="..." -> a real CSS class with a :hover rule
    def sub_hover(m):
        return ' class-hover="%s"' % hover_class(m.group(1))
    tpl = re.sub(r'\s+style-hover="([^"]*)"', sub_hover, tpl)

    # sc-camel-foo-bar -> the attribute the runtime actually wants
    def sub_camel(m):
        name = m.group(1)
        if name not in SC_CAMEL:
            raise SystemExit('unmapped sc-camel attribute: ' + name)
        return ' ' + SC_CAMEL[name] + '='
    tpl = re.sub(r'\s+sc-camel-([a-z-]+)=', sub_camel, tpl)

    # control-flow elements
    tpl = re.sub(r'<sc-if value=("[^"]*")[^>]*>', r'<x-if value=\1>', tpl)
    tpl = tpl.replace('</sc-if>', '</x-if>')
    tpl = re.sub(r'<sc-for list=("[^"]*") as=("[^"]*")[^>]*>', r'<x-for list=\1 as=\2>', tpl)
    tpl = tpl.replace('</sc-for>', '</x-for>')
    tpl = re.sub(r'<sc-raw-select\b', '<select', tpl)
    tpl = tpl.replace('</sc-raw-select>', '</select>')

    # editor-only hints
    tpl = re.sub(r'\s+hint-placeholder-[a-z]+="[^"]*"', '', tpl)

    return tpl, hovers


def expand_static_for(tpl, list_expr, values):
    """<x-for> cannot live inside <select>: the HTML parser drops anything that is
    not an <option>. The office list is static, so write the options out."""
    m = re.search(r'<x-for list="\{\{ %s \}\}" as="(\w+)">(.*?)</x-for>' % list_expr, tpl, re.S)
    if not m:
        raise SystemExit('static for not found: ' + list_expr)
    name, body = m.group(1), m.group(2)
    out = ''.join(body.replace('{{ %s }}' % name, v) for v in values)
    return tpl[:m.start()] + out.strip() + tpl[m.end():]


def split_template(tpl):
    head = re.search(r'<helmet>(.*?)</helmet>', tpl, re.S).group(1)
    body = tpl[tpl.find('</helmet>') + len('</helmet>'):]
    body = body[:body.rfind('</x-dc>')]
    return head, body


# ---------------------------------------------------------------- per page

def convert(filename, page):
    manifest, tpl = read_bundle(os.path.join(SRC, filename))
    notes = []

    # --- fonts and images out of the manifest
    labels = font_labels(''.join(re.findall(r'<style>(.*?)</style>', tpl, re.S)))
    for uuid, entry in manifest.items():
        if entry['mime'] == 'text/javascript':
            continue  # React + the canvas runtime; both go away
        data = unpack(entry)
        if uuid in labels:
            path = 'assets/fonts/%s.%s' % (labels[uuid], extension_of(data))
        elif entry['mime'] == 'image/png':
            alt = (re.search(r'<img[^>]*src="%s"[^>]*alt="([^"]*)"' % uuid, tpl)
                   or re.search(r'<img[^>]*alt="([^"]*)"[^>]*src="%s"' % uuid, tpl))
            name = IMAGE_UUIDS.get(uuid) or IMAGE_NAMES.get(alt.group(1) if alt else '')
            if not name:
                raise SystemExit('unnamed image %s on %s' % (uuid, page))
            path = 'assets/img/%s.png' % name
        else:
            raise SystemExit('unreferenced asset %s (%s)' % (uuid, entry['mime']))
        uuid_to_path[uuid] = publish(data, path)

    # --- known export bug
    tpl, fixed = fix_known_export_bug(tpl)
    if fixed:
        notes.append('repaired a truncated style attribute on the footer state select')

    # --- point every uuid reference at its published file
    def sub_uuid(m):
        uuid = m.group(0)
        if uuid not in uuid_to_path:
            return uuid
        depth_prefix = ''  # pages sit at the repo root
        return depth_prefix + uuid_to_path[uuid]
    tpl = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', sub_uuid, tpl)

    # --- pull the stylesheets out
    blocks = re.findall(r'<style>(.*?)</style>', tpl, re.S)
    sheets = []
    page_css = ''
    for block in blocks:
        # url() resolves against the stylesheet, which sits in assets/css/
        block = block.replace('url("assets/', 'url("../').replace("url('assets/", "url('../")
        if '@layer ux4g-tokens' in block:
            sheets.append(publish(block.encode(), 'assets/css/ux4g.css'))
        elif '@font-face' in block:
            # Deliberately not shared between pages: each page links a sheet
            # named after itself, so editing one cannot surprise another.
            path = 'assets/css/fonts-%s.css' % page
            os.makedirs(os.path.join(OUT, 'assets/css'), exist_ok=True)
            open(os.path.join(OUT, path), 'w').write(block)
            sheets.append(path)
        else:
            page_css = block
    tpl = re.sub(r'<style>.*?</style>', '', tpl, flags=re.S)

    # --- the page logic
    script = re.search(r'<script type="text/x-dc"[^>]*>(.*?)</script>', tpl, re.S)
    logic = script.group(1).strip()
    declared = re.search(r'data-props="([^"]+)"', script.group(0))
    props = json.loads(declared.group(1).replace('&quot;', '"')) if declared else {}
    tpl = tpl.replace(script.group(0), '')

    logic = logic.replace('class Component extends DCLogic', 'class Page extends DCLogic')
    logic = logic.replace('React.createRef()', 'DC.ref()')

    # --- markup rewrites
    tpl, hovers = rewrite_markup(tpl, page)
    if page == 'index':
        tpl = expand_static_for(tpl, 'officeStates',
                                ['Delhi', 'Maharashtra', 'Karnataka', 'Tamil Nadu',
                                 'Uttar Pradesh', 'West Bengal'])
    head, body = split_template(tpl)

    for tag in ('select', 'table', 'tbody', 'tr'):
        for m in re.finditer(r'<%s\b.*?</%s>' % (tag, tag), body, re.S):
            if '<x-if' in m.group(0) or '<x-for' in m.group(0):
                notes.append('WARNING: control flow inside <%s> may be dropped by the parser' % tag)

    title = re.search(r'<title>(.*?)</title>', tpl, re.S).group(1)
    # The Google Fonts preconnects are dead weight now that the fonts are local.
    links = [l for l in re.findall(r'<link [^>]*>', head)
             if 'preconnect' not in l and 'fonts.g' not in l]

    hover_css = '\n'.join('.%s:hover { %s; }' % (cls, css) for css, cls in hovers.items())
    css_out = page_css.strip() + ('\n\n/* hover styles, lifted out of style-hover attributes */\n'
                                  + hover_css if hover_css else '')
    publish_page_css = 'assets/css/%s.css' % page
    os.makedirs(os.path.join(OUT, 'assets/css'), exist_ok=True)
    open(os.path.join(OUT, publish_page_css), 'w').write(css_out + '\n')

    os.makedirs(os.path.join(OUT, 'assets/js'), exist_ok=True)
    default_props = {k: v['default'] for k, v in props.items()}
    js = (logic + '\n\nDC.mount(Page, document.getElementById(\'app\'), '
          + json.dumps(default_props, ensure_ascii=False) + ');\n')
    open(os.path.join(OUT, 'assets/js/%s.js' % page), 'w').write(js)

    sheet_links = '\n'.join('<link rel="stylesheet" href="%s">' % s for s in sheets)
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
%s
%s
<link rel="stylesheet" href="%s">
<style>.dc-loading #app { visibility: hidden; }</style>
<script>
  // Hold the page back until the first render, otherwise the raw {{ }} bindings
  // and every x-if branch flash up at once. dc-lite clears this once it has
  // rendered; the timeout is a failsafe, so a script that fails to load leaves
  // an unbound page rather than a blank one.
  document.documentElement.classList.add('dc-loading');
  setTimeout(function () {
    document.documentElement.classList.remove('dc-loading');
  }, 4000);
</script>
</head>
<body>
<div id="app">%s</div>
<script src="assets/js/dc-lite.js"></script>
<script src="assets/js/%s.js"></script>
</body>
</html>
''' % (title, '\n'.join(links), sheet_links, publish_page_css, body.rstrip(), page)
    open(os.path.join(OUT, page + '.html'), 'w').write(html)

    print('%-20s css=%-28s hovers=%-3d %s'
          % (page, publish_page_css, len(hovers), '; '.join(notes)))


shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dc-lite.js'),
            os.path.join(OUT, 'assets/js/dc-lite.js'))

for filename, page in PAGES.items():
    convert(filename, page)
print('\nassets written:', len(written))
