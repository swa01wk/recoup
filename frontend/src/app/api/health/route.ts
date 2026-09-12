/** App Runner HTTP health check — always 200 (no cache). */
export async function GET() {
  return Response.json({ status: "ok", ts: Date.now() }, { status: 200 });
}
