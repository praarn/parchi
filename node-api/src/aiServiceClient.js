import "dotenv/config";

export async function callAiService(pathname, body) {
  const response = await fetch(`${process.env.AI_SERVICE_URL}${pathname}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Internal-Token": process.env.INTERNAL_SERVICE_TOKEN,
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`AI service ${pathname} failed (${response.status}): ${detail}`);
  }
  return response.json();
}