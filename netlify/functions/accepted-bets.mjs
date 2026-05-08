import { handleAcceptedBetRequest } from './_shared/accepted-bets.mjs';

export default async function acceptedBets(req) {
  return handleAcceptedBetRequest(req);
}

export const config = {
  path: '/api/accepted-bets',
};
