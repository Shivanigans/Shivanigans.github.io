/* dc-lite — the small binding layer these pages run on.
 *
 * It replaces the Claude Design canvas runtime. Nothing here is a framework:
 * it walks the page once, remembers where the bindings are, and updates just
 * those spots whenever state changes. Inputs keep their caret because nothing
 * is re-created.
 *
 * Markup contract
 *   {{ expr }}                      in any text or attribute value
 *   <x-if value="{{ expr }}">       children exist while expr is truthy
 *   <x-for list="{{ expr }}" as="item">   children repeat per entry
 *   on-click="{{ fn }}"             also on-change, on-submit, on-input,
 *                                   on-focus, on-blur, on-mouseenter, on-mouseleave
 *   ref="{{ refObject }}"           stores the element on refObject.current
 *   class-hover="hv-3"              a plain class; the rule lives in the page CSS
 *
 * Page contract
 *   class Page extends DCLogic { state = {…}; renderVals() { return {…}; } }
 *   DC.mount(Page, document.getElementById('app'), props);
 *
 * `expr` is a dotted path (v.firstName, errs.state.show) or a literal
 * (true, false, null, a number, a quoted string). Keep it that simple —
 * anything cleverer belongs in renderVals().
 */
(function (global) {
  'use strict';

  var EVENT_ATTRS = {
    'on-click': 'click',
    'on-input': 'input',
    'on-submit': 'submit',
    'on-focus': 'focus',
    'on-blur': 'blur',
    'on-mouseenter': 'mouseenter',
    'on-mouseleave': 'mouseleave'
  };

  // Attributes that are present-or-absent rather than string valued.
  var BOOLEAN_ATTRS = ['required', 'disabled', 'hidden', 'open', 'readonly', 'multiple'];

  var MUSTACHE = /\{\{([^}]*)\}\}/g;

  // --- expression evaluation ------------------------------------------------

  function resolve(scope, expr) {
    expr = expr.trim();
    if (expr === 'true') return true;
    if (expr === 'false') return false;
    if (expr === 'null') return null;
    if (/^-?\d+(\.\d+)?$/.test(expr)) return Number(expr);
    var quoted = expr.match(/^'(.*)'$/) || expr.match(/^"(.*)"$/);
    if (quoted) return quoted[1];

    var value = scope;
    var parts = expr.split('.');
    for (var i = 0; i < parts.length; i++) {
      if (value == null) return undefined;
      value = value[parts[i]];
    }
    return value;
  }

  // "{{ x }}" on its own returns the real value; mixed text returns a string.
  function soleExpression(text) {
    var m = text.match(/^\s*\{\{([^}]*)\}\}\s*$/);
    return m ? m[1] : null;
  }

  function interpolate(scope, template) {
    return template.replace(MUSTACHE, function (_, expr) {
      var value = resolve(scope, expr);
      return value == null ? '' : String(value);
    });
  }

  function evaluate(scope, template) {
    var sole = soleExpression(template);
    return sole === null ? interpolate(scope, template) : resolve(scope, sole);
  }

  // --- compiling ------------------------------------------------------------
  //
  // compile() walks a subtree once and returns an update(scope) function that
  // re-runs every binding it found. x-if and x-for compile their children
  // lazily, into their own nested update functions.

  function compile(root) {
    var bindings = [];
    var child = root.firstChild;
    while (child) {
      var next = child.nextSibling;
      compileNode(child, bindings);
      child = next;
    }
    return function update(scope) {
      for (var i = 0; i < bindings.length; i++) bindings[i](scope);
    };
  }

  function compileNode(node, bindings) {
    if (node.nodeType === 3) {
      if (node.nodeValue.indexOf('{{') !== -1) {
        var template = node.nodeValue;
        bindings.push(function (scope) {
          var text = interpolate(scope, template);
          if (node.nodeValue !== text) node.nodeValue = text;
        });
      }
      return;
    }
    if (node.nodeType !== 1) return;

    var tag = node.tagName.toLowerCase();
    if (tag === 'x-if') return compileIf(node, bindings);
    if (tag === 'x-for') return compileFor(node, bindings);

    compileAttributes(node, bindings);

    var child = node.firstChild;
    while (child) {
      var next = child.nextSibling;
      compileNode(child, bindings);
      child = next;
    }
  }

  function takeChildren(element) {
    var template = document.createDocumentFragment();
    while (element.firstChild) template.appendChild(element.firstChild);
    return template;
  }

  // Build one instance of a template: compile it, then keep hold of its nodes
  // so it can be removed again later.
  function instantiate(template, anchor) {
    var fragment = template.cloneNode(true);
    var update = compile(fragment);
    var nodes = Array.prototype.slice.call(fragment.childNodes);
    anchor.parentNode.insertBefore(fragment, anchor);
    return { nodes: nodes, update: update };
  }

  function removeInstance(instance) {
    for (var i = 0; i < instance.nodes.length; i++) {
      var node = instance.nodes[i];
      if (node.parentNode) node.parentNode.removeChild(node);
    }
  }

  function compileIf(element, bindings) {
    var test = element.getAttribute('value');
    var template = takeChildren(element);
    var anchor = document.createComment(' if ' + test + ' ');
    element.parentNode.replaceChild(anchor, element);

    var instance = null;
    bindings.push(function (scope) {
      var on = !!evaluate(scope, test);
      if (on && !instance) instance = instantiate(template, anchor);
      else if (!on && instance) { removeInstance(instance); instance = null; }
      if (instance) instance.update(scope);
    });
  }

  function compileFor(element, bindings) {
    var listExpr = element.getAttribute('list');
    var name = element.getAttribute('as');
    var template = takeChildren(element);
    var anchor = document.createComment(' for ' + name + ' ');
    element.parentNode.replaceChild(anchor, element);

    var instances = [];
    bindings.push(function (scope) {
      var list = evaluate(scope, listExpr) || [];
      while (instances.length > list.length) removeInstance(instances.pop());
      while (instances.length < list.length) instances.push(instantiate(template, anchor));
      for (var i = 0; i < list.length; i++) {
        // Inherit the page scope so {{ userName }} still resolves inside a loop.
        var itemScope = Object.create(scope);
        itemScope[name] = list[i];
        itemScope[name + 'Index'] = i;
        instances[i].update(itemScope);
      }
    });
  }

  // React's onChange fires per keystroke on text fields but on commit for
  // pickers, so route it to whichever DOM event matches that.
  function changeEventFor(element) {
    if (element.tagName === 'SELECT') return 'change';
    var type = (element.getAttribute('type') || '').toLowerCase();
    if (type === 'checkbox' || type === 'radio' || type === 'file') return 'change';
    return 'input';
  }

  function bindEvent(element, eventName, expr, bindings) {
    var handler = null;
    element.addEventListener(eventName, function (event) {
      if (typeof handler === 'function') handler(event);
    });
    bindings.push(function (scope) { handler = resolve(scope, expr); });
  }

  function compileAttributes(element, bindings) {
    var attrs = Array.prototype.slice.call(element.attributes);

    for (var i = 0; i < attrs.length; i++) {
      var name = attrs[i].name;
      var value = attrs[i].value;

      if (name === 'class-hover') {
        element.classList.add(value);
        element.removeAttribute(name);
        continue;
      }

      if (name === 'on-change') {
        element.removeAttribute(name);
        bindEvent(element, changeEventFor(element), soleExpression(value) || '', bindings);
        continue;
      }

      if (EVENT_ATTRS[name]) {
        element.removeAttribute(name);
        bindEvent(element, EVENT_ATTRS[name], soleExpression(value) || '', bindings);
        continue;
      }

      if (value.indexOf('{{') === -1) continue;

      if (name === 'ref') {
        var refExpr = soleExpression(value);
        element.removeAttribute(name);
        bindings.push(function (scope) {
          var ref = resolve(scope, refExpr);
          if (ref) ref.current = element;
        });
        continue;
      }

      // Form state lives on the property, not the attribute: writing the
      // attribute would not move the caret or tick the box.
      if (name === 'value' || name === 'checked') {
        bindProperty(element, name, value, bindings);
        element.removeAttribute(name);
        continue;
      }

      bindAttribute(element, name, value, bindings);
    }
  }

  function bindProperty(element, name, template, bindings) {
    bindings.push(function (scope) {
      var value = evaluate(scope, template);
      if (name === 'checked') value = !!value;
      else value = value == null ? '' : String(value);
      if (element[name] !== value) element[name] = value;
    });
  }

  function bindAttribute(element, name, template, bindings) {
    var isBoolean = BOOLEAN_ATTRS.indexOf(name) !== -1;
    bindings.push(function (scope) {
      var value = evaluate(scope, template);

      if (isBoolean && typeof value === 'boolean') {
        if (value) element.setAttribute(name, '');
        else element.removeAttribute(name);
        return;
      }
      var text = value == null ? '' : String(value);
      if (element.getAttribute(name) !== text) element.setAttribute(name, text);
    });
  }

  // --- page base class ------------------------------------------------------

  function DCLogic(props) {
    this.props = props || {};
    if (!this.state) this.state = {};
  }

  DCLogic.prototype.componentDidMount = function () {};
  DCLogic.prototype.renderVals = function () { return {}; };

  DCLogic.prototype.setState = function (patch) {
    var next = typeof patch === 'function' ? patch(this.state) : patch;
    var merged = {};
    var key;
    for (key in this.state) merged[key] = this.state[key];
    for (key in next) merged[key] = next[key];
    this.state = merged;
    scheduleUpdate(this);
  };

  var pending = null;

  function scheduleUpdate(page) {
    if (pending) return;
    pending = Promise.resolve().then(function () {
      pending = null;
      page.render();
    });
  }

  var DC = {
    ref: function () { return { current: null }; },

    mount: function (PageClass, root, props) {
      var page = new PageClass(props);
      var update = compile(root);
      page.render = function () { update(page.renderVals()); };
      page.render();
      page.componentDidMount();
      page.render();
      return page;
    }
  };

  global.DCLogic = DCLogic;
  global.DC = DC;
})(window);
