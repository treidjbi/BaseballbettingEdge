import crypto from 'node:crypto';
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildDeliveryRow,
  hmacSha256Hex,
  timingSafeEqualHex,
} from '../netlify/functions/propline-webhook.mjs';

test('hmacSha256Hex matches PropLine signature contract', () => {
  const secret = 'whsec_test';
  const timestamp = '1770000000';
  const body = JSON.stringify({ event: 'line_movement', player: 'Gerrit Cole' });
  const expected = crypto
    .createHmac('sha256', secret)
    .update(`${timestamp}.${body}`)
    .digest('hex');

  assert.equal(hmacSha256Hex(secret, timestamp, body), expected);
  assert.equal(timingSafeEqualHex(expected, expected), true);
  assert.equal(timingSafeEqualHex(expected, expected.replace(/.$/, '0')), false);
});

test('buildDeliveryRow maps PropLine headers to Supabase row', () => {
  const row = buildDeliveryRow({
    deliveryId: 'delivery-1',
    propLineEvent: 'line_movement',
    timestamp: '1770000000',
    signatureValid: true,
    payload: { ok: true },
  });

  assert.equal(row.prop_line_delivery_id, 'delivery-1');
  assert.equal(row.prop_line_event, 'line_movement');
  assert.equal(row.prop_line_timestamp, '2026-02-02T02:40:00.000Z');
  assert.equal(row.signature_valid, true);
  assert.equal(row.processed, false);
  assert.equal(row.processing_error, null);
  assert.deepEqual(row.payload, { ok: true });
});

test('buildDeliveryRow marks invalid signatures for audit', () => {
  const row = buildDeliveryRow({
    deliveryId: 'delivery-2',
    propLineEvent: 'test',
    timestamp: '1770000000',
    signatureValid: false,
    payload: { ok: true },
  });

  assert.equal(row.signature_valid, false);
  assert.equal(row.processing_error, 'invalid_signature');
});
