import { createClient } from "npm:@supabase/supabase-js@2";

const encoder = new TextEncoder();

function hex(buffer: ArrayBuffer): string {
  return [...new Uint8Array(buffer)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function hmacSha256(secret: string, timestamp: string, body: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(`${timestamp}.${body}`),
  );
  return hex(signature);
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i += 1) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const secret = Deno.env.get("PROPLINE_WEBHOOK_SECRET");
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!secret || !supabaseUrl || !serviceRoleKey) {
    return new Response("Webhook receiver not configured", { status: 500 });
  }

  const propLineEvent = req.headers.get("X-PropLine-Event") ?? "";
  const timestamp = req.headers.get("X-PropLine-Timestamp") ?? "";
  const signature = req.headers.get("X-PropLine-Signature") ?? "";
  const deliveryId = req.headers.get("X-PropLine-Delivery") ?? "";
  const body = await req.text();

  if (!propLineEvent || !timestamp || !signature || !deliveryId) {
    return new Response("Missing PropLine headers", { status: 400 });
  }

  const timestampSeconds = Number(timestamp);
  if (!Number.isFinite(timestampSeconds) || timestampSeconds <= 0) {
    return new Response("Invalid PropLine timestamp", { status: 400 });
  }
  const propLineTimestamp = new Date(timestampSeconds * 1000).toISOString();

  const expected = await hmacSha256(secret, timestamp, body);
  const signatureValid = timingSafeEqual(expected, signature);
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(body);
  } catch {
    payload = { raw_body_parse_error: true };
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  });

  const { error } = await supabase
    .from("propline_webhook_deliveries")
    .upsert({
      prop_line_delivery_id: deliveryId,
      prop_line_event: propLineEvent,
      prop_line_timestamp: propLineTimestamp,
      signature_valid: signatureValid,
      payload,
      processed: false,
      processing_error: signatureValid ? null : "invalid_signature",
    }, { onConflict: "prop_line_delivery_id" });

  if (error) {
    return new Response("Failed to store delivery", { status: 500 });
  }

  if (!signatureValid) {
    return new Response("Invalid signature", { status: 401 });
  }

  return Response.json({ ok: true, deliveryId });
});
