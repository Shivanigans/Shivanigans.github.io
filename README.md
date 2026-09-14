# Election Commission of India — Citizen Service Portal (prototype)

A static prototype of a voter registration journey, served from the root of this
repository by GitHub Pages. It was originally built in Claude Design and has been
converted to plain HTML, CSS and JavaScript so it can be edited directly.

| Page | What it is |
| --- | --- |
| `index.html` | Portal home: search, service cards, SIR banner, help and footer |
| `login.html` | Sign in |
| `form6-prep.html` | "Before you apply" — what you need for Form 6 |
| `form6-application.html` | The Form 6 application itself, with validation and preview |

The pages are linked to each other and pass a `?loggedIn=1` query parameter to
fake a signed-in session. There is no backend; nothing is submitted anywhere.

## Layout

```
index.html, login.html, form6-prep.html, form6-application.html
assets/css/ux4g.css          the UX4G design system, unchanged
assets/css/fonts-*.css       @font-face rules pointing at assets/fonts/
assets/css/<page>.css        that page's own styles, plus its :hover rules
assets/fonts/                Noto Sans subsets and the UX4G icon fonts
assets/img/                  illustrations
assets/js/dc-lite.js         the binding layer every page runs on
assets/js/<page>.js          that page's state and behaviour
portfolio/                   the previous personal site, kept but no longer served at /
tools/                       the one-off migration script
```

## How a page works

Each page is ordinary HTML with a few extra attributes, plus a small class in
`assets/js/<page>.js` that holds the state:

```js
class Page extends DCLogic {
  state = { loggedIn: false };

  renderVals() {
    return {
      userName: 'Ananya Rao',
      isLoggedIn: this.state.loggedIn,
      signIn: () => this.setState({ loggedIn: true }),
    };
  }
}
```

Everything `renderVals()` returns is available to the markup:

```html
<span>{{ userName }}</span>
<x-if value="{{ isLoggedIn }}"> … shown only while signed in … </x-if>
<x-for list="{{ sections }}" as="item"> <li>{{ item.label }}</li> </x-for>
<button on-click="{{ signIn }}">Sign in</button>
```

`setState` re-runs `renderVals()` and updates only the bindings whose values
changed, so typing in a field does not lose the caret.

Each page's `<head>` holds the page back with a `dc-loading` class until that
first render, so the raw `{{ }}` bindings and every `x-if` branch are never shown
at once. `dc-lite` clears the class when it has rendered, and a four second
timeout clears it anyway, so a script that fails to load leaves an unbound page
rather than a blank one.

The full contract — every attribute, and what counts as a valid expression — is
documented at the top of `assets/js/dc-lite.js`. It is about 250 lines; read it
before changing how bindings behave.

### Editing tips

- **Copy, wording, layout**: edit the HTML directly. Styles are inline, as they
  came out of the design tool.
- **Hover styles**: these were inline too, so they live in `assets/css/<page>.css`
  as `.hv-1:hover { … }` and the element carries `class-hover="hv-1"`.
- **Behaviour and data**: edit `assets/js/<page>.js`. The placeholder content —
  office addresses, SIR phase dates, constituency numbers — is there.
- **Expressions in markup** are deliberately limited to dotted paths and literals.
  Anything that needs logic should be computed in `renderVals()` and read back as
  a plain value.
- `<x-if>` and `<x-for>` cannot be used inside `<select>`: the HTML parser drops
  anything there that is not an `<option>`. Write the options out, or build them
  in JavaScript.

## Content accuracy

The Special Intensive Revision dates, the list of states mid-phase, and the
accepted-documents lists are placeholders carried over from the design and were
never verified against the Election Commission's own material. They are marked
with a comment in `assets/js/index.js`. Check them before this is shown to
anyone as representative of real ECI guidance.

## Provenance

`tools/migrate-from-claude-design.py` is the script that produced this site from
the four exported Claude Design bundles. It is kept for reference and is not part
of any build — the files in this repository are the source now. Keep it only if
you expect to re-export from Claude Design; otherwise it can be deleted.

The conversion was checked by running the original bundles and these pages side
by side in Chromium: rendered text matched exactly on all four pages, full-page
screenshots matched to within a handful of hairline pixels, and a scripted run
through the accessibility controls, the language menu, the selects and the form's
accordion and validation produced identical results on both.
