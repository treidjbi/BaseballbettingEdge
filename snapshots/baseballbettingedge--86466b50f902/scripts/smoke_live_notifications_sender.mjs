#!/usr/bin/env node

const siteUrl = (process.env.NETLIFY_SITE_URL || 'https://baseballbettingedge.netlify.app').replace(/\/$/, '');
const notifySecret = process.env.NOTIFY_SECRET;
const limit = Number(process.env.LIVE_NOTIFICATION_SMOKE_LIMIT || 1);

if (!notifySecret) {
  console.error('NOTIFY_SECRET is required for live notification sender smoke check');
  process.exit(2);
}

const response = await fetch(`${siteUrl}/api/send-live-notifications-now`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-notify-secret': notifySecret,
  },
  body: JSON.stringify({
    smoke_check: true,
    limit: Number.isFinite(limit) && limit > 0 ? limit : 1,
  }),
});

let payload = {};
try {
  payload = await response.json();
} catch {}

if (!response.ok || payload.mode !== 'smoke_check') {
  console.error(JSON.stringify({
    ok: false,
    status: response.status,
    payload,
  }));
  process.exit(1);
}

console.log(JSON.stringify({
  ok: true,
  enabled: Boolean(payload.enabled),
  pending: Number(payload.pending || 0),
  stale: Number(payload.stale || 0),
  subscribers: Number(payload.subscribers || 0),
}));
