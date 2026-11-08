import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

// The Reset demo button is shown only when App passes a handler (reviewers only).
test('sidebar shows Reset demo only for reviewers', async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
  try {
    const { default: IncidentList } = await server.ssrLoadModule('/src/IncidentList.jsx');
    const render = onResetDemo => renderToStaticMarkup(React.createElement(IncidentList, {
      incidents: [], selected: '', onSelect() {}, onRunDemo() {}, onResetDemo, busy: false,
    }));
    assert.match(render(() => {}), /Reset demo/);
    assert.doesNotMatch(render(null), /Reset demo/);
  } finally {
    await server.close();
  }
});
