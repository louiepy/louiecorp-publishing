import test from 'node:test';
import assert from 'node:assert/strict';
import { authenticateBot } from '../worker/index.js';

test('rejects requests when the Worker secret is missing', () => {
  const result = authenticateBot({}, 'Bearer newsroom-secret');
  assert.equal(result.ok, false);
  assert.equal(result.status, 500);
  assert.equal(result.error, 'MEDIA_BOT_SECRET is not configured on the Worker.');
});

test('rejects a missing bearer token', () => {
  const result = authenticateBot({ MEDIA_BOT_SECRET: 'newsroom-secret' }, '');
  assert.equal(result.ok, false);
  assert.equal(result.status, 401);
  assert.equal(result.error, 'Bot authentication failed.');
});

test('rejects a mismatched bearer token', () => {
  const result = authenticateBot(
    { MEDIA_BOT_SECRET: 'newsroom-secret' },
    'Bearer other-secret'
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, 401);
  assert.equal(result.error, 'Bot authentication failed.');
});

test('accepts a matching bearer token after trimming whitespace', () => {
  const result = authenticateBot(
    { MEDIA_BOT_SECRET: ' newsroom-secret\n' },
    'Bearer newsroom-secret'
  );
  assert.equal(result.ok, true);
});
