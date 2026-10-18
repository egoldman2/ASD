"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

test("workflow loading and failures preserve the forms and announce status", () => {
  const listeners = {};
  const feedback = {
    attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
  };
  const panel = {
    id: "multi-agent-panel",
    attributes: {},
    querySelector(selector) {
      assert.equal(selector, "#multi-agent-feedback");
      return feedback;
    },
    setAttribute(name, value) { this.attributes[name] = value; },
    set textContent(_) { assert.fail("must preserve question/reason forms"); },
    set innerHTML(_) { assert.fail("must preserve question/reason forms"); },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../frontend/js/support.js"), "utf8"), {
    document: {
      querySelector: () => null,
      addEventListener: (name, callback) => { listeners[name] = callback; },
    },
  });
  const event = { detail: { target: panel } };
  listeners["htmx:beforeRequest"](event);
  assert.equal(panel.attributes["aria-busy"], "true");
  assert.equal(feedback.attributes.role, "status");
  for (const name of ["htmx:timeout", "htmx:sendError"]) {
    listeners[name](event);
    assert.equal(panel.attributes["aria-busy"], "false");
    assert.equal(feedback.attributes.role, "alert");
    assert.match(feedback.textContent, /Reload recorded history before retrying/);
  }
  listeners["htmx:beforeRequest"](event);
  listeners["htmx:afterRequest"]({ detail: { target: feedback, elt: {
    closest(selector) { assert.equal(selector, "#multi-agent-panel"); return panel; },
  } } });
  assert.equal(panel.attributes["aria-busy"], "false");
  const error = { detail: { xhr: { status: 504 } } };
  listeners["htmx:beforeSwap"](error);
  assert.equal(error.detail.shouldSwap, true);
  assert.equal(error.detail.isError, false);
  const proxyError = { detail: { xhr: { status: 504 }, target: panel } };
  listeners["htmx:beforeSwap"](proxyError);
  assert.equal(proxyError.detail.shouldSwap, false);
  assert.equal(proxyError.detail.isError, false);
  assert.equal(feedback.attributes.role, "alert");
});
