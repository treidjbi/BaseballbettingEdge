import { sendLiveNotifications } from './_shared/live-notification-sender.mjs';

export default async function sendLiveNotificationsNow(req) {
  return sendLiveNotifications(req, { requiresSharedSecret: true });
}

export const config = {
  path: '/api/send-live-notifications-now',
};
