import test from 'node:test';
import assert from 'node:assert/strict';
import { authenticateBot, isApprovedBotImageSource } from '../worker/index.js';

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

test('approves the known Wikimedia and Unsplash image hosts', () => {
  assert.equal(isApprovedBotImageSource('https://upload.wikimedia.org/example.jpg'), true);
  assert.equal(isApprovedBotImageSource('https://commons.wikimedia.org/example.jpg'), true);
  assert.equal(isApprovedBotImageSource('https://images.unsplash.com/photo-123'), true);
  assert.equal(isApprovedBotImageSource('https://plus.unsplash.com/premium-photo-123'), true);
  assert.equal(isApprovedBotImageSource('https://en.wikipedia.org/wiki/Special:FilePath/Example.jpg'), true);
  assert.equal(isApprovedBotImageSource('https://maps.wikimedia.org/img/example.jpg'), true);
  assert.equal(isApprovedBotImageSource('https://upload.wikimedia.org.evil.example/image.jpg'), false);
});

test('rejects untrusted hosts, non-HTTPS URLs, and credential-bearing URLs', () => {
  assert.equal(isApprovedBotImageSource('https://example.com/image.jpg'), false);
  assert.equal(isApprovedBotImageSource('http://upload.wikimedia.org/example.jpg'), false);
  assert.equal(isApprovedBotImageSource('https://user:pass@upload.wikimedia.org/example.jpg'), false);
  assert.equal(isApprovedBotImageSource('not-a-url'), false);
});
