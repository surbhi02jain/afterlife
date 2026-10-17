// Run with: npm test (Node's built-in test runner, no extra dependencies)
import assert from "node:assert/strict";
import { test } from "node:test";
import { parseRoute } from "./nav.js";

test("case screens", () => {
  assert.deepEqual(parseRoute("#/case/abc/plan"), { name: "case", id: "abc", screen: "plan" });
  assert.deepEqual(parseRoute("#/case/abc"), { name: "case", id: "abc", screen: "upload" });
});

test("a query after the screen does not change the screen", () => {
  assert.equal(parseRoute("#/case/abc/letters?l=deadbeef").screen, "letters");
});

test("share links and the start page", () => {
  assert.deepEqual(parseRoute("#/share/tok123"), { name: "share", token: "tok123" });
  assert.deepEqual(parseRoute(""), { name: "start" });
  assert.deepEqual(parseRoute("#/deleted"), { name: "start" });
});
