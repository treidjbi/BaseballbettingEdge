// Offseason dormancy approved 2026-10-01. No scheduled reads or sends.
// Restore only under the separately approved next-season restart plan.
export default async function sendLiveNotificationsScheduled() {
  return new Response(JSON.stringify({ status: 'offseason_dormant', sent: 0 }), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
}
