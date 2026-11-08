import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

// Reset Demo sits next to Run Demo in the toolbar and is shown only to reviewers.
test('toolbar shows Reset Demo only for reviewers', async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  const store = {};
  globalThis.sessionStorage = { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); }, clear() {} };
  try {
    const { default: App } = await server.ssrLoadModule('/src/App.jsx');
    const renderAs = role => {
      store.sentinel_user = JSON.stringify({ username: role, role });
      return renderToStaticMarkup(React.createElement(App));
    };
    const reviewer = renderAs('reviewer');
    assert.match(reviewer, /Run Demo/);
    assert.match(reviewer, /Reset Demo/);
    assert.doesNotMatch(renderAs('viewer'), /Reset Demo/);
  } finally {
    delete globalThis.sessionStorage;
    await server.close();
  }
});
