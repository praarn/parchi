import { Router } from "express";
import { pool } from "../db.js";
import { callAiService } from "../aiServiceClient.js";

export const chatRouter = Router();

// Express 4 doesn't auto-catch rejected promises from async handlers —
// without this wrapper, a thrown error just hangs the connection instead
// of sending a response, which shows up in the browser as "Failed to fetch".
function asyncHandler(fn) {
  return (req, res, next) => fn(req, res, next).catch(next);
}

async function getOrCreateSession(documentId, userId) {
  const existing = await pool.query(
    "SELECT * FROM chat_sessions WHERE document_id = $1 AND user_id = $2 ORDER BY created_at DESC LIMIT 1",
    [documentId, userId]
  );
  if (existing.rows.length > 0) return existing.rows[0];

  const created = await pool.query(
    "INSERT INTO chat_sessions (document_id, user_id) VALUES ($1, $2) RETURNING *",
    [documentId, userId]
  );
  return created.rows[0];
}

chatRouter.post("/:id/chat", asyncHandler(async (req, res) => {
  const { id } = req.params;
  const { message, language } = req.body;
  if (!message) return res.status(400).json({ error: "message is required" });

  const session = await getOrCreateSession(id, req.user.sub);

  const historyRows = await pool.query(
    "SELECT role, content FROM chat_messages WHERE session_id = $1 ORDER BY created_at ASC",
    [session.id]
  );

  await pool.query(
    "INSERT INTO chat_messages (session_id, role, content, language) VALUES ($1, 'user', $2, $3)",
    [session.id, message, language || "en"]
  );

  const result = await callAiService("/internal/qa", {
    document_id: id,
    question: message,
    history: historyRows.rows,
    language: language || "en",
  });

  await pool.query(
    "INSERT INTO chat_messages (session_id, role, content, language) VALUES ($1, 'assistant', $2, $3)",
    [session.id, result.answer, language || "en"]
  );

  res.json(result);
}));

chatRouter.get("/:id/chat", asyncHandler(async (req, res) => {
  const { id } = req.params;
  const session = await pool.query(
    "SELECT * FROM chat_sessions WHERE document_id = $1 AND user_id = $2 ORDER BY created_at DESC LIMIT 1",
    [id, req.user.sub]
  );
  if (session.rows.length === 0) return res.json({ messages: [] });

  const messages = await pool.query(
    "SELECT role, content, language, created_at FROM chat_messages WHERE session_id = $1 ORDER BY created_at ASC",
    [session.rows[0].id]
  );
  res.json({ messages: messages.rows });
}));