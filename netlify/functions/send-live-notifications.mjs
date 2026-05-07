import { sendLiveNotifications } from './_shared/live-notification-sender.mjs';

export default async function sendLiveNotificationsScheduled(req) {
  return sendLiveNotifications(req, { requiresSharedSecret: false });
}

export const config = {
  schedule: '*/10 * * * *',
};
